from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from ml_model.model_utils import predict_dehydration_risk
from ontology.owl_reasoner import infer_risk_and_action
from pddl_planning.planner_runner import run_planner

class HealthAgent(Agent):
    class Processor(CyclicBehaviour):
        # Waits for a message from the sensor agent, 
        # processes it, and sends a response to the reminder agent.
        
        # Waiting for a message from the sensor agent
        async def run(self):
            msg = await self.receive(timeout=20)

            if msg:
                print(f"[Health] Received vitals: {msg.body}")

                try:
                    # Split the message body to get baseline and current weight
                    baseline_str, current_str = msg.body.split(",")
                    baseline = float(baseline_str.strip())
                    current = float(current_str.strip())

                    # predict TBW Loss % and risk from the trained ML model
                    _, _, tbw_pct = predict_dehydration_risk(baseline, current)
                    # Infer risk and action from the ontology
                    risk, action = infer_risk_and_action(tbw_pct)
                    print(f"[Health] Risk={risk}, Action={action}")
                    
                    if risk is None:
                        print("[Health] No action required for Euhydrated status.")
                        return

                    # Run the PDDL planner to get a plan for the action
                    plan = run_planner(risk)

                    if plan is not None:
                        plan = plan.replace("\n", " ")
                    else:
                        plan = ""

                    if (risk == "Mild"):
                        to_jid = "reminderagent@localhost"
                    elif risk in ["Moderate", "Severe"]:
                        to_jid = "careagent@localhost"
                    else:
                        print("[Health] No action required for Euhydrated status.")
                        return
                    
                    m = Message(to=to_jid)
                    m.set_metadata("performative", "inform")
                    m.body = f"{risk},{action},{plan}"
                    
                    await self.send(m)
                    print(f"[Health] Sent action to {to_jid}")

                except Exception as e:
                    print(f"[Health] Error processing message: {e}")

    async def setup(self):
        print("[Health] Agent started and ready.")
        processor = self.Processor()

        template = Template()
        template.set_metadata("performative", "inform")

        self.add_behaviour(processor, template)
