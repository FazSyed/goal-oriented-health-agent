from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from ml_model.model_utils import predict_dehydration_risk
from ontology.owl_reasoner import infer_risk_and_action
from pddl_planning.planner_runner import run_planner

from kafka_db.kafka_utils import KafkaLogger
import ast

class HealthAgent(Agent):
    class Processor(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=20)

            if msg:
                print(f"[Health] Received vitals: {msg.body}")

                try:
                    # Unpack biochemical parameters from message
                    data = ast.literal_eval(msg.body)

                    sodium     = data.get("sodium")
                    potassium  = data.get("potassium")
                    chloride   = data.get("chloride")
                    bun        = data.get("bun")
                    creatinine = data.get("creatinine")
                    glucose    = data.get("glucose")
                    age        = data.get("age")
                    gender        = data.get("gender")
                    weight     = data.get("weight")
                    bmi        = data.get("bmi")
                    oral_intake_feasible = data.get("oral_intake_feasible")

                    # Predict risk from biochemical parameters
                    _, prediction_label = predict_dehydration_risk(
                        sodium, potassium, chloride, bun,
                        creatinine, glucose, age, gender, weight, bmi
                    )
                    print(f"[Health] ML Prediction: {prediction_label}")

                    # Pass ML label directly to ontology
                    # Ontology infers triggersAction from hasRiskStatus
                    risk, action = infer_risk_and_action(prediction_label)
                    print(f"[Health] Risk={risk}, Action={action}")

                    # Run PDDL planner
                    plan = run_planner(
                        risk_status = risk,
                        oral_intake_feasible = oral_intake_feasible
                    )
                    if plan is None:
                        plan = ""

                    # Route to appropriate agent
                    if risk == "Euhydrated":
                        # No agent routing, only logs to Kafka and return
                        KafkaLogger(topic='vitals_raw').publish(
                            {"risk": risk, "action": action, "plan": plan}
                        )
                        print("[Health] Euhydrated — no agent routing required.")
                        return
                    
                    elif risk == "Mild":
                        to_jid = "reminderagent@localhost"
                        KafkaLogger(topic='reminders').publish(
                            {"risk": risk, "action": action, "plan": plan}
                        )
                        print("[Health] Routing to ReminderAgent for Mild Dehydration")

                    elif risk in ["Moderate", "Severe"]:
                        to_jid = "careagent@localhost"
                        KafkaLogger(topic='care_alerts').publish(
                            {"risk": risk, "action": action, "plan": plan}
                        )
                        print(f"[Health] Routing to AlertAgent for {risk} Dehydration")

                    else:
                        print(f"[Health] Unknown risk label: {risk}. No routing performed.")
                        return

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