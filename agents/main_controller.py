from agents.sensor_agent import SensorAgent
from agents.health_agent import HealthAgent
from agents.reminder_agent import ReminderAgent
from agents.care_assisstant_alert_agent import CareAssistantAlertAgent

import asyncio
import logging

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
        - SensorAgent: Monitors hydration levels and sends data to the health agent.
        - HealthAgent: Analyzes health data, provides recommendations, and alerts appropriate agents (reminder or care assistant).
        - ReminderAgent: Sends reminders for hydration (Mild Dehydration).
        - CareAssistantAlertAgent: Alerts caregivers in case of critical conditions (Moderate/Severe Dehydration).
        
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
        await asyncio.sleep(120) # Run for 2 minutes

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
            
        print("🏁 System shutdown complete")   

if __name__ == "__main__":
    asyncio.run(main())
