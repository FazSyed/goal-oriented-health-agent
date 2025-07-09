'''
NOTES:
Domain file has -> predicate, actions
Problem file has -> object, initial state, goals

Domain Name - care_agent
Problem Name - care_routine

--> I have a healthcare agent that generates a 'Plan' 
    based on hydration and threshold values


--> TASK:
There is a health agent that can check the patient's hydration level 
every 1 hour to ensure it is greater than or equal to the threshold value
and will either remind the patient to drink more water, or alert the 
caregiver if the hydration level is Moderate (they need IV) or Severe (Emergency).
It continues rechecking every 1 hour to ensure the threshold value is met.
The hydration value is what is initially noted. We want to make sure it is
greater than or equal to threshold value.


1. Objects: Patient, hydration value, threshold value
2. Predicates: 
3. Initial State: Current Hydration value 
4. Goal Specifications: Hydration value >= Threshold Value
5. Actions/Operators: Remind, AlertCaregiver, Recheck

'''

import subprocess

def run_planner():
    # Define input files
    domain_file = "hydration_domain.pddl"
    problem_file = "hydration_problem.pddl"
    output_file = "hydration_plan.txt"

    # Run the Fast Downward planner 
    subprocess.run([
    "python",  # or full path to python if needed
    "C:/Users/Fazila Syed/Downloads/FastDownward/downward/fast-downward.py",
    domain_file,
    problem_file,
    "--search", "astar(blind())"
])


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

