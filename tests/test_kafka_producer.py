from kafka import KafkaProducer
import json
import time

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

topics = ['sensor_data', 'vitals_raw', 'reminders', 'care_alerts']

for topic in topics:
    message = {"test": f"Hello from {topic}", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    producer.send(topic, value=message)
    print(f"[TEST PRODUCER] Sent to {topic}: {message}")

producer.flush()
print("[TEST PRODUCER] All messages sent successfully.")
