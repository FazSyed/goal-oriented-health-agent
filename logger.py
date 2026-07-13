import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LOGS_DIR = os.getenv("LOGS_DIR", "logs")

def _ensure_logs_dir_exists():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

def _log_path(patient_id) -> str:
    return os.path.join(LOGS_DIR, f"patient_{patient_id}_log.json")

def log_pipeline_run(patient_id, vitals: dict, ml_prediction: str, ontology_result: dict, planner_result: dict, routing_result: dict):
    
    _ensure_logs_dir_exists()

    entry = {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "patient_id":     patient_id,
        "vitals":         vitals,
        "ml_prediction":  ml_prediction,
        "ontology":       ontology_result,
        "planner":        planner_result,
        "routing":        routing_result,
    }

    log_file_path = _log_path(patient_id)

    try:
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as f:
                existing = json.load(f)
        else:
            existing = []
    except (json.JSONDecodeError, OSError):
        print(f"[Logger] WARNING: Could not read existing log for patient_id={patient_id}. Starting fresh.")
        existing = []
 
    existing.append(entry)


    try:
        with open(log_file_path, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"[Logger] Entry saved → {log_file_path} (total entries: {len(existing)})")
    except OSError as e:
        print(f"[Logger] ERROR: Could not write log for patient_id={patient_id}: {e}")
 
    return entry


def build_vitals_dict(data: dict) -> dict:
    return {
        "sodium":     data.get("sodium"),
        "potassium":  data.get("potassium"),
        "chloride":   data.get("chloride"),
        "bun":        data.get("bun"),
        "creatinine": data.get("creatinine"),
        "glucose":    data.get("glucose"),
        "age":        data.get("age"),
        "gender":     data.get("gender"),
        "weight":     data.get("weight"),
        "bmi":        data.get("bmi"),
    }