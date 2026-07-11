import json
import os
import glob
import datetime

import pandas as pd
import plotly.graph_objects as go # Plotly for creating interactive visualizations

from dash import Dash, dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc

# File path constants and refresh interval for live dashboard updates
LOGS_DIR = "logs"
REFRESH_MS = 10_000 # Refresh interval in milliseconds (10 seconds)

# Color mapping for hydration risk categories
RISK_COLORS = {
    "Euhydrated":"#2ECC71",
    "Mild":"#F39C12",
    "Moderate":"#E67E22",
    "Severe":"#E74C3C",
    "Unknown":"#95A5A6",
}

# Labels displayed for each risk category in the dashboard
RISK_LABELS = {
    "Euhydrated": "NORMAL",
    "Mild": "LOW",
    "Moderate": "CONCERNING",
    "Severe": "CRITICAL",
    "Unknown": "UNKNOWN",
}

# Messages shown to the patient based on current hydration category
PATIENT_MESSAGES = {
    "Euhydrated": "You are well hydrated today. Keep it up!",
    "Mild": "Please drink water or an ORS solution now.",
    "Moderate": "Please call your healthcare provider immediately.",
    "Severe": "Emergency help has been contacted. Stay calm.",
    "Unknown": "Status is being checked. Please wait.",
}

# Messages shown to the family based on current hydration category
FAMILY_MESSAGES = {
    "Euhydrated": "Your family member is well hydrated.",
    "Mild": "Hydration is slightly low. Encourage fluid intake.",
    "Moderate": "Hydration levels are concerning. Contact clinician.",
    "Severe": "Critical dehydration detected. Emergency services contacted.",
    "Unknown": "Status is currently being assessed.",
}

def load_json_logs():
    # initialize list to collect log records from JSON files
    records = []

    # iterate through all matching patient JSON files in the logs directory
    for path in glob.glob(os.path.join(LOGS_DIR, "patient_*.json")):
        try:
            # open the current JSON file and parse its contents
            with open(path) as f:
                entries = json.load(f)

            # convert each JSON entry into a flat record dictionary
            for e in entries:
                records.append({
                    "timestamp": e.get("timestamp"),
                    "patient_id": e.get("patient_id"),
                    "ml_prediction": e.get("ml_prediction"),
                    "ontology_action": e.get("ontology", {}).get("action"),
                    "ontology_fallback": e.get("ontology", {}).get("fallback_used"),
                    "planner_fallback": e.get("planner", {}).get("fallback_used"),
                    "kafka_success": e.get("routing", {}).get("kafka_publish_success"),
                    "plan": e.get("planner", {}).get("plan", ""),
                })

        except Exception:
            continue # ignore files that cannot be read or parsed

    if not records:
        return pd.DataFrame() # return an empty DataFrame if no records were found
    
    # build a DataFrame from the collected records
    df = pd.DataFrame(records)
    # convert timestamp strings to datetime objects
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # sort records by timestamp and reset the index
    return df.sort_values("timestamp").reset_index(drop=True)

def load_chart_data():
    '''Load vitals and ML predictions from JSON logs and return a DataFrame for charting'''

    # Initialize list to store all patient records
    records = []
    
    # Iterate through all patient JSON files in the logs directory
    for path in glob.glob(os.path.join(LOGS_DIR, "patient_*.json")):
        try:
            # Open and parse the JSON file
            with open(path) as f:
                entries = json.load(f)
            
            # Process each entry (record) in the JSON file
            for e in entries:
                # Extract vitals dictionary from the entry
                vitals = e.get("vitals", {})
                # Skip entries with missing or incomplete vitals data
                if not vitals or vitals.get("sodium") is None:
                    continue
                
                # Build a record dictionary with all vitals and ML prediction data
                records.append({
                    "timestamp": e.get("timestamp"),
                    "patient_id": e.get("patient_id"),
                    "sodium": vitals.get("sodium"),
                    "potassium": vitals.get("potassium"),
                    "chloride": vitals.get("chloride"),
                    "bun": vitals.get("bun"),
                    "creatinine": vitals.get("creatinine"),
                    "glucose": vitals.get("glucose"),
                    "age": vitals.get("age"),
                    "gender": vitals.get("gender"),
                    "weight": vitals.get("weight"),
                    "bmi": vitals.get("bmi"),
                    "RISK_STATUS": e.get("ml_prediction", "Unknown"),
                })
        except Exception:
            continue # Skip files that cannot be read or parsed

    # Return empty DataFrame if no valid records were collected
    if not records:
        return pd.DataFrame()

    # Create DataFrame from collected records
    df = pd.DataFrame(records)
    # Convert timestamp strings to datetime objects for proper sorting
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Remove rows with missing critical vitals data
    df = df.dropna(subset=["sodium", "bun", "creatinine"])
    # Sort by timestamp and reset index for clean sequential indexing
    return df.sort_values("timestamp").reset_index(drop=True)

def latest_summary(df: pd.DataFrame):  
    ''' function to summarize the latest reading'''
    
    if df.empty:  # check if the DataFrame contains no rows
        return {}  # return an empty dict when there is no data
    
    row = df.iloc[-1]  # select the last row from the DataFrame
    
    return {
        "timestamp": str(row["timestamp"]),  # convert the timestamp to string format
        "sodium": round(float(row["sodium"]), 1),  # round sodium value to one decimal place
        "bun": round(float(row["bun"]), 1),  # round BUN value to one decimal place
        "creatinine": round(float(row["creatinine"]), 2),  # round creatinine value to two decimal places
        "glucose": round(float(row["glucose"]), 1),  # round glucose value to one decimal place
        "potassium": round(float(row["potassium"]), 1),  # round potassium value to one decimal place
        "chloride": round(float(row["chloride"]), 1),  # round chloride value to one decimal place
        "risk": row["RISK_STATUS"],  # include the calculated risk status from the row
    }


def today_counts(df: pd.DataFrame) -> dict:
    '''function to count today's risk statuses - used in Family View'''

    today = datetime.date.today()  # get the current date
    today_df = df[df["timestamp"].dt.date == today]  # filter rows to those recorded today
    counts = today_df["RISK_STATUS"].value_counts().to_dict()  # count risk categories and convert to dict
    return counts


def _layout(**extra):
    ''' helper function for reusable layout settings for charts'''

    base = dict(
        paper_bgcolor="#1A1A2E",  # outer paper background color
        plot_bgcolor="#16213E",  # plot area background color
        font=dict(color="#E0E0E0", family="Inter, sans-serif"),  # font styling for the plot
        margin=dict(l=50, r=30, t=50, b=40),  # set plot margins
        legend=dict(bgcolor="rgba(0,0,0,0)"),  # transparent legend background
        xaxis=dict(gridcolor="#2C2C4A", showgrid=True),  # x-axis grid styling
        yaxis=dict(gridcolor="#2C2C4A", showgrid=True),  # y-axis grid styling
    )
    
    base.update(extra)  # merge additional layout configuration
    return base


def fig_line(df, col, title, ylabel, color) -> go.Figure:
    '''Single line chart for a given column in the DataFrame.'''

    fig = go.Figure()  # initialize an empty figure object
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[col],  # use timestamps on x-axis and specified column on y-axis
        mode="lines",  # display as a connected line
        line=dict(color=color, width=2),  # set line color and thickness
        hovertemplate=f"<b>%{{x}}</b><br>{ylabel}: %{{y}}<extra></extra>"  # tooltip formatting
    ))
    fig.update_layout(title=title, xaxis_title="Time", yaxis_title=ylabel, **_layout())  # apply titles and shared layout
    return fig


def fig_risk_scatter(df: pd.DataFrame, title="Risk Level Over Time") -> go.Figure:
    '''Scatter Plot color-coded by risk level.'''

    fig = go.Figure()  # initialize an empty figure

    for risk, color in RISK_COLORS.items():  # iterate through defined risk categories and colors
        mask = df["RISK_STATUS"] == risk  # select rows matching the current risk category
        if mask.sum() == 0:  # if no rows for this risk, skip adding a trace
            continue
        fig.add_trace(go.Scatter(
            x=df.loc[mask, "timestamp"],  # timestamps for selected risk rows
            y=[RISK_LABELS.get(risk, risk)] * mask.sum(),  # use risk label repeated for y-axis values
            mode="markers",  # display individual points only
            marker=dict(color=color, size=10),  # set point color and size
            name=RISK_LABELS.get(risk, risk),  # legend label for the trace
            hovertemplate=f"<b>{risk}</b><br>%{{x}}<extra></extra>"  # tooltip text for points
        ))
    fig.update_layout(title=title, xaxis_title="Time", **_layout())  # apply title and shared layout settings
    fig.update_yaxes(
        categoryorder="array",  # order categories explicitly
        categoryarray=["NORMAL", "LOW", "CONCERNING", "CRITICAL"],  # define category order
        gridcolor="#2C2C4A"  # set y-axis grid line color
    )
    return fig


def fig_risk_donut(df: pd.DataFrame, title="Risk Distribution") -> go.Figure:
    '''Donut Chart for risk level count distribution'''
    
    counts = df["RISK_STATUS"].value_counts()  # count rows per risk status
    labels = [RISK_LABELS.get(r, r) for r in counts.index]  # map status values to display labels
    fig = go.Figure(go.Pie(
        labels=labels,  # pie segment labels
        values=counts.values,  # pie segment values
        hole=0.55,  # create donut hole size
        marker=dict(colors=[RISK_COLORS.get(r, "#95A5A6") for r in counts.index]),  # assign colors per status
        textinfo="label+percent",  # show label and percentage inside segments
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>"  # tooltip formatting
    ))
    fig.update_layout(title=title, showlegend=True, **_layout())  # apply title, legend, and shared layout
    return fig


def fig_bar(x, y, colors, title, ylabel) -> go.Figure:
    '''Bar chart function for creating bar plots with specified labels, values, and colors'''
    fig = go.Figure(go.Bar(
        x=x, y=y,  # set bar labels and values
        marker_color=colors,  # assign bar colors
        text=y,  # show values on bars
        textposition="outside"  # position text above bars
    ))
    fig.update_layout(title=title, yaxis_title=ylabel, **_layout())  # apply title and shared layout settings
    return fig  # return the bar chart figure


def fig_fallback_bar(log_df: pd.DataFrame) -> go.Figure:
    '''Fallback and failure tracking bar chart for system reliability metrics'''
    
    if log_df.empty:  # check if the provided dataframe has no rows
        return go.Figure().update_layout(title="No log data available", **_layout())  # return an empty figure with a message
    
    total = len(log_df)  # compute total number of log entries
    onto_fb = int(log_df["ontology_fallback"].eq(True).sum())  # count ontology fallback occurrences
    plan_fb = int(log_df["planner_fallback"].eq(True).sum())  # count planner fallback occurrences
    kafka_fail = int(log_df["kafka_success"].eq(False).sum())  # count kafka failures (success==False)

    return fig_bar(  # build and return a bar chart with the computed counts
        x=["Ontology Fallbacks", "Planner Fallbacks", "Kafka Failures"],  # labels for x-axis
        y=[onto_fb, plan_fb, kafka_fail],  # corresponding counts for each label
        colors=["#9B59B6", "#E67E22", "#E74C3C"],  # colors for each bar
        title="System Reliability: Fallback & Failure Tracking",  # chart title
        ylabel=f"Count (of {total} total runs)"  # y-axis label with total runs info
    )


def fig_prediction_bar(log_df: pd.DataFrame) -> go.Figure:
    '''Bar chart for displaying distribution of ML predictions'''

    if log_df.empty:  # if no data, return an empty figure with title
        return go.Figure().update_layout(title="No log data", **_layout())
    
    counts = log_df["ml_prediction"].value_counts()  # count occurrences of each ML prediction
    labels = [RISK_LABELS.get(r, r) for r in counts.index]  # map raw prediction keys to display labels

    return fig_bar(  # return a bar chart showing distribution of predictions
        x=labels,  # labels for each prediction category
        y=counts.values.tolist(),  # counts for each category as list
        colors=[RISK_COLORS.get(r, "#95A5A6") for r in counts.index],  # assign colors per category
        title="ML Prediction Distribution",  # chart title
        ylabel="Count"  # y-axis label
    )

# CSS Styles for Sidebar
SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "220px", "padding": "2rem 1rem",
    "backgroundColor": "#0F0F1A",
    "borderRight": "1px solid #2C2C4A",
    "zIndex": 1000,
}

# CSS Styles for Main Content Area
CONTENT_STYLE = {
    "marginLeft": "240px",
    "padding": "2rem",
    "backgroundColor": "#1A1A2E",
    "minHeight": "100vh",
}

# CSS Styles for Card Components
CARD_STYLE = {
    "backgroundColor": "#16213E",
    "borderRadius": "12px",
    "padding": "1.2rem",
    "marginBottom": "1rem",
    "border": "1px solid #2C2C4A",
}

# CSS Styles for Metric Cards
METRIC_STYLE = {
    "backgroundColor": "#16213E",
    "borderRadius": "10px",
    "padding": "1rem",
    "textAlign": "center",
    "border": "1px solid #2C2C4A",
}

# Initialize the Dash application with external stylesheets for Bootstrap and Google Fonts
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap"
    ],
    title="Hydration MAS Dashboard" # Title of the dashboard in the browser tab
)

# Sidebar layout for the dashboard
sidebar = html.Div([
    # Application logo and title container
    html.Div([
        html.Div("💧", style={"fontSize": "2rem", "textAlign": "center"}),
        html.H5("Hydration MAS", style={
            "color": "#3498DB", "textAlign": "center",
            "fontWeight": "700", "marginTop": "0.5rem",
            "fontSize": "0.95rem", "letterSpacing": "0.05em"
        }),
    ], style={"marginBottom": "2rem"}),

    # Role selector dropdown allows users to view the dashboard from different perspectives
    html.Label("VIEW AS", style={
        "color": "#7F8C8D", "fontSize": "0.7rem",
        "letterSpacing": "0.12em", "fontWeight": "600"
    }),
    dcc.Dropdown(
        id="role-selector",
        options=[
            {"label": "Patient", "value": "patient"},
            {"label": "Family / Caretaker", "value": "family"},
            {"label": "Clinician", "value": "clinician"},
            {"label": "Researcher", "value": "researcher"},
        ],
        value="clinician",
        clearable=False,
        style={"marginBottom": "2rem", "fontSize": "0.9rem", "color": "#252525"}
    ),

    # Patient selector dropdown for selecting the patient whose data is displayed
    html.Label("PATIENT", style={
        "color": "#7F8C8D", "fontSize": "0.7rem",
        "letterSpacing": "0.12em", "fontWeight": "600"
    }),
    dcc.Dropdown(
        id="patient-selector",
        options=[
            # {"label": f"Patient {p['patient_id']}", "value": p['patient_id']}
            # for p in ALL_PROFILES

            {"label": "Patient 1", "value": 1},
            {"label": "Patient 2", "value": 2},
            {"label": "Patient 3", "value": 3},
            {"label": "Patient 4", "value": 4},
        ],
        value=1,
        clearable=False,
        style={"marginBottom": "2rem", "fontSize": "0.9rem", "color": "#252525"}
    ),

    # Last updated timestamp shown at the bottom of the sidebar
    html.Div(id="last-updated", style={
        "color": "#7F8C8D", "fontSize": "0.7rem",
        "position": "absolute", "bottom": "1rem",
        "left": "1rem", "right": "1rem"
    }),

    # Interval component for refreshing data periodically
    dcc.Interval(id="refresh-interval", interval=REFRESH_MS, n_intervals=0),
], style=SIDEBAR_STYLE)

# Main content layout for the dashboard
content = html.Div([
    # Patient dashboard section for a single patient's hydration summary
    html.Div(id="patient-view", children=[
        html.Div([
            html.H2("Your Hydration Status", style={
                "color": "#E0E0E0", "fontWeight": "700",
                "textAlign": "center", "marginBottom": "2rem"
            }),
            html.Div(id="patient-status-circle", style={"textAlign": "center"}),
            html.Div(id="patient-message", style={
                "textAlign": "center", "marginTop": "1.5rem"
            }),
            html.Div(id="patient-timestamp", style={
                "textAlign": "center", "marginTop": "1rem"
            }),
        ], style={**CARD_STYLE, "padding": "3rem"}),
    ]),

    # Family view section with overview charts and status message
    html.Div(id="family-view", children=[
        html.Div([
            html.H2("Patient Hydration Overview", style={
                "color": "#E0E0E0", "fontWeight": "700",
                "marginBottom": "0.5rem"
            }),
            html.Div(id="family-status-message"),
        ], style=CARD_STYLE),

        dbc.Row([
            dbc.Col(html.Div([
                dcc.Graph(id="family-scatter", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=7),
            dbc.Col(html.Div([
                dcc.Graph(id="family-donut", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=5),
        ]),
    ]),

    # Clinician view section with clinical metrics and trend charts
    html.Div(id="clinician-view", children=[
        html.H2("Clinical Overview", style={
            "color": "#E0E0E0", "fontWeight": "700", "marginBottom": "1rem"
        }),

        # Latest reading metric cards
        html.Div(id="metric-cards", style={
            "display": "grid",
            "gridTemplateColumns": "repeat(6, 1fr)",
            "gap": "0.75rem", "marginBottom": "1rem"
        }),

        # Sodium - most important, full width
        html.Div([
            dcc.Graph(id="sodium-chart", config={"displayModeBar": False})
        ], style=CARD_STYLE),

        # BUN and Creatinine
        dbc.Row([
            dbc.Col(html.Div([
                dcc.Graph(id="bun-chart", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
            dbc.Col(html.Div([
                dcc.Graph(id="creatinine-chart", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
        ]),

        # Glucose and Potassium
        dbc.Row([
            dbc.Col(html.Div([
                dcc.Graph(id="glucose-chart", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
            dbc.Col(html.Div([
                dcc.Graph(id="potassium-chart", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
        ]),

        # Chloride and Risk donut
        dbc.Row([
            dbc.Col(html.Div([
                dcc.Graph(id="chloride-chart", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
            dbc.Col(html.Div([
                dcc.Graph(id="risk-donut", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
        ]),

        # Risk scatter
        html.Div([
            dcc.Graph(id="risk-scatter", config={"displayModeBar": False})
        ], style=CARD_STYLE),

        # Care plan history
        html.Div([
            html.H5("Recent Alerts & Care Plans", style={
                "color": "#E0E0E0", "marginBottom": "1rem"
            }),
            html.Div(id="care-plan-history"),
        ], style=CARD_STYLE),
    ]),

    # Researcher dashboard section with analytics and raw data display
    html.Div(id="researcher-view", children=[
        html.H4("System Analytics", style={
            "color": "#E0E0E0", "fontWeight": "700",
            "marginTop": "1rem", "marginBottom": "1rem"
        }),

        # Prediction and fallback graphs shown side by side
        dbc.Row([
            dbc.Col(html.Div([
                dcc.Graph(id="prediction-bar", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
            dbc.Col(html.Div([
                dcc.Graph(id="fallback-bar", config={"displayModeBar": False})
            ], style=CARD_STYLE), width=6),
        ]),

        # Raw readings panel with a risk filter and table output
        html.Div([
            html.Div([
                html.H5("Raw Readings", style={
                    "color": "#E0E0E0", "display": "inline-block"
                }),
                dcc.Dropdown(
                    id="risk-filter",
                    options=[{"label": r, "value": r}
                             for r in ["All", "Euhydrated", "Mild",
                                       "Moderate", "Severe"]],
                    value="All", clearable=False,
                    style={
                        "width": "180px", "display": "inline-block",
                        "marginLeft": "1rem", "verticalAlign": "middle",
                        "fontSize": "0.85rem"
                    }
                ),
            ], style={"marginBottom": "0.75rem"}),
            html.Div(id="raw-table"),
        ], style=CARD_STYLE),
    ]),

], style=CONTENT_STYLE)

# Main application layout combining the sidebar and the content container
app.layout = html.Div([sidebar, content])

# Callback to show only the selected user role's dashboard view
@app.callback(
    Output("patient-view", "style"),
    Output("family-view", "style"),
    Output("clinician-view", "style"),
    Output("researcher-view", "style"),
    Input("role-selector", "value"),
)

def toggle_views(role):
    # CSS controls for showing and hiding sections
    show = {"display": "block"}
    hide = {"display": "none"}
    if role == "patient":
        return show, hide, hide, hide
    elif role == "family":
        return hide, show, hide, hide
    elif role == "clinician":
        return hide, hide, show, hide
    else:  # researcher
        return hide, hide, show, show

# Main update callback for all view components and filters
@app.callback(
    # Patient view
    Output("patient-status-circle", "children"),
    Output("patient-message", "children"),
    Output("patient-timestamp", "children"),
    # Family view
    Output("family-status-message",  "children"),
    Output("family-scatter", "figure"),
    Output("family-donut", "figure"),
    # Clinician view
    Output("metric-cards", "children"),
    Output("sodium-chart", "figure"),
    Output("bun-chart", "figure"),
    Output("creatinine-chart", "figure"),
    Output("glucose-chart", "figure"),
    Output("potassium-chart", "figure"),
    Output("chloride-chart", "figure"),
    Output("risk-donut", "figure"),
    Output("risk-scatter", "figure"),
    Output("care-plan-history", "children"),
    # Researcher view
    Output("prediction-bar", "figure"),
    Output("fallback-bar", "figure"),
    Output("raw-table", "children"),
    # Sidebar
    Output("last-updated", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("risk-filter", "value"),
    Input("patient-selector", "value"),
)

def update_all(n, risk_filter, patient_id):
    '''Update all dashboard components based on the latest data and user selections'''

    # Load the latest dataset and any log entries for the dashboard update cycle
    df = load_chart_data()
    log_df = load_json_logs()

    # Filter both data sources to selected patient
    if not df.empty:
        df = df[df["patient_id"] == patient_id].reset_index(drop=True)

    if not log_df.empty:
        log_df = log_df[log_df["patient_id"] == patient_id].reset_index(drop=True)

    # Prepare fallback UI elements when no data is available.
    empty_fig = go.Figure().update_layout(
        title="No data — run the MAS to generate readings",
        **_layout()
    )
    no_data   = html.P("No data available.", style={"color": "#7F8C8D"})
    last_upd  = f"Updated {datetime.datetime.now().strftime('%H:%M:%S')}"

    # If there is no data, return placeholders for all outputs
    if df.empty:
        return (
            no_data, no_data, no_data,
            no_data, empty_fig, empty_fig,
            [], empty_fig, empty_fig, empty_fig,
            empty_fig, empty_fig, empty_fig,
            empty_fig, empty_fig, no_data,
            empty_fig, empty_fig, no_data,
            "No data loaded"
        )

    # Classify each record by risk and summarize the latest patient state
    latest = latest_summary(df)
    risk = latest.get("risk", "Unknown")
    color = RISK_COLORS.get(risk, "#95A5A6")
    label = RISK_LABELS.get(risk, "UNKNOWN")

    # Build the risk status circle display for the patient overview
    status_circle = html.Div([
        html.Div(
            label,
            style={
                "width": "200px", "height": "200px",
                "borderRadius": "50%",
                "backgroundColor": color,
                "margin": "0 auto",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "fontSize": "1.8rem",
                "fontWeight": "700",
                "color": "white",
                "letterSpacing": "0.05em",
            }
        )
    ])

    # Display a tailored patient message based on current risk
    patient_msg = html.P(
        PATIENT_MESSAGES.get(risk, ""),
        style={
            "color": "#E0E0E0", "fontSize": "1.3rem",
            "fontWeight": "400", "maxWidth": "500px",
            "margin": "0 auto"
        }
    )

    # Format timestamp as friendly time e.g. "2:30 PM"
    try:
        ts = pd.to_datetime(latest.get("timestamp"))
        friendly_time = ts.strftime("%-I:%M %p")
    except Exception:
        friendly_time = latest.get("timestamp", "N/A")

    patient_ts = html.P(
        f"Last checked: {friendly_time}",
        style={"color": "#7F8C8D", "fontSize": "0.95rem"}
    )

    # Count today’s risk categories and determine a family-facing summary
    counts = today_counts(df)
    mild_today = counts.get("Mild", 0)
    mod_today = counts.get("Moderate", 0)
    sev_today = counts.get("Severe", 0)

    if sev_today > 0:
        family_note = f"{sev_today} critical reading(s) detected today. Emergency services notified."
    elif mod_today > 0:
        family_note = f"{mod_today} concerning reading(s) today. Contact their clinician."
    elif mild_today > 0:
        family_note = f"{mild_today} low reading(s) today. Encourage fluid intake."
    else:
        family_note = "All readings today are normal. No action needed."

    # Build the family status card with the current risk label and supporting message
    family_status = html.Div([
        html.Div([
            html.Span(label, style={
                "backgroundColor": color,
                "color": "white",
                "padding": "0.3rem 1rem",
                "borderRadius": "20px",
                "fontWeight": "700",
                "fontSize": "1rem",
                "marginRight": "1rem"
            }),
            html.Span(
                FAMILY_MESSAGES.get(risk, ""),
                style={"color": "#E0E0E0", "fontSize": "1rem"}
            ),
        ], style={"marginBottom": "0.5rem"}),
        html.P(family_note, style={"color": "#7F8C8D", "fontSize": "0.9rem"}),
    ])

    # Create family-facing visualizations summarizing recent readings
    family_scatter = fig_risk_scatter(df, title="Readings Over Time")
    family_donut = fig_risk_donut(df, title="Today's Summary")

    # Define key metric cards shown on the dashboard
    metrics = [
        ("Na⁺", f"{latest.get('sodium', 'N/A')} mmol/L", "#3498DB"),
        ("BUN", f"{latest.get('bun', 'N/A')} mg/dL",  "#E67E22"),
        ("Cr", f"{latest.get('creatinine', 'N/A')} mg/dL",  "#9B59B6"),
        ("K⁺", f"{latest.get('potassium', 'N/A')} mmol/L", "#27AE60"),
        ("Cl⁻", f"{latest.get('chloride', 'N/A')} mmol/L", "#2980B9"),
        ("Gluc", f"{latest.get('glucose', 'N/A')} mg/dL",  "#1ABC9C"),
    ]
    metric_cards = [
        html.Div([
            html.Div(lbl, style={
                "color": "#7F8C8D", "fontSize": "0.7rem",
                "letterSpacing": "0.1em", "marginBottom": "0.3rem"
            }),
            html.Div(val, style={
                "color": col, "fontWeight": "700", "fontSize": "1rem"
            }),
        ], style=METRIC_STYLE)
        for lbl, val, col in metrics
    ]

    # Create trend charts for each lab value and overall risk visuals
    sodium_chart = fig_line(df, "sodium", "Sodium (Na⁺) Over Time", "mmol/L", "#3498DB")
    bun_chart = fig_line(df, "bun", "BUN Over Time", "mg/dL",  "#E67E22")
    creatinine_chart = fig_line(df, "creatinine", "Creatinine Over Time", "mg/dL",  "#9B59B6")
    glucose_chart = fig_line(df, "glucose", "Blood Glucose Over Time", "mg/dL",  "#1ABC9C")
    potassium_chart = fig_line(df, "potassium", "Potassium (K⁺) Over Time", "mmol/L", "#27AE60")
    chloride_chart = fig_line(df, "chloride", "Chloride (Cl⁻) Over Time", "mmol/L", "#2980B9")
    risk_donut = fig_risk_donut(df, "Risk Level Distribution")
    risk_scatter = fig_risk_scatter(df, "Risk Level Over Time")

    if not log_df.empty:
        # Filter the log data to display only alerts that indicate a hydration issue
        alerts = log_df[log_df["ml_prediction"] != "Euhydrated"].tail(5)
        care_items = []
        for _, row in alerts.iterrows():
            pred  = row.get("ml_prediction", "Unknown")

            # Use a colored icon based on the prediction severity
            if pred == "Severe":
                icon = "🔴" 
            elif pred == "Moderate":
                icon = "🟠"
            else:
                icon = "🔵"

            # Parse the care plan into readable list items
            steps = [
                s.strip()
                for s in str(row.get("plan", "")).split("\n")
                if s.strip()
            ]
            clean_steps = [
                # Create ordered list items from each care plan step
                html.Li(
                    s.split(": ", 1)[-1] if ": " in s else s,
                    style={"color": "#BDC3C7", "fontSize": "0.85rem"}
                )
                for s in steps
            ]
            care_items.append(html.Div([
                html.Div([
                    # Display the prediction severity icon and label
                    html.Span(f"{icon} {pred}", style={
                        "color": RISK_COLORS.get(pred, "#95A5A6"),
                        "fontWeight": "600", "marginRight": "1rem"
                    }),
                    # Show the timestamp of the alert
                    html.Span(str(row.get("timestamp", "")),
                              style={"color": "#7F8C8D", "fontSize": "0.8rem"}),
                    # Show the recommended ontology action.
                    html.Span(f" — Action: {row.get('ontology_action', 'N/A')}",
                              style={"color": "#BDC3C7", "fontSize": "0.8rem"}),
                ]),
                # Render the care plan steps as an ordered list
                html.Ol(clean_steps,
                        style={"marginTop": "0.3rem", "paddingLeft": "1.5rem"}),
            ], style={
                # Add a colored left border to indicate risk severity
                "borderLeft": f"3px solid {RISK_COLORS.get(pred, '#95A5A6')}",
                "paddingLeft": "0.75rem", "marginBottom": "0.75rem"
            }))
        care_plan_section = (
            html.Div(care_items) if care_items
            else html.P("No alerts recorded yet.",
                        style={"color": "#7F8C8D"})
        )
    else:
        # Show a fallback message when the log dataset is empty
        care_plan_section = html.P("No log data available.", style={"color": "#7F8C8D"})

    # Generate bar charts for prediction confidence and fallback counts
    prediction_bar = fig_prediction_bar(log_df)
    fallback_bar = fig_fallback_bar(log_df)

    # Prepare the data table by copying the dataset and applying the selected risk filter
    table_df = df.copy()
    if risk_filter != "All":
        table_df = table_df[table_df["RISK_STATUS"] == risk_filter]

    # Select only the relevant columns and keep the last 100 records for display
    display_cols = [
        "timestamp", "sodium", "potassium", "chloride",
        "bun", "creatinine", "glucose", "RISK_STATUS"
    ]
    table_df = table_df[display_cols].tail(100).copy()
    table_df["timestamp"] = table_df["timestamp"].astype(str)

    # Dash DataTable component for the latest patient readings
    raw_table = dash_table.DataTable(
        data=table_df.to_dict("records"),  # convert filtered dataframe rows to list of dicts
        columns=[{"name": c, "id": c} for c in display_cols],  # define visible columns
        style_table={"overflowX": "auto"},  # enable horizontal scrolling if needed
        style_header={
            "backgroundColor": "#0F0F1A", "color": "#E0E0E0",
            "fontWeight": "600", "border": "1px solid #2C2C4A"
        },
        style_cell={
            "backgroundColor": "#1A1A2E", "color": "#BDC3C7",
            "border": "1px solid #2C2C4A",
            "fontSize": "0.82rem", "padding": "6px 12px"
        },
        style_data_conditional=[
            # Use risk status to color rows for quick visual scanning
            {"if": {"filter_query": '{RISK_STATUS} = "Severe"'},
             "backgroundColor": "#2C1515", "color": "#E74C3C"},
            {"if": {"filter_query": '{RISK_STATUS} = "Moderate"'},
             "backgroundColor": "#2C1E0F", "color": "#E67E22"},
            {"if": {"filter_query": '{RISK_STATUS} = "Mild"'},
             "backgroundColor": "#2C2008", "color": "#F39C12"},
            {"if": {"filter_query": '{RISK_STATUS} = "Euhydrated"'},
             "backgroundColor": "#0F2C15", "color": "#2ECC71"},
        ],
        page_size=15,  # show up to 15 rows per page
        sort_action="native",  # allow client-side sorting
        filter_action="native",  # allow client-side filtering
    )

    # Return all the generated components to update the dashboard in one callback
    return (
        status_circle, patient_msg, patient_ts,
        family_status, family_scatter, family_donut,
        metric_cards,
        sodium_chart, bun_chart, creatinine_chart,
        glucose_chart, potassium_chart, chloride_chart,
        risk_donut, risk_scatter, care_plan_section,
        prediction_bar, fallback_bar, raw_table,
        last_upd,
    )

if __name__ == "__main__":
    app.run(debug=True)