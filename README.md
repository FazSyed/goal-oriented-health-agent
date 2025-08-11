# Goal Oriented Elderly Care

This project provides a framework for goal-oriented elderly care using intelligent agents and ontology-based reasoning. The system leverages multi-agent communication and semantic technologies to support elderly care scenarios.

### Technologies Used

- **OWL Ontology**: Developed using [Protégé](https://protege.stanford.edu/) to model elderly care concepts and relationships.
- **Machine Learning Model**: Integrated for intelligent decision-making and dehydration risk status prediction.
- **PDDL Planner**: Utilized for automated planning and goal-oriented task execution.
- **SPADE Agents**: Multi-agent system implemented with [Spade](https://spade-mas.readthedocs.io/en/latest/) for distributed reasoning and communication.

## Features

- **Ontology-based reasoning** using [Owlready2](https://owlready2.readthedocs.io/en/latest/) for knowledge representation and inference
- **Automated planning** using a PDDL planner for goal-oriented task execution
- **Machine learning model** for intelligent decision-making and dehydration risk prediction
- **Multi-agent system** implemented with [Spade](https://spade-mas.readthedocs.io/en/latest/) for distributed reasoning and coordination
- **XMPP-based communication** for agent interaction
- **Dockerized XMPP server** (Ejabberd) for easy setup for easy deployment

## Prerequisites

- **Python 3.7+**
- **Rust** (required for Spade installation)  
    Install Rust: [https://rustup.rs/](https://rustup.rs/)
- **Docker** (for running the Ejabberd XMPP server)
- **Protégé** (for editing OWL ontologies, optional but recommended)  
    Download: [https://protege.stanford.edu/](https://protege.stanford.edu/)
- **PDDL Planner** (for automated planning; e.g., [Fast Downward](https://www.fast-downward.org/), optional if you want to run planning tasks)
- **Trained Machine Learning Model** (provided in the repository and can also be found [here](https://colab.research.google.com/drive/1DVTupGbRvht9y42A1_a-Kq_tIcT9-nI_?usp=sharing))

## Installation

1. **Clone the repository**
     ```bash
     git clone <repository-url>
     cd GoalOrientedElderlyCare
     ```

2. **Install dependencies**
     ```bash
     pip install owlready2
     pip install spade
     ```

3. **Set up the XMPP server**
     - Run Ejabberd using Docker:
         ```bash
         docker run -d --name ejabberd -p 5222:5222 -p 5280:5280 ejabberd/ecs
         ```
     - Ensure the Ejabberd ports are active and accessible.

## Agent Accounts

Register the following agent accounts on your XMPP server:

- `healthagent@localhost` / `agentforpassword`
- `sensoragent@localhost` / `sensoragentforpassword`
- `reminderagent@localhost` / `reminderagentforpassword`
- `careagent@localhost` / `careagentforpassword`

## Usage

1. Start the XMPP server (Ejabberd).
2. Run the main.py file to examine the multi-agent communication.
3. Agents will communicate and coordinate to provide elderly care functionalities with respect to Dehydration.

## Acknowledgements

- [Owlready2](https://owlready2.readthedocs.io/en/latest/)
- [Spade](https://spade-mas.readthedocs.io/en/latest/)
- [Ejabberd](https://www.ejabberd.im/)
- [Protégé](https://protege.stanford.edu/)
- [Fast Downward PDDL Planner](https://www.fast-downward.org/)