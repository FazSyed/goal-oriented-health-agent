from owlready2 import *
import owlready2

counter = 0

# Mapping of risk labels to fallback actions in case ontology inference fails
FALLBACK_ACTION_MAP = {
    "Euhydrated": "NoActionRequired",
    "Mild":       "SendHydrationReminder",
    "Moderate":   "SendIVRequiredAlert",
    "Severe":     "SendEmergencySignal",
}

def infer_risk_and_action(risk_label: str):
    """"
    Infers care action based on ML-predicted risk label using OWL ontology.
    Phase 2: ML model handles classification, ontology handles action inference only.

    Parameters:
    - risk_label: ML predicted risk label
                  One of: "Euhydrated", "Mild", "Moderate", "Severe"

    Returns:
    - risk: Inferred risk status (str)
    - action: Inferred action to be taken (str)
    """

    global counter

    try:

        # Specifying path to Java executable (required for running Pellet reasoner)
        owlready2.JAVA_EXE = "C:/Program Files/ Files/Oracle/Java/javapath/java.exe"
        # Set amount of memory (in MB) that Java can use
        owlready2.JAVA_MEMORY = 8000

        # Loading existing OWL ontology
        onto = get_ontology("./ontology/healthagent.owl").load()
        
        with onto:
            # Create a new Patient instance with a unique ID to prevent conflicts
            # This ensures that each run creates a fresh patient instance
            patient_id=f"Patient_1.{counter}"
            p = onto.Patient(patient_id)

            # Phase 2 change: set hasRiskStatus directly from ML prediction
            # instead of setting TBWLossPercent and letting SWRL infer risk
            risk_individual = onto.search_one(iri="*#"+risk_label)
            if risk_individual is not None:
                p.hasRiskStatus.append(risk_individual)
            else:
                print(f"[ERROR] Risk individual '{risk_label}' not found in ontology.")
                return _use_fallback(risk_label, reason="risk individual not found in ontology")

            counter += 1
        
        # Working within the ontology context to run reasoner
        with onto:
            # Run Pellet reasoner to infer triggersAction from hasRiskStatus
            sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        # List of valid risk names to check against patient's hasRiskStatus
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

        # If Pellet ran but produced no usable inference, treat as a failure
        # and fall back rather than returning (None, None) to HealthAgent
        if risk is None or action is None:
            print(f"[Ontology] WARNING: Reasoner produced no valid inference for '{risk_label}'. Using fallback mapping.")
            return _use_fallback(risk_label, reason="empty reasoner inference")

        return risk, action, {"fallback_used": False, "fallback_reason": None}

    except Exception as e:
        #  Catches: Java not found, ontology file missing/corrupt,
        # Pellet timeout/crash, or any other unexpected reasoner failure
        print(f"[Ontology] ERROR: Reasoner failed for '{risk_label}': {e}")
        return _use_fallback(risk_label, reason=str(e))

def _use_fallback(risk_label: str, reason: str):
    """
    Fallback mechanism to return a predefined action based on the risk label when ontology inference fails.

    Parameters:
    - risk_label: ML predicted risk label
    - reason: Reason for using fallback (for logging purposes)

    Returns:
    - risk: The original risk label (str)
    - action: Fallback action corresponding to the risk label (str)
    """

    action = FALLBACK_ACTION_MAP.get(risk_label)
 
    if action is None:
        print(f"[Ontology] FALLBACK FAILED: Unrecognised risk label '{risk_label}'. Reason for fallback: {reason}")
        return None, None, {"fallback_used": True, "fallback_reason": reason}

    print(f"[Ontology] FALLBACK USED (reason: {reason}) — Input: {risk_label} → Risk: {risk_label}, Action: {action}")
    return risk_label, action, {"fallback_used": True, "fallback_reason": reason}

# Debugging
if __name__ == "__main__":
    test_labels = ["Euhydrated", "Mild", "Moderate", "Severe"]
    for label in test_labels:
        risk, action, meta = infer_risk_and_action(label)
        print(f"Input: {label} → Risk: {risk}, Action: {action} | Fallback: {meta['fallback_used']}")