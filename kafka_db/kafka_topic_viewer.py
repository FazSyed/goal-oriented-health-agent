from kafka import KafkaConsumer
import json

# create a KafkaConsumer subscribed to multiple topics
consumer = KafkaConsumer(
    'sensor_data',
    'vitals_raw',
    'reminders',
    'care_alerts',
    bootstrap_servers=['localhost:9092'],  # Kafka broker to connect to
    auto_offset_reset='earliest',  # start reading from the earliest offset if no committed offset
    group_id='viewer_group',  # consumer group id for offset commits and coordination
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))  # function to deserialize message bytes to Python object
)

print("Listening to topics:")

try:
    for msg in consumer: 
        topic = msg.topic  # topic name of the current message
        print(f"[{topic.upper()}] {msg.value}")
except KeyboardInterrupt:
    print("Stopped viewer.")
