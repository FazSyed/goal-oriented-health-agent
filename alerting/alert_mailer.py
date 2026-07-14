import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SENDER = os.getenv("ALERT_EMAIL_SENDER")
PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD")
RECEIVER  = os.getenv("ALERT_EMAIL_RECEIVER")
THRESHOLD = int(os.getenv("ALERT_FALLBACK_THRESHOLD", "3"))

# Session based fallback counters
# Reset to 0 each time main_controller.py starts
# Email fires once per component per session when threshold is crossed; not on every single fallback after that
_session_counts = {
    "ontology": 0,
    "planner": 0,
    "kafka": 0,
}
_email_sent = {
    "ontology": False,
    "planner": False,
    "kafka": False,
}
# Track which patient IDs have triggered fallbacks per component this session
_session_patients = {
    "ontology": set(),
    "planner": set(),
    "kafka": set(),
}

def _validate_config() -> bool:
    '''Check if all required email env vars are set'''
    if not all([SENDER, PASSWORD, RECEIVER]):
        print("[AlertMailer] WARNING: Email alerting not configured. "
              "Set ALERT_EMAIL_SENDER, ALERT_EMAIL_PASSWORD, "
              "ALERT_EMAIL_RECEIVER in .env")
        return False
    return True
    
def _send_email(subject: str, body: str):
    '''Send plain-text email via Gmail SMTP'''
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER
        msg["To"] = RECEIVER
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER, PASSWORD)
            server.sendmail(SENDER, RECEIVER, msg.as_string())

        print(f"[AlertMailer] Alert email sent to {RECEIVER} : {subject}")

    except Exception as e:
        print(f"[AlertMailer] ERROR: Failed to send email: {e}")


def report_fallback(component: str, reason: str, patient_id = None):

    if component not in _session_counts:
        return
    # Record patient id for this component (if provided)
    try:
        if patient_id is not None:
            _session_patients[component].add(patient_id)
    except Exception:
        pass
    
    _session_counts[component] += 1
    count = _session_counts[component]

    print(f"[AlertMailer] Fallback count - {component}: {count}/{THRESHOLD}")

    # Only send email once per component per session
    if count >= THRESHOLD and not _email_sent[component]:
        _email_sent[component] = True
 
        if not _validate_config():
            return
 
        timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Determine patient string based on recorded patient ids for the component
        patients = _session_patients.get(component, set())
        if len(patients) == 0:
            patient_str = "Multiple patients"
        elif len(patients) == 1:
            patient_str = str(next(iter(patients)))
        else:
            patient_str = "Multiple patients"
 
        subject = (f"[MAS ALERT] {component.capitalize()} fallback "
                   f"threshold reached ({count} times)")
 
        body = f"""
Elderly Dehydration Monitoring MAS — System Alert
==================================================
Timestamp  : {timestamp}
Component  : {component.upper()}
Patient ID : {patient_str}
Fallbacks  : {count} (threshold: {THRESHOLD})
Last reason: {reason}
 
The {component} component has activated its fallback mechanism
{count} times this session. The system is still running using
fallback logic, but the underlying component may need attention.
 
What to check:
{"  • Verify Java is installed and JAVA_PATH in .env is correct" if component == "ontology" else ""}
{"  • Verify Fast Downward is installed and FAST_DOWNWARD_PATH in .env is correct" if component == "planner" else ""}
{"  • Verify Kafka broker is running at KAFKA_SERVER in .env" if component == "kafka" else ""}
  • Check logs/agent_system.log for detailed error messages
  • Check logs/patient_*_log.json for fallback_used entries
 
This is an automated alert from the MAS research prototype.
        """.strip()
 
        _send_email(subject, body)
 
 
def get_session_counts() -> dict:
    '''
    Returns current session fallback counts.
    Used by the dashboard banner to check recent fallback activity.
    '''
    return dict(_session_counts)
 
 
def reset_session():
    '''
    Resets all session counters and email flags.
    Call this if you want to re-arm alerting mid-session.
    Not called automatically; session resets on MAS restart.
    '''
    for key in _session_counts:
        _session_counts[key] = 0
        _email_sent[key] = False
        # clear patient tracking as well
        try:
            _session_patients[key].clear()
        except Exception:
            pass
    print("[AlertMailer] Session counters reset.")

if __name__== "__main__":
    # Test email sending
    reset_session()
    THRESHOLD = 1
    report_fallback("ontology", "Test email trigger", patient_id=4)