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
    """Runs HeartPy, NeuroKit2, and IMU vector analysis to derive features."""
    features = {}

    # -------------------------------------------------------------
    # 1. Accelerometer Feature Extraction (Custom Vector Math)
    # -------------------------------------------------------------
    acc_cols = ['acc_x', 'acc_y', 'acc_z']
    if all(col in df_signal.columns for col in acc_cols):
        # Resultant Acceleration Vector: |a| = sqrt(x^2 + y^2 + z^2)
        acc_magnitude = np.sqrt(
            df_signal['acc_x']**2 + 
            df_signal['acc_y']**2 + 
            df_signal['acc_z']**2
        )
        
        acc_std_val = float(np.std(acc_magnitude))
        acc_mean_val = float(np.mean(acc_magnitude))

        features["acc_std"] = 0.0 if np.isnan(acc_std_val) else acc_std_val
        features["acc_mean"] = 0.0 if np.isnan(acc_mean_val) else acc_mean_val
    else:
        features["acc_std"] = 0.0
        features["acc_mean"] = 0.0

    # -------------------------------------------------------------
    # 2. PPG HeartPy Processing
    # -------------------------------------------------------------
    signal_col = "ppg" if "ppg" in df_signal.columns else df_signal.select_dtypes(include=[np.number]).columns[0]
    ppg_data = df_signal[signal_col].values

    try:
        wd, m = hp.process(ppg_data, sample_rate=sample_rate)
        features["hp_bpm"] = float(m.get("bpm", 0.0))
        features["hp_rmssd"] = float(m.get("rmssd", 0.0))
        features["hp_sdnn"] = float(m.get("sdnn", 0.0))
        features["hp_pnn50"] = float(m.get("pnn50", 0.0))
    except Exception as e:
        print(f"HeartPy processing error: {e}")
        features["hp_bpm"] = 0.0
        features["hp_rmssd"] = 0.0
        features["hp_sdnn"] = 0.0
        features["hp_pnn50"] = 0.0

    # -------------------------------------------------------------
    # 3. PPG NeuroKit2 Processing
    # -------------------------------------------------------------
    try:
        cleaned_ppg = nk.ppg_clean(ppg_data, sampling_rate=int(sample_rate))
        peaks, _ = nk.ppg_peaks(cleaned_ppg, sampling_rate=int(sample_rate))
        hrv_time = nk.hrv_time(peaks, sampling_rate=int(sample_rate))
        
        nk_mean = hrv_time.get("HRV_MeanNN", [0.0])[0]
        nk_sdnn = hrv_time.get("HRV_SDNN", [0.0])[0]
        nk_rmssd = hrv_time.get("HRV_RMSSD", [0.0])[0]

        features["nk_mean_hr"] = 0.0 if np.isnan(nk_mean) else float(nk_mean)
        features["nk_sdnn"] = 0.0 if np.isnan(nk_sdnn) else float(nk_sdnn)
        features["nk_rmssd"] = 0.0 if np.isnan(nk_rmssd) else float(nk_rmssd)
    except Exception as e:
        print(f"NeuroKit2 processing error: {e}")
        features["nk_mean_hr"] = 0.0
        features["nk_sdnn"] = 0.0
        features["nk_rmssd"] = 0.0

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
                print(f"✅ Extracted HRV & Acc Biometrics: {biometrics}")
                
                # Excel row indexing starts at 2 (1 is header row)
                row_idx = idx + 2 
                
                # Update acc_std column in Google Sheets (ensure column named 'acc_std' exists in sheet)
                if "acc_std" in df_visits.columns:
                    col_idx = df_visits.columns.get_loc("acc_std") + 1
                    sheet.update_cell(row_idx, col_idx, biometrics["acc_std"])
                    print(f"Updated Google Sheet Row {row_idx} acc_std = {biometrics['acc_std']}")

            except Exception as e:
                print(f"❌ Failed processing file {file_id}: {e}")

if __name__ == "__main__":
    process_unprocessed_drive_files()