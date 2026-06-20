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

    test_cases = [
        # Label         Na    K    Cl   BUN   Cr    Glu  Age Gender  Wt   BMI
        ("Euhydrated",  135, 4.0, 103,  16,  0.9,  110,  70,  2,  65, 25.0),
        ("Mild",        143, 4.4, 104,  37,  2.5,  240,  68,  1,  72, 27.0),
        ("Moderate",    147, 4.7, 106,  65,  5.7,  182,  75,  2,  60, 24.0),
        ("Severe",      160, 4.7, 112,  49,  1.7,  114,  80,  1,  55, 22.0),
    ]

    for expected, na, k, cl, bun, cr, glu, age, gender, wt, bmi in test_cases:
        code, label = predict_dehydration_risk(na, k, cl, bun, cr, glu, age, gender, wt, bmi)
        print(f"Expected: {expected:15} → Got: {label}")