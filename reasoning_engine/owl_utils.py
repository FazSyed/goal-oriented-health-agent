from owlready2 import *
import owlready2

# Specifying path to Java executable (required for running Pellet reasoner)
owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
# Set amount of memory (in MB) that Java can use
owlready2.JAVA_MEMORY = 8000

# Loading existing OWL ontology
onto = get_ontology("C:/Users/Fazila Syed/Documents/COLLEGE/RIT/Coop/Research Coop/GoalOrientedElderlyCare/ontology/healthagent.owl").load()

# Work within the context of loaded ontology
# with onto:
#     # Access instance named "Patient1" defined in the ontology
#     patient1 = onto.Patient1
#     # Update hydartionValue (data property) of the patient
#     patient1.hydrationValue = [1350]

# Save updated ontology witha new file name
# onto.save(file="updated.owl", format="rdfxml")

# Working within the ontology context to run reasoner
with onto:
    # Run the Pellet reasoner and infer new property values (including updated hydrationValue data property)
    sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

# Optional: reloading after saving file
# onto = get_ontology("updated.owl").load()

# Optional: Search the Patient instance using its IRI
# patient = onto.search_one(iri="*Patient1")

# Loop through all Patient class instances
for patient in onto.Patient.instances():
    print(f"\nPatient: {patient.name}") # name of the Patient

    # Check if patient has a hydrationValue
    if hasattr(patient, "hydrationValue") and patient.hydrationValue:
        print("Hydration:", patient.hydrationValue[0])

        if (patient.hydrationValue[0] >= patient.thresholdValue):
            print("Patient is Hydrated!")
        else:
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
        print("Hydration: Not set")
    
    
