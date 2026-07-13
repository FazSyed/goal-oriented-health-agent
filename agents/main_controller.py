import os
import asyncio
import logging
import threading
from threading import Thread
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables from .env file before other imports that require the env vars
load_dotenv()

from agents.sensor_agent import SensorAgent
from agents.health_agent import HealthAgent
from agents.reminder_agent import ReminderAgent
from agents.care_assisstant_alert_agent import CareAssistantAlertAgent
from patients import ALL_PROFILES
from kafka_db.consumer_to_csv import consume_and_save_to_csv

# ENCRYPTION SETUP

# Key is generated on first run and saved to secret.key
# Both .env and secret.key are gitignored
KEY_PATH = "secret.key"

def load_or_generate_key() -> bytes:
    """
    Loads the Fernet encryption key from secret.key if it exists.
    Generates and saves a new key on first run.
 
    WARNING: Losing secret.key means losing access to all
    encrypted CSV data. Back it up securely.
    """
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            key = f.read()
        print("[Security] Encryption key loaded from secret.key")
    else:
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as f:
            f.write(key)
        print("[Security] New encryption key generated and saved to secret.key")
        print("[Security] WARNING: Back up secret.key; Losing it means losing access to all encrypted data.")
    return key
 
ENCRYPTION_KEY = load_or_generate_key()

# Suppress daemon thread stderr lock error on Windows shutdown
original_excepthook = threading.excepthook

def suppress_shutdown_errors(args):
    if "could not acquire lock" in str(args.exc_value):
        return
    original_excepthook(args)
 
threading.excepthook = suppress_shutdown_errors

# LOGGING SETUP

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/agent_system.log'),
        logging.StreamHandler()
    ]
)

# AGENT CREDENTIALS

HEALTH_AGENT_JID = os.getenv("HEALTH_AGENT_JID", "healthagent@localhost")
HEALTH_AGENT_PASSWORD = os.getenv("HEALTH_AGENT_PASSWORD")
if not HEALTH_AGENT_PASSWORD:
    raise EnvironmentError("[Security] HEALTH_AGENT_PASSWORD not found in .env")
 
REMINDER_AGENT_JID = os.getenv("REMINDER_AGENT_JID", "reminderagent@localhost")
REMINDER_AGENT_PASSWORD = os.getenv("REMINDER_AGENT_PASSWORD")
if not REMINDER_AGENT_PASSWORD:
    raise EnvironmentError("[Security] REMINDER_AGENT_PASSWORD not found in .env")
 
ALERT_AGENT_JID = os.getenv("ALERT_AGENT_JID", "careagent@localhost")
ALERT_AGENT_PASSWORD = os.getenv("ALERT_AGENT_PASSWORD")
if not ALERT_AGENT_PASSWORD:
    raise EnvironmentError("[Security] ALERT_AGENT_PASSWORD not found in .env")
 
 
def get_sensor_credentials(patient_id: int) -> tuple:
    '''Read per-patient sensor agent JID and password from .env.'''
    jid = os.getenv(f"SENSOR_AGENT_{patient_id}_JID", f"sensoragent{patient_id}@localhost")
    password = os.getenv(f"SENSOR_AGENT_{patient_id}_PASSWORD")
    if not password:
        raise EnvironmentError(f"[Security] SENSOR_AGENT_{patient_id}_PASSWORD not found in .env")
    return jid, password

async def main():

    """
    Main controller for the Elderly Dehydration Monitoring System.

    This script initializes and starts all agents in the multi-agent system.
    It handles agent registration, startup, and shutdown processes.
    It also includes error handling and logging for better traceability.
    The system runs for 2 minutes before shutting down all agents.

    The following agents are utilized:
        - SensorAgent x N: Simulates biochemical parameters (Na, K, BUN, Cr, Glucose, etc.).
                        One per patient profile (loaded from patients/)
        - HealthAgent: Predicts dehydration risk from biochemical parameters,
                       infers care actions via OWL ontology, generates PDDL care plans
        - ReminderAgent: Sends reminders for Mild/Impending dehydration
        - CareAssistantAlertAgent: Alerts caregivers for Moderate/Severe dehydration
        
    The agents communicate via XMPP and are designed to work together in a cohesive manner.
    """

    print("=" * 60)
    print("🏥 ELDERLY DEHYDRATION MONITORING SYSTEM")
    print("🤖 Multi-Agent System Starting...")
    print("=" * 60)

    sensors = []

    try:

        sensors = [
             SensorAgent(
                jid = get_sensor_credentials(p["patient_id"])[0],
                password = get_sensor_credentials(p["patient_id"])[1],
                patient_profile = p
            )
            for p in ALL_PROFILES
        ]

        # sensor = SensorAgent("sensoragent@localhost", "sensoragentforpassword")
        health = HealthAgent(HEALTH_AGENT_JID, HEALTH_AGENT_PASSWORD)
        reminder = ReminderAgent(REMINDER_AGENT_JID, REMINDER_AGENT_PASSWORD)
        alert = CareAssistantAlertAgent(ALERT_AGENT_JID, ALERT_AGENT_PASSWORD)
        
        # Start all agents
        print("🚀 Starting agents...")
            
        await health.start(auto_register=True)
        print("✅ Health Agent started")
        
        await reminder.start(auto_register=True)
        print("✅ Reminder Agent started")
            
        await alert.start(auto_register=True)
        print("✅ Alert Agent started")

        for sensor in sensors:
            pid = sensor.patient_profile["patient_id"]
            await sensor.start(auto_register=True)
            print(f"✅ Sensor Agent started for Patient {pid}-{sensor.patient_profile.get('name', 'Unknown')}")
        
        print("Initializing all agents...")
            
        # Start Kafka consumer in a separate thread
        csv_consumer_thread = Thread(
            target=consume_and_save_to_csv,
            args=(ENCRYPTION_KEY,),
            daemon=True
        )
        csv_consumer_thread.start()
        
        print("📊 Kafka consumer running in background (saving to vitals_raw_log_phase2.csv)")
        
        print("Press Ctrl+C to stop the system at any time.")

        while True:
            await asyncio.sleep(2)  # Run the loop indefinitely

    except KeyboardInterrupt:
        print("\n⚠️  System interrupted by user")

    except Exception as e:
        print(f"❌ Error in main controller: {e}")
        logging.error(f"Main controller error: {e}")
    
    finally:
        print("\n🛑 Shutting down agents...")

        for sensor in sensors:
            try:
                pid = sensor.patient_profile["patient_id"]
                await sensor.stop()
                print(f"✅ Sensor Agent {pid} stopped")
            except:
                pass

        # wait for in-flight messages to drain
        await asyncio.sleep(2)
            
        try:
            await health.stop()
            print("✅ Health Agent stopped")
        except:
            pass
            
        try:
            await reminder.stop()
            print("✅ Reminder Agent stopped")
        except:
            pass
            
        try:
            await alert.stop()
            print("✅ Alert Agent stopped")
        except:
            pass

        print("✅ Kafka consumer stopped")
            
        print("🏁 System shutdown complete")   

if __name__ == "__main__":
    asyncio.run(main())
