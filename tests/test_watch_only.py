import os
import sys
# Ensure project root is accessible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from backend import backend_service

# 1. Create dummy staging data for P001 directly
os.makedirs("logs/watch_staging", exist_ok=True)
dummy_signal = {
    "raw_ppg": (500 + 100 * np.sin(np.linspace(0, 10, 250))).tolist(),
    "raw_eda": [0.12, 0.13, 0.15, 0.18, 0.22, 0.21, 0.19, 0.17, 0.16, 0.15, 0.14, 0.13, 0.12],
    "raw_temp": 36.5
}

# 2. Test watch processing logic directly
from visualization.data_collection_dash import process_raw_watch_payload
extracted_watch_features = process_raw_watch_payload(dummy_signal)

print("\n--- STEP 1: Extracted Keys from process_raw_watch_payload ---")
print(json.dumps(extracted_watch_features, indent=2))

# 3. Test sending directly to backend pipeline
demographics = {"age": 70, "gender": 1, "weight": 70.0, "bmi": 24.0}
labs = {"sodium": 140.0, "potassium": 4.5, "chloride": 102.0, "bun": 20.0, "creatinine": 1.0, "glucose": 100.0}

response = backend_service.process_full_clinical_visit(
    patient_id="P_ISOLATION_TEST",
    labs=labs,
    demographics=demographics,
    raw_watch_data=extracted_watch_features
)

print("\n--- STEP 2: Backend Service Response ---")
print("Status:", response.get("status"))
print("Record saved to CSV:", response.get("record"))