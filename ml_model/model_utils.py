import joblib
import numpy as np
import pandas as pd

# Load the trained model
model = joblib.load("ml_model/dehydration_model_rf.pkl")

risk_mapping = {
    0: "Euhydrated",
    1: "Mild",
    2: "Moderate",
    3: "Severe" 
}

def predict_dehydration_risk(sodium, potassium, chloride, bun, creatinine, glucose, age, gender, weight, bmi):

    # Match feature order from training
    feature_names = [
        'Sodium',
        'Potassium',
        'Chloride',
        'BUN',
        'Creatinine',
        'Glucose',
        'Age',
        'Gender',
        'Weight',
        'BMI'
    ]
    features = pd.DataFrame([[sodium, potassium, chloride, bun, creatinine, glucose, age, gender, weight, bmi]], columns=feature_names)

    prediction_code = model.predict(features)[0]
    prediction_label = risk_mapping.get(int(prediction_code), "Unknown")

    return prediction_code, prediction_label

# Debugging
if __name__ == "__main__":
    # Example: elderly female patient with mild dehydration indicators
    code, label = predict_dehydration_risk(
        sodium=142,
        potassium=4.1,
        chloride=103,
        bun=18,
        creatinine=0.9,
        glucose=98,
        age=72,
        gender=2,
        weight=65,
        bmi=26.5
    )
    print(f"Prediction Code: {code}")
    print(f"Prediction Label: {label}")