from owlready2 import *
import owlready2

# Specifying path to Java executable (required for running Pellet reasoner)
owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
# Set amount of memory (in MB) that Java can use
owlready2.JAVA_MEMORY = 8000

# Loading existing OWL ontology
onto = get_ontology("C:/Users/Fazila Syed/Documents/COLLEGE/RIT/Coop/Research Coop/GoalOrientedElderlyCare/ontology/healthagent.owl").load()

# with onto:
#     patient1 = onto.Patient1
#     patient1.TBWLossPercent = 6.6

# Working within the ontology context to run reasoner
with onto:
    # Run the Pellet reasoner and infer new property values (including updated TBWLossPercent data property)
    sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

# Loop through all Patient class instances
for patient in onto.Patient.instances():
    print(f"\nPatient: {patient.name}") # name of the Patient

    # Check if patient has a TBWLossPercent
    if hasattr(patient, "TBWLossPercent") and patient.TBWLossPercent:
        print("TBWLossPercent:", patient.TBWLossPercent, "%")
        
        # Check if patient has a RiskStatus
        if hasattr(patient, "hasRiskStatus") and patient.hasRiskStatus:
            print("  Risk Status:", patient.hasRiskStatus[0].name)
        else:               
            print("  Risk Status: Not inferred")

        # Check if patient requires as action to be triggered as a result of the RiskStatus
        if hasattr(patient, "triggersAction") and patient.triggersAction:
            print("  Action:", patient.triggersAction[0].name)
        else:
            print("  Action: Not inferred")
    else:
        print("Could not find TBWLossPercent for patient.")
    
    
