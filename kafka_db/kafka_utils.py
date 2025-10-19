from kafka import KafkaProducer
import json

class KafkaLogger:
    def __init__(self, topic='vitals_raw', bootstrap_servers=['localhost:9092']):
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def publish(self, data: dict):
        try:
            self.producer.send(self.topic, value=data)
            self.producer.flush()
            print(f"[KafkaLogger] Published to {self.topic}: {data}")
        except Exception as e:
            print(f"[KafkaLogger] Error publishing to Kafka: {e}")
