import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerting.alert_mailer import report_fallback
from dotenv import load_dotenv

load_dotenv()

FAST_DOWNWARD_PATH = os.getenv("FAST_DOWNWARD_PATH")
if not FAST_DOWNWARD_PATH:
    raise EnvironmentError("[Security] FAST_DOWNWARD_PATH not found in .env")

BASE_PATH = "pddl_planning"
DOMAIN_FILE = "hydration_domain.pddl"
PROBLEM_FILE = "hydration_problem.pddl"
OUTPUT_FILE = "hydration_plan.txt"

PLANNER_TIMEOUT_SEC = 30  # max time to wait for Fast Downward before giving up

# Hardcoded fallback plans for each risk status in case the planner fails or no plan is found
FALLBACK_PLANS = {
    "Euhydrated": "(check_hydration patient1)\n(log_status_euhydrated patient1)",
    "Mild":       "(check_hydration patient1)\n(consume_ORS patient1)\n(monitor_intake patient1)",
    "Moderate":   "(check_hydration patient1)\n(alert_caregiver patient1)\n(transfer_to_hospital_moderate patient1)",
    "Severe":     "(check_hydration patient1)\n(call_emergency patient1)\n(transfer_to_hospital_severe patient1)",
}

def create_problem_file(risk_status: str, problem_path: str, oral_intake_feasible: bool = True):
    """
    Generates a PDDL problem file dynamically based on dehydration risk status and patient capability flag

    Parameters:
    - risk_status: The dehydration risk status ("Euhydrated", "Mild", "Moderate", "Severe")
    - problem_path: Full path where the problem file will be written.
    - oral_intake_feasible: Patient-specific flag set by HealthAgent.
                            True  = patient can swallow safely (ORS path).
                            False = dysphagia / altered consciousness / ORS failed after 2 MAS-layer rechecks (escalation path).
                            Only relevant for Mild; ignored for all others.
    """

    init_facts = [] # Initialize the list of initial facts (:init) for the PDDL problem
    goal_facts = [] # Initialize the list of goal facts (:goal) for the PDDL problem

    if risk_status == "Euhydrated":
        # log_status_euhydrated
        init_facts = [
            "(euhydrated patient1)",
            "(monitoring_active patient1)",
        ]
        goal_facts = [
            "(threshold_met patient1)",
            "(status_logged patient1)",
        ]

    elif risk_status == "Mild":
        init_facts = [
            "(mildly_dehydrated patient1)",
            "(monitoring_active patient1)",
        ]
        if oral_intake_feasible:
            # consume_ORS → monitor_intake → recheck_hydration → log_status_mild
            init_facts.append("(oral_intake_feasible patient1)")
            goal_facts = [
                "(threshold_met patient1)",
                "(status_logged patient1)",
            ]
        else:
            # Escalation path: check_hydration → escalate_to_moderate
            # escalate_to_moderate → alert_caregiver → transfer_to_hospital → administer_fluids_moderate → recheck_labs_moderate → monitor_vitals_moderate → log_status_moderate
            goal_facts = [
                "(transferred_to_hospital patient1)",
                "(threshold_met patient1)",
                "(status_logged patient1)",
            ]

    elif risk_status == "Moderate":
        # Covers: direct Moderate prediction OR escalated from Mild

        # alert_caregiver → transfer_to_hospital → administer_fluids_moderate → recheck_labs_moderate → monitor_vitals_moderate → log_status_moderate
        init_facts = [
            "(moderately_dehydrated patient1)",
            "(monitoring_active patient1)",
        ]
        goal_facts = [
            "(transferred_to_hospital patient1)",
            "(threshold_met patient1)",
            "(status_logged patient1)",
        ]

    elif risk_status == "Severe":
        # Covers: direct Severe prediction OR escalated from Moderate

        # call_emergency → transfer_to_hospital → administer_fluids_severe → recheck_labs_severe → monitor_vitals_continuous → log_status_severe
        init_facts = [
            "(severely_dehydrated patient1)",
            "(monitoring_active patient1)",
        ]
        goal_facts = [
            "(transferred_to_hospital patient1)",
            "(threshold_met patient1)",
            "(status_logged patient1)",
        ]

    else:
        # Fallback: no risk status — monitoring only, no intervention
        init_facts = [
            "(monitoring_active patient1)",
        ]
        goal_facts = []

    # Build goal block — single predicate or conjunction
    if len(goal_facts) == 1:
        goal_block = f"        {goal_facts[0]}"
    else:
        inner = "\n            ".join(goal_facts)
        goal_block = f"        (and\n            {inner}\n        )"

    init_block = "\n        ".join(init_facts)

    problem_template = f"""
(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        {init_block}
    )

    (:goal
{goal_block}
    )
)
"""

    with open(problem_path, "w") as f:
        f.write(problem_template)

    print(f"[Planner] Problem file created: {problem_path}")
    print(f"[Planner] Risk={risk_status} | oral_intake_feasible={oral_intake_feasible}")


def run_planner(risk_status: str, oral_intake_feasible: bool = True, patient_id=None) -> tuple:
    """
    Runs the Fast Downward planner for the given risk status and patient capability flag. 
    Returns the generated plan as a string.

    Parameters:
    - risk_status: The dehydration risk status ("Euhydrated", "Mild", "Moderate", "Severe").
    - oral_intake_feasible: Patient-specific flag from HealthAgent.
                            Determines Mild plan variant (ORS vs escalation).
                            Default: True.

    Returns:
    - plan (str): The generated PDDL plan as a string.
    - None: If no plan was found or risk_status is None.
    """

    if risk_status is None:
        print("[Planner] No risk status provided. No planning needed.")
        return None, {"fallback_used": False, "fallback_reason": None}

    problem_path = os.path.join(BASE_PATH, PROBLEM_FILE)
    output_path = os.path.join(BASE_PATH, OUTPUT_FILE)
    sas_path = os.path.join(BASE_PATH, "sas_plan")

    # Step 0: Remove any stale sas_plan from a previous run
    # Prevents reading an old successful plan after a new run has actually failed
    if os.path.exists(sas_path):
        try:
            os.remove(sas_path)
        except OSError as e:
            print(f"[Planner] WARNING: Could not remove stale sas_plan: {e}")

    # Step 1: Generate problem file dynamically
    try:
        create_problem_file(
            risk_status = risk_status,
            problem_path = problem_path,
            oral_intake_feasible = oral_intake_feasible
        )
    except OSError as e:
        print(f"[Planner] ERROR: Could not write problem file: {e}")
        return _use_fallback(risk_status, patient_id, reason="problem file write failed")

    # Step 2: Run Fast Downward planner
    print(f"[Planner] Running Fast Downward for risk={risk_status}...")
    try:
        subprocess.run(
            [
                "python",
                FAST_DOWNWARD_PATH,
                DOMAIN_FILE,
                PROBLEM_FILE,
                "--search", "astar(blind())"
            ],
            cwd = BASE_PATH,
            stdout=subprocess.PIPE,  # suppress Fast Downward stdout
            stderr=subprocess.PIPE,   # suppress Fast Downward stderr
            timeout=PLANNER_TIMEOUT_SEC
        )
    except FileNotFoundError:
        print(f"[Planner] ERROR: Fast Downward not found at {FAST_DOWNWARD_PATH}")
        return _use_fallback(risk_status, patient_id, reason="Fast Downward executable not found")
    except subprocess.TimeoutExpired:
        print(f"[Planner] ERROR: Fast Downward timed out after {PLANNER_TIMEOUT_SEC}s")
        return _use_fallback(risk_status, patient_id, reason="planner timeout")
    except Exception as e:
        print(f"[Planner] ERROR: Unexpected error running Fast Downward: {e}")
        return _use_fallback(risk_status, patient_id, reason=str(e))

    # Step 3: Capture and return the plan
    try:
        with open(sas_path, "r") as f:
            raw_plan = f.read()

        # Filter out comment lines (Fast Downward metadata starts with ";") and blank lines 
        # Keep only action lines
        plan_lines = [
            line for line in raw_plan.splitlines()
            if line.strip() and not line.strip().startswith(";")
        ]

        # sas_plan existed but contained no usable action lines — treat as failure
        if not plan_lines:
            print(f"[Planner] WARNING: sas_plan was empty for risk={risk_status}.")
            return _use_fallback(risk_status, patient_id, reason="empty sas_plan")

        plan = "\n".join(plan_lines)

        with open(output_path, "w") as out:
            out.write(plan)

        print(f"[Planner] Plan for risk={risk_status}:")
        print(f"[Planner] ----------")

        for line in plan_lines:
            print(f"[Planner] {line}")
            
        print(f"[Planner] ----------")
        print(f"[Planner] Total steps: {len(plan_lines)}")

        return plan, {"fallback_used": False, "fallback_reason": None}

    except FileNotFoundError:
        print(f"[Planner] No plan found for risk={risk_status}. Problem may be unsolvable, or domain/problem files are invalid.")
        return _use_fallback(risk_status, patient_id, reason="no sas_plan produced (unsolvable or invalid PDDL)")

def _use_fallback(risk_status: str, patient_id, reason: str) -> tuple:
    """
    Fallback mechanism to return a predefined plan based on the risk status when planner fails or produces no plan.

    Parameters:
    - risk_status: The dehydration risk status ("Euhydrated", "Mild", "Moderate", "Severe").
    - reason: Reason for using fallback (for logging purposes)

    Returns:
    - plan (str): The fallback PDDL plan as a string.
    - None: If no fallback plan is defined for the given risk status.
    """

    report_fallback("planner", reason, patient_id)

    plan = FALLBACK_PLANS.get(risk_status)
 
    if plan is None:
        print(f"[Planner] FALLBACK FAILED: No fallback plan available for risk_status='{risk_status}'. Reason for fallback: {reason}")
        return None, {"fallback_used": True, "fallback_reason": f"no fallback for: {risk_status}"}
 
    print(f"[Planner] FALLBACK PLAN USED (reason: {reason}) for risk={risk_status}:")
    print(f"[Planner] ----------")
    for line in plan.splitlines():
        print(f"[Planner] {line}")
    print(f"[Planner] ----------")
 
    return plan, {"fallback_used": True, "fallback_reason": reason}

# Debugging
if __name__ == "__main__":

    test_cases = [
        ("Euhydrated", True),
        ("Mild", True), # ORS feasible
        ("Mild", False), # ORS not feasible (escalates to Moderate)
        ("Moderate", True),
        ("Severe", True),
    ]

    for risk, feasible in test_cases:
        print(f"\n{'='*50}")
        print(f"TEST: risk={risk} | oral_intake_feasible={feasible}")
        print('='*50)
        plan, meta = run_planner(risk_status=risk, oral_intake_feasible=feasible)
        if plan:
            print(f"Plan returned ({len(plan.splitlines())} lines) | Fallback: {meta['fallback_used']}")
        else:
            print("No plan returned.")