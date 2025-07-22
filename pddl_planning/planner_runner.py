import subprocess

def run_planner():
    # Define input files
    base_path = "C:/Users/Fazila Syed/Documents/COLLEGE/RIT/Coop/Research Coop/GoalOrientedElderlyCare/pddl_planning"
    domain_file = "hydration_domain.pddl"
    problem_file = "hydration_problem.pddl"
    output_file = "hydration_plan.txt"

    # Run the Fast Downward planner 
    subprocess.run([
        "python",
        "C:/Users/Fazila Syed/Downloads/FastDownward/downward/fast-downward.py",
        domain_file,
        problem_file,
        "--search", "astar(blind())"
    ], cwd=base_path)


    # Read the generated plan file and save it to a new file
    try:
        with open("sas_plan", "r") as f:
            plan = f.read()

        with open(output_file, "w") as out:
            out.write(plan)

        print("Plan saved to:", output_file)

    except FileNotFoundError:
        print("No plan was found. Check your domain/problem setup.")

if __name__ == "__main__":
    run_planner()

