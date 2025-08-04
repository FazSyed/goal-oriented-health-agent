from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

class CareAssistantAlertAgent(Agent):
    class AlertBehaviour(CyclicBehaviour):
       
        async def run(self):
                # Wait for a message from the health agent
                msg = await self.receive(timeout=30)

                if msg:
                    try:
                        # Split the message body into risk, action, and plan
                        risk, action, plan = msg.body.split(",", 2)

                        print(f"[ALERT] Risk={risk}, Action={action}")

                        if (risk == "Moderate"):
                            print("[ALERT] Hydration level is Moderate, please drink water.")
                        elif (risk == "Severe"):
                            print("[ALERT] Hydration level is Severe, immediate action required! Alerting care assistant.")

                        print("[ALERT] Plan:\n", plan)
                    except Exception as e:
                        print("[ALERT] Failed to process message:", e)

    async def setup(self):
        print("[ALERT] CareAssistantAlertAgent started.")
        processor = self.AlertBehaviour()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(processor, template)
