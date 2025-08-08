from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message
import asyncio
import random
import logging

class SensorAgent(Agent):

    """
    The SensorAgent simulates a weight sensor that periodically sends weight readings to the HealthAgent.
    It uses a periodic behaviour to send readings every 10 seconds.
    The readings simulate a baseline weight of 72kg, with current values ranging from 63kg to 72kg.
    The TBW (Total Body Water) Loss percentage for these values would range from 0% to 12.5%.
    """
    class PeriodicSensor(PeriodicBehaviour):

        async def run(self):
            try:
                # Simulate a weight sensor reading
                baseline = 72
                current = round(max(0, baseline - random.uniform(0, 9)), 2)

                # Send the message to the health agent
                msg = Message(to="healthagent@localhost")
                # Set the performative of the message (ie) what the message is intended to do
                msg.set_metadata("performative", "inform")
                msg.body = f"{baseline},{current}"

                await self.send(msg)
                
                print(f"[Sensor] Baseline: {baseline}kg, Current: {current:.2f}kg")
                print(f"[Sensor] Message sent to health agent")
            
            except Exception as e:
                print(f"[Sensor] Error in sensor reading: {e}")
                logging.error(f"[Sensor] SensorAgent error: {e}")

    async def setup(self):
        # Add the periodic behaviour to the agent ie it will run every 10 seconds
        print("[Sensor] SensorAgent starting...")
        await asyncio.sleep(5) # Wait for other agents to start
        print("[Sensor] SensorAgent ready to collect data")
        self.add_behaviour(self.PeriodicSensor(period=1800))  # Run every 30 minutes
