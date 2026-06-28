import subprocess
import os

FAST_DOWNWARD_PATH = "C:/Users/fazil/Downloads/FastDownward/downward/fast-downward.py"
BASE_PATH = "pddl_planning"
DOMAIN_FILE = "hydration_domain.pddl"
PROBLEM_FILE = "hydration_problem.pddl"
OUTPUT_FILE = "hydration_plan.txt"


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


def run_planner(risk_status: str, oral_intake_feasible: bool = True) -> str | None:
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
        return None

    problem_path = os.path.join(BASE_PATH, PROBLEM_FILE)
    output_path = os.path.join(BASE_PATH, OUTPUT_FILE)
    sas_path = os.path.join(BASE_PATH, "sas_plan")

    # Step 1: Generate problem file dynamically
    create_problem_file(
        risk_status = risk_status,
        problem_path = problem_path,
        oral_intake_feasible = oral_intake_feasible
    )

    # Step 2: Run Fast Downward planner
    print(f"[Planner] Running Fast Downward for risk={risk_status}...")
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
        stderr=subprocess.PIPE   # suppress Fast Downward stderr
    )

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

        plan = "\n".join(plan_lines)

        with open(output_path, "w") as out:
            out.write(plan)

        print(f"[Planner] Plan for risk={risk_status}:")
        print(f"[Planner] ----------")

        for line in plan_lines:
            print(f"[Planner] {line}")
            
        print(f"[Planner] ----------")
        print(f"[Planner] Total steps: {len(plan_lines)}")

        return plan

    except FileNotFoundError:
        print("[Planner] No plan found. Check domain/problem file validity.")
        return None

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
        plan = run_planner(risk_status=risk, oral_intake_feasible=feasible)
        if plan:
            print(f"Plan returned ({len(plan.splitlines())} lines)")
        else:
            print("No plan returned.")