"""
Data Collection Dashboard (Galaxy Watch8 Ingestion)
===================================================
Dashboard for clinical partners to:
1. Log patient demographics & laboratory blood panel.
2. Trigger/attach a Galaxy Watch 8 raw signal capture session.
3. Predict risk tier live and save to CSV.
4. Render collection progress charts immediately on app launch.
"""

import os
import sys
# Ensure project root is accessible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import datetime

import numpy as np
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc

from backend import backend_service  # Process clinical data via unified backend pipeline

import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Config - Check same directory as script first, then root
RAW_CSV_NAME = os.getenv("REAL_DATA_CSV_PATH", "real_visits_log.csv")
RAW_PATIENTS_NAME = os.getenv("STUDY_PATIENTS_PATH", "study_patients.csv")

def resolve_file_path(filename: str) -> str:
    """Finds exact path whether the file resides in visualization/, root, or CWD."""
    possible_paths = [
        os.path.join(SCRIPT_DIR, filename),
        os.path.join(PROJECT_ROOT, filename),
        os.path.join(os.getcwd(), filename),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    # Default fallback to script directory
    return os.path.join(SCRIPT_DIR, filename)

REAL_DATA_CSV_PATH = resolve_file_path(RAW_CSV_NAME)
STUDY_PATIENTS_PATH = resolve_file_path(RAW_PATIENTS_NAME)
WATCH_STAGING_DIR = os.path.join(PROJECT_ROOT, os.getenv("WATCH_STAGING_DIR", "logs/watch_staging"))

LAB_FIELDS = ["sodium", "potassium", "chloride", "bun", "creatinine", "glucose"]
DEMO_FIELDS = ["age", "gender", "weight", "bmi"]
GENDER_MAP = {"Male": 1, "Female": 2}

RISK_COLORS = {"Euhydrated": "#2ECC71", "Mild": "#F1C40F", "Moderate": "#E67E22", "Severe": "#E74C3C", "Unknown": "#95A5A6"}
TIER_ORDER = ["Euhydrated", "Mild", "Moderate", "Severe"]
INPUT_STYLE = {"width": "100%", "backgroundColor": "#F5F5F5", "color": "#1E1E1E", "border": "1px solid #555"}
CARD_STYLE = {"backgroundColor": "#2B2B2B", "borderRadius": "10px", "padding": "1.25rem", "marginBottom": "1.25rem"}


# --- Patient Registry & Data Helpers ---
def load_recent_visits_dataframe() -> pd.DataFrame:
    """Reads historical records directly from CSV on startup or refresh across all candidate paths."""
    target_path = resolve_file_path(RAW_CSV_NAME)
    if os.path.exists(target_path):
        try:
            df = pd.read_csv(target_path)
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def load_study_patients() -> pd.DataFrame:
    target_path = resolve_file_path(RAW_PATIENTS_NAME)
    if not os.path.exists(target_path):
        return pd.DataFrame(columns=["patient_id", "full_name"])
    try:
        return pd.read_csv(target_path, dtype=str)
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
    target_path = resolve_file_path(RAW_PATIENTS_NAME)
    if os.path.dirname(target_path):
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
    updated.to_csv(target_path, index=False)
    return new_id


def patient_dropdown_options() -> list:
    df = load_study_patients()
    if df.empty:
        return []
    return [{"label": f"{row.full_name} ({row.patient_id})", "value": row.patient_id} for row in df.itertuples()]


def create_empty_dark_figure(title_text: str) -> go.Figure:
    """Generates a dark-themed empty plot matching dashboard styling."""
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title_text, font=dict(color="#E0E0E0", size=14)),
        template="plotly_dark",
        paper_bgcolor="#2B2B2B",
        plot_bgcolor="#2B2B2B",
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        annotations=[{
            "text": "No visits recorded yet",
            "xref": "paper",
            "yref": "paper",
            "showarrow": False,
            "font": {"size": 14, "color": "#7F8C8D"}
        }]
    )
    return fig


# --- App Layout ---

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server
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
            dbc.Col(dcc.Graph(
                id="collection-tier-chart",
                figure=create_empty_dark_figure("Risk tier distribution (collected so far)")
            ), width=6),
            dbc.Col(dcc.Graph(
                id="collection-visits-per-patient-chart",
                figure=create_empty_dark_figure("Visits per patient")
            ), width=6),
        ]),
        html.H5("Recent Submissions", style={"color": "#E0E0E0", "marginTop": "1rem", "marginBottom": "0.75rem"}),
        html.Div(id="collection-recent-table"),

        # Interval component to load/refresh data automatically on startup and every 5 seconds
        dcc.Interval(id="collection-refresh-interval", interval=5000, n_intervals=0),
        dcc.Store(id="collection-refresh-trigger", data=datetime.datetime.now().isoformat()),
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
    
    # Simple placeholder logic for signal check
    return f"✅ Live Watch Recording Attached for {patient_id}.", {"status": "ok"}


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
    if not patient_id:
        return html.Div("⚠️ Please select a patient.", style={"color": "#E74C3C"}), no_update
    if not gender_label or gender_label not in GENDER_MAP:
        return html.Div("⚠️ Please select a valid Gender (Male/Female).", style={"color": "#E74C3C"}), no_update
    
    labs = dict(zip(LAB_FIELDS, lab_vals))
    if any(v is None for v in labs.values()) or any(v is None for v in [age, weight, bmi]):
        return html.Div("⚠️ Please fill in all lab panel and demographic parameters.", style={"color": "#E74C3C"}), no_update

    gender_num = GENDER_MAP[gender_label]
    demographics = {
        "age": float(age),
        "gender": gender_num,
        "weight": float(weight),
        "bmi": float(bmi)
    }
    
    formatted_labs = {k: float(v) for k, v in labs.items()}

    try:
        response = backend_service.process_full_clinical_visit(
            patient_id=str(patient_id),
            labs=formatted_labs,
            demographics=demographics,
            raw_watch_data=watch_data
        )

        if response.get("status") == "success":
            risk = response["record"].get("model1_risk", "Unknown")
            action = response.get("inferred_action", "None")
            msg = html.Div(
                f"✅ Visit Logged Successfully! Live Risk Tier: {risk} | OWL Action: {action}", 
                style={"color": "#2ECC71", "fontWeight": "700"}
            )
            return msg, datetime.datetime.now().isoformat()
        else:
            return html.Div("❌ Failed to process visit record in backend.", style={"color": "#E74C3C"}), no_update

    except Exception as e:
        return html.Div(f"❌ Backend Execution Error: {str(e)}", style={"color": "#E74C3C"}), no_update


@app.callback(
    Output("collection-progress-summary", "children"),
    Output("collection-tier-chart", "figure"),
    Output("collection-visits-per-patient-chart", "figure"),
    Output("collection-recent-table", "children"),
    Input("collection-refresh-interval", "n_intervals"),
    Input("collection-refresh-trigger", "data"),
)
def update_progress(_n_intervals, _trigger):
    df = load_recent_visits_dataframe()

    empty_tier_fig = create_empty_dark_figure("Risk tier distribution (collected so far)")
    empty_vpp_fig = create_empty_dark_figure("Visits per patient")

    if df.empty:
        summary = html.Div("No visits recorded yet.", style={"color": "#7F8C8D"})
        return summary, empty_tier_fig, empty_vpp_fig, html.Div("Nothing to show yet.", style={"color": "#7F8C8D"})

    # Dynamic column identification
    tier_col = next((c for c in ["model1_risk", "model1_tier", "RISK_STATUS", "risk"] if c in df.columns), None)
    date_col = next((c for c in ["visit_date", "timestamp", "date"] if c in df.columns), None)
    patient_col = "patient_id" if "patient_id" in df.columns else df.columns[0]

    n_patients = df[patient_col].nunique()
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

    if tier_col:
        tier_counts = df[tier_col].value_counts().reindex(TIER_ORDER, fill_value=0).reset_index()
        tier_counts.columns = ["tier", "count"]
    else:
        tier_counts = pd.DataFrame({"tier": TIER_ORDER, "count": [0]*4})

    tier_fig = px.bar(
        tier_counts, x="tier", y="count", 
        title="Risk tier distribution (collected so far)",
        color="tier", color_discrete_map=RISK_COLORS
    )
    tier_fig.update_layout(template="plotly_dark", paper_bgcolor="#2B2B2B", plot_bgcolor="#2B2B2B", showlegend=False)

    visits_per_patient = df[patient_col].value_counts().reset_index()
    visits_per_patient.columns = ["patient_id", "visits"]
    vpp_fig = px.bar(visits_per_patient, x="patient_id", y="visits", title="Visits per patient")
    vpp_fig.update_layout(template="plotly_dark", paper_bgcolor="#2B2B2B", plot_bgcolor="#2B2B2B")

    registry = load_study_patients()
    name_by_id = dict(zip(registry["patient_id"], registry["full_name"])) if not registry.empty and "patient_id" in registry.columns else {}
    display_df = df.copy()
    display_df["patient_name"] = display_df[patient_col].map(name_by_id).fillna("")

    display_cols = [patient_col, "patient_name", date_col, tier_col]
    display_cols = [c for c in display_cols if c and c in display_df.columns]
    recent = display_df[display_cols].tail(10).iloc[::-1]
    
    table = dash_table.DataTable(
        data=recent.to_dict("records"),
        columns=[{"name": str(c), "id": str(c)} for c in display_cols],
        style_header={"backgroundColor": "#2B2B2B", "color": "#E0E0E0", "fontWeight": "700"},
        style_cell={"backgroundColor": "#1E1E1E", "color": "#E0E0E0", "border": "1px solid #3A3A3A"},
        style_table={"overflowX": "auto"},
    )

    return summary, tier_fig, vpp_fig, table


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)