from agents.sensor_agent import SensorAgent
from agents.health_agent import HealthAgent
from agents.reminder_agent import ReminderAgent
from agents.care_assisstant_alert_agent import CareAssistantAlertAgent

import asyncio
import logging
from threading import Thread
from kafka_db.consumer_to_csv import consume_and_save_to_csv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/agent_system.log'),
        logging.StreamHandler()
    ]
)

async def main():

    """
    Main controller for the Elderly Dehydration Monitoring System.

    This script initializes and starts all agents in the multi-agent system.
    It handles agent registration, startup, and shutdown processes.
    It also includes error handling and logging for better traceability.
    The system runs for 2 minutes before shutting down all agents.

    The following agents are utilized:
        - SensorAgent: Simulates biochemical parameters (Na, K, BUN, Cr, Glucose, etc.)
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

    try:
        sensor = SensorAgent("sensoragent@localhost", "sensoragentforpassword")
        health = HealthAgent("healthagent@localhost", "agentforpassword")
        reminder = ReminderAgent("reminderagent@localhost", "reminderagentforpassword")
        alert = CareAssistantAlertAgent("careagent@localhost", "careagentforpassword")
        
        # Start all agents
        print("🚀 Starting agents...")
            
        await health.start(auto_register=True)
        print("✅ Health Agent started")
        
        await reminder.start(auto_register=True)
        print("✅ Reminder Agent started")
            
        await alert.start(auto_register=True)
        print("✅ Alert Agent started")

        await sensor.start(auto_register=True)
        print("✅ Sensor Agent started")
        
        print("Initializing all agents...")
            
        # Start Kafka consumer in a separate thread
        csv_consumer_thread = Thread(target=consume_and_save_to_csv, daemon=True)
        csv_consumer_thread.start()
        
        print("📊 Kafka consumer running in background (saving to sensor_data.csv)")
        
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
        try:
            await sensor.stop()
            print("✅ Sensor Agent stopped")
        except:
            pass
            
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
