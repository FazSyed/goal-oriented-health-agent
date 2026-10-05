"""
Data Collection Dashboard (Galaxy Watch8 Ingestion)
===================================================
Dashboard for clinical partners to:
1. Register new patients or select existing patients.
2. Auto-populate existing patient demographics (Age, Gender, Weight, BMI).
3. Log lab panel values and upload Galaxy Watch raw CSV directly to Google Drive.
4. Predict dehydration risk tier and append structured record to Google Sheets.
"""

import os
import sys
import json
import base64
import io
import datetime
import traceback
import warnings
from pathlib import Path
from functools import lru_cache

# Suppress external library deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning, module="heartpy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

import dash
from dash import dcc, html, Input, Output, State, no_update, dash_table
import dash_bootstrap_components as dbc

import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

from backend import backend_service

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

LAB_FIELDS = [
    ("sodium", "Sodium"),
    ("potassium", "Potassium"),
    ("chloride", "Chloride"),
    ("bun", "Bun"),
    ("creatinine", "Creatinine"),
    ("glucose", "Glucose")
]

GENDER_MAP = {"Male": 1, "Female": 2}
RISK_COLORS = {"Euhydrated": "#2ECC71", "Mild": "#F1C40F", "Moderate": "#E67E22", "Severe": "#E74C3C", "Unknown": "#95A5A6"}
TIER_ORDER = ["Euhydrated", "Mild", "Moderate", "Severe"]

INPUT_STYLE = {
    "width": "100%",
    "backgroundColor": "#F8F9FA",
    "color": "#1E1E1E",
    "border": "1px solid #CED4DA",
    "borderRadius": "4px",
    "padding": "6px 12px",
    "height": "38px"
}
LABEL_STYLE = {"color": "#B0B0B0", "marginBottom": "4px", "fontSize": "0.9rem", "fontWeight": "500"}
CARD_STYLE = {"backgroundColor": "#2B2B2B", "borderRadius": "8px", "padding": "1.5rem", "marginBottom": "1.5rem"}

SPREADSHEET_KEY = os.getenv("GOOGLE_SHEET_ID", "").strip()
SPREADSHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Dehydration_Study_Visits").strip()


# --- Google Auth & Cached Data Helpers ---

def get_google_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "GOOGLE_CREDENTIALS_JSON" in os.environ and os.environ["GOOGLE_CREDENTIALS_JSON"].strip():
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
        return Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    local_creds_path = Path(__file__).resolve().parent.parent / "google_credentials.json"
    if not local_creds_path.exists():
        local_creds_path = Path("google_credentials.json")
        
    return Credentials.from_service_account_file(str(local_creds_path), scopes=scopes)


def get_gspread_client():
    creds = get_google_credentials()
    return gspread.authorize(creds)


def open_google_sheet(gc):
    if SPREADSHEET_KEY:
        return gc.open_by_key(SPREADSHEET_KEY).sheet1
    return gc.open(SPREADSHEET_NAME).sheet1


def open_patients_worksheet(gc):
    """Opens or creates the dedicated 'Patients' tab inside the Google Sheet (Case-Insensitive)."""
    sh = gc.open_by_key(SPREADSHEET_KEY) if SPREADSHEET_KEY else gc.open(SPREADSHEET_NAME)
    worksheets = sh.worksheets()
    for ws in worksheets:
        if ws.title.strip().lower() == "patients":
            return ws
    
    ws = sh.add_worksheet(title="Patients", rows=100, cols=5)
    ws.append_row(["patient_id", "patient_name", "registered_date"])
    return ws


# --- API Rate Limit Mitigation (Cached Reads) ---

@lru_cache(maxsize=16)
def _fetch_registered_patients_cached(cache_key: str) -> str:
    """Internal cached reader converting records to JSON string representation."""
    gc = get_gspread_client()
    ws = open_patients_worksheet(gc)
    records = ws.get_all_records()
    return json.dumps(records)


def load_registered_patients_from_sheet() -> pd.DataFrame:
    try:
        # Use a minute-level cache key to auto-refresh every minute at most
        cache_key = f"patients_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
        raw_json = _fetch_registered_patients_cached(cache_key)
        records = json.loads(raw_json)
        return pd.DataFrame(records)
    except Exception as e:
        print(f"[Patients Sheet Load Detail]: {e}")
        return pd.DataFrame()


def clear_patient_cache():
    _fetch_registered_patients_cached.cache_clear()


@lru_cache(maxsize=16)
def _fetch_visits_cached(cache_key: str) -> str:
    """Internal cached reader for visits data."""
    gc = get_gspread_client()
    sh = open_google_sheet(gc)
    records = sh.get_all_records()
    return json.dumps(records)


def load_visits_from_google_sheet() -> pd.DataFrame:
    try:
        cache_key = f"visits_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
        raw_json = _fetch_visits_cached(cache_key)
        records = json.loads(raw_json)
        return pd.DataFrame(records)
    except Exception as e:
        print(f"[Google Sheets Fetch Detail]: Raw error -> {repr(e)}")
        return pd.DataFrame()


def clear_visit_cache():
    _fetch_visits_cached.cache_clear()


def register_new_patient_to_sheet(patient_id: str, patient_name: str):
    gc = get_gspread_client()
    ws = open_patients_worksheet(gc)
    ws.append_row([patient_id, patient_name, datetime.date.today().isoformat()])
    clear_patient_cache()


def append_visit_to_google_sheet(record_data: dict):
    gc = get_gspread_client()
    sh = open_google_sheet(gc)
    
    row = [
        record_data.get("patient_id", ""),
        record_data.get("patient_name", ""),
        record_data.get("visit_date", ""),
        record_data.get("age", ""),
        record_data.get("gender", ""),
        record_data.get("weight", ""),
        record_data.get("bmi", ""),
        record_data.get("sodium", ""),
        record_data.get("potassium", ""),
        record_data.get("chloride", ""),
        record_data.get("bun", ""),
        record_data.get("creatinine", ""),
        record_data.get("glucose", ""),
        record_data.get("model1_risk", ""),
        record_data.get("inferred_action", ""),
        record_data.get("drive_file_id", "None"),
        record_data.get("timestamp", "")
    ]
    sh.append_row(row)
    clear_visit_cache()


def upload_signal_to_google_drive(file_contents: str, filename: str, patient_id: str) -> str:
    try:
        creds = get_google_credentials()
        drive_service = build("drive", "v3", credentials=creds)
        
        content_type, content_string = file_contents.split(",")
        decoded = base64.b64decode(content_string)
        
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        file_metadata = {
            "name": f"{patient_id}_{datetime.date.today().isoformat()}_{filename}",
            "parents": [folder_id] if folder_id else []
        }
        
        media = MediaIoBaseUpload(io.BytesIO(decoded), mimetype="text/csv", resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id, name"
        ).execute()
        
        return uploaded_file.get("id", "")
    except Exception as e:
        print(f"Google Drive Upload Error: {e}")
        return ""


def generate_next_patient_id(existing_df: pd.DataFrame) -> str:
    if existing_df.empty or "patient_id" not in existing_df.columns:
        return "P001"
    nums = existing_df["patient_id"].astype(str).str.extract(r"P(\d+)")[0].dropna().astype(int)
    next_n = (nums.max() + 1) if not nums.empty else 1
    return f"P{next_n:03d}"


def create_empty_dark_figure(title_text: str) -> go.Figure:
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
            "xref": "paper", "yref": "paper",
            "showarrow": False, "font": {"size": 14, "color": "#7F8C8D"}
        }]
    )
    return fig


# --- App Layout ---

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server
app.title = "Clinical Data Collection - Galaxy Watch8 Study"

def serve_layout():
    return html.Div(style={"backgroundColor": "#1E1E1E", "minHeight": "100vh", "padding": "2rem"}, children=[
        
        # Section 1: Patient Selection & Enrollment
        html.Div([
            html.H4("1. Patient Selection & Enrollment", style={"color": "#E0E0E0", "fontWeight": "400", "marginBottom": "1.25rem"}),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Label("Select Patient ID", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="patient-selector",
                            options=[{"label": "Choose patient...", "value": "NEW_PATIENT"}],
                            value="NEW_PATIENT",
                            clearable=False,
                            placeholder="Choose patient...",
                            style={"color": "#000"}
                        )
                    ], style={"marginBottom": "1.25rem"}),
                    html.Div([
                        html.Label("Register a new patient:", style={"color": "#7F8C8D", "fontSize": "0.85rem", "marginBottom": "4px"}),
                        dcc.Input(id="patient-name-input", type="text", placeholder="Full Name (e.g. Jane Doe)", style=INPUT_STYLE)
                    ])
                ], width=6),
                
                dbc.Col([
                    html.Div([
                        html.Label("Visit Date", style=LABEL_STYLE),
                        dcc.Input(id="visit-date", type="text", value=datetime.date.today().isoformat(), style=INPUT_STYLE)
                    ], style={"marginBottom": "1.25rem"}),
                    html.Div([
                        html.Button(
                            "Register Patient", id="register-btn", n_clicks=0,
                            style={
                                "backgroundColor": "#2ECC71",
                                "color": "#FFF",
                                "fontWeight": "600",
                                "padding": "7px 20px",
                                "border": "none",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "marginTop": "24px"
                            }
                        ),
                        html.Div(id="register-output", style={"marginTop": "8px"})
                    ])
                ], width=6)
            ])
        ], style=CARD_STYLE),

        # Section 2: Clinical Laboratory Panel & Demographics
        html.Div([
            html.H4("2. Clinical Laboratory Panel & Demographics", style={"color": "#E0E0E0", "fontWeight": "400", "marginBottom": "1.25rem"}),
            
            dbc.Row([
                dbc.Col([
                    html.Label("Age", style=LABEL_STYLE),
                    dcc.Input(id="input-age", type="number", style=INPUT_STYLE)
                ], width=3),
                dbc.Col([
                    html.Label("Gender", style=LABEL_STYLE),
                    dcc.Dropdown(
                        id="input-gender",
                        options=[{"label": "Male", "value": "Male"}, {"label": "Female", "value": "Female"}],
                        placeholder="Select gender...",
                        style={"color": "#000"}
                    )
                ], width=3),
                dbc.Col([
                    html.Label("Weight (kg)", style=LABEL_STYLE),
                    dcc.Input(id="input-weight", type="number", style=INPUT_STYLE)
                ], width=3),
                dbc.Col([
                    html.Label("BMI", style=LABEL_STYLE),
                    dcc.Input(id="input-bmi", type="number", style=INPUT_STYLE)
                ], width=3),
            ], style={"marginBottom": "1.25rem"}),
            
            dbc.Row([
                dbc.Col([
                    html.Label(label_text, style=LABEL_STYLE),
                    dcc.Input(id=f"lab-{field_key}", type="number", style=INPUT_STYLE)
                ], width=2)
                for field_key, label_text in LAB_FIELDS
            ])
        ], style=CARD_STYLE),

        # Section 3: Galaxy Watch Signal Upload
        html.Div([
            html.H4("3. Galaxy Watch 8 Raw Telemetry Upload (.csv)", style={"color": "#E0E0E0", "fontWeight": "400", "marginBottom": "0.75rem"}),
            dcc.Upload(
                id="upload-watch-signal",
                children=html.Div(["Drag and Drop or ", html.A("Select Raw Watch Signal CSV File")]),
                style={
                    "width": "100%", "height": "60px", "lineHeight": "60px",
                    "borderWidth": "1px", "borderStyle": "dashed", "borderRadius": "5px",
                    "textAlign": "center", "margin": "10px 0", "color": "#E0E0E0"
                },
                multiple=False
            ),
            html.Div(id="uploaded-filename", style={"color": "#2ECC71", "fontWeight": "600"})
        ], style=CARD_STYLE),

        # Section 4: Submit & Save
        html.Div([
            html.Button("Save Visit & Submit Telemetry", id="submit-btn", n_clicks=0,
                        style={"backgroundColor": "#2980B9", "color": "#FFF", "padding": "0.75rem 2rem", "fontSize": "1.1rem", "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
            html.Div(id="submit-output", style={"marginTop": "1rem"})
        ], style=CARD_STYLE),

        html.Hr(style={"borderColor": "#3A3A3A", "margin": "2rem 0"}),

        # Collection Progress Dashboard
        html.H3("Collection Progress", style={"color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1rem"}),
        html.Div(id="collection-progress-summary", style={"marginBottom": "1rem"}),
        dbc.Row([
            dbc.Col(dcc.Graph(id="collection-tier-chart", figure=create_empty_dark_figure("Risk tier distribution")), width=6),
            dbc.Col(dcc.Graph(id="collection-visits-per-patient-chart", figure=create_empty_dark_figure("Visits per patient")), width=6),
        ]),
        html.H5("Recent Submissions", style={"color": "#E0E0E0", "marginTop": "1rem", "marginBottom": "0.75rem"}),
        html.Div(id="collection-recent-table"),

        # Relaxed interval to 30,000ms (30 seconds) to conserve Google Sheets API rate limits
        dcc.Interval(id="collection-refresh-interval", interval=30000, n_intervals=0),
        dcc.Store(id="collection-refresh-trigger", data=datetime.datetime.now().isoformat()),
    ])

app.layout = serve_layout


# --- Callbacks ---

@app.callback(
    Output("patient-selector", "options"),
    Input("collection-refresh-trigger", "data")
)
def update_patient_dropdown(_trigger):
    df_patients = load_registered_patients_from_sheet()
    options = [{"label": "Choose patient...", "value": "NEW_PATIENT"}]
    
    if not df_patients.empty and "patient_id" in df_patients.columns:
        for _, row in df_patients.iterrows():
            pid = str(row.get("patient_id", "")).strip()
            pname = str(row.get("patient_name", "")).strip()
            if pid:
                label = f"{pid} - {pname}" if pname else pid
                options.append({"label": label, "value": pid})
    else:
        df_visits = load_visits_from_google_sheet()
        if not df_visits.empty and "patient_id" in df_visits.columns:
            for _, row in df_visits.drop_duplicates(subset=["patient_id"]).iterrows():
                pid = str(row.get("patient_id", "")).strip()
                pname = str(row.get("patient_name", "")).strip()
                if pid:
                    options.append({"label": f"{pid} - {pname}" if pname else pid, "value": pid})
                    
    return options


@app.callback(
    Output("register-output", "children"),
    Output("patient-selector", "options", allow_duplicate=True),
    Output("patient-selector", "value"),
    Output("collection-refresh-trigger", "data", allow_duplicate=True),
    Input("register-btn", "n_clicks"),
    State("patient-name-input", "value"),
    prevent_initial_call=True
)
def register_patient_only(n_clicks, patient_name):
    if not n_clicks or not patient_name:
        return html.Div("⚠️ Please enter a Full Name to register a new patient.", style={"color": "#E74C3C", "fontSize": "0.85rem"}), no_update, no_update, no_update

    existing_patients_df = load_registered_patients_from_sheet()
    
    if not existing_patients_df.empty and "patient_name" in existing_patients_df.columns:
        if patient_name.strip().lower() in existing_patients_df["patient_name"].astype(str).str.strip().str.lower().values:
            return html.Div(f"⚠️ Patient '{patient_name}' is already registered.", style={"color": "#F1C40F", "fontSize": "0.85rem"}), no_update, no_update, no_update

    new_id = generate_next_patient_id(existing_patients_df)
    register_new_patient_to_sheet(new_id, patient_name.strip())

    updated_df = load_registered_patients_from_sheet()
    updated_options = [{"label": "Choose patient...", "value": "NEW_PATIENT"}]
    if not updated_df.empty and "patient_id" in updated_df.columns:
        for _, row in updated_df.iterrows():
            pid = str(row.get("patient_id", "")).strip()
            pname = str(row.get("patient_name", "")).strip()
            if pid:
                updated_options.append({"label": f"{pid} - {pname}" if pname else pid, "value": pid})

    msg = html.Div(f"✅ Registered {patient_name.strip()} as {new_id}.", style={"color": "#2ECC71", "fontSize": "0.85rem", "fontWeight": "600"})
    
    return msg, updated_options, new_id, datetime.datetime.now().isoformat()


@app.callback(
    Output("patient-name-input", "value"),
    Output("input-age", "value"),
    Output("input-gender", "value"),
    Output("input-weight", "value"),
    Output("input-bmi", "value"),
    Output("patient-name-input", "disabled"),
    Input("patient-selector", "value")
)
def handle_patient_selection(selected_pid):
    if not selected_pid or selected_pid == "NEW_PATIENT":
        return "", None, None, None, None, False

    df_patients = load_registered_patients_from_sheet()
    patient_name = ""
    if not df_patients.empty and "patient_id" in df_patients.columns:
        match = df_patients[df_patients["patient_id"].astype(str) == str(selected_pid)]
        if not match.empty:
            patient_name = str(match.iloc[-1].get("patient_name", ""))

    df_visits = load_visits_from_google_sheet()
    if not df_visits.empty and "patient_id" in df_visits.columns:
        df_visits["patient_id"] = df_visits["patient_id"].astype(str)
        p_data = df_visits[df_visits["patient_id"] == str(selected_pid)]
        if not p_data.empty:
            last_record = p_data.iloc[-1]
            return (
                patient_name or str(last_record.get("patient_name", "")),
                last_record.get("age"),
                last_record.get("gender"),
                last_record.get("weight"),
                last_record.get("bmi"),
                True
            )

    return patient_name, None, None, None, None, True


@app.callback(
    Output("uploaded-filename", "children"),
    Input("upload-watch-signal", "filename")
)
def update_upload_label(filename):
    if filename:
        return f"📁 Attached CSV: {filename}"
    return ""


@app.callback(
    Output("submit-output", "children"),
    Output("collection-refresh-trigger", "data", allow_duplicate=True),
    Input("submit-btn", "n_clicks"),
    State("patient-selector", "value"),
    State("patient-name-input", "value"),
    State("visit-date", "value"),
    State("input-age", "value"),
    State("input-gender", "value"),
    State("input-weight", "value"),
    State("input-bmi", "value"),
    State("upload-watch-signal", "contents"),
    State("upload-watch-signal", "filename"),
    [State(f"lab-{k}", "value") for k, _ in LAB_FIELDS],
    prevent_initial_call=True
)
def submit_visit(n_clicks, selected_pid, patient_name, visit_date, age, gender_label, weight, bmi, watch_file_contents, watch_filename, *lab_vals):
    if not n_clicks:
        return no_update, no_update
    
    df_patients = load_registered_patients_from_sheet()
    patient_id = selected_pid if (selected_pid and selected_pid != "NEW_PATIENT") else generate_next_patient_id(df_patients)

    if not patient_name:
        return html.Div("⚠️ Please enter a Patient Name.", style={"color": "#E74C3C"}), no_update
    if not gender_label or gender_label not in GENDER_MAP:
        return html.Div("⚠️ Please select a valid Gender.", style={"color": "#E74C3C"}), no_update
    
    labs = dict(zip([k for k, _ in LAB_FIELDS], lab_vals))
    if any(v is None for v in labs.values()) or any(v is None for v in [age, weight, bmi]):
        return html.Div("⚠️ Please fill in all lab panel and demographic fields.", style={"color": "#E74C3C"}), no_update

    gender_num = GENDER_MAP[gender_label]
    demographics = {"age": float(age), "gender": gender_num, "weight": float(weight), "bmi": float(bmi)}
    formatted_labs = {k: float(v) for k, v in labs.items()}

    try:
        drive_file_id = ""
        if watch_file_contents and watch_filename:
            drive_file_id = upload_signal_to_google_drive(watch_file_contents, watch_filename, str(patient_id))

        raw_response = backend_service.process_full_clinical_visit(
            patient_id=str(patient_id),
            labs=formatted_labs,
            demographics=demographics,
            raw_watch_data={"drive_file_id": drive_file_id}
        )

        if hasattr(raw_response, "json"):
            try:
                res_dict = raw_response.json()
            except Exception:
                res_dict = {}
            is_success = getattr(raw_response, "ok", False) or res_dict.get("status") == "success"
        elif isinstance(raw_response, dict):
            res_dict = raw_response
            is_success = res_dict.get("status") == "success" or "status" not in res_dict
        else:
            res_dict = {}
            is_success = False

        if is_success:
            record = res_dict.get("record") if isinstance(res_dict.get("record"), dict) else {}
            risk = record.get("model1_risk") or res_dict.get("model1_risk") or res_dict.get("risk") or "Unknown"
            action = res_dict.get("inferred_action") or record.get("inferred_action") or "None"

            record_data = {
                "patient_id": str(patient_id),
                "patient_name": str(patient_name),
                "visit_date": str(visit_date),
                "age": float(age),
                "gender": gender_label,
                "weight": float(weight),
                "bmi": float(bmi),
                "sodium": formatted_labs.get("sodium", ""),
                "potassium": formatted_labs.get("potassium", ""),
                "chloride": formatted_labs.get("chloride", ""),
                "bun": formatted_labs.get("bun", ""),
                "creatinine": formatted_labs.get("creatinine", ""),
                "glucose": formatted_labs.get("glucose", ""),
                "model1_risk": risk,
                "inferred_action": action,
                "drive_file_id": drive_file_id if drive_file_id else "None",
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            append_visit_to_google_sheet(record_data)

            msg = html.Div(f"✅ Visit Logged for {patient_name} ({patient_id})! Live Risk Tier: {risk}", style={"color": "#2ECC71", "fontWeight": "700"})
            return msg, datetime.datetime.now().isoformat()
        else:
            err_detail = res_dict.get("error") or res_dict.get("message") or "Failed to process visit record in backend."
            return html.Div(f"❌ Backend Error: {err_detail}", style={"color": "#E74C3C"}), no_update

    except Exception as e:
        print(f"[Backend Exception Traceback]:\n{traceback.format_exc()}")
        return html.Div(f"❌ Execution Error: {type(e).__name__} - {str(e)}", style={"color": "#E74C3C"}), no_update


@app.callback(
    Output("collection-progress-summary", "children"),
    Output("collection-tier-chart", "figure"),
    Output("collection-visits-per-patient-chart", "figure"),
    Output("collection-recent-table", "children"),
    Input("collection-refresh-interval", "n_intervals"),
    Input("collection-refresh-trigger", "data"),
)
def update_progress(_n_intervals, _trigger):
    df = load_visits_from_google_sheet()

    if df.empty:
        return html.Div("No visits recorded yet.", style={"color": "#7F8C8D"}), create_empty_dark_figure("Risk tier distribution"), create_empty_dark_figure("Visits per patient"), html.Div("Nothing to show yet.", style={"color": "#7F8C8D"})

    tier_col = next((c for c in ["model1_risk", "model1_tier", "risk"] if c in df.columns), None)
    patient_col = "patient_id" if "patient_id" in df.columns else df.columns[0]

    n_patients = df[patient_col].nunique()
    n_visits = len(df)
    summary = dbc.Row([
        dbc.Col(html.Div([html.Div(str(n_patients), style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}), html.Div("Patients enrolled", style={"color": "#7F8C8D", "fontSize": "0.8rem"})]), width=4),
        dbc.Col(html.Div([html.Div(str(n_visits), style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}), html.Div("Visits recorded", style={"color": "#7F8C8D", "fontSize": "0.8rem"})]), width=4),
        dbc.Col(html.Div([html.Div(f"{n_visits / n_patients:.1f}" if n_patients else "0", style={"fontSize": "2rem", "fontWeight": "700", "color": "#3498DB"}), html.Div("Avg visits / patient", style={"color": "#7F8C8D", "fontSize": "0.8rem"})]), width=4),
    ])

    tier_counts = df[tier_col].value_counts().reindex(TIER_ORDER, fill_value=0).reset_index() if tier_col else pd.DataFrame({"tier": TIER_ORDER, "count": [0]*4})
    tier_counts.columns = ["tier", "count"]
    
    tier_fig = px.bar(tier_counts, x="tier", y="count", title="Risk tier distribution", color="tier", color_discrete_map=RISK_COLORS)
    tier_fig.update_layout(template="plotly_dark", paper_bgcolor="#2B2B2B", plot_bgcolor="#2B2B2B", showlegend=False)

    visits_per_patient = df[patient_col].value_counts().reset_index()
    visits_per_patient.columns = ["patient_id", "visits"]
    vpp_fig = px.bar(visits_per_patient, x="patient_id", y="visits", title="Visits per patient")
    vpp_fig.update_layout(template="plotly_dark", paper_bgcolor="#2B2B2B", plot_bgcolor="#2B2B2B")

    recent = df.tail(10).iloc[::-1]
    table = dash_table.DataTable(
        data=recent.to_dict("records"),
        columns=[{"name": str(c), "id": str(c)} for c in df.columns[:7]],
        style_header={"backgroundColor": "#2B2B2B", "color": "#E0E0E0", "fontWeight": "700"},
        style_cell={"backgroundColor": "#1E1E1E", "color": "#E0E0E0", "border": "1px solid #3A3A3A"},
        style_table={"overflowX": "auto"},
    )

    return summary, tier_fig, vpp_fig, table


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)