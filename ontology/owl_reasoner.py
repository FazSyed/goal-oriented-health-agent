from owlready2 import *
import owlready2
import uuid # For generating unique patient IDs

def infer_risk_and_action(tbw_percent: float):

    """
    Infers dehydration risk and action based on TBW Loss Percent using OWL ontology.

    Parameters:
    - tbw_percent: Total Body Water Loss Percent

    Returns:
    - risk: Inferred risk status (str)
    - action: Inferred action to be taken (str)
    """

    # Specifying path to Java executable (required for running Pellet reasoner)
    owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
    # Set amount of memory (in MB) that Java can use
    owlready2.JAVA_MEMORY = 8000

    # Loading existing OWL ontology
    onto = get_ontology("./ontology/healthagent.owl").load()
    
    with onto:
        # Create a new Patient instance with a unique ID to prevent conflicts
        # This ensures that each run creates a fresh patient instance
        patient_id = f"Patient_1.{uuid.uuid4().hex[:6]}" 
        p = onto.Patient(patient_id)
        p.TBWLossPercent = [int(tbw_percent)]

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

    # Return the Risk Status and Action for Patient1
    risk = p.hasRiskStatus[0].name if p.hasRiskStatus else None
    action = p.triggersAction[0].name if p.triggersAction else None
    
    return risk, action    

# Debugging
if __name__ == "__main__":
    for weight in [63.1, 65.54, 70.54, 69.32]:
        tbw = ((72 - weight) / 72) * 100
        print(infer_risk_and_action(tbw))