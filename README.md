# Goal Oriented Elderly Care

**Goal-Oriented Agents for Real-Time Task Automation in Elderly Care**

This project implements a Goal-Oriented Multi-Agent System (MAS) for real-time dehydration monitoring and intervention in geriatric patients (age>=65). It combines a machine learning risk classifier, OWL ontology reasoning, PDDL-based care planning, and a multi-agent SPADE architecture streamed over Apache Kafka, with a role-based Plotly Dash dashboard for patients, caretakers, clinicians, and researchers.



### Technologies Used

- **OWL Ontology**: Developed using [Protégé](https://protege.stanford.edu/) to model elderly care concepts and relationships.
- **Machine Learning Model**: Integrated for intelligent decision-making and dehydration risk status prediction.
- **PDDL Planner**: Utilized for automated planning and goal-oriented task execution.
- **SPADE Agents**: Multi-agent system implemented with [Spade](https://spade-mas.readthedocs.io/en/latest/) for distributed reasoning and communication.
- **Apache Kafka**: Real-time streaming pipeline for sensor readings, alerts, and logs, powered by [Apache Kafka](https://kafka.apache.org/).
- **Plotly Dash**: Role-based monitoring dashboard (dark theme, 4 roles) built with [Plotly Dash](https://dash.plotly.com/).
- **Fernet (cryptography)**: Symmetric encryption for logged sensor data at rest using [Fernet](https://cryptography.io/en/latest/fernet/).

## Features

- **Machine learning model** (Random Forest, trained on real NHANES elderly biochemical data) for dehydration risk classification for intelligent decision-making and dehydration risk prediction
- **Ontology-based reasoning** using [Owlready2](https://owlready2.readthedocs.io/en/latest/) and Pellet reasoner for knowledge representation and inferring care actions from ML-assigned risk status
- **Automated planning** using PDDL Fast Downward for personalized, multi-step clinical care pathways
- **Multi-agent system** implemented with [Spade](https://spade-mas.readthedocs.io/en/latest/) for distributed reasoning, alerting, and coordination
- **Streaming Database** for real-time vitals, reminders, care alerts, and euhydrated logs, powered by [Apache Kafka](https://kafka.apache.org/)
- **Dynamic monitoring intervals** automatically adjusts each patient's sensor polling rate based on their current risk level
- **Multi-Patient Management** using 5 dehydration profiles providing distinct pathways (Euhydrated, Mild w/ ORS, Mild w/o ORS, Moderate, Severe) for demonstrating personalized care planning
- **Role-based dashboard** built using [Plotly Dash](https://dash.plotly.com/) with separate Patient, Family/Caretaker, Clinician, and Researcher views
- **Encrypted logging**: sensor data logged to CSV, encrypted at rest with Fernet
- **Error handling & fallbacks**: retry logic and fallback behavior for Kafka, ontology reasoning, and PDDL planning, with proactive email alerting on repeated failures
- **Structured JSON pipeline logs** per patient, capturing every stage of the ML → ontology → planner → routing pipeline
- **XMPP-based communication** for agent-to-agent interaction
- **Dockerized XMPP server** [Ejabberd](https://docs.ejabberd.im/) for easy setup for easy deployment


## Prerequisites

- **Python 3.13** (project developed and tested on this version; a virtual environment is recommended)
- **Rust** (required for SPADE installation)
    Install Rust: [https://rustup.rs/](https://rustup.rs/)
- **Docker** (for running the Ejabberd XMPP server)
- **Apache Kafka + Zookeeper** (local install, for streaming; see Kafka setup below)
- **Java** (required for the Pellet OWL reasoner; path is set via `.env`)
- **Protégé** (for editing OWL ontologies, optional but recommended)
    Download: [https://protege.stanford.edu/](https://protege.stanford.edu/)
- **Fast Downward PDDL Planner** (required for automated planning)
    Download: [https://www.fast-downward.org/](https://www.fast-downward.org/)
- **Trained Machine Learning Model** (provided in the repository at `ml_model/dehydration_model_rf.pkl` and can also be found [here](https://colab.research.google.com/drive/1JXv9FAQMFpbfxguE7TrwfwvMD-nEi-3y?usp=sharing))

## Installation

1. **Clone the repository**
     ```bash
     git clone <repository-url>
     cd GoalOrientedElderlyCare
     ```

2. **Create a virtual environment and install dependencies**
    ```bash
        python -m venv venv
        venv\Scripts\activate        # Windows
        source venv/bin/activate     # macOS/Linux
        pip install -r requirements.txt
    ```
 
3. **Set up the XMPP server**
     - Run Ejabberd using Docker:
    ```bash
            docker run -d --name ejabberd -p 5222:5222 -p 5280:5280 ejabberd/ecs
    ```
     - Ensure the Ejabberd ports are active and accessible.
 
4. **Set up Apache Kafka (local, with Zookeeper)**
     - Start Zookeeper and the Kafka broker locally.
     - On Windows, if you hit file-locking errors on restart:
    ```bash
            rd /s /q "kafka_db\kafka-logs"
    ```
 
5. **Configure environment variables**
     - Copy `.env.example` to `.env` and fill in your values (XMPP credentials, `KAFKA_SERVER`, `JAVA_PATH`, `FAST_DOWNWARD_PATH`, email alerting credentials, etc.).
     - `secret.key` (Fernet encryption key) is generated automatically on first run — do not commit it.
     - The system will refuse to start if required `.env` variables are missing.

## Agent Accounts

Register the following agent accounts on your XMPP server (JIDs and passwords configured via `.env`):
 
- `healthagent@localhost`
- `sensoragent1@localhost`
- `sensoragent2@localhost`
- `sensoragent3@localhost`
- `sensoragent4@localhost`
- `sensoragent5@localhost`
- `reminderagent@localhost`
- `careagent@localhost`

See `.env.example` for the full configuration template. Copy it to `.env` and fill in your own values before running the system.

## Patient Profiles
 
Four patient profiles are provided under `patients/`, each demonstrating a distinct dehydration pathway:
 
| No. | Patient | Pathway | Notes |
|---|---|---|---|
| 1 | Fatima Al-Rashid | Mild → ORS | Oral rehydration feasible |
| 2 | Ahmed Hassan | Mild → escalation | Dysphagia; no ORS, escalates to Moderate pathway |
| 3 | Margaret Osei | Moderate → hospital transfer | IV / Hypodermoclysis |
| 4 | Robert Mensah | Severe → emergency transfer | IV bolus / IO |
| 5 | Salman Mehfuz | Euhydrated | No Action Required |
 
Profiles are auto-loaded from `patients/*.json` via `patients/__init__.py`.
 
## Dynamic Monitoring Intervals
 
Each `SensorAgent`'s polling rate adjusts automatically based on that patient's most recent risk classification, rather than staying fixed:
 
| Risk level | Polling interval |
|---|---|
| Euhydrated | 60s |
| Mild | 30s |
| Moderate | 20s |
| Severe | 10s |
 
After each prediction, `HealthAgent` sends an `interval_update` message (tagged `ontology="interval_control"`) to the relevant `SensorAgent`, which adjusts its live `PeriodicSensor` behavior without restarting. Because of how SPADE schedules periodic behaviors, an interval change takes effect starting from the *next* reading after the one that triggered it, not the one immediately following the change — this is expected, not a bug.
 
## Usage
 
1. Start the XMPP server (Ejabberd) and the Kafka broker.
2. Run the main.py file to start all agents:
    ```bash
        python agents/main.py
    ```
3. In a separate terminal, run the dashboard:
    ```bash
        python visualization/dashboard.py
    ```
4. Agents will sense, classify, reason, plan, alert, and log in real time. Adjust `PATIENT_ID`/profiles under `patients/` to add or modify simulated patients.

To decrypt the logged CSV for offline analysis:
    ```bash
    python decrypt_csv.py
    ```

To view the Kafka topics in real time:
    ```bash
    python kafka_db/kafka_topic_viewer.py
    ```
 
## Dashboard
 
The Plotly Dash dashboard (`visualization/dashboard.py`, dark/CYBORG theme, auto-refreshes every 10s) offers four role-based views:
 
- **Patient** — a single status indicator and a plain-language message, no charts or jargon
- **Family/Caretaker** — status badge, plain message, and simple charts
- **Clinician** — full biomarker trends, risk distribution, and recent care plans
- **Researcher** — everything in Clinician, plus a fallback-health banner, ML prediction breakdown, and a filterable raw data table

## Security
 
- All credentials and paths are kept in `.env` (never committed; see `.env.example` for the template)
- Sensor data logged to CSV is encrypted at rest using Fernet (`secret.key`, auto-generated on first run, also never committed)
- `.gitignore` excludes `.env`, `secret.key`, `logs/`, `kafka-logs/`, `__pycache__/`, and `venv/`

***Remember to save your `secret.key` file in a secure location. If lost, you will not be able to decrypt your logged sensor data.***

## Error Handling
 
The system includes retry and fallback mechanisms for its three external dependencies:
 
- **Kafka**: 3-attempt retry with delay before falling back
- **Ontology reasoner (Pellet)**: falls back to a hardcoded action map mirroring the SWRL rules if reasoning fails
- **PDDL planner (Fast Downward)**: falls back to a minimal critical-steps plan if planning fails or times out

Repeated fallbacks trigger an email alert (via `alert_mailer.py`) and are surfaced on the Researcher dashboard view.

## Acknowledgements
 
- [Owlready2](https://owlready2.readthedocs.io/en/latest/)
- [Spade](https://spade-mas.readthedocs.io/en/latest/)
- [Ejabberd](https://www.ejabberd.im/)
- [Protégé](https://protege.stanford.edu/)
- [Fast Downward PDDL Planner](https://www.fast-downward.org/)
- [Apache Kafka](https://kafka.apache.org/)
- [Plotly Dash](https://dash.plotly.com/)
- [NHANES](https://wwwn.cdc.gov/nchs/nhanes/) (National Health and Nutrition Examination Survey)