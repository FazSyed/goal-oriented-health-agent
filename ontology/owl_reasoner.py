from owlready2 import *
import owlready2

counter = 0

def infer_risk_and_action(risk_label: str):

    global counter

    # Specifying path to Java executable (required for running Pellet reasoner)
    owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
    # Set amount of memory (in MB) that Java can use
    owlready2.JAVA_MEMORY = 8000

    # Loading existing OWL ontology
    onto = get_ontology("./ontology/healthagent-v2.owl").load()
    
    with onto:
        # Create a new Patient instance with a unique ID to prevent conflicts
        # This ensures that each run creates a fresh patient instance
        patient_id=f"Patient_1.{counter}"
        p = onto.Patient(patient_id)

        risk_individual = onto.search_one(iri="*#"+risk_label)
        if risk_individual is not None:
            p.hasRiskStatus.append(risk_individual)
        else:
            print(f"[ERROR] Risk individual '{risk_label}' not found in ontology.")

        counter += 1

    # Working within the ontology context to run reasoner
    with onto:
        # Run the Pellet reasoner and infer new property values (including updated TBWLossPercent data property)
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

    '''
    # Debugging output to verify the TBW Loss Percent and inferred values

    print(f"[DEBUG] {p.name}")
    print(f"[DEBUG] Patient1 TBW Loss = {int(tbw_percent)}%")
    print(f"[DEBUG] Inferred Classes: {[cls.name for cls in p.is_a]}")
    print(f"[DEBUG] Risk Status: {[r.name for r in p.hasRiskStatus]}")
    print(f"[DEBUG] Action Trigger: {[a.name for a in p.triggersAction]}")
    '''

    valid_risk_names = ["Euhydrated", "Mild", "Moderate", "Severe"]

    # Check if the patient has a Risk Status that matches one of the three valid risks
    valid_risks = [
        r for r in p.hasRiskStatus
        if r != p and hasattr(r, "name") and r.name in valid_risk_names
    ]
    # Check if the patient has an Action that matches an existing action provided by the ontology
    valid_actions = [
        a for a in p.triggersAction
        if a != p and hasattr(a, "name")
    ]

    # Assign the first valid risk and action to their variables if they exist
    # If no valid risks or actions are found, set them to None
    risk = valid_risks[0].name if valid_risks else None
    action = valid_actions[0].name if valid_actions else None

    return risk, action    

# Debugging
if __name__ == "__main__":
    test_labels = ["Euhydrated", "Mild", "Moderate", "Severe"]
    for label in test_labels:
        risk, action = infer_risk_and_action(label)
        print(f"Input: {label} → Risk: {risk}, Action: {action}")