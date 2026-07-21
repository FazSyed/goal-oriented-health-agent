from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from ml_model.model_utils import predict_dehydration_risk
from ontology.owl_reasoner import infer_risk_and_action
from pddl_planning.planner_runner import run_planner
from patients import ALL_PROFILES

from kafka_db.kafka_utils import KafkaLogger

from logger import log_pipeline_run, build_vitals_dict

import ast, os, logging

# Risk label -> target sensor polling interval (seconds)
INTERVAL_MAP = {
    "Euhydrated": 60,
    "Mild": 30,
    "Moderate": 20,
    "Severe": 10,
}

SENSOR_JID_BY_PATIENT = {
    p["patient_id"]: os.getenv(f"SENSOR_AGENT_{p['patient_id']}_JID") for p in ALL_PROFILES
}

class HealthAgent(Agent):
    class Processor(CyclicBehaviour):
        
        async def update_sensor_interval(self, patient_id, risk):
            target_period = INTERVAL_MAP.get(risk)
            if target_period is None:
                print(f"[Health] Unknown risk '{risk}' for patient {patient_id} -- skipping interval update")
                return

            sensor_jid = SENSOR_JID_BY_PATIENT.get(patient_id)
            if not sensor_jid:
                print(f"[Health] No sensor JID configured for patient {patient_id} -- skipping interval update")
                logging.warning(f"[Health] No sensor JID configured for patient {patient_id}")
                return

            m = Message(to=sensor_jid)
            m.set_metadata("performative", "inform")
            m.set_metadata("ontology", "interval_control")
            m.body = str(target_period)

            await self.send(m)
            print(f"[Health] Sent interval_update({target_period}s) to {sensor_jid} (risk={risk})")

        async def run(self):
            msg = await self.receive(timeout=20)

            if msg:
                print(f"[Health] Received vitals: {msg.body}")

                try:
                    # Unpack biochemical parameters from message
                    data = ast.literal_eval(msg.body)

                    patient_id = data.get("patient_id")
                    sodium     = data.get("sodium")
                    potassium  = data.get("potassium")
                    chloride   = data.get("chloride")
                    bun        = data.get("bun")
                    creatinine = data.get("creatinine")
                    glucose    = data.get("glucose")
                    age        = data.get("age")
                    gender     = data.get("gender")
                    weight     = data.get("weight")
                    bmi        = data.get("bmi")
                    oral_intake_feasible = data.get("oral_intake_feasible")

                    # Build a dictionary of vitals for logging purposes
                    vitals = build_vitals_dict(data)

                    # Predict risk from biochemical parameters
                    _, prediction_label = predict_dehydration_risk(
                        sodium, potassium, chloride, bun,
                        creatinine, glucose, age, gender, weight, bmi
                    )
                    print(f"[Health] ML Prediction: {prediction_label}")

                    # Pass ML label directly to ontology
                    # Ontology infers triggersAction from hasRiskStatus
                    risk, action, ontology_meta = infer_risk_and_action(prediction_label, patient_id=patient_id)
                    print(f"[Health] Risk={risk}, Action={action}")

                    # Update this patient's sensor polling interval based on risk
                    # Runs for every risk label (Euhydrated included), before any branch-specific routing logic below.
                    await self.update_sensor_interval(patient_id, risk)

                    # Log the ontology result for this patient
                    ontology_result = {"risk": risk, "action": action, "fallback_used": ontology_meta["fallback_used"], "fallback_reason": ontology_meta["fallback_reason"]}

                    # Run PDDL planner
                    plan, planner_meta = run_planner(
                        risk_status = risk,
                        oral_intake_feasible = oral_intake_feasible,
                        patient_id = patient_id
                    )

                    if plan is None:
                        plan = ""

                    # Split the plan into lines and count them for logging
                    plan_lines = [line for line in plan.splitlines() if line.strip()]

                    # Log the planner result for this patient
                    planner_result = {"plan": plan, "step_count": len(plan_lines), "fallback_used": planner_meta["fallback_used"], "fallback_reason": planner_meta["fallback_reason"]}
                    
                    # Initialize routing result dictionary
                    routing_result = {"routed_to": None, "kafka_topic": None, "kafka_publish_success": False}

                    # Route to appropriate agent
                    if risk == "Euhydrated":
                        # No agent routing, only logs to Kafka and return
                        kafka_sucess = KafkaLogger(topic='euhydrated_log').publish(
                            {"patient_id": patient_id, "risk": risk, "action": action, "plan": plan}
                        )
                        
                        # Update routing result for logging
                        routing_result.update({"routed_to": None, "kafka_topic": "euhydrated_log", "kafka_publish_success": kafka_sucess})

                        print(f"[Health] 🟢 Euhydrated -- No Agent routing required for patient {patient_id} 🟢")

                        # Log the entire pipeline run for this patient
                        log_pipeline_run(
                            patient_id      = patient_id,
                            vitals          = vitals,
                            ml_prediction   = prediction_label,
                            ontology_result = ontology_result,
                            planner_result  = planner_result,
                            routing_result  = routing_result,
                        )

                        return
                    
                    elif risk == "Mild":
                        to_jid = "reminderagent@localhost"
                        # Send to Kafka topic for reminders
                        kafka_success = KafkaLogger(topic='reminders').publish(
                            {"patient_id": patient_id, "risk": risk, "action": action, "plan": plan}
                        )

                        # Update routing result for logging
                        routing_result.update({"routed_to": to_jid, "kafka_topic": "reminders", "kafka_publish_success": kafka_success})
                        print("[Health] Routing to ReminderAgent for Mild Dehydration")

                    elif risk in ["Moderate", "Severe"]:
                        to_jid = "careagent@localhost"
                        # Send to Kafka topic for care alerts
                        kafka_success = KafkaLogger(topic='care_alerts').publish(
                            {"patient_id": patient_id, "risk": risk, "action": action, "plan": plan}
                        )
                        # Update routing result for logging
                        routing_result.update({"routed_to": to_jid, "kafka_topic": "care_alerts", "kafka_publish_success": kafka_success})
                        print(f"[Health] Routing to AlertAgent for {risk} Dehydration")

                    else:
                        print(f"[Health] Unknown risk label: {risk}. No routing performed.")

                        # Log the entire pipeline run for this patient even if routing failed
                        log_pipeline_run(
                            patient_id      = patient_id,
                            vitals          = vitals,
                            ml_prediction   = prediction_label,
                            ontology_result = ontology_result,
                            planner_result  = planner_result,
                            routing_result  = routing_result,
                        )
                        return

                    m = Message(to=to_jid)
                    m.set_metadata("performative", "inform")
                    m.body = f"{risk},{action},{plan},{patient_id}"

                    await self.send(m)
                    print(f"[Health] Sent Message to {to_jid}")
                    
                    # Log the entire pipeline run for this patient
                    log_pipeline_run(
                        patient_id      = patient_id,
                        vitals          = vitals,
                        ml_prediction   = prediction_label,
                        ontology_result = ontology_result,
                        planner_result  = planner_result,
                        routing_result  = routing_result,
                    )

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