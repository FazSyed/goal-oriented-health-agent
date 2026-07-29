'''
Checks routing.routed_to and routing.kafka_topic against the expected
mapping for every logged reading. Flags mismatches
'''

import json
import glob
import os
import argparse
 
# Set to True only after fixing HealthAgent to route Mild-NoORS -> careagent
STRICT_ORAL_INTAKE_AWARE_ROUTING = True
 
ORAL_INTAKE_FEASIBLE_BY_PATIENT = {
    1: True,
    2: False,
    3: True,
    4: True,
    5: True,
}
 
 
def expected_routing(risk, oral_intake_feasible):
    if risk == "Euhydrated":
        return {"routed_to": None, "kafka_topic": "euhydrated_log"}
    if risk == "Mild":
        if STRICT_ORAL_INTAKE_AWARE_ROUTING and not oral_intake_feasible:
            return {"routed_to": "careagent@localhost", "kafka_topic": "care_alerts"}
        return {"routed_to": "reminderagent@localhost", "kafka_topic": "reminders"}
    if risk in ("Moderate", "Severe"):
        return {"routed_to": "careagent@localhost", "kafka_topic": "care_alerts"}
    return None
 
 
def validate_entry(entry):
    patient_id = entry.get("patient_id")
    risk = entry.get("ml_prediction")
    routing = entry.get("routing", {})
 
    if patient_id not in ORAL_INTAKE_FEASIBLE_BY_PATIENT:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"No config for patient {patient_id}"}
 
    oral_ok = ORAL_INTAKE_FEASIBLE_BY_PATIENT[patient_id]
    expected = expected_routing(risk, oral_ok)
 
    if expected is None:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"Unrecognized risk label '{risk}'"}
 
    actual = {"routed_to": routing.get("routed_to"), "kafka_topic": routing.get("kafka_topic")}
    routed_to_ok = actual["routed_to"] == expected["routed_to"]
    kafka_topic_ok = actual["kafka_topic"] == expected["kafka_topic"]
 
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-dir", default="logs", help="Path to the phase-specific logs folder (e.g. logs_evaluation)")
    args = parser.parse_args()
    logs_dir = args.logs_dir
 
    entries = []
    for path in glob.glob(os.path.join(logs_dir, "patient_*.json")):
        try:
            with open(path) as f:
                entries.extend(json.load(f))
        except Exception as e:
            print(f"Could not read {path}: {e}")
 
    print(f"Loaded {len(entries)} log entries from {logs_dir}/")
    print(f"Strict oral-intake-aware routing check: {STRICT_ORAL_INTAKE_AWARE_ROUTING}\n")
 
    results = [validate_entry(e) for e in entries]
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]
 
    print(f"PASS:    {len(passed)}")
    print(f"FAIL:    {len(failed)}")
    print(f"SKIPPED: {len(skipped)}\n")
 
    if failed:
        print("=== FAILURES ===")
        for r in failed:
            print(f"Patient {r['patient_id']} @ {r['timestamp']} (risk={r['risk']})")
            print(f"  Expected: {r['expected']}")
            print(f"  Actual:   {r['actual']}")
            print()
 
    # Per-risk-level pass rate
    print("=== Per-risk-level pass rate ===")
    by_risk = {}
    for r in results:
        if r["status"] == "SKIPPED":
            continue
        risk = r["risk"]
        by_risk.setdefault(risk, {"pass": 0, "total": 0})
        by_risk[risk]["total"] += 1
        if r["status"] == "PASS":
            by_risk[risk]["pass"] += 1
    for risk, counts in by_risk.items():
        pct = 100 * counts["pass"] / counts["total"] if counts["total"] else 0
        print(f"  {risk:12s}: {counts['pass']}/{counts['total']} ({pct:.1f}%)")
 
 
if __name__ == "__main__":
    main()