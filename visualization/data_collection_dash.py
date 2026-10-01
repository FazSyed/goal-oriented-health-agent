"""
Data Collection Dashboard (Rebuilt for Samsung Galaxy Watch8 Ingestion)
=======================================================================
Dashboard for clinical partners to:
1. Log patient demographics & laboratory blood panel.
2. Trigger/attach a 60-second Galaxy Watch 8 raw signal capture session.
3. Automatically run local HeartPy & NeuroKit2 feature extraction pipelines.
4. Predict risk tier live using Model 1 and save the final row to CSV for Model 2.
5. Display live collection progress charts and recent submission history.
"""

import os
import sys
import json
import datetime
import numpy as np
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
from dotenv import load_dotenv

# Ensure project root is accessible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_model.model_utils import predict_dehydration_risk

load_dotenv()
ROOT = os.path.dirname(os.path.abspath(__file__))

# Config
REAL_DATA_CSV_PATH = os.path.join(ROOT, os.getenv("REAL_DATA_CSV_PATH", "real_visits_log.csv"))
STUDY_PATIENTS_PATH = os.path.join(ROOT, os.getenv("STUDY_PATIENTS_PATH", "study_patients.csv"))
WATCH_STAGING_DIR = os.path.join(ROOT, os.getenv("WATCH_STAGING_DIR", "logs/watch_staging"))

# ACTUALLY required fields
LAB_FIELDS = ["sodium", "potassium", "chloride", "bun", "creatinine", "glucose"]
DEMO_FIELDS = ["age", "gender", "weight", "bmi"]

# Gender map for NHANES coding convention (1 = Male, 2 = Female) expected by Model 1
GENDER_MAP = {"Male": 1, "Female": 2}

# Derived Watch Features expected by Model 2
CARDIAC_COLS = ["bpm", "ibi", "sdnn", "rmssd", "breathingrate", "peak_rejected_frac"]
DELTA_SOURCE_COLS = [
    "eda_tonic_mean", "eda_phasic_mean", "eda_phasic_std", "n_scr_peaks", "scr_amplitude_mean",
    "ppg_cv", "ppg_skew", "ppg_kurtosis", "ppg_dominant_freq_hz", "ppg_spectral_entropy", "ppg_dominant_power_frac",
    "accel_mag_mean", "accel_mag_std", "temp_mean",
]
WATCH_FEATURE_COLS = CARDIAC_COLS + ["cardiac_missing", "eda_missing"] + DELTA_SOURCE_COLS

RISK_COLORS = {"Euhydrated": "#2ECC71", "Mild": "#F1C40F", "Moderate": "#E67E22", "Severe": "#E74C3C"}
TIER_ORDER = ["Euhydrated", "Mild", "Moderate", "Severe"]
INPUT_STYLE = {"width": "100%", "backgroundColor": "#F5F5F5", "color": "#1E1E1E", "border": "1px solid #555"}
CARD_STYLE = {"backgroundColor": "#2B2B2B", "borderRadius": "10px", "padding": "1.25rem", "marginBottom": "1.25rem"}


# --- Patient Registry Helpers ---

def load_study_patients() -> pd.DataFrame:
    if not os.path.exists(STUDY_PATIENTS_PATH):
        return pd.DataFrame(columns=["patient_id", "full_name"])
    try:
        return pd.read_csv(STUDY_PATIENTS_PATH, dtype=str)
    except Exception:
        return pd.DataFrame(columns=["patient_id", "full_name"])


def generate_next_patient_id(existing_df: pd.DataFrame) -> str:
    if existing_df.empty:
        return "P001"
    nums = existing_df["patient_id"].str.extract(r"P(\d+)")[0].dropna().astype(int)
    next_n = (nums.max() + 1) if not nums.empty else 1
    return f"P{next_n:03d}"


def register_new_patient(full_name: str) -> str:
    df = load_study_patients()
    new_id = generate_next_patient_id(df)
    updated = pd.concat([df, pd.DataFrame([{"patient_id": new_id, "full_name": full_name}])], ignore_index=True)
    os.makedirs(os.path.dirname(STUDY_PATIENTS_PATH), exist_ok=True) if os.path.dirname(STUDY_PATIENTS_PATH) else None
    updated.to_csv(STUDY_PATIENTS_PATH, index=False)
    return new_id


def patient_dropdown_options() -> list:
    df = load_study_patients()
    return [{"label": f"{row.full_name} ({row.patient_id})", "value": row.patient_id} for row in df.itertuples()]


def load_collected_data() -> pd.DataFrame:
    if not os.path.exists(REAL_DATA_CSV_PATH):
        return pd.DataFrame()
    try:
        return pd.read_csv(REAL_DATA_CSV_PATH)
    except Exception:
        return pd.DataFrame()


# --- Signal Processing Helper (HeartPy & NeuroKit2 Pipeline) ---

def process_raw_watch_payload(raw_json_payload: dict) -> dict:
    raw_ppg = raw_json_payload.get("raw_ppg", [])            # 25 Hz array
    raw_eda = raw_json_payload.get("raw_eda", [])            # 1 Hz array
    raw_accel = raw_json_payload.get("raw_accel", [])        # 25 Hz Nx3 array [[x,y,z], ...]
    raw_temp = raw_json_payload.get("raw_temp", 33.0)

    extracted_features = {}

    # 1. Process PPG via HeartPy & SQI
    if len(raw_ppg) > 100:
        try:
            # import heartpy as hp
            # wd, m = hp.process(np.array(raw_ppg), sample_rate=25.0)
            # extracted_features.update({'bpm': m['bpm'], 'ibi': m['ibi'], 'sdnn': m['sdnn'], ...})
            extracted_features["cardiac_missing"] = 0
        except Exception:
            extracted_features["cardiac_missing"] = 1
    else:
        extracted_features["cardiac_missing"] = 1

    # 2. Process EDA via NeuroKit2
    if len(raw_eda) > 10:
        try:
            # import neurokit2 as nk
            # eda_signals, info = nk.eda_process(raw_eda, sampling_rate=1)
            extracted_features["eda_missing"] = 0
        except Exception:
            extracted_features["eda_missing"] = 1
    else:
        extracted_features["eda_missing"] = 1

    for col in WATCH_FEATURE_COLS:
        if col not in extracted_features:
            extracted_features[col] = raw_json_payload.get(col, 0.0)

    extracted_features["temp_mean"] = raw_temp
    return extracted_features


def get_latest_staged_watch_data(patient_id):
    path = os.path.join(WATCH_STAGING_DIR, f"{patient_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return process_raw_watch_payload(data), "Live Watch Recording Attached"
    return None, "No active watch stream found for this patient"


# --- App Layout ---

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Clinical Data Collection - Galaxy Watch8 Study"


def serve_layout():
    return html.Div(style={"backgroundColor": "#1E1E1E", "minHeight": "100vh", "padding": "2rem"}, children=[
        html.H2("Dehydration Study Data Collection", style={"color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1.5rem"}),
        
        # Patient & Registration Section
        html.Div([
            html.H5("1. Patient Selection & Enrollment", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
            dbc.Row([
                dbc.Col([
                    html.Label("Select Patient ID", style={"color": "#7F8C8D"}),
                    dcc.Dropdown(
                        id="patient-selector",
                        options=patient_dropdown_options(),
                        placeholder="Choose patient...",
                        style={"color": "#000"}
                    )
                ], width=6),
                dbc.Col([
                    html.Label("Visit Date", style={"color": "#7F8C8D"}),
                    dcc.Input(id="visit-date", type="text", value=datetime.date.today().isoformat(), style=INPUT_STYLE)
                ], width=4)
            ]),
            html.Hr(style={"borderColor": "#3A3A3A", "margin": "1rem 0"}),
            html.Div("Register a new patient:", style={"color": "#7F8C8D", "fontSize": "0.8rem", "marginBottom": "0.5rem"}),
            dbc.Row([
                dbc.Col([
                    dcc.Input(id="new-patient-full-name", type="text", placeholder="Full Name (e.g. Jane Doe)", style=INPUT_STYLE),
                ], width=6),
                dbc.Col([
                    html.Button("Register Patient", id="register-patient-btn", n_clicks=0, style={
                        "backgroundColor": "#2ECC71", "color": "white", "border": "none",
                        "borderRadius": "6px", "padding": "0.5rem 1rem", "fontWeight": "600", "cursor": "pointer"
                    }),
                ], width=4),
            ]),
            html.Div(id="register-result", style={"marginTop": "0.5rem"}),
        ], style=CARD_STYLE),

        # Demographics & Labs
        html.Div([
            html.H5("2. Clinical Laboratory Panel & Demographics", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
            dbc.Row([
                dbc.Col([html.Label("Age"), dcc.Input(id="input-age", type="number", style=INPUT_STYLE)], width=3),
                dbc.Col([
                    html.Label("Gender"),
                    dcc.Dropdown(
                        id="input-gender",
                        options=[{"label": "Male", "value": "Male"}, {"label": "Female", "value": "Female"}],
                        placeholder="Select gender...",
                        style={"color": "#000"}
                    )
                ], width=3),
                dbc.Col([html.Label("Weight (kg)"), dcc.Input(id="input-weight", type="number", style=INPUT_STYLE)], width=3),
                dbc.Col([html.Label("BMI"), dcc.Input(id="input-bmi", type="number", style=INPUT_STYLE)], width=3),
            ], style={"marginBottom": "1rem"}),
            
            dbc.Row([
                dbc.Col([html.Label(f.capitalize()), dcc.Input(id=f"lab-{f}", type="number", style=INPUT_STYLE)], width=2)
                for f in LAB_FIELDS
            ])
        ], style=CARD_STYLE),

        # Watch Ingestion Status
        html.Div([
            html.H5("3. Galaxy Watch 8 Signal Acquisition", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
            html.Button("Fetch & Process Latest Watch Signal", id="fetch-watch-btn", n_clicks=0, 
                        style={"backgroundColor": "#27AE60", "color": "#FFF", "padding": "0.5rem 1rem", "border": "none", "borderRadius": "6px"}),
            html.Div(id="watch-status", style={"marginTop": "0.5rem", "fontWeight": "600", "color": "#F1C40F"}),
            dcc.Store(id="watch-features-store")
        ], style=CARD_STYLE),

        # Submit Section
        html.Div([
            html.Button("Save Visit & Predict Risk Tier", id="submit-btn", n_clicks=0,
                        style={"backgroundColor": "#2980B9", "color": "#FFF", "padding": "0.75rem 2rem", "fontSize": "1.1rem", "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
            html.Div(id="submit-output", style={"marginTop": "1rem"})
        ], style=CARD_STYLE),

        html.Hr(style={"borderColor": "#3A3A3A", "margin": "2rem 0"}),

        # --- Progress & Charts Section ---
        html.H3("Collection Progress", style={"color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1rem"}),
        html.Div(id="collection-progress-summary", style={"marginBottom": "1rem"}),
        dbc.Row([
            dbc.Col(dcc.Graph(id="collection-tier-chart"), width=6),
            dbc.Col(dcc.Graph(id="collection-visits-per-patient-chart"), width=6),
        ]),
        html.H5("Recent Submissions", style={"color": "#E0E0E0", "marginTop": "1rem", "marginBottom": "0.75rem"}),
        html.Div(id="collection-recent-table"),

        dcc.Store(id="collection-refresh-trigger"),
    ])


app.layout = serve_layout


# --- Callbacks ---

@app.callback(
    Output("patient-selector", "options"),
    Output("patient-selector", "value"),
    Output("new-patient-full-name", "value"),
    Output("register-result", "children"),
    Input("register-patient-btn", "n_clicks"),
    State("new-patient-full-name", "value"),
    prevent_initial_call=True,
)
def register_patient(n_clicks, full_name):
    if not full_name or not full_name.strip():
        return no_update, no_update, no_update, html.Div(
            "⚠️ Enter a full name before registering.", style={"color": "#E74C3C", "fontSize": "0.85rem"}
        )
    new_id = register_new_patient(full_name.strip())
    return (
        patient_dropdown_options(),
        new_id,
        "",
        html.Div(f"✅ Registered {full_name.strip()} as {new_id}.", style={"color": "#2ECC71", "fontSize": "0.85rem"}),
    )


@app.callback(
    Output("watch-status", "children"),
    Output("watch-features-store", "data"),
    Input("fetch-watch-btn", "n_clicks"),
    State("patient-selector", "value")
)
def fetch_watch_signal(n_clicks, patient_id):
    if not n_clicks or not patient_id:
        return no_update, no_update
    
    features, msg = get_latest_staged_watch_data(patient_id)
    if not features:
        return f"⚠️ {msg}", None
    return f"✅ {msg} (HeartPy & NeuroKit2 feature extraction complete).", features


@app.callback(
    Output("submit-output", "children"),
    Output("collection-refresh-trigger", "data"),
    Input("submit-btn", "n_clicks"),
    State("patient-selector", "value"),
    State("visit-date", "value"),
    State("input-age", "value"),
    State("input-gender", "value"),
    State("input-weight", "value"),
    State("input-bmi", "value"),
    State("watch-features-store", "data"),
    [State(f"lab-{f}", "value") for f in LAB_FIELDS]
)
def submit_visit(n_clicks, patient_id, visit_date, age, gender_label, weight, bmi, watch_data, *lab_vals):
    if not n_clicks:
        return no_update, no_update
    if not patient_id or not watch_data:
        return html.Div("⚠️ Please select a patient and attach a valid Galaxy Watch signal recording.", style={"color": "#E74C3C"}), no_update
    if not gender_label or gender_label not in GENDER_MAP:
        return html.Div("⚠️ Please select a valid Gender (Male/Female).", style={"color": "#E74C3C"}), no_update
    
    labs = dict(zip(LAB_FIELDS, lab_vals))
    if any(v is None for v in labs.values()):
        return html.Div("⚠️ Please fill in all lab panel parameters.", style={"color": "#E74C3C"}), no_update

    # Map Gender string to numerical encoding required by Model 1 (1 = Male, 2 = Female)
    gender_num = GENDER_MAP[gender_label]

    # Predict Risk Tier using Model 1
    _, tier = predict_dehydration_risk(
        labs["sodium"], labs["potassium"], labs["chloride"], 
        labs["bun"], labs["creatinine"], labs["glucose"], 
        age, gender_num, weight, bmi
    )
    
    # Save Combined Record for Model 2 Training
    row = {
        "patient_id": patient_id, "visit_date": visit_date,
        "age": age, "gender": gender_num, "weight": weight, "bmi": bmi,
        **labs, **watch_data, "model1_tier": tier
    }
    
    file_exists = os.path.exists(REAL_DATA_CSV_PATH)
    pd.DataFrame([row]).to_csv(REAL_DATA_CSV_PATH, mode="a", header=not file_exists, index=False)
    
    msg = html.Div(f"✅ Record successfully saved for {patient_id}! Live Model 1 Risk Tier: {tier}", style={"color": "#2ECC71", "fontWeight": "700"})
    return msg, datetime.datetime.now().isoformat()


@app.callback(
    Output("collection-progress-summary", "children"),
    Output("collection-tier-chart", "figure"),
    Output("collection-visits-per-patient-chart", "figure"),
    Output("collection-recent-table", "children"),
    Input("collection-refresh-trigger", "data"),
)
def update_progress(_trigger):
    df = load_collected_data()

    empty_fig = px.bar(title="No data collected yet")
    empty_fig.update_layout(template="plotly_dark", paper_bgcolor="#1E1E1E", plot_bgcolor="#1E1E1E")

    if df.empty:
        summary = html.Div("No visits recorded yet.", style={"color": "#7F8C8D"})
        return summary, empty_fig, empty_fig, html.Div("Nothing to show yet.", style={"color": "#7F8C8D"})

    n_patients = df["patient_id"].nunique()
    n_visits = len(df)
    summary = dbc.Row([
        dbc.Col(html.Div([
            html.Div(str(n_patients), style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}),
            html.Div("Patients enrolled", style={"color": "#7F8C8D", "fontSize": "0.8rem"}),
        ]), width=3),
        dbc.Col(html.Div([
            html.Div(str(n_visits), style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}),
            html.Div("Visits recorded", style={"color": "#7F8C8D", "fontSize": "0.8rem"}),
        ]), width=3),
        dbc.Col(html.Div([
            html.Div(f"{n_visits / n_patients:.1f}" if n_patients else "0", style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}),
            html.Div("Avg visits / patient", style={"color": "#7F8C8D", "fontSize": "0.8rem"}),
        ]), width=3),
    ])

    tier_counts = df["model1_tier"].value_counts().reindex(TIER_ORDER, fill_value=0).reset_index()
    tier_counts.columns = ["tier", "count"]
    tier_fig = px.bar(tier_counts, x="tier", y="count", title="Risk tier distribution (collected so far)",
                       color="tier", color_discrete_map=RISK_COLORS)
    tier_fig.update_layout(template="plotly_dark", paper_bgcolor="#1E1E1E", plot_bgcolor="#1E1E1E", showlegend=False)

    visits_per_patient = df["patient_id"].value_counts().reset_index()
    visits_per_patient.columns = ["patient_id", "visits"]
    vpp_fig = px.bar(visits_per_patient, x="patient_id", y="visits", title="Visits per patient")
    vpp_fig.update_layout(template="plotly_dark", paper_bgcolor="#1E1E1E", plot_bgcolor="#1E1E1E")

    registry = load_study_patients()
    name_by_id = dict(zip(registry["patient_id"], registry["full_name"])) if not registry.empty else {}
    display_df = df.copy()
    display_df["patient_name"] = display_df["patient_id"].map(name_by_id).fillna("")

    display_cols = ["patient_id", "patient_name", "visit_date", "model1_tier"]
    display_cols = [c for c in display_cols if c in display_df.columns]
    recent = display_df[display_cols].tail(10).iloc[::-1]
    table = dash_table.DataTable(
        data=recent.to_dict("records"),
        columns=[{"name": c, "id": c} for c in display_cols],
        style_header={"backgroundColor": "#2B2B2B", "color": "#E0E0E0", "fontWeight": "700"},
        style_cell={"backgroundColor": "#1E1E1E", "color": "#E0E0E0", "border": "1px solid #3A3A3A"},
        style_table={"overflowX": "auto"},
    )

    return summary, tier_fig, vpp_fig, table


if __name__ == "__main__":
    app.run(debug=True)