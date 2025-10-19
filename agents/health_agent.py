from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from ml_model.model_utils import predict_dehydration_risk
from ontology.owl_reasoner import infer_risk_and_action
from pddl_planning.planner_runner import run_planner

from kafka_db.kafka_utils import KafkaLogger
import ast # for safely evaluating string representations of Python literals

class HealthAgent(Agent):

    """
    The HealthAgent is responsible for processing health data received from the sensor agent.
    It predicts dehydration risk based on the vitals data and routes the information to the appropriate agent.

    It uses the following components:
        - Machine Learning model to predict dehydration risk
        - Ontology to infer risk and action
        - PDDL planner to generate a plan for the action

    It communicates with the ReminderAgent for mild dehydration and the CareAgent for moderate or severe dehydration
    """
    class Processor(CyclicBehaviour):

        # Waiting for a message from the sensor agent
        async def run(self):
            msg = await self.receive(timeout=20)

            if msg:
                print(f"[Health] Received vitals: {msg.body}")

                try:
                    # Split the message body to get baseline and current weight
                    data = ast.literal_eval(msg.body)
                    baseline = data.get("baseline")
                    current = data.get("current")

                    # Predict TBW Loss % and risk from the trained ML model
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
                        KafkaLogger(topic='reminders').publish({"risk": risk, "action": action, "plan": plan})
                        print("[Health] Routing to ReminderAgent for Mild Dehydration")
                    elif risk in ["Moderate", "Severe"]:
                        to_jid = "careagent@localhost"
                        KafkaLogger(topic='care_alerts').publish({"risk": risk, "action": action, "plan": plan})
                        print(f"[Health] Routing to AlertAgent for {risk} Dehydration")
                    else:
                        print("[Health] No action required for Euhydrated status.")
                        return
                    
                    # Uncomment to debug Kafka publishing
                    # print(f"[DEBUG] Sent {risk} alert to topic: {'care_alerts' if risk in ['Moderate', 'Severe'] else 'reminders'}")

                    m = Message(to=to_jid)
                    m.set_metadata("performative", "inform")
                    m.body = f"{risk},{action},{plan}"
                    
                    await self.send(m)
                    print(f"[Health] Sent Message to {to_jid}")

                except Exception as e:
                    print(f"[Health] Error processing message: {e}")

    async def setup(self):
        print("[Health] HealthAgent starting...")

        print(f"[HealthAgent] Started as {str(self.jid)}")
        processor = self.Processor()

        template = Template()
        template.set_metadata("performative", "inform")

        self.add_behaviour(processor, template)
        print("[Health] HealthAgent ready to process health data")