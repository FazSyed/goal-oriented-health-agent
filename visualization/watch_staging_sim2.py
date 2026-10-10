import os
import numpy as np
import pandas as pd

# 100 Hz sampling rate over 15 seconds (1500 samples)
fs = 100
t = np.linspace(0, 15, 15 * fs)

# Continuous PPG signal with simulated pulse peaks (~72 BPM)
ppg = 500 + 100 * np.sin(2 * np.pi * 1.2 * t)

# EDA signal with low-frequency skin conductance variation
eda = 0.15 + 0.05 * np.sin(2 * np.pi * 0.1 * t)

# 3-axis Accelerometer simulation for total magnitude std calculation
acc_x = 0.02 * np.random.randn(len(t))
acc_y = 0.02 * np.random.randn(len(t))
acc_z = 0.98 + 0.02 * np.random.randn(len(t))

df = pd.DataFrame({
    "timestamp": t,
    "ppg": ppg,
    "eda": eda,
    "acc_x": acc_x,
    "acc_y": acc_y,
    "acc_z": acc_z
})

folder = "watch_staging"
os.makedirs(folder, exist_ok=True)

filepath = os.path.join(folder, "sample_watch_P002.csv")
df.to_csv(filepath, index=False)

print(f"✅ Generated 100Hz 15-sec test signal: {filepath}")