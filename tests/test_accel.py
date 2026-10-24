import gspread
import pandas as pd
import numpy as np

# 1. Connect to Sheet
gc = gspread.service_account(filename="google_credentials.json")
sheet = gc.open("Dehydration_Study_Visits").sheet1

# 2. Check Header Columns
headers = sheet.row_values(1)
print(f"📋 Detected Google Sheet Headers: {headers}")

if "acc_std" not in headers:
    print("❌ ERROR: 'acc_std' header was NOT found in Row 1 of your Google Sheet!")
else:
    col_index = headers.index("acc_std") + 1
    print(f"✅ Found 'acc_std' at Column Index: {col_index}")

# 3. Test Math Extraction on Dummy Vector
dummy_acc_x = np.random.normal(0, 0.02, 100)
dummy_acc_y = np.random.normal(0, 0.02, 100)
dummy_acc_z = np.random.normal(0.98, 0.02, 100)

magnitude = np.sqrt(dummy_acc_x**2 + dummy_acc_y**2 + dummy_acc_z**2)
calculated_acc_std = float(np.std(magnitude))

print(f"🧮 Test Calculated acc_std: {calculated_acc_std:.6f}")

# 4. Test Writing to Row 2
sheet.update_cell(2, col_index, round(calculated_acc_std, 5))
print("🚀 Successfully wrote test acc_std value to Row 2 in Google Sheets!")