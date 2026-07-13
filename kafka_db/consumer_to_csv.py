from kafka import KafkaConsumer
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import json 
import pandas as pd 
import os 

load_dotenv()

KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")
CSV_PATH = os.getenv("CSV_PATH", os.path.join(os.path.dirname(__file__), '..', 'visualization', 'vitals_raw_log.csv'))

UPDATED_COLUMNS = [
    "timestamp", "patient_id",
    "sodium", "potassium", "chloride",
    "bun", "creatinine", "glucose",
    "age", "gender", "weight", "bmi"
]

def consume_and_save_to_csv(encryption_key: bytes = None):
    '''
    Consumes messages from the 'vitals_raw' Kafka topic and appends them to a CSV file.
    The CSV file is created if it does not already exist, with appropriate headers.
    The expected message format is a JSON object with fields: timestamp, patient_id, baseline, current.

    If encryption_key is provided, each row is encrypted using Fernet (AES-128) before being written to disk. 
    The CSV file stores one encrypted token per row rather than plaintext values.
    The dashboard decrypts rows on read using the same key.
 
    If no key is provided, rows are written as plaintext
 
    Parameters:
    - encryption_key : Fernet key bytes from main_controller.py loaded from secret.key on startup.
    '''

    fernet = Fernet(encryption_key) if encryption_key else None

    csv_file = os.path.abspath(CSV_PATH)

    # Create CSV file with headers if it doesn't exist
    if not os.path.exists(csv_file):
        pd.DataFrame(columns=UPDATED_COLUMNS).to_csv(csv_file, index=False)
        print(f"[CSV Consumer] Created new CSV at {csv_file}")

    # Instantiate the Kafka consumer with desired options
    consumer = KafkaConsumer(  
        'vitals_raw',  # topic to consume
        bootstrap_servers=[KAFKA_SERVER],  # Kafka bootstrap server address
        auto_offset_reset='earliest',  # start reading from the earliest offset if no committed offset exists
        group_id='csv_writer_group',  # consumer group id for offset commits and load balancing
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))  # deserialize bytes to Python dict via JSON
    )

    print("[CSV Consumer] Listening to vitals_raw topic...")

    try: 
        for msg in consumer: 
            # the deserialized message payload (expected to be a dict)
            data = msg.value  
            # map the expected fields into a row dictionary for CSV
            row = {  
                "timestamp": data.get("timestamp"), 
                "patient_id": data.get("patient_id"), 
                "sodium": data.get("sodium"),
                "potassium": data.get("potassium"),
                "chloride": data.get("chloride"),
                "bun": data.get("bun"),
                "creatinine": data.get("creatinine"),
                "glucose": data.get("glucose"),
                "age": data.get("age"),
                "gender": data.get("gender"),
                "weight": data.get("weight"),
                "bmi": data.get("bmi")
            }

            if fernet:
                # Encrypt the full row as a JSON string
                # Store as a single-column encrypted CSV row
                row_json = json.dumps(row).encode("utf-8")
                encrypted = fernet.encrypt(row_json).decode("utf-8")
                enc_df = pd.DataFrame([{"encrypted_row": encrypted}])
                enc_df.to_csv(csv_file, mode='a', header=False, index=False)
                print(f"[CSV Consumer] Encrypted row appended for patient_id={row.get('patient_id')}")

            else:
                # append the row to the CSV without writing the header
                pd.DataFrame([row]).to_csv(csv_file, mode='a', header=False, index=False)
                # log the appended row for visibility
                print(f"[CSV Consumer] Appended to CSV: {row}")

    except KeyboardInterrupt:
        print("[CSV consumer] Stopped.")
