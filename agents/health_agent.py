from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
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
                # Split the message body to get baseline and current weight
                baseline, current = map(float, msg.body.split(","))
                # predict TBW Loss % and risk from the trained ML model
                code, label, tbw_pct = predict_dehydration_risk(baseline, current)
                # Infer risk and action from the ontology
                risk, action = infer_risk_and_action("./ontology/healthagent.owl", tbw_pct)
                print(f"[Health] Risk={risk}, Action={action}")
                
                # Run the PDDL planner to get a plan for the action
                plan = run_planner(risk)
                
                # Send the plan to the reminder agent
                m = Message(to="reminderagent@localhost")
                m.set_metadata("performative", "inform")
                m.body = f"{risk},{action},{plan}"
                
                await self.send(m)

    async def setup(self):
        self.add_behaviour(self.Processor())
