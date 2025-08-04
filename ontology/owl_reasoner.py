from owlready2 import *
import owlready2

def infer_risk_and_action(tbw_percent: float):
    # Specifying path to Java executable (required for running Pellet reasoner)
    owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
    # Set amount of memory (in MB) that Java can use
    owlready2.JAVA_MEMORY = 8000

    # Loading existing OWL ontology
    onto = get_ontology("./ontology/healthagent.owl").load()

    with onto:
        patient1 = onto.Patient1
        
        # Clean previous assertions
        patient1.TBWLossPercent = []
        patient1.hasRiskStatus = []
        patient1.triggersAction = []
        patient1.is_a = [onto.Patient]  # Reset class

        # Add new value
        patient1.TBWLossPercent.append(int(tbw_percent))

    # Working within the ontology context to run reasoner
    with onto:
        # Run the Pellet reasoner and infer new property values (including updated TBWLossPercent data property)
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
    # Extracting inferred risk status and action for Patient1
    p = onto.Patient1
    # Return the Risk Status and Action for Patient1
    risk = p.hasRiskStatus[0].name if p.hasRiskStatus else None
    action = p.triggersAction[0].name if p.triggersAction else None
    
    return risk, action    

# print(infer_risk_and_action(5.0))