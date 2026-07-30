'''
Automates the manual gap-table analysis done during development. 
For each patient, reads consecutive reading timestamps from the decrypted vitals_raw CSV and the 
corresponding risk label from the JSON logs (joined on patient_id + sensor_timestamp), 
then checks that each gap matches the interval implied by the risk TWO readings back.

Now supports timed runs: only validates readings within [start, start + duration].
'''

import argparse
import json
import glob
import os
import pandas as pd
from datetime import datetime, timedelta

# Mapping from risk label to expected inter-reading interval (seconds)
INTERVAL_MAP = {
    "Euhydrated": 60,
    "Mild": 30,
    "Moderate": 20,
    "Severe": 10,
}

# Default interval for the very first gap per patient (no prior risk yet)
BASELINE_INTERVAL = 60

# Allowed slack (seconds) around the expected interval, to absorb normal
# processing/network overhead rather than flagging every few-hundred-ms
# jitter as a failure.
TOLERANCE_SECONDS = 3 # Any gap within +3/-3 seconds is considered PASS


def parse_ts(ts_str):
    """Parse timestamp from CSV/JSON. Handles 'YYYY-MM-DD HH:MM:SS' and ISO formats."""
    # If timestamp is missing, return None
    if ts_str is None:
        return None
    try:
        s = str(ts_str).strip()
        # Convert "2026-07-29 15:57:52" -> "2026-07-29T15:57:52"
        s = s.replace(" ", "T", 1) # Replace first space with 'T' to make it ISO-like
        # If timestamp ends with 'Z' (UTC marker), replace 'Z' with explicit UTC offest
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s) # Parse ISO-like timestamp into datetime
    except Exception:
        return None


def load_json_logs(logs_dir, start_ts, end_ts):
    """Load JSON logs filtered to [start_ts, end_ts] based on sensor_timestamp."""
    # List to accumulate filtered log entries
    records = []
    # Iterate over all JSON files matching patient_*.json in the given logs_dir
    for path in glob.glob(os.path.join(logs_dir, "patient_*.json")):
        try:
            with open(path) as f:
                entries = json.load(f)
            # Iterate over entries in the file
            for e in entries:
                ts = parse_ts(e.get("sensor_timestamp")) # Parse sensor_timestamp from log entry
                # Include only entries whose sensor_timestamp falls in [start_ts, end_ts]
                if ts and start_ts <= ts <= end_ts:
                    records.append(e) # Add entry to filtered records
        except Exception as e:
            print(f"Could not read {path}: {e}")
    return records


def build_risk_lookup(log_records):
    """(patient_id, sensor_timestamp_str) -> risk label, for joining against CSV rows."""
    lookup = {}  # Dict mapping (patient_id, sensor_timestamp_str) to risk label
    # Iterate over all log entries
    for r in log_records:
        # Key: patient_id + sensor_timestamp string
        key = (r.get("patient_id"), str(r.get("sensor_timestamp")))
        lookup[key] = r.get("ml_prediction")
    return lookup


def check_patient(patient_id, readings_df, risk_lookup):
    """readings_df: rows for one patient, sorted by timestamp ascending,
    with a 'timestamp' column matching the SensorAgent/CSV timestamp format."""
    readings_df = readings_df.sort_values("timestamp").reset_index(drop=True)
    # Sort readings by timestamp and reset index to 0..n-1
    n = len(readings_df) # Number of readings for this patient

    rows_out = [] # List of result rows (one per gap between readings)
    # Iterate over indices 0..n-2 to compare reading i to reading i+1
    for i in range(n - 1):
        ts_i = str(readings_df.loc[i, "timestamp"]) # Timestamp of current reading i
        ts_next = str(readings_df.loc[i + 1, "timestamp"]) # Timestamp of next reading i+1

        try:
            t_i = pd.to_datetime(ts_i) # Convert current timestamp to datetime
            t_next = pd.to_datetime(ts_next) # Convert next timestamp to datetime
            actual_gap = (t_next - t_i).total_seconds() # Compute gap in seconds between consecutive readings
        except Exception:
            continue

        if i == 0:
            # First gap for this patient: driven by baseline interval (no prior risk yet)
            expected_gap = BASELINE_INTERVAL
            source = "baseline (no prior prediction yet)"
        else:
            # For subsequent gaps, expected interval is driven by risk TWO readings back
            ts_source = str(readings_df.loc[i - 1, "timestamp"]) # Timestamp of the previous reading (source of risk)
            risk_source = risk_lookup.get((patient_id, ts_source)) #  Look up risk label for that reading
            # If no risk label for that reading, mark this gap as SKIPPED
            if risk_source is None:
                rows_out.append({
                    "patient_id": patient_id, "from_ts": ts_i, "to_ts": ts_next,
                    "actual_gap": actual_gap, "expected_gap": None,
                    "status": "SKIPPED", "reason": f"No risk label found for sensor reading @ {ts_source}"
                })
                continue # Skip gap

            # Expected interval: lookup by risk_source, default to baseline if unknown
            expected_gap = INTERVAL_MAP.get(risk_source, BASELINE_INTERVAL)
            # Describe source of expected interval
            source = f"risk='{risk_source}' @ {ts_source}"

        # Check if actual gap is within tolerance of expected gap
        within_tolerance = abs(actual_gap - expected_gap) <= TOLERANCE_SECONDS
        rows_out.append({
            "patient_id": patient_id, "from_ts": ts_i, "to_ts": ts_next,
            "actual_gap": round(actual_gap, 1), "expected_gap": expected_gap, # Round gap to 0.1s for output
            "status": "PASS" if within_tolerance else "FAIL", # PASS/FAIL based on tolerance
            "source": source,
        })

    # Return list of gap analysis rows for this patient
    return rows_out


def main():
    # Set up argument parser for command-line usage
    parser = argparse.ArgumentParser()

    parser.add_argument("--csv", required=True, help="Path to decrypted vitals_raw CSV")
    parser.add_argument("--logs-dir", default="logs", help="Path to the phase-specific logs folder")
    parser.add_argument("--start", required=True, help="ISO start time of run (e.g. 2026-07-29T15:57:52)")
    parser.add_argument("--duration", type=int, required=True, help="Run duration in seconds (e.g. 300)")

    args = parser.parse_args() # Parse arguments from command line

    start_ts = parse_ts(args.start) # Parse start time string into datetime
    if start_ts is None:
        print(f"Invalid --start value: {args.start}")
        return
    end_ts = start_ts + timedelta(seconds=args.duration) # Compute end time = start + duration

    # CSV file missing
    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}")
        return

    csv_df = pd.read_csv(args.csv) # Load CSV into DataFrame
    if "patient_id" not in csv_df.columns or "timestamp" not in csv_df.columns:
        print(f"CSV must have 'patient_id' and 'timestamp' columns. Found: {list(csv_df.columns)}")
        return

    # Filter CSV readings to the time window [start_ts, end_ts]
    csv_df["ts"] = csv_df["timestamp"].apply(parse_ts) # Parse timestamp column into datetime
    csv_df = csv_df[csv_df["ts"].notna()] # Drop rows where timestamp parsing failed
    csv_df = csv_df[(csv_df["ts"] >= start_ts) & (csv_df["ts"] <= end_ts)] # Keep only readings whose timestamp is inside the validation window

    log_records = load_json_logs(args.logs_dir, start_ts, end_ts) # Load JSON logs in window
    risk_lookup = build_risk_lookup(log_records) # Build lookup: (patient_id, sensor_ts) -> risk

    print(f"Validating interval adjustments within window:")
    print(f"  start  = {start_ts.isoformat()}")
    print(f"  end    = {end_ts.isoformat()}")
    print(f"  duration = {args.duration}s")
    print(f"Loaded {len(csv_df)} sensor readings and {len(log_records)} log entries in window\n")

    all_results = [] # Accumulate results for all patients
    # Group CSV readings by patient_id and analyze each group separately
    for patient_id, group in csv_df.groupby("patient_id"):
        results = check_patient(patient_id, group, risk_lookup) # Analyze gaps for this patient
        all_results.extend(results)  # Add to global results list

    passed = [r for r in all_results if r["status"] == "PASS"]
    failed = [r for r in all_results if r["status"] == "FAIL"]
    skipped = [r for r in all_results if r["status"] == "SKIPPED"]

    # SUMMARY OUTPUT
    print(f"PASS: {len(passed)}")
    print(f"FAIL: {len(failed)}")
    print(f"SKIPPED: {len(skipped)}\n")

    # FAILED
    if failed:
        print("=== FAILURES (gap did not match expected interval within tolerance) ===")
        for r in failed:
            print(f"Patient {r['patient_id']}: {r['from_ts']} -> {r['to_ts']} "
                  f"actual={r['actual_gap']}s expected={r['expected_gap']}s ({r['source']})")
        print()

    # SKIPPED
    if skipped:
        print("=== SKIPPED ===")
        for r in skipped:
            print(f"Patient {r['patient_id']}: {r['reason']}")
        print()

    # Compute and print per-patient pass rates
    print("=== Per-patient pass rate ===")
    by_patient = {} # Dict: patient_id -> {"pass": count, "total": count}
    for r in all_results:
        if r["status"] == "SKIPPED":
            continue # Do not include SKIPPED gaps in pass rate

        pid = r["patient_id"]
        by_patient.setdefault(pid, {"pass": 0, "total": 0}) # Initialize counters if needed
        by_patient[pid]["total"] += 1 # Increment total gaps
        if r["status"] == "PASS":
            by_patient[pid]["pass"] += 1
    # Print pass/total and percentage for each patient
    for pid, counts in by_patient.items():
        pct = 100 * counts["pass"] / counts["total"] if counts["total"] else 0
        print(f" Patient {pid}: {counts['pass']}/{counts['total']} ({pct:.1f}%)")


if __name__ == "__main__":
    main()