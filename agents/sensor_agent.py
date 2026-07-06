from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message
import asyncio, random, time, logging

from kafka_db.kafka_utils import KafkaLogger

class SensorAgent(Agent):
    class PeriodicSensor(PeriodicBehaviour):
        async def run(self):
            try:
                patient_id = 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                # Simulate biochemical parameters
                # Values randomly drawn from ranges covering all 4 risk classes
                # Based on NHANES training data distributions
                data = {
                    "patient_id": patient_id,
                    "timestamp":  timestamp,
                    "sodium":     round(random.uniform(135, 165), 1),
                    "potassium":  round(random.uniform(3.5, 5.5),  1),
                    "chloride":   round(random.uniform(98, 115),   1),
                    "bun":        round(random.uniform(10, 65),    1),
                    "creatinine": round(random.uniform(0.6, 6.0),  2),
                    "glucose":    round(random.uniform(80, 300),   1),
                    "age":        72,       # fixed patient profile
                    "gender":     2,        # fixed patient profile (2 = Female)
                    "weight":     65.0,     # fixed patient profile
                    "bmi":        26.5,     # fixed patient profile

                    # Patient capability flag (from patient profile) -- used in PDDL planning
                    # True  = patient can swallow safely → ORS path for Mild
                    # False = dysphagia / altered consciousness → escalate
                    
                    "oral_intake_feasible": True  # fixed patient profile
                }

                # Send the message to the health agent
                msg = Message(
                    to="healthagent@localhost",
                    body=str(data),
                    # Set the performative of the message (ie) what the message is intended to do
                    metadata={"performative": "inform", "ontology": "vitals"}
                )
                await self.send(msg)
                print(f"[SensorAgent] Sent to HealthAgent: {data}")

                # Also publish to Kafka
                self.agent.kafka_logger.publish(data)
                KafkaLogger(topic='sensor_data').publish(data)
                
            except Exception as e:
                print(f"[Sensor] Error in sensor reading: {e}")
                logging.error(f"[Sensor] SensorAgent error: {e}")

    async def setup(self):
        # Add the periodic behaviour to the agent ie it will run every 10 seconds
        print("[Sensor] SensorAgent starting...")
        print(f"[SensorAgent] Started as {str(self.jid)}")

        await asyncio.sleep(5) # Wait for other agents to start

        print("[Sensor] SensorAgent ready to collect data")

        self.kafka_logger = KafkaLogger(topic='vitals_raw') # log in csv file
        self.add_behaviour(self.PeriodicSensor(period=20))  # 20 seconds interval for sensor readings