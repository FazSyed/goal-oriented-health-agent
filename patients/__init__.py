import json
import glob
import os


def load_all_profiles() -> list:
    """
    Loads all patient JSON profiles from the patients/ directory.

    Returns:
    - list of dicts, one per patient profile
    """
    profiles = []
    pattern  = os.path.join(os.path.dirname(__file__), "patient_*.json")

    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                profile = json.load(f)
            profiles.append(profile)
            pid = profile.get("patient_id", "?")

            # DEBUGGING
            # print(f"[Profiles] Loaded patient_{pid}.json (Patient {pid}, age={profile.get('age')}, oral_intake_feasible={profile.get('oral_intake_feasible')})")
        except Exception as e:
            print(f"[Profiles] WARNING: Could not load {path}: {e}")

    # DEBUGGING
    # print(f"[Profiles] {len(profiles)} patient profile(s) loaded.")
    return profiles


ALL_PROFILES = load_all_profiles()