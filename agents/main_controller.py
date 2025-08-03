from sensor_agent import SensorAgent
from health_agent import HealthAgent
from reminder_agent import ReminderAgent
from care_assisstant_alert_agent import CareAssistantAlertAgent

import asyncio

async def main():
    sensor = SensorAgent("sensoragent@localhost", "sensoragentforpassword")
    health = HealthAgent("healthagent@localhost", "agentforpassword")
    reminder = ReminderAgent("reminderagent@localhost", "reminderagentforpassword")
    alert = CareAssistantAlertAgent("alertagent@localhost", "careagentforpassword")

    # Start the agents
    await sensor.start(auto_register=True)
    await health.start(auto_register=True)
    await reminder.start(auto_register=True)
    await alert.start(auto_register=True)

    print("Initializing agents...")
    await asyncio.sleep(60)  
    # run for 1 minute - 10 for sensor agent to send data, 
    # 20 for health agent to process, and 30 for reminder agent to receive

    await sensor.stop()
    await health.stop()
    await reminder.stop()
    await alert.stop()

if __name__ == "__main__":
    asyncio.run(main())
