import numpy as np
import heartpy as hp
import neurokit2 as nk
from typing import Dict

class WatchSignalProcessor:
    """Extracts Model 2 physiological features using HeartPy and NeuroKit2."""

    @staticmethod
    def process_raw_ppg(ppg_signal: np.ndarray, sample_rate: float = 100.0) -> Dict[str, float]:
        # HeartPy requires at least ~10 seconds of signal at 100 Hz to detect peaks reliably
        if ppg_signal is None or len(ppg_signal) < int(sample_rate * 5):
            return {"mean_hr": 0.0, "sdnn": 0.0, "rmssd": 0.0}
            
        try:
            working_data, measures = hp.process(ppg_signal, sample_rate=sample_rate)
            return {
                "mean_hr": float(measures.get("bpm", 0.0)),
                "sdnn": float(measures.get("sdnn", 0.0)),
                "rmssd": float(measures.get("rmssd", 0.0))
            }
        except Exception as e:
            print(f"[WatchSignalProcessor] HeartPy extraction warning: {e}")
            return {"mean_hr": 0.0, "sdnn": 0.0, "rmssd": 0.0}
        
    @staticmethod
    def process_raw_eda(eda_signal: np.ndarray, sample_rate: float = 4.0) -> Dict[str, float]:
        if eda_signal is None or len(eda_signal) < int(sample_rate * 4):
            return {"mean_eda": 0.0, "eda_num_peaks": 0}
            
        try:
            # Explicitly set sampling_rate=sample_rate (default in NK2 is 1000Hz)
            signals, info = nk.eda_process(eda_signal, sampling_rate=sample_rate)
            mean_eda = float(np.mean(eda_signal))
            num_peaks = int(np.sum(signals.get("SCR_Peaks", [0])))
            return {"mean_eda": mean_eda, "eda_num_peaks": num_peaks}
        except Exception as e:
            print(f"[WatchSignalProcessor] NeuroKit2 EDA extraction warning: {e}")
            return {"mean_eda": 0.0, "eda_num_peaks": 0}
        
    @staticmethod
    def process_accelerometer(acc_x: np.ndarray, acc_y: np.ndarray, acc_z: np.ndarray) -> float:
        """Calculates standard deviation of total acceleration magnitude."""
        try:
            mag = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
            return float(np.std(mag))
        except Exception:
            return 0.0