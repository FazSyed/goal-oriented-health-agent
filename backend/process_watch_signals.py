"""
Local Background Signal Processing Pipeline
===========================================
Downloads raw PPG/watch CSV files from Google Drive, calculates HRV & signal
features using HeartPy and NeuroKit2, and appends extracted metrics for Model 2.
"""

import os
import io
import json
import pandas as pd
import numpy as np
import heartpy as hp
import neurokit2 as nk
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import gspread

def get_google_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    return Credentials.from_service_account_file("google_credentials.json", scopes=scopes)

def download_file_from_drive(file_id: str) -> pd.DataFrame:
    """Downloads CSV watch file from Google Drive into a pandas DataFrame."""
    creds = get_google_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    
    request = drive_service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    
    done = False
    while not done:
        _, done = downloader.next_chunk()
        
    file_stream.seek(0)
    return pd.read_csv(file_stream)

def extract_biometric_features(df_signal: pd.DataFrame, sample_rate: float = 100.0) -> dict:
    """Runs HeartPy and NeuroKit2 on raw PPG column to derive Model 2 features."""
    # Assumes signal column named 'ppg' or takes first numeric column
    signal_col = "ppg" if "ppg" in df_signal.columns else df_signal.select_dtypes(include=[np.number]).columns[0]
    ppg_data = df_signal[signal_col].values

    features = {}

    # 1. HeartPy Processing
    try:
        wd, m = hp.process(ppg_data, sample_rate=sample_rate)
        features["hp_bpm"] = m.get("bpm", np.nan)
        features["hp_rmssd"] = m.get("rmssd", np.nan)
        features["hp_sdnn"] = m.get("sdnn", np.nan)
        features["hp_pnn50"] = m.get("pnn50", np.nan)
    except Exception as e:
        print(f"HeartPy processing error: {e}")

    # 2. NeuroKit2 Processing
    try:
        cleaned_ppg = nk.ppg_clean(ppg_data, sampling_rate=int(sample_rate))
        peaks, _ = nk.ppg_peaks(cleaned_ppg, sampling_rate=int(sample_rate))
        hrv_time = nk.hrv_time(peaks, sampling_rate=int(sample_rate))
        
        features["nk_mean_hr"] = hrv_time.get("HRV_MeanNN", [np.nan])[0]
        features["nk_sdnn"] = hrv_time.get("HRV_SDNN", [np.nan])[0]
        features["nk_rmssd"] = hrv_time.get("HRV_RMSSD", [np.nan])[0]
    except Exception as e:
        print(f"NeuroKit2 processing error: {e}")

    return features

def process_unprocessed_drive_files():
    """Reads Google Sheet, finds rows with Drive File IDs, processes signals, and updates features."""
    creds = get_google_credentials()
    gc = gspread.authorize(creds)
    sheet = gc.open("Dehydration_Study_Visits").sheet1
    
    records = sheet.get_all_records()
    df_visits = pd.DataFrame(records)
    
    if df_visits.empty or "drive_file_id" not in df_visits.columns:
        print("No records with drive_file_id found.")
        return

    for idx, row in df_visits.iterrows():
        file_id = row.get("drive_file_id", "")
        if file_id and file_id != "None":
            print(f"Processing signal file for Patient {row.get('patient_id')} (File ID: {file_id})...")
            try:
                raw_df = download_file_from_drive(file_id)
                biometrics = extract_biometric_features(raw_df)
                print(f"✅ Extracted HRV Biometrics: {biometrics}")
                # Save extracted features locally or update Google Sheets columns here
            except Exception as e:
                print(f"❌ Failed processing file {file_id}: {e}")

if __name__ == "__main__":
    process_unprocessed_drive_files()