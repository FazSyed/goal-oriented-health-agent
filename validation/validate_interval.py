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


INTERVAL_MAP = {
    "Euhydrated": 60,
    "Mild": 30,
    "Moderate": 20,
    "Severe": 10,
}

BASELINE_INTERVAL = 60

# Allowed slack (seconds) around the expected interval, to absorb normal
# processing/network overhead rather than flagging every few-hundred-ms
# jitter as a failure.
TOLERANCE_SECONDS = 3


def parse_ts(ts_str):
    """Parse timestamp from CSV/JSON. Handles 'YYYY-MM-DD HH:MM:SS' and ISO formats."""
    if ts_str is None:
        return None
    try:
        s = str(ts_str).strip()
        # Convert "2026-07-29 15:57:52" -> "2026-07-29T15:57:52"
        s = s.replace(" ", "T", 1)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def load_json_logs(logs_dir, start_ts, end_ts):
    """Load JSON logs filtered to [start_ts, end_ts] based on sensor_timestamp."""
    records = []
    for path in glob.glob(os.path.join(logs_dir, "patient_*.json")):
        try:
            with open(path) as f:
                entries = json.load(f)
            for e in entries:
                ts = parse_ts(e.get("sensor_timestamp"))
                if ts and start_ts <= ts <= end_ts:
                    records.append(e)
        except Exception as e:
            print(f"Could not read {path}: {e}")
    return records


def build_risk_lookup(log_records):
    """(patient_id, sensor_timestamp_str) -> risk label, for joining against CSV rows."""
    lookup = {}
    for r in log_records:
        key = (r.get("patient_id"), str(r.get("sensor_timestamp")))
        lookup[key] = r.get("ml_prediction")
    return lookup


def check_patient(patient_id, readings_df, risk_lookup):
    """readings_df: rows for one patient, sorted by timestamp ascending,
    with a 'timestamp' column matching the SensorAgent/CSV timestamp format."""
    readings_df = readings_df.sort_values("timestamp").reset_index(drop=True)
    n = len(readings_df)

    rows_out = []
    for i in range(n - 1):
        ts_i = str(readings_df.loc[i, "timestamp"])
        ts_next = str(readings_df.loc[i + 1, "timestamp"])

        try:
            t_i = pd.to_datetime(ts_i)
            t_next = pd.to_datetime(ts_next)
            actual_gap = (t_next - t_i).total_seconds()
        except Exception:
            continue

        if i == 0:
            expected_gap = BASELINE_INTERVAL
            source = "baseline (no prior prediction yet)"
        else:
            ts_source = str(readings_df.loc[i - 1, "timestamp"])
            risk_source = risk_lookup.get((patient_id, ts_source))
            if risk_source is None:
                rows_out.append({
                    "patient_id": patient_id, "from_ts": ts_i, "to_ts": ts_next,
                    "actual_gap": actual_gap, "expected_gap": None,
                    "status": "SKIPPED", "reason": f"No risk label found for sensor reading @ {ts_source}"
                })
                continue
            expected_gap = INTERVAL_MAP.get(risk_source, BASELINE_INTERVAL)
            source = f"risk='{risk_source}' @ {ts_source}"

        within_tolerance = abs(actual_gap - expected_gap) <= TOLERANCE_SECONDS
        rows_out.append({
            "patient_id": patient_id, "from_ts": ts_i, "to_ts": ts_next,
            "actual_gap": round(actual_gap, 1), "expected_gap": expected_gap,
            "status": "PASS" if within_tolerance else "FAIL",
            "source": source,
        })

    return rows_out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to decrypted vitals_raw CSV")
    parser.add_argument("--logs-dir", default="logs", help="Path to the phase-specific logs folder")
    parser.add_argument("--start", required=True, help="ISO start time of run (e.g. 2026-07-29T15:57:52)")
    parser.add_argument("--duration", type=int, required=True, help="Run duration in seconds (e.g. 300)")
    args = parser.parse_args()

    start_ts = parse_ts(args.start)
    if start_ts is None:
        print(f"Invalid --start value: {args.start}")
        return
    end_ts = start_ts + timedelta(seconds=args.duration)

    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}")
        return

    csv_df = pd.read_csv(args.csv)
    if "patient_id" not in csv_df.columns or "timestamp" not in csv_df.columns:
        print(f"CSV must have 'patient_id' and 'timestamp' columns. Found: {list(csv_df.columns)}")
        return

    # Filter CSV to [start_ts, end_ts]
    csv_df["ts"] = csv_df["timestamp"].apply(parse_ts)
    csv_df = csv_df[csv_df["ts"].notna()]
    csv_df = csv_df[(csv_df["ts"] >= start_ts) & (csv_df["ts"] <= end_ts)]

    log_records = load_json_logs(args.logs_dir, start_ts, end_ts)
    risk_lookup = build_risk_lookup(log_records)

    print(f"Validating interval adjustments within window:")
    print(f"  start  = {start_ts.isoformat()}")
    print(f"  end    = {end_ts.isoformat()}")
    print(f"  duration = {args.duration}s")
    print(f"Loaded {len(csv_df)} sensor readings and {len(log_records)} log entries in window\n")

    all_results = []
    for patient_id, group in csv_df.groupby("patient_id"):
        results = check_patient(patient_id, group, risk_lookup)
        all_results.extend(results)

    passed = [r for r in all_results if r["status"] == "PASS"]
    failed = [r for r in all_results if r["status"] == "FAIL"]
    skipped = [r for r in all_results if r["status"] == "SKIPPED"]

    print(f"PASS: {len(passed)}")
    print(f"FAIL: {len(failed)}")
    print(f"SKIPPED: {len(skipped)}\n")

    if failed:
        print("=== FAILURES (gap did not match expected interval within tolerance) ===")
        for r in failed:
            print(f"Patient {r['patient_id']}: {r['from_ts']} -> {r['to_ts']} "
                  f"actual={r['actual_gap']}s expected={r['expected_gap']}s ({r['source']})")
        print()

    if skipped:
        print("=== SKIPPED ===")
        for r in skipped:
            print(f"Patient {r['patient_id']}: {r['reason']}")
        print()

    print("=== Per-patient pass rate ===")
    by_patient = {}
    for r in all_results:
        if r["status"] == "SKIPPED":
            continue
        pid = r["patient_id"]
        by_patient.setdefault(pid, {"pass": 0, "total": 0})
        by_patient[pid]["total"] += 1
        if r["status"] == "PASS":
            by_patient[pid]["pass"] += 1
    for pid, counts in by_patient.items():
        pct = 100 * counts["pass"] / counts["total"] if counts["total"] else 0
        print(f" Patient {pid}: {counts['pass']}/{counts['total']} ({pct:.1f}%)")


if __name__ == "__main__":
    main()