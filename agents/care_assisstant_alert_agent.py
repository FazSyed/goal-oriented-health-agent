from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template
import logging
from datetime import datetime

class CareAssistantAlertAgent(Agent):
    class AlertBehaviour(CyclicBehaviour):
       
        async def run(self):
            try:
                # Wait for a message from the health agent
                msg = await self.receive(timeout=30)

                if msg:

                    # Get the current timestamp for logging
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    print(f"\n[ALERT] 🚨 === CARE ASSISTANT ALERT ===")

                    try:
                        # Split the message body into risk, action, and plan
                        risk, action, plan = msg.body.split(",", 2)

                        if (risk == "Moderate"):
                            print(f"[ALERT] 🔴 MODERATE DEHYDRATION ALERT 🔴")
                            print(f"[ALERT] Risk Level: {risk}")
                            print(f"[ALERT] Recommended Action: {action}")
                        elif (risk == "Severe"):
                            print(f"[ALERT] 🔴 SEVERE DEHYDRATION ALERT 🔴")
                            print(f"[ALERT] Risk Level: {risk}")
                            print(f"[ALERT] Recommended Action: {action}")

                        print(f"[ALERT] Care Plan: {plan}")
                        print(f"[ALERT] === END ALERT ===\n")

                        # Logging the Alert
                        if risk == "Severe":
                            logging.critical(f"SEVERE DEHYDRATION ALERT at {timestamp}")
                        else:
                            logging.warning(f"MODERATE DEHYDRATION ALERT at {timestamp}")

                    except Exception as e:
                        print(f"[ALERT] Failed to process message: {e}")

            except Exception as e:
                print(f"[ALERT] Error in alert behavior: {e}")
                logging.error(f"AlertAgent error: {e}")

    async def setup(self):
        print("[ALERT] CareAssistantAlertAgent starting...")
        processor = self.AlertBehaviour()
        
        template = Template()
        template.set_metadata("performative", "inform")
        
        self.add_behaviour(processor, template)
        print("[ALERT] CareAssistantAlertAgent ready for emergency alerts")
