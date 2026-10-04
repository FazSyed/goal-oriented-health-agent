import os
import json
import numpy as np

# Ensure directory exists
os.makedirs("logs/watch_staging", exist_ok=True)
os.makedirs("visualization/logs/watch_staging", exist_ok=True)

# Generate 250 sample points (~10 seconds of PPG at 25Hz)
t = np.linspace(0, 10, 250)
simulated_ppg = (500 + 100 * np.sin(2 * np.pi * 1.2 * t)).tolist()  # 1.2 Hz = 72 BPM
simulated_eda = (0.15 + 0.05 * np.sin(2 * np.pi * 0.1 * t[:30])).tolist()

payload = {
    "raw_ppg": simulated_ppg,
    "raw_eda": simulated_eda,
    "raw_temp": 36.5
}

# Write to both potential paths so the dashboard finds it regardless of launch folder
for path in ["logs/watch_staging/P002.json", "visualization/logs/watch_staging/P002.json"]:
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

print("✅ Generated watch staging file for P002 successfully!")