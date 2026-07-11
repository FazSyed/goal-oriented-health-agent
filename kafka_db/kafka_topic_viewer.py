from kafka import KafkaConsumer
import json

# create a KafkaConsumer subscribed to multiple topics
consumer = KafkaConsumer(
    'sensor_data',
    'reminders',
    'care_alerts',
    'euhydrated_log',
    bootstrap_servers=['localhost:9092'],  # Kafka broker to connect to
    auto_offset_reset='earliest',  # start reading from the earliest offset if no committed offset
    group_id='viewer_group',  # consumer group id for offset commits and coordination
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))  # function to deserialize message bytes to Python object
)

print("Listening to topics:")

try:
    for msg in consumer:
        topic = msg.topic
        data = msg.value

        if topic == 'sensor_data':
            print(f"\n[{topic.upper()}]")
            print(f"  Patient ID : {data.get('patient_id')}")
            print(f"  Timestamp  : {data.get('timestamp')}")
            print(f"  Sodium     : {data.get('sodium')} mmol/L")
            print(f"  Potassium  : {data.get('potassium')} mmol/L")
            print(f"  Chloride   : {data.get('chloride')} mmol/L")
            print(f"  BUN        : {data.get('bun')} mg/dL")
            print(f"  Creatinine : {data.get('creatinine')} mg/dL")
            print(f"  Glucose    : {data.get('glucose')} mg/dL")

        elif topic == 'euhydrated_log':
            print(f"\n[{topic.upper()}] 🟢 Euhydrated")
            print(f"  Patient ID : {data.get('patient_id')}")
            print(f"  Risk       : {data.get('risk')}")
            print(f"  Action     : {data.get('action')}")
            print(f"  Plan       : {data.get('plan')}")

        elif topic == 'reminders':
            print(f"\n[{topic.upper()}] 🔵 Mild/Impending Dehydration")
            print(f"  Patient ID : {data.get('patient_id')}")
            print(f"  Risk       : {data.get('risk')}")
            print(f"  Action     : {data.get('action')}")
            print(f"  Plan       : {data.get('plan')}")

        elif topic == 'care_alerts':
            
            if data.get('risk') == 'Severe':
                icon = "🔴"
            else:
                icon = "🟠"

            print(f"\n[{topic.upper()}] {icon} {data.get('risk')} Dehydration Alert")
            print(f"  Patient ID : {data.get('patient_id')}")
            print(f"  Risk       : {data.get('risk')}")
            print(f"  Action     : {data.get('action')}")
            print(f"  Plan       : {data.get('plan')}")

        else:
            print(f"[{topic.upper()}] {data}")

except KeyboardInterrupt:
    print("Stopped viewer.")
