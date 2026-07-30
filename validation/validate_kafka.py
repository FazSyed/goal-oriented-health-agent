'''
Two separate checks, since they cover two different hops in the pipeline:

  A) Sensor -> Kafka -> HealthAgent completeness:
     compares decrypted vitals_raw CSV row count (what SensorAgents actually
     sent) against patient_{id}_log.json entry count (what HealthAgent
     actually processed and logged), per patient. A gap here means a
     reading was sent but never made it through the pipeline -- e.g. lost
     in Kafka, or HealthAgent crashed before logging it.

  B) HealthAgent -> downstream topic publish success:
     tabulates routing.kafka_publish_success (True/False) per Kafka topic
     (reminders / care_alerts / euhydrated_log) from the JSON logs
     themselves. A False here means KafkaLogger's publish() exhausted its
     3 retries -- this is what should trigger alert_mailer.report_fallback.
'''

import argparse
import json
import glob
import os
import pandas as pd
from datetime import datetime, timedelta


def parse_ts(ts_str):
    """Parse timestamp from CSV/JSON. Handles 'YYYY-MM-DD HH:MM:SS' and ISO formats."""
    if ts_str is None:
        return None
    try:
        s = str(ts_str).strip()
        # Convert "2026-07-29 15:57:52" -> "2026-07-29T15:57:52"
        s = s.replace(" ", "T", 1) # Replace first space with 'T' to make it ISO-like
        if s.endswith("Z"): # If timestamp ends with 'Z' (UTC designator, replace 'Z' with explicit UTC offset
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s) # Parse into a datetime object
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


def check_sensor_to_healthagent_completeness(csv_path, log_records, start_ts, end_ts):
    # If CSV path is missing or file does not exist, skip completeness check
    if not csv_path or not os.path.exists(csv_path):
        print("=== A) Sensor -> HealthAgent completeness: SKIPPED ===")
        print("No --csv path given, or file not found. Run decrypt_csv.py first,")
        print("then pass its output path with --csv.\n")
        return

    print("=== A) Sensor -> HealthAgent completeness ===")
    try:
        csv_df = pd.read_csv(csv_path) # Load decrypted vitals_raw CSV into DataFrame
    except Exception as e:
        print(f"Could not read CSV: {e}\n")
        return
    
    # Ensure required columns are present
    if "patient_id" not in csv_df.columns or "timestamp" not in csv_df.columns:
        print(f"CSV missing 'patient_id'/'timestamp' columns. Columns found: {list(csv_df.columns)}\n")
        return

    # Filter CSV rows to [start_ts, end_ts] based on timestamp
    csv_df["ts"] = csv_df["timestamp"].apply(parse_ts) # Parse timestamp column into datetime
    csv_df = csv_df[csv_df["ts"].notna()] # Drop rows where timestamp parsing failed
    # Keep only sensor readings whose timestamp falls inside the validation window
    csv_df = csv_df[(csv_df["ts"] >= start_ts) & (csv_df["ts"] <= end_ts)]

    logged_keys = set() # Set of (patient_id, sensor_timestamp_str) for logged entries
    for r in log_records:
        sensor_ts = r.get("sensor_timestamp") # Sensor timestamp from HealthAgent log
        if sensor_ts is not None:
            # Add key (patient_id, sensor_timestamp) to set of logged readings
            logged_keys.add((r.get("patient_id"), str(sensor_ts)))

    # Get sorted list of unique patient IDs from CSV
    all_patients = sorted(csv_df["patient_id"].unique())
    print(f"{'Patient':<10}{'Sensor sent':<14}{'HealthAgent logged':<20}{'Gap':<8}{'Status'}")

    missing_by_patient = {} # Dict: patient_id -> list of missing timestamps
    # For each patient, compare sent vs logged readings
    for pid in all_patients:
        patient_rows = csv_df[csv_df["patient_id"] == pid] # All CSV rows for this patient
        sent = len(patient_rows) # Number of sensor readings from CSV
        # Find CSV timestamps that are not present in logged_keys
        missing_ts = [str(ts) for ts in patient_rows["timestamp"] if (pid, str(ts)) not in logged_keys]
        logged = sent - len(missing_ts) # Logged = sent - missing
        gap = len(missing_ts) # Gap = number of missing readings
        status = "OK" if gap == 0 else "MISSING READINGS" # Status: OK if no gap, else MISSING
        # Print per-patient summary row
        print(f"{pid:<10}{sent:<14}{logged:<20}{gap:<8}{status}")
        if missing_ts:
            # Store missing timestamps for detailed reporting
            missing_by_patient[pid] = sorted(missing_ts)
    print()

    # If any missing readings exist, print detailed list
    if missing_by_patient:
        print("=== Exact missing readings (sensor sent, HealthAgent never logged) ===")
        for pid, timestamps in missing_by_patient.items():
            print(f"Patient {pid} -- {len(timestamps)} missing:")
            for ts in timestamps:
                print(f"    {ts}")
        print("\nCross-reference these exact timestamps against agent_system.log and your")
        print("console output for '[Health] Error processing message:' around each one --")
        print("that tells you whether HealthAgent received but crashed on it (exception),")
        print("vs. never receiving it at all (delivery/XMPP-level issue).\n")


def check_downstream_publish_success(log_records):
    print("=== B) HealthAgent -> downstream topic publish success ===")

    by_topic = {} # Dict: topic -> counters and failure details
    # Iterate through all log records in window
    for r in log_records:
        routing = r.get("routing", {}) # Get routing sub-dict from log entry
        topic = routing.get("kafka_topic") # Kafka topic name (reminders/care_alerts/euhydrated_log)
        success = routing.get("kafka_publish_success") # True/False publish flag
        # Skip entries with no topic (e.g., no routing)
        if topic is None:
            continue
        # Initialize counters for each topic if not present
        by_topic.setdefault(topic, {"success": 0, "fail": 0, "failures": []})
        if success:
            by_topic[topic]["success"] += 1 # Increment success count
        else:
            by_topic[topic]["fail"] += 1 # Increment failure count
            # Record failure details: patient_id and timestamp
            by_topic[topic]["failures"].append({
                "patient_id": r.get("patient_id"),
                "timestamp": r.get("timestamp"),
            })

    print(f"{'Topic':<18}{'Success':<10}{'Fail':<8}{'Success Rate'}")
    for topic, counts in by_topic.items():
        total = counts["success"] + counts["fail"] # Total attempts for this topic
        pct = 100 * counts["success"] / total if total else 0 # Success rate percentage
        print(f"{topic:<18}{counts['success']:<10}{counts['fail']:<8}{pct:.1f}%")

    # Check whether any topic had publish failures
    any_failures = any(c["fail"] > 0 for c in by_topic.values())
    if any_failures:
        print("\n=== Publish failures (should correlate with alert_mailer fallback emails) ===")
        # For each topic with failures, print detailed list of failed publishes
        for topic, counts in by_topic.items():
            for f in counts["failures"]:
                print(f" [{topic}] Patient {f['patient_id']} @ {f['timestamp']}")
        print()


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

    # Load JSON log entries whose sensor_timestamp falls within [start_ts, end_ts]
    log_records = load_json_logs(args.logs_dir, start_ts, end_ts)

    print(f"Validating Kafka delivery within window:")
    print(f"  start  = {start_ts.isoformat()}")
    print(f"  end    = {end_ts.isoformat()}")
    print(f"  duration = {args.duration}s")
    print(f"Loaded {len(log_records)} log entries in window\n")

    # Run completeness check (sensor -> Kafka -> HealthAgent)
    check_sensor_to_healthagent_completeness(args.csv, log_records, start_ts, end_ts)
    # Run downstream publish success check (HealthAgent -> Kafka topics)
    check_downstream_publish_success(log_records)


if __name__ == "__main__":
    main()