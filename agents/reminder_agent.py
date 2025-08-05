from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template
import logging
import logging
from datetime import datetime

class ReminderAgent(Agent):
    class ReminderBehaviour(CyclicBehaviour):

        async def run(self):
            try:
                # Wait for a message from the health agent
                msg = await self.receive(timeout=30)

                if msg:

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    print(f"\n[Reminder] 🚨 === HYDRATION REMINDER ===")
                    
                    try:
                        # Split the message body into risk, action, and plan
                        risk, action, plan = msg.body.split(",", 2)

                        print(f"[Reminder] 💧 MILD HYDRATION ALERT 💧")
                        print(f"[Reminder] Risk Level: {risk}")
                        print(f"[Reminder] Recommended Action: {action}")
                        print(f"[Reminder] Care Plan: {plan}")

                        print(f"[Reminder] ‼️ Please Drink Water")
                            
                        print(f"[Reminder] === END REMINDER ===\n")

                        # Logging the Reminder
                        logging.info(f"HYDRATION REMINDER at {timestamp}")
                    
                    except Exception as e:
                        print(f"[Reminder] Failed to process message: {e}")

            except Exception as e:
                print(f"[Reminder] Error processing message: {e}")
                logging.error(f"[Reminder] ReminderAgent error: {e}")

    async def setup(self):
        print("[ALERT] ReminderAgent starting...")
        processor = self.ReminderBehaviour()

        template = Template()
        template.set_metadata("performative", "inform")
        
        self.add_behaviour(processor, template)
        print("[Reminder] ReminderAgent ready to send hydration reminders")