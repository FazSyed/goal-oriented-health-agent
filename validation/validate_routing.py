'''
Checks routing.routed_to and routing.kafka_topic against the expected
mapping for every logged reading. Flags mismatches
'''

import json
import glob
import os
import argparse

# Controls whether Mild_NoORS is expected to go to careagent
STRICT_ORAL_INTAKE_AWARE_ROUTING = True

# Static mapping: patient_id -> oral_intake_feasible flag
ORAL_INTAKE_FEASIBLE_BY_PATIENT = {
    1: True,
    2: False,
    3: True,
    4: True,
    5: True,
}
 
 
def expected_routing(risk, oral_intake_feasible):
    # Compute expected routed_to and kafka_topic for given risk + oral intake flag
    if risk == "Euhydrated":
        # Euhydrated patients are only logged, no agent routing
        return {"routed_to": None, "kafka_topic": "euhydrated_log"}
    if risk == "Mild":
        # For Mild risk, routing depends on oral intake feasibility if strict check is enabled
        if STRICT_ORAL_INTAKE_AWARE_ROUTING and not oral_intake_feasible:
            # Mild-NoORS → escalate directly to care agent / care_alerts
            return {"routed_to": "careagent@localhost", "kafka_topic": "care_alerts"}
        # Otherwise Mild with ORS feasible → reminders path
        return {"routed_to": "reminderagent@localhost", "kafka_topic": "reminders"}
    if risk in ("Moderate", "Severe"):
        # Moderate/Severe always go to care agent / care_alerts
        return {"routed_to": "careagent@localhost", "kafka_topic": "care_alerts"}
    return None # Unknown risk label → cannot compute expected routing
 
 
def validate_entry(entry):
    patient_id = entry.get("patient_id") # Extract patient_id from log entry
    risk = entry.get("ml_prediction") # Extract ML-predicted risk label
    routing = entry.get("routing", {}) # Extract routing sub-dict (or empty dict if missing)

    # If we have no oral_intake_feasible config for this patient, skip validation
    if patient_id not in ORAL_INTAKE_FEASIBLE_BY_PATIENT:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"No config for patient {patient_id}"}
    
    oral_ok = ORAL_INTAKE_FEASIBLE_BY_PATIENT[patient_id] # Lookup oral intake flag
    expected = expected_routing(risk, oral_ok) # Compute expected routing for this risk + flag

    # If risk label is unrecognized, skip this entry
    if expected is None:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"Unrecognized risk label '{risk}'"}

    # Build actual routing dict from log entry
    actual = {"routed_to": routing.get("routed_to"), "kafka_topic": routing.get("kafka_topic")}
    # Compare routed_to and kafka_topic against expected values
    routed_to_ok = actual["routed_to"] == expected["routed_to"]
    kafka_topic_ok = actual["kafka_topic"] == expected["kafka_topic"]

    # Return detailed result for this entry
    return {
        "patient_id": patient_id,
        "timestamp": entry.get("timestamp"),
        "risk": risk,
        "expected": expected,
        "actual": actual,
        "routed_to_ok": routed_to_ok,
        "kafka_topic_ok": kafka_topic_ok,
        "status": "PASS" if (routed_to_ok and kafka_topic_ok) else "FAIL",
    }
 
 
def main():
    parser = argparse.ArgumentParser() # Set up argument parser
    parser.add_argument("--logs-dir", default="logs", help="Path to the phase-specific logs folder (e.g. logs_evaluation)")
    args = parser.parse_args() # Parse CLI arguments
    logs_dir = args.logs_dir # Folder containing patient_*.json logs
 
    entries = [] # Accumulate all log entries from all files

    # Iterate over all JSON files matching patient_*.json in the specified logs_dir
    for path in glob.glob(os.path.join(logs_dir, "patient_*.json")):
        try:
            with open(path) as f:
                entries.extend(json.load(f)) # Extend entries list with JSON array from file
        except Exception as e:
            print(f"Could not read {path}: {e}")
 
    print(f"Loaded {len(entries)} log entries from {logs_dir}/")
    print(f"Strict oral-intake-aware routing check: {STRICT_ORAL_INTAKE_AWARE_ROUTING}\n")

    # Partition results into PASS, FAIL, and SKIPPED
    results = [validate_entry(e) for e in entries]
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]
 
    print(f"PASS:    {len(passed)}")
    print(f"FAIL:    {len(failed)}")
    print(f"SKIPPED: {len(skipped)}\n")

    # FAILED
    if failed:
        print("=== FAILURES ===")
        for r in failed:
            print(f"Patient {r['patient_id']} @ {r['timestamp']} (risk={r['risk']})")
            print(f"  Expected: {r['expected']}")
            print(f"  Actual:   {r['actual']}")
            print()
 
    # Per-risk-level pass rate
    print("=== Per-risk-level pass rate ===")
    by_risk = {} # Dict: risk label -> {"pass": count, "total": count}
    for r in results:
        if r["status"] == "SKIPPED":
            continue # Skip entries that weren't validated

        risk = r["risk"]
        by_risk.setdefault(risk, {"pass": 0, "total": 0}) # Initialize counters if needed
        by_risk[risk]["total"] += 1 # Increment total for this risk
        if r["status"] == "PASS":
            by_risk[risk]["pass"] += 1 # Increment pass count

    # Print per-risk pass/total and percentage
    for risk, counts in by_risk.items():
        pct = 100 * counts["pass"] / counts["total"] if counts["total"] else 0
        print(f"  {risk:12s}: {counts['pass']}/{counts['total']} ({pct:.1f}%)")
 
 
if __name__ == "__main__":
    main()