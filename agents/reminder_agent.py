from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template
import logging
from datetime import datetime

class ReminderAgent(Agent):

    """
    The ReminderAgent is responsible for sending hydration reminders to the user based on the health agent's messages.
    It listens for messages from the health agent and processes them to send 
    reminders about hydration if the dehydration risk level is Mild.

    Role-Based Output:
        - Patient View  : simple plain-language reminder, no technical terms, no patient ID, no care plan details
        - Provider View : full clinical detail including risk label, recommended action, and structured care plan steps
    """
    class ReminderBehaviour(CyclicBehaviour):

        async def run(self):
            try:
                # Wait for a message from the health agent
                msg = await self.receive(timeout=30)

                if msg:

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    try:
                        # Split the message body into risk, action, and plan
                        risk, action, plan, patient_id = msg.body.split(",", 3)

                        # PATIENT VIEW
                        print(f"\n{'='*50}")
                        print(f"💧 [REMINDER] Your hydration levels are low.")
                        print(f"💧 Please drink an ORS (rehydration) solution now.")
                        print(f"💧 Rest and monitor your fluid intake.")
                        print(f"💧 If you feel worse, contact your healthcare provider.")
                        print(f"{'='*50}\n")

                        # HEALTHCARE PROVIDER VIEW
                        plan_steps = [line.strip() for line in plan.split("\n") if line.strip()]
 
                        print(f"{'='*50}")
                        print(f"🔵 [PROVIDER ALERT] Mild Dehydration — Patient ID: {patient_id}")
                        print(f"   Timestamp: {timestamp}")
                        print(f"   Risk Level: {risk}")
                        print(f"   Recommended Action: {action}")
                        print(f"   Care Plan:")
                        for i, step in enumerate(plan_steps, 1):
                            # Strip PDDL timestamp prefix (e.g. "0.00000: ") if present
                            clean = step.split(": ", 1)[-1] if ": " in step else step
                            print(f"     Step {i}: {clean}")
                        print(f"{'='*50}\n")

                        # Logging the Reminder
                        logging.info(f"HYDRATION REMINDER at {timestamp} for patient {patient_id} | Action: {action}")
                    
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