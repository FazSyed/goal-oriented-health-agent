from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'sensor_data',
    'vitals_raw',
    'reminders',
    'care_alerts',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    group_id='test_group',
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

print("[TEST CONSUMER] Listening to all topics...")

try:
    for msg in consumer:
        print(f"[{msg.topic.upper()}] {msg.value}")
except KeyboardInterrupt:
    print("Stopped consumer.")
