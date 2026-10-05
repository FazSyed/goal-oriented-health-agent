"""
Data Collection Dashboard (Galaxy Watch8 Ingestion)
===================================================
Dashboard for clinical partners to:
1. Register new patients or select existing patients from Google Sheets.
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

# Suppress known external library deprecation warnings (e.g., heartpy / pkg_resources)
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

load_dotenv()

LAB_FIELDS = ["sodium", "potassium", "chloride", "bun", "creatinine", "glucose"]
GENDER_MAP = {"Male": 1, "Female": 2}
RISK_COLORS = {"Euhydrated": "#2ECC71", "Mild": "#F1C40F", "Moderate": "#E67E22", "Severe": "#E74C3C", "Unknown": "#95A5A6"}
TIER_ORDER = ["Euhydrated", "Mild", "Moderate", "Severe"]

INPUT_STYLE = {"width": "100%", "backgroundColor": "#F5F5F5", "color": "#1E1E1E", "border": "1px solid #555"}
CARD_STYLE = {"backgroundColor": "#2B2B2B", "borderRadius": "10px", "padding": "1.25rem", "marginBottom": "1.25rem"}

SPREADSHEET_KEY = os.getenv("GOOGLE_SHEET_ID", "")
SPREADSHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Dehydration_Study_Visits")


# --- Auth & Data Helpers ---

def get_google_credentials():
    """Retrieves Google Service Account credentials from env var or local JSON file."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file"
    ]
    if "GOOGLE_CREDENTIALS_JSON" in os.environ:
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
        return Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        return Credentials.from_service_account_file("google_credentials.json", scopes=scopes)


def get_gspread_client():
    creds = get_google_credentials()
    return gspread.authorize(creds)


def open_google_sheet(gc):
    """Helper to open spreadsheet by key ID if available, otherwise by name."""
    if SPREADSHEET_KEY:
        return gc.open_by_key(SPREADSHEET_KEY).sheet1
    return gc.open(SPREADSHEET_NAME).sheet1


def upload_signal_to_google_drive(file_contents: str, filename: str, patient_id: str) -> str:
    """Uploads raw watch signal file to Google Drive folder."""
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


def append_visit_to_google_sheet(record_data: dict):
    """Appends structured clinical visit record to Google Sheets."""
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


def load_visits_from_google_sheet() -> pd.DataFrame:
    """Loads visits from Google Sheet into a pandas DataFrame safely."""
    try:
        gc = get_gspread_client()
        sh = open_google_sheet(gc)
        records = sh.get_all_records()

        # Handle requests.Response objects returned by custom client wrappers
        if hasattr(records, "json"):
            try:
                records = records.json()
            except Exception:
                records = []
        elif not isinstance(records, (list, dict)):
            records = []

        return pd.DataFrame(records)
    except Exception as e:
        print(f"[Google Sheets Fetch Detail]: Raw error -> {repr(e)}")
        return pd.DataFrame()

def load_recent_visits_dataframe() -> pd.DataFrame:
    """Helper alias used by update_progress callback."""
    return load_visits_from_google_sheet()


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
        html.H2("Dehydration Study Data Collection", style={"color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1.5rem"}),
        
        # Section 1: Patient Selection & Registration
        html.Div([
            html.H5("1. Patient Selection / Registration", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
            dbc.Row([
                dbc.Col([
                    html.Label("Select Existing Patient or Add New", style={"color": "#7F8C8D"}),
                    dcc.Dropdown(
                        id="patient-dropdown",
                        options=[{"label": "➕ Add New Patient", "value": "NEW_PATIENT"}],
                        value="NEW_PATIENT",
                        clearable=False,
                        style={"color": "#000"}
                    )
                ], width=6),
                dbc.Col([
                    html.Label("Visit Date", style={"color": "#7F8C8D"}),
                    dcc.Input(id="visit-date", type="text", value=datetime.date.today().isoformat(), style=INPUT_STYLE)
                ], width=6)
            ], style={"marginBottom": "1rem"}),

            dbc.Row([
                dbc.Col([
                    html.Label("Patient ID", style={"color": "#7F8C8D"}),
                    dcc.Input(id="patient-id-input", type="text", placeholder="e.g. P001", style=INPUT_STYLE)
                ], width=6),
                dbc.Col([
                    html.Label("Patient Name", style={"color": "#7F8C8D"}),
                    dcc.Input(id="patient-name-input", type="text", placeholder="e.g. John Doe", style=INPUT_STYLE)
                ], width=6)
            ], id="new-patient-fields-row")
        ], style=CARD_STYLE),

        # Section 2: Clinical Panel & Demographics
        html.Div([
            html.H5("2. Clinical Laboratory Panel & Demographics", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
            dbc.Row([
                dbc.Col([html.Label("Age"), dcc.Input(id="input-age", type="number", style=INPUT_STYLE)], width=3),
                dbc.Col([
                    html.Label("Gender"),
                    dcc.Dropdown(
                        id="input-gender",
                        options=[{"label": "Male", "value": "Male"}, {"label": "Female", "value": "Female"}],
                        placeholder="Select gender...", style={"color": "#000"}
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

        # Section 3: Galaxy Watch Raw Telemetry Upload
        html.Div([
            html.H5("3. Galaxy Watch 8 Raw Telemetry File (.csv)", style={"color": "#E0E0E0", "marginBottom": "0.75rem"}),
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

        # Section 4: Submit
        html.Div([
            html.Button("Save Visit & Submit Telemetry", id="submit-btn", n_clicks=0,
                        style={"backgroundColor": "#2980B9", "color": "#FFF", "padding": "0.75rem 2rem", "fontSize": "1.1rem", "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
            html.Div(id="submit-output", style={"marginTop": "1rem"})
        ], style=CARD_STYLE),

        html.Hr(style={"borderColor": "#3A3A3A", "margin": "2rem 0"}),

        # Progress Charts
        html.H3("Collection Progress", style={"color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1rem"}),
        html.Div(id="collection-progress-summary", style={"marginBottom": "1rem"}),
        dbc.Row([
            dbc.Col(dcc.Graph(id="collection-tier-chart", figure=create_empty_dark_figure("Risk tier distribution")), width=6),
            dbc.Col(dcc.Graph(id="collection-visits-per-patient-chart", figure=create_empty_dark_figure("Visits per patient")), width=6),
        ]),
        html.H5("Recent Submissions", style={"color": "#E0E0E0", "marginTop": "1rem", "marginBottom": "0.75rem"}),
        html.Div(id="collection-recent-table"),

        dcc.Interval(id="collection-refresh-interval", interval=5000, n_intervals=0),
        dcc.Store(id="collection-refresh-trigger", data=datetime.datetime.now().isoformat()),
    ])

app.layout = serve_layout


# --- Callbacks ---

@app.callback(
    Output("patient-dropdown", "options"),
    Input("collection-refresh-trigger", "data")
)
def update_patient_dropdown(_trigger):
    """Populates dropdown with existing patients logged in Google Sheets."""
    df = load_visits_from_google_sheet()
    options = [{"label": "➕ Add New Patient", "value": "NEW_PATIENT"}]
    
    if not df.empty and "patient_id" in df.columns:
        patients = df.drop_duplicates(subset=["patient_id"])
        for _, row in patients.iterrows():
            pid = str(row.get("patient_id", ""))
            pname = str(row.get("patient_name", ""))
            label = f"{pid} - {pname}" if pname else pid
            if pid:
                options.append({"label": label, "value": pid})
    return options


@app.callback(
    Output("patient-id-input", "value"),
    Output("patient-name-input", "value"),
    Output("input-age", "value"),
    Output("input-gender", "value"),
    Output("input-weight", "value"),
    Output("input-bmi", "value"),
    Output("patient-id-input", "disabled"),
    Output("patient-name-input", "disabled"),
    Input("patient-dropdown", "value")
)
def handle_patient_selection(selected_pid):
    """Auto-fills patient demographics when an existing patient is selected."""
    if not selected_pid or selected_pid == "NEW_PATIENT":
        return "", "", None, None, None, None, False, False

    df = load_visits_from_google_sheet()
    if not df.empty:
        df["patient_id"] = df["patient_id"].astype(str)
        p_data = df[df["patient_id"] == str(selected_pid)]
        if not p_data.empty:
            last_record = p_data.iloc[-1]
            return (
                str(last_record.get("patient_id", "")),
                str(last_record.get("patient_name", "")),
                last_record.get("age"),
                last_record.get("gender"),
                last_record.get("weight"),
                last_record.get("bmi"),
                True,
                True
            )
    return selected_pid, "", None, None, None, None, True, True


@app.callback(
    Output("uploaded-filename", "children"),
    Input("upload-watch-signal", "filename")
)
def update_upload_label(filename):
    if filename:
        return f"📁 Attached file: {filename}"
    return ""


@app.callback(
    Output("submit-output", "children"),
    Output("collection-refresh-trigger", "data"),
    Input("submit-btn", "n_clicks"),
    State("patient-id-input", "value"),
    State("patient-name-input", "value"),
    State("visit-date", "value"),
    State("input-age", "value"),
    State("input-gender", "value"),
    State("input-weight", "value"),
    State("input-bmi", "value"),
    State("upload-watch-signal", "contents"),
    State("upload-watch-signal", "filename"),
    [State(f"lab-{f}", "value") for f in LAB_FIELDS]
)
def submit_visit(n_clicks, patient_id, patient_name, visit_date, age, gender_label, weight, bmi, watch_file_contents, watch_filename, *lab_vals):
    if not n_clicks:
        return no_update, no_update
    if not patient_id or not patient_name:
        return html.Div("⚠️ Please enter both Patient ID and Patient Name.", style={"color": "#E74C3C"}), no_update
    if not gender_label or gender_label not in GENDER_MAP:
        return html.Div("⚠️ Please select a valid Gender.", style={"color": "#E74C3C"}), no_update
    
    labs = dict(zip(LAB_FIELDS, lab_vals))
    if any(v is None for v in labs.values()) or any(v is None for v in [age, weight, bmi]):
        return html.Div("⚠ Please fill in all lab panel and demographic fields.", style={"color": "#E74C3C"}), no_update

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

            msg = html.Div(f"✅ Visit Logged for {patient_name} ({patient_id})! Risk: {risk} | Drive File ID: {drive_file_id or 'None'}", style={"color": "#2ECC71", "fontWeight": "700"})
            return msg, datetime.datetime.now().isoformat()
        else:
            err_detail = res_dict.get("error") or res_dict.get("message") or "Failed to process visit record in backend."
            return html.Div(f"❌ Backend Error: {err_detail}", style={"color": "#E74C3C"}), no_update

    except gspread.exceptions.SpreadsheetNotFound:
        return html.Div(
            f"❌ Google Sheet Error: Could not find spreadsheet '{SPREADSHEET_NAME}'. "
            "Ensure the Google Sheet is shared with your Service Account email as Editor, "
            "or set GOOGLE_SHEET_ID in your .env file.",
            style={"color": "#E74C3C"}
        ), no_update
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
    df = load_recent_visits_dataframe()

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