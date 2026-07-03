from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template
import logging
from datetime import datetime

class CareAssistantAlertAgent(Agent):

    """
    The CareAssistantAlertAgent is responsible for sending emergency reminders to the user based on the health agent's messages.
    It listens for messages from the health agent and processes them to send warnings or emergencies
    if the dehydration risk level is Moderate or Severe.

    Role-Based Output:
    - Patient View: simple plain-language warning or emergency message, no patient ID, no clinical jargon, no care plan details
    - Provider View: full clinical detail including risk label, recommended action, and structured care plan steps with severity icon
    """
    class AlertBehaviour(CyclicBehaviour):
       
        async def run(self):
            try:
                # Wait for a message from the health agent
                msg = await self.receive(timeout=30)

                if msg:

                    # Get the current timestamp for logging
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    try:
                        # Split the message body into risk, action, and plan
                        risk, action, plan, patient_id = msg.body.split(",", 3)

                        # PATIENT VIEW
                        print(f"\n{'='*50}")

                        if risk == "Moderate":
                            print(f"🟠 [WARNING] Your hydration levels are concerning.")
                            print(f"🟠 Please contact your healthcare provider immediately.")
                            print(f"🟠 Do not attempt to self-treat, you may need medical fluids.")
                            print(f"🟠 If you feel faint or confused, call for help now.")

                        elif risk == "Severe":
                            print(f"🔴 [EMERGENCY] Your hydration levels are critically low.")
                            print(f"🔴 Emergency services are being contacted.")
                            print(f"🔴 Do not move. Stay calm and wait for assistance.")
                            print(f"🔴 If someone is with you, ask them to stay.")

                        print(f"{'='*50}\n")

                        # HEALTHCARE PROVIDER VIEW
                        plan_steps = [line.strip() for line in plan.split("\n") if line.strip()]
 
                        icon = "🔴" if risk == "Severe" else "🟠"
 
                        print(f"{'='*50}")
                        print(f"{icon} [PROVIDER ALERT] {risk} Dehydration — Patient ID: {patient_id}")
                        print(f"   Timestamp: {timestamp}")
                        print(f"   Risk Level: {risk}")
                        print(f"   Recommended Action: {action}")
                        print(f"   Care Plan:")
                        for i, step in enumerate(plan_steps, 1):
                            # Strip PDDL timestamp prefix (e.g. "0.00000: ") if present
                            clean = step.split(": ", 1)[-1] if ": " in step else step
                            print(f"     Step {i}: {clean}")
                        print(f"{'='*50}\n")

                        # Logging the Alert
                        if risk == "Severe":
                            logging.critical(f"SEVERE DEHYDRATION ALERT at {timestamp} for patient {patient_id} | Action: {action}")
                        else:
                            logging.warning(f"MODERATE DEHYDRATION ALERT at {timestamp} for patient {patient_id} | Action: {action}")

                    except Exception as e:
                        print(f"[ALERT] Failed to process message: {e}")

            except Exception as e:
                print(f"[ALERT] Error in alert behavior: {e}")
                logging.error(f"CareAssistantAlertAgent error: {e}")

    async def setup(self):
        print("[ALERT] CareAssistantAlertAgent starting...")
        processor = self.AlertBehaviour()
        
        template = Template()
        template.set_metadata("performative", "inform")
        
        self.add_behaviour(processor, template)
        print("[ALERT] CareAssistantAlertAgent ready for emergency alerts")
