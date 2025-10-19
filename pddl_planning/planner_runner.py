import subprocess
import os

def create_problem_file(risk_status: str, problem_path: str):

    """
    Generates a PDDL problem file based on the dehydration risk status.

    Parameters:
    - risk_status: The dehydration risk status (e.g., "Mild", "Moderate", "Severe", or None).
    - problem_path: The path where the PDDL problem file will be saved.

    """

    init_facts = []

    if risk_status == "Mild":
        init_facts.append("(mildly_dehydrated patient1)")
        init_facts.append("(monitoring_active patient1)")
    elif risk_status == "Moderate":
        init_facts.append("(moderately_dehydrated patient1)")
        init_facts.append("(monitoring_active patient1)")
    elif risk_status == "Severe":
        init_facts.append("(severely_dehydrated patient1)")
        init_facts.append("(monitoring_active patient1)")
    elif risk_status == None:
        init_facts.append("(monitoring_active patient1)")


    init_facts_str = "\n        ".join(init_facts)
    problem_template = f"""
(define (problem care_routine)
    (:domain care_agent)

    (:objects
        patient1 - patient
    )

    (:init
        {init_facts_str}
    )

    (:goal
        (threshold_met patient1)
    )
)
"""
    with open(problem_path, "w") as f:
        f.write(problem_template.strip())
    print("Problem file created.")

def run_planner(risk_status: str):

    """
    Runs the Fast Downward planner with the generated PDDL problem file.
    
    Parameters:
    - risk_status: The dehydration risk status (e.g., "Mild", "Moderate", "Severe", or None).

    Returns:
    - plan: The generated plan as a string, or None if no plan was generated.

    """
    
    if risk_status is None:
        print("Not at Risk. No planning needed.")
        return None

    base_path = "pddl_planning"
    domain_file = "hydration_domain.pddl"
    problem_file = "hydration_problem.pddl"
    output_file = "hydration_plan.txt"

    # Step 1: Generate problem file dynamically
    create_problem_file(risk_status, os.path.join(base_path, problem_file))

    # Step 2: Run Fast Downward planner
    subprocess.run([
        "python",
        "C:/Users/fazil/Downloads/FastDownward/downward/fast-downward.py",
        domain_file,
        problem_file,
        "--search", "astar(blind())"
    ], cwd=base_path)

    # Step 3: Capture the plan
    try:
        with open(os.path.join(base_path, "sas_plan"), "r") as f:
            plan = f.read()

        with open(os.path.join(base_path, output_file), "w") as out:
            out.write(plan)

        print("Generated Plan:\n", plan)
        return plan

    except FileNotFoundError:
        print("No plan was found. Check your domain/problem setup.")
        return None

# Debugging
if __name__ == "__main__":
    inferred_risk_status = "Mild"
    run_planner(inferred_risk_status)