from kafka import KafkaConsumer
import json 
import pandas as pd 
import os 

def consume_and_save_to_csv():
    '''
    Consumes messages from the 'vitals_raw' Kafka topic and appends them to a CSV file.
    The CSV file is created if it does not already exist, with appropriate headers.
    The expected message format is a JSON object with fields: timestamp, patient_id, baseline, current.
    '''

    topic = 'vitals_raw'  # Kafka topic to subscribe to
    csv_file = os.path.join(os.path.dirname(__file__), 'vitals_raw_log.csv')  # Path to CSV file

    # Create CSV file with headers if it doesn't exist
    if not os.path.exists(csv_file):
        pd.DataFrame(columns=["timestamp","patient_id","baseline","current"]).to_csv(csv_file, index=False)

    # Instantiate the Kafka consumer with desired options
    consumer = KafkaConsumer(  
        topic,  # topic to consume
        bootstrap_servers=['localhost:9092'],  # Kafka bootstrap server address
        auto_offset_reset='earliest',  # start reading from the earliest offset if no committed offset exists
        group_id='csv_writer_group',  # consumer group id for offset commits and load balancing
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))  # deserialize bytes to Python dict via JSON
    )

    print("CSV consumer listening...")

    try: 
        for msg in consumer: 
            # the deserialized message payload (expected to be a dict)
            data = msg.value  
            # map the expected fields into a row dictionary for CSV
            row = {  
                "timestamp": data.get("timestamp"), 
                "patient_id": data.get("patient_id"), 
                "baseline": data.get("baseline"), 
                "current": data.get("current")
            }
            # append the row to the CSV without writing the header
            pd.DataFrame([row]).to_csv(csv_file, mode='a', header=False, index=False)  
            # log the appended row for visibility
            print("Appended to CSV:", row)  

    except KeyboardInterrupt:
        print("CSV consumer stopped.")
