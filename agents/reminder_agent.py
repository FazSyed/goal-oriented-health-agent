from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

class ReminderAgent(Agent):
    class ReminderBehaviour(CyclicBehaviour):

        async def run(self):
            # Wait for a message from the health agent
            msg = await self.receive(timeout=30)

            if msg:
                # Split the message body into risk, action, and plan
                risk, action, plan = msg.body.split(",", 2)

                print(f"[Reminder] Risk={risk}, Action={action}")
                print("[Reminder] Plan:\n", plan)

    async def setup(self):
        self.add_behaviour(self.ReminderBehaviour())
