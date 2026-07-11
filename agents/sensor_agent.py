from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message
import asyncio, random, time, logging

from kafka_db.kafka_utils import KafkaLogger

# Default biochemical ranges used as fallback if patient profile does not specify its own ranges
DEFAULT_RANGES = {
    "sodium_range":     [135, 165],
    "potassium_range":  [3.5, 5.5],
    "chloride_range":   [98, 115],
    "bun_range":        [10, 65],
    "creatinine_range": [0.6, 6.0],
    "glucose_range":    [80, 300],
}

class SensorAgent(Agent):

    def __init__(self, jid, password, patient_profile, **kwargs):
        # Initialize the SensorAgent with patient profile and biochemical ranges
        # super() calls the parent class constructor to set up the agent with its JID and password
        super().__init__(jid, password, **kwargs)
        self.patient_profile = patient_profile
    
    class PeriodicSensor(PeriodicBehaviour):
        async def run(self):
            try:
                profile = self.agent.patient_profile
                patient_id = profile.get("patient_id")
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                def get_range(key):
                    return profile.get(key, DEFAULT_RANGES[key])

                # Simulate biochemical parameters
                # Values randomly drawn from ranges covering all 4 risk classes
                # Based on NHANES training data distributions

                data = {
                    "patient_id": patient_id,
                    "timestamp": timestamp,

                    "sodium": round(random.uniform(*get_range("sodium_range")), 1),
                    "potassium": round(random.uniform(*get_range("potassium_range")), 1),
                    "chloride": round(random.uniform(*get_range("chloride_range")), 1),
                    "bun": round(random.uniform(*get_range("bun_range")), 1),
                    "creatinine": round(random.uniform(*get_range("creatinine_range")), 2),
                    "glucose": round(random.uniform(*get_range("glucose_range")), 1),

                    "age": profile.get("age"),
                    "gender": profile.get("gender"),
                    "weight": profile.get("weight"),
                    "bmi": profile.get("bmi"),
                
                    # Patient capability flag (from patient profile) -- used in PDDL planning
                    # True  = patient can swallow safely → ORS path for Mild
                    # False = dysphagia / altered consciousness → escalate
                    "oral_intake_feasible": profile.get("oral_intake_feasible", True),
                }

                # Send the message to the health agent
                msg = Message(
                    to="healthagent@localhost",
                    body=str(data),
                    # Set the performative of the message (ie) what the message is intended to do
                    metadata={"performative": "inform", "ontology": "vitals"}
                )
                await self.send(msg)
                print(f"[SensorAgent-{patient_id}] Sent to HealthAgent: {data}")

                # Also publish to Kafka
                self.agent.kafka_logger.publish(data)
                KafkaLogger(topic='sensor_data').publish(data)
                
            except Exception as e:
                pid = self.agent.patient_profile.get("patient_id", "?")
                print(f"[SensorAgent-{pid}] Error in sensor reading: {e}")
                logging.error(f"[SensorAgent-{pid}] Error: {e}")

    async def setup(self):
        pid = self.patient_profile.get("patient_id")

        # Add the periodic behaviour to the agent ie it will run every 10 seconds
        print(f"[SensorAgent-{pid}] Starting...")
        print(f"[SensorAgent-{pid}] Started as {str(self.jid)}")

        await asyncio.sleep(5) # Wait for other agents to start

        print(f"[SensorAgent-{pid}] SensorAgent ready to collect data")

        self.kafka_logger = KafkaLogger(topic='vitals_raw') # log in csv file
        self.add_behaviour(self.PeriodicSensor(period=30))  # 30 seconds interval for sensor readings