import itertools
import joblib
from numpy import rint
import pandas as pd

MODEL_PATH = "ml_model/dehydration_model_rf.pkl"
RISK_MAPPING = {0: "Euhydrated", 1: "Mild", 2: "Moderate", 3: "Severe"}
FEATURE_COLS = [
    'Sodium', 'Potassium', 'Chloride', 'BUN',
    'Creatinine', 'Glucose', 'Age', 'Gender', 'Weight', 'BMI'
]

# Fixed demographic values used across all scans (Patient 1 profile: age 72, female, 65.0 kg, BMI 26.5)
FIXED_DEMOGRAPHICS = [72, 2, 65.0, 26.5]

# Same grid resolution the original Mild scan used
NA_VALUES = range(135, 166, 2)
BUN_VALUES = range(10, 66, 5)
CR_VALUES = [0.6, 1.0, 1.5, 2.0, 3.0, 4.0]
GLUCOSE_VALUES = [80, 120, 180, 250]
K_VALUES = [3.5, 4.5, 5.5]
CL_VALUES = [98, 106, 114]

# Set True to also print a summary block for Euhydrated combinations found
INCLUDE_EUHYDRATED = True


def load_model():
    print(f"Loading model from {MODEL_PATH} ...\n")
    return joblib.load(MODEL_PATH)


def run_full_sweep(model):
    """Builds every combination in one batch, predicts once, returns a
    DataFrame with a Risk column attached."""
    combos = list(itertools.product(
        NA_VALUES, K_VALUES, CL_VALUES, BUN_VALUES, CR_VALUES, GLUCOSE_VALUES
    ))
    print(f"Testing {len(combos)} combinations in a single batched predict()...\n")

    rows = [[na, k, cl, bun, cr, glucose, *FIXED_DEMOGRAPHICS]
            for na, k, cl, bun, cr, glucose in combos]
    df = pd.DataFrame(rows, columns=FEATURE_COLS)

    preds = model.predict(df)
    df["Risk"] = [RISK_MAPPING[p] for p in preds]

    # Rename to short labels for readable output
    df = df.rename(columns={
        "Sodium": "Na", "Potassium": "K", "Chloride": "Cl", "Creatinine": "Cr"
    })
    return df


def print_class_summary(df, label):
    subset = df[df["Risk"] == label]

    if subset.empty:
        print(f"No {label} predictions found in full scan.")
        if label == "Mild":
            print("The Mild class boundary may be extremely narrow.")
            print("Consider checking if SMOTE worked correctly for Mild class.")
        return

    display_cols = ["Na", "BUN", "Cr", "Glucose", "K", "Cl"]
    if len(subset) > 20:
        print(f"Found {len(subset)} {label} combinations (showing first 20):")
        print(subset[display_cols].head(20).to_string(index=False))
    else:
        print(f"Found {len(subset)} {label} combinations:")
        print(subset[display_cols].to_string(index=False))
    print()
    print("=== Summary ranges (computed from all matches, not just those shown above) ===")
    print(f"Sodium:     {subset['Na'].min()} - {subset['Na'].max()}")
    print(f"BUN:        {subset['BUN'].min()} - {subset['BUN'].max()}")
    print(f"Creatinine: {subset['Cr'].min()} - {subset['Cr'].max()}")
    print(f"Glucose:    {subset['Glucose'].min()} - {subset['Glucose'].max()}")
    print(f"Potassium:  {subset['K'].min()} - {subset['K'].max()}")
    print(f"Chloride:   {subset['Cl'].min()} - {subset['Cl'].max()}")


if __name__ == "__main__":
    model = load_model()
    df = run_full_sweep(model)

    print("=" * 60)
    print("MILD")
    print("=" * 60)
    print_class_summary(df, "Mild")

    print("\n" + "=" * 60)
    print("MODERATE")
    print("=" * 60)
    print_class_summary(df, "Moderate")

    print("\n" + "=" * 60)
    print("SEVERE")
    print("=" * 60)
    print_class_summary(df, "Severe")

    if INCLUDE_EUHYDRATED:
        print("\n" + "=" * 60)
        print("EUHYDRATED")
        print("=" * 60)
        print_class_summary(df, "Euhydrated")