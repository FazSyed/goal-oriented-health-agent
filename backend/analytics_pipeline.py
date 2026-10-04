import os
import sys
from datetime import datetime
from typing import Dict, Any

# Ensure project imports resolve
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ml_model.model_utils import predict_dehydration_risk
from ontology.owl_reasoner import infer_risk_and_action
from backend.database_repository import DatabaseRepository
from backend.watch_ingestion import WatchSignalProcessor
from kafka_db.kafka_utils import KafkaLogger

class LocalAnalyticsService:
    def __init__(self):
        self.repo = DatabaseRepository()
        self.signal_processor = WatchSignalProcessor()
        self.kafka_logger = KafkaLogger(topic='sensor_data') # Dispatches visit events

    def process_full_clinical_visit(
        self,
        patient_id: str,
        labs: Dict[str, float],
        demographics: Dict[str, float],
        raw_watch_data: Dict[str, Any] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Runs Model 1 ML evaluation, processes raw PPG/EDA signals or pre-extracted watch features,
        queries OWL reasoner, and commits record to storage.
        """
        # 1. Predict Model 1 Risk
        tier, risk_label = predict_dehydration_risk(
            sodium=labs["sodium"],
            potassium=labs["potassium"],
            chloride=labs["chloride"],
            bun=labs["bun"],
            creatinine=labs["creatinine"],
            glucose=labs["glucose"],
            age=demographics["age"],
            gender=demographics["gender"],
            weight=demographics["weight"],
            bmi=demographics["bmi"]
        )

        # 2. Extract / Map Signal Features using HeartPy & NeuroKit2
        watch_features = {
            "mean_hr": None,
            "sdnn": None,
            "rmssd": None,
            "mean_eda": None,
            "eda_num_peaks": None,
            "acc_std": None
        }

        if raw_watch_data and isinstance(raw_watch_data, dict):
            # Case A: If pre-extracted features were passed from dashboard or test script
            if any(k in raw_watch_data for k in ["mean_hr", "bpm", "sdnn", "mean_eda", "eda_tonic_mean"]):
                watch_features["mean_hr"] = raw_watch_data.get("mean_hr", raw_watch_data.get("bpm"))
                watch_features["sdnn"] = raw_watch_data.get("sdnn")
                watch_features["rmssd"] = raw_watch_data.get("rmssd")
                watch_features["mean_eda"] = raw_watch_data.get("mean_eda", raw_watch_data.get("eda_tonic_mean"))
                watch_features["eda_num_peaks"] = raw_watch_data.get("eda_num_peaks", raw_watch_data.get("n_scr_peaks"))
                watch_features["acc_std"] = raw_watch_data.get("acc_std", raw_watch_data.get("accel_mag_std", 0.02))

            # Case B: If raw PPG/EDA signal arrays are passed directly
            else:
                ppg_array = raw_watch_data.get("raw_ppg", raw_watch_data.get("ppg"))
                eda_array = raw_watch_data.get("raw_eda", raw_watch_data.get("eda"))

                if ppg_array is not None:
                    ppg_res = self.signal_processor.process_raw_ppg(ppg_array)
                    if isinstance(ppg_res, dict):
                        watch_features["mean_hr"] = ppg_res.get("mean_hr", ppg_res.get("bpm"))
                        watch_features["sdnn"] = ppg_res.get("sdnn")
                        watch_features["rmssd"] = ppg_res.get("rmssd")

                if eda_array is not None:
                    eda_res = self.signal_processor.process_raw_eda(eda_array)
                    if isinstance(eda_res, dict):
                        watch_features["mean_eda"] = eda_res.get("mean_eda", eda_res.get("eda_tonic_mean"))
                        watch_features["eda_num_peaks"] = eda_res.get("eda_num_peaks", eda_res.get("n_scr_peaks"))

                if "raw_accel" in raw_watch_data or "accel" in raw_watch_data:
                    acc_array = raw_watch_data.get("raw_accel", raw_watch_data.get("accel"))
                    if isinstance(acc_array, (list, tuple)) and len(acc_array) > 0:
                        import numpy as np
                        watch_features["acc_std"] = float(np.std(acc_array))

        # 3. Infer OWL Action
        inferred_risk, action, meta = infer_risk_and_action(risk_label, patient_id=1)

        # 4. Construct Output Schema
        visit_record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patient_id": patient_id,
            "age": demographics["age"],
            "gender": demographics["gender"],
            "weight": demographics["weight"],
            "bmi": demographics["bmi"],
            "sodium": labs["sodium"],
            "potassium": labs["potassium"],
            "chloride": labs["chloride"],
            "bun": labs["bun"],
            "creatinine": labs["creatinine"],
            "glucose": labs["glucose"],
            "model1_tier": int(tier),
            "model1_risk": risk_label,
            **watch_features,
            "notes": notes
        }

        # 5. Persist Record
        success = self.repo.save_visit_record(visit_record)

        # 6. Publish Event to Kafka for Multi-Agent System (MAS) consumption
        self.kafka_logger.publish(visit_record)

        return {
            "status": "success" if success else "failed",
            "record": visit_record,
            "inferred_action": action,
            "owl_metadata": meta
        }

# Shared singleton instance
backend_service = LocalAnalyticsService()