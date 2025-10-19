from kafka import KafkaConsumer
import json
import pandas as pd
import os

def consume_and_save_to_csv():
    topic = 'vitals_raw'
    csv_file = os.path.join(os.path.dirname(__file__), 'vitals_raw_log.csv')

    if not os.path.exists(csv_file):
        pd.DataFrame(columns=["timestamp","patient_id","baseline","current"]).to_csv(csv_file, index=False)

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='csv_writer_group',
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )

    print("CSV consumer listening...")

    try:
        for msg in consumer:
            data = msg.value
            row = {
                "timestamp": data.get("timestamp"),
                "patient_id": data.get("patient_id"),
                "baseline": data.get("baseline"),
                "current": data.get("current")
            }
            pd.DataFrame([row]).to_csv(csv_file, mode='a', header=False, index=False)
            print("Appended to CSV:", row)
    except KeyboardInterrupt:
        print("CSV consumer stopped.")
