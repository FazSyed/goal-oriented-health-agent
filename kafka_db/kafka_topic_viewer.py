from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'sensor_data',
    'vitals_raw',
    'reminders',
    'care_alerts',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    group_id='viewer_group',
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

print("Listening to topics:")

try:
    for msg in consumer:
        topic = msg.topic
        print(f"[{topic.upper()}] {msg.value}")
except KeyboardInterrupt:
    print("Stopped viewer.")
