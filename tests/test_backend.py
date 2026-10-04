import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import backend_service

def run_test():
    print("Testing Local Backend Processing...")
    
    # 1. Simulate 15 seconds of raw PPG (100 Hz) and EDA (4 Hz)
    time_ppg = np.linspace(0, 15, 1500)
    simulated_ppg = np.sin(2 * np.pi * 1.2 * time_ppg) # ~72 BPM
    simulated_eda = np.full(60, 0.15) # Constant baseline EDA
    
    # 2. Invoke service
    result = backend_service.process_full_clinical_visit(
        patient_id="P999",
        labs={"sodium": 145, "potassium": 4.5, "chloride": 105, "bun": 40, "creatinine": 2.1, "glucose": 130},
        demographics={"age": 78, "gender": 1, "weight": 62, "bmi": 23.5},
        raw_watch_data={"ppg": simulated_ppg, "eda": simulated_eda},
        notes="Automated Integration Test"
    )
    
    print("\n--- Pipeline Execution Output ---")
    print(f"Status          : {result['status']}")
    print(f"Model 1 Risk    : {result['record']['model1_risk']}")
    print(f"Inferred Action : {result['inferred_action']}")
    print(f"Extracted HR    : {result['record']['mean_hr']} BPM")

if __name__ == "__main__":
    run_test()