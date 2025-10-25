# to run: streamlit run Overview.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Dehydration MAS", layout="wide")

st.title("Elderly Dehydration Monitoring Multi-Agent System")

# Load data
@st.cache_data
def load_data():
    # Read the CSV file
    import os
    file_path = os.path.join(os.path.dirname(__file__), "vitals_raw_log.csv")
    df = pd.read_csv(file_path)
    
    # Rename columns to more readable names
    column_mapping = {
        'timestamp': 'TIMESTAMP',
        'patient_id': 'PATIENT_ID',
        'baseline': 'BASELINE',
        'current': 'CURRENT'
    }
    df = df.rename(columns=column_mapping)
    
    # Calculate total body water loss percentage
    df['TBW_LOSS%'] = ((df['BASELINE'] - df['CURRENT']) / df['BASELINE']) * 100
    
    # Define risk levels based on water loss percentage
    def get_risk_status(loss):
        if pd.isna(loss):
            return 'Unknown'
        if loss <= 2:
            return 'Euhydrated'
        elif loss < 5:
            return 'Mild'
        elif loss <= 10:
            return 'Moderate'
        else:
            return 'Severe'
    
    # Add risk status column
    df['RISK_STATUS'] = df['TBW_LOSS%'].apply(get_risk_status)
    
    return df

# print(load_data())

st.markdown("""
Dehydration is a prevalent clinical condition, 
particularly among older adults, due to age-related physiological 
changes. We proposed a systematic approach for 
monitoring and managing hydration levels in elderly patients 
using a multi-agent system (MAS). The MAS categorizes 
dehydration into four distinct risk levels: Euhydration, Mild, 
Moderate, and Severe Dehydration based on the percentage of 
Total Body Water (TBW) loss. The system continuously tracks a 
patient's hydration status by calculating TBW loss from changes 
in weight, predicts the dehydration risk using a machine learning 
model, and generates a personalized, goal-driven care plan. The 
primary objective of this system is to provide proactive alerts and 
ensure timely, automated interventions to maintain optimal 
hydration in elderly patients.  

This dashboard presents data from a dehydration monitoring system for elderly patients. It tracks total body water loss percentage and categorizes patients into different risk levels based on their hydration status.
""", width=800)