import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get logs directory from environment or use default "logs"
LOGS_DIR = os.getenv("LOGS_DIR", "logs")

# Function to ensure the logs directory exists
def _ensure_logs_dir_exists():
    # Check if logs directory doesn't exist
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR) # Create the logs directory

# Function to generate log file path for a patient
def _log_path(patient_id) -> str:
    # Return the full path to the patient's log file
    return os.path.join(LOGS_DIR, f"patient_{patient_id}_log.json")

# Function to log a pipeline run with patient data
def log_pipeline_run(patient_id, vitals: dict, ml_prediction: str, ontology_result: dict, planner_result: dict, routing_result: dict):
    
    # Ensure logs directory exists before writing
    _ensure_logs_dir_exists()

    # Create entry dictionary with current timestamp and pipeline data
    entry = {
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Current timestamp
        "patient_id":     patient_id,  # Patient ID
        "vitals":         vitals,  # Vital signs data
        "ml_prediction":  ml_prediction,  # ML model prediction
        "ontology":       ontology_result,  # Ontology processing result
        "planner":        planner_result,  # Planner result
        "routing":        routing_result,  # Routing result
    }

    # Get the log file path for this patient
    log_file_path = _log_path(patient_id)

    # Try to read existing log entries
    try:
        # Check if log file already exists
        if os.path.exists(log_file_path):
            # Open log file in read mode
            with open(log_file_path, "r") as f:
                # Load existing JSON entries
                existing = json.load(f)
        # Log file doesn't exist yet
        else:
            existing = [] # Initialize empty list for entries

    except (json.JSONDecodeError, OSError):
        print(f"[Logger] WARNING: Could not read existing log for patient_id={patient_id}. Starting fresh.")
        existing = [] # Start with empty list
 
    # Append the new entry to the list
    existing.append(entry)


    # Write the log entries to file
    try:
        # Open log file in write mode
        with open(log_file_path, "w") as f:
            # Write entries as formatted JSON
            json.dump(existing, f, indent=2)
        print(f"[Logger] Entry saved → {log_file_path} (total entries: {len(existing)})")

    except OSError as e:
        print(f"[Logger] ERROR: Could not write log for patient_id={patient_id}: {e}")
 
    # Return the created entry
    return entry


# Function to build a vitals dictionary from raw data
def build_vitals_dict(data: dict) -> dict:
    # Return dictionary with extracted vital signs
    return {
        "sodium":     data.get("sodium"),  # Sodium level
        "potassium":  data.get("potassium"),  # Potassium level
        "chloride":   data.get("chloride"),  # Chloride level
        "bun":        data.get("bun"),  # Blood urea nitrogen
        "creatinine": data.get("creatinine"),  # Creatinine level
        "glucose":    data.get("glucose"),  # Glucose level
        "age":        data.get("age"),  # Patient age
        "gender":     data.get("gender"),  # Patient gender
        "weight":     data.get("weight"),  # Patient weight
        "bmi":        data.get("bmi"),  # Body mass index
    }