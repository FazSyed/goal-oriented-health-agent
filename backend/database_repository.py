import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
from backend.security import SecurityManager

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "visualization")
VISITS_CSV = os.path.join(DATA_DIR, "real_visits_log.csv")
PATIENTS_CSV = os.path.join(DATA_DIR, "study_patients.csv")

VISIT_SCHEMA = [
    "timestamp", "patient_id", "age", "gender", "weight", "bmi",
    "sodium", "potassium", "chloride", "bun", "creatinine", "glucose",
    "model1_tier", "model1_risk", "mean_hr", "sdnn", "rmssd", "mean_eda",
    "eda_num_peaks", "acc_std", "notes"
]

class DatabaseRepository:
    def __init__(self):
        self.security = SecurityManager()
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(VISITS_CSV):
            pd.DataFrame(columns=VISIT_SCHEMA).to_csv(VISITS_CSV, index=False)
        if not os.path.exists(PATIENTS_CSV):
            pd.DataFrame(columns=["patient_id", "full_name", "created_at"]).to_csv(PATIENTS_CSV, index=False)

    def register_patient(self, name: str) -> str:
        df = pd.read_csv(PATIENTS_CSV)
        pid = f"P{len(df)+1:03d}"
        new_patient = pd.DataFrame([{
            "patient_id": pid,
            "full_name": name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        df = pd.concat([df, new_patient], ignore_index=True)
        df.to_csv(PATIENTS_CSV, index=False)
        return pid

    def save_visit_record(self, record: Dict[str, Any]) -> bool:
        try:
            df = pd.read_csv(VISITS_CSV)
            row = {col: record.get(col, None) for col in VISIT_SCHEMA}
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_csv(VISITS_CSV, index=False)
            return True
        except Exception as e:
            print(f"[DatabaseRepository] Error writing visit: {e}")
            return False

    def get_latest_patient_demographics(self, patient_id: str) -> Dict[str, Any]:
        if not os.path.exists(VISITS_CSV):
            return {}
        df = pd.read_csv(VISITS_CSV)
        p_data = df[df["patient_id"] == patient_id]
        if not p_data.empty:
            last = p_data.iloc[-1]
            return {
                "age": last.get("age"),
                "gender": last.get("gender"),
                "weight": last.get("weight"),
                "bmi": last.get("bmi")
            }
        return {}