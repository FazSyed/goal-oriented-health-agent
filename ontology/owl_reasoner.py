from owlready2 import *
import owlready2

def infer_risk_and_action(ontology_path: str, tbw_percent: float):
    # Specifying path to Java executable (required for running Pellet reasoner)
    owlready2.JAVA_EXE = "C:/Program Files/Common Files/Oracle/Java/javapath/java.exe"
    # Set amount of memory (in MB) that Java can use
    owlready2.JAVA_MEMORY = 8000

    # Loading existing OWL ontology
    onto = get_ontology("C:/Users/Fazila Syed/Documents/COLLEGE/RIT/Coop/Research Coop/GoalOrientedElderlyCare/ontology/healthagent.owl").load()

    with onto:
        patient1 = onto.Patient1
        patient1.TBWLossPercent = int(tbw_percent)

    # Working within the ontology context to run reasoner
    with onto:
        # Run the Pellet reasoner and infer new property values (including updated TBWLossPercent data property)
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
    # Extracting inferred risk status and action for Patient1
    p = onto.Patient1
    # Return the Risk Status and Action for Patient1
    risk = p.hasRiskStatus[0].name if p.hasRiskStatus else "No Risk Status" 
    action = p.hasAction[0].name if p.hasAction else "No Action"
    
    return risk, action    