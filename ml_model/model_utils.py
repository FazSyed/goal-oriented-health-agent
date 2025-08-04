import joblib
import numpy as np
import pandas as pd

# Load the trained model
model = joblib.load("ml_model/dehydration_model.pkl")

risk_mapping = {
    0: "Euhydrated",
    1: "Mild",
    2: "Moderate",
    3: "Severe" 
}

def predict_dehydration_risk(baseline_weight, current_weight):
    """
    Predict dehydration risk from patient data.

    Parameters:
    - baseline_weight: Baseline weight in kg
    - current_weight: Current weight in kg

    Returns:
    - prediction_code (int)
    - prediction_label (str)
    - tbw_loss_percent (float)
    """
    absolute_weight_loss = baseline_weight - current_weight
    tbw_loss_percent = (absolute_weight_loss / baseline_weight) * 100

    # Match feature order from training
    feature_names = [
        'Absolute Weight Loss',
        'TBW Loss % (Elders)'
    ]
    features = pd.DataFrame([[absolute_weight_loss, tbw_loss_percent]], columns=feature_names)

    prediction_code = model.predict(features)[0]
    prediction_label = risk_mapping.get(int(prediction_code), "Unknown")

    return prediction_code, prediction_label, tbw_loss_percent


# baseline_weight = 72  # kg
# current_weight = 65   # kg

# code, label, percent = predict_dehydration_risk(baseline_weight, current_weight)

# print("Dehydration Risk Code:", code)
# print("Dehydration Risk Label:", label)
# print("TBW Loss %:", round(percent, 2))
