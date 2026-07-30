'''
Validates every logged PDDL plan against the 5 documented plan templates
For each patient_*.json log entry, determines which template SHOULD have fired 
(based on ml_prediction + this patient's static oral_intake_feasible flag), 
parses the actual plan into an ordered ist of action names, and checks both step count and exact step sequence.
'''

import json
import glob
import os
import re
import argparse

# Static per-patient capability flag -- pulled from patient profiles, not
# from the log entry, since oral_intake_feasible is a fixed property of the
# patient, not something that varies per reading. Update patient_id -> bool
# to match your actual patients/*.json files.
ORAL_INTAKE_FEASIBLE_BY_PATIENT = {
    1: True,   # Fatima Al-Rashid  -- Mild, ORS feasible
    2: False,  # Ahmed Hassan      -- Mild, ORS NOT feasible (dysphagia)
    3: True,   # Margaret Osei     -- Moderate
    4: True,   # Robert Mensah     -- Severe
    5: True,   # Salman Mehfuz     -- Euhydrated patient
}

# The 5 documented plan templates, as ordered lists of action names
TEMPLATES = {
    "Euhydrated": [
        "check_hydration", "log_status_euhydrated"
    ],
    "Mild_ORS": [
        "check_hydration", "consume_ors", "monitor_intake",
        "recheck_hydration", "log_status_mild"
    ],
    "Mild_NoORS": [
        "check_hydration", "escalate_to_moderate", "alert_caregiver",
        "transfer_to_hospital_moderate", "administer_fluids_moderate",
        "recheck_labs_moderate", "monitor_vitals_moderate", "log_status_moderate"
    ],
    "Moderate": [
        "check_hydration", "alert_caregiver", "transfer_to_hospital_moderate",
        "administer_fluids_moderate", "recheck_labs_moderate",
        "monitor_vitals_moderate", "log_status_moderate"
    ],
    "Severe": [
        "check_hydration", "call_emergency", "transfer_to_hospital_severe",
        "administer_fluids_severe", "recheck_labs_severe",
        "monitor_vitals_continuous", "log_status_severe"
    ],
}


def expected_template_name(risk, oral_intake_feasible):
    # Decide which template name should apply for a given risk + oral intake flag
    if risk == "Euhydrated":
        return "Euhydrated"
    if risk == "Mild": # Mild patients use ORS path if oral intake is feasible, else escalate path
        return "Mild_ORS" if oral_intake_feasible else "Mild_NoORS"
    if risk == "Moderate":
        return "Moderate"
    if risk == "Severe":
        return "Severe"
    return None  # unknown/unexpected risk label -- can't validate
 
 
def parse_plan_steps(plan_text):
    """Extracts action names from PDDL plan text. Handles lines like
    '(check_hydration patient1)' -- takes the first token inside the
    parentheses as the action name. Empty/malformed lines are skipped."""
    steps = [] # List of action names parsed from the plan
    # Process plan line by line
    for line in plan_text.splitlines():
        line = line.strip() # Strip whitespace from each line
        # Skip empty lines
        if not line:
            continue
        # Match an optional '(' followed by an action name (letters/underscores, then letters/digits/underscores)
        match = re.match(r"\(?\s*([a-zA-Z_][a-zA-Z0-9_]*)", line)
        if match:
            steps.append(match.group(1)) # Append the captured action name
    return steps # Return ordered list of actions in the plan
 
 
def validate_entry(entry):
    """Returns a dict describing pass/fail for one log entry, or None if
    this entry can't be validated (unknown risk, missing patient config)."""

    patient_id = entry.get("patient_id") #  Extract patient_id from log entry
    risk = entry.get("ml_prediction") # Extract ML-predicted risk label
    plan_text = entry.get("planner", {}).get("plan", "") # Get raw planner plan text (or empty string)

    # If we don't have an oral_intake_feasible config for this patient, skip
    if patient_id not in ORAL_INTAKE_FEASIBLE_BY_PATIENT:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"No oral_intake_feasible config for patient {patient_id}"}
 
    oral_ok = ORAL_INTAKE_FEASIBLE_BY_PATIENT[patient_id] # Look up static oral intake flag
    template_name = expected_template_name(risk, oral_ok) # Determine expected template name

    # If risk label is unrecognized, skip validation
    if template_name is None:
        return {"patient_id": patient_id, "timestamp": entry.get("timestamp"),
                "status": "SKIPPED", "reason": f"Unrecognized risk label '{risk}'"}
 
    expected_steps = TEMPLATES[template_name] # Get expected action sequence for this template
    actual_steps = parse_plan_steps(plan_text) # Parse actual plan into list of actions
 
    step_count_ok = len(actual_steps) == len(expected_steps) # Check step count matches
    sequence_ok = actual_steps == expected_steps # Check full sequence matches exactly
 
    result = {
        "patient_id": patient_id,
        "timestamp": entry.get("timestamp"),
        "risk": risk,
        "expected_template": template_name,
        "expected_step_count": len(expected_steps),
        "actual_step_count": len(actual_steps),
        "step_count_ok": step_count_ok,
        "sequence_ok": sequence_ok,
        "status": "PASS" if sequence_ok else "FAIL",
    }

    # If sequence does not match, include the expected vs actual sequences for reporting
    if not sequence_ok:
        result["expected_steps"] = expected_steps
        result["actual_steps"] = actual_steps
    return result
 
 
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
 
    print(f"Loaded {len(entries)} log entries from {logs_dir}/\n")

    # Validate each entry and collect results
    results = [validate_entry(e) for e in entries]
    
    # Partition results into PASS, FAIL, and SKIPPED groups
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]
 
    print(f"PASS:    {len(passed)}")
    print(f"FAIL:    {len(failed)}")
    print(f"SKIPPED: {len(skipped)}")
    print()

    # FAILED
    if failed:
        print("=== FAILURES ===")
        for r in failed:
            print(f"Patient {r['patient_id']} @ {r['timestamp']} -- expected {r['expected_template']} "
                  f"({r['expected_step_count']} steps), got {r['actual_step_count']} steps")
            print(f"  Expected: {r['expected_steps']}")
            print(f"  Actual:   {r['actual_steps']}")
            print()

    # SKIPPED
    if skipped:
        reasons = {} # Dict: reason -> count
        for r in skipped:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
        print("=== SKIPPED (by reason) ===")
        for reason, count in reasons.items():
            print(f"  {count}x -- {reason}")
 
    # Per-template pass rate, useful directly for the paper's Results table
    print("\n=== Per-template pass rate ===")
    by_template = {} # Dict: template_name -> {"pass": count, "total": count}
    for r in results:
        if r["status"] == "SKIPPED":
            continue # Skip entries that couldn't be validated
        t = r["expected_template"]
        by_template.setdefault(t, {"pass": 0, "total": 0}) # Initialize counters if needed
        by_template[t]["total"] += 1 # Increment total for this template
        if r["status"] == "PASS":
            by_template[t]["pass"] += 1 # Increment pass count
    # Print per-template pass/total and percentage
    for t, counts in by_template.items():
        pct = 100 * counts["pass"] / counts["total"] if counts["total"] else 0
        print(f"  {t:12s}: {counts['pass']}/{counts['total']} ({pct:.1f}%)")
 
 
if __name__ == "__main__":
    main()