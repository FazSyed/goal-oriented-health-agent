from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message
import asyncio, random, time, logging

from kafka_db.kafka_utils import KafkaLogger

class SensorAgent(Agent):
    class PeriodicSensor(PeriodicBehaviour):

        """
        The SensorAgent simulates a weight sensor that periodically sends weight readings to the HealthAgent.
        It uses a periodic behaviour to send readings every 20 seconds.
        The readings simulate a baseline weight of 72kg, with current values ranging from 63kg to 72kg.
        The TBW (Total Body Water) Loss percentage for these values would range from 0% to 12.5%.
        """
        async def run(self):
            try:
                # Simulate a weight sensor reading
                baseline = 72.0
                current = round(max(0, baseline - random.uniform(0, 9)), 2)
                patient_id = 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                # Prepare data to send to HealthAgent and Kafka logger
                data = {
                    "patient_id": patient_id,
                    "baseline": baseline,
                    "current": current,
                    "timestamp": timestamp
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
        self.add_behaviour(self.PeriodicSensor(period=10))  # 10 seconds interval for sensor readings