from kafka import KafkaProducer
from kafka.errors import KafkaError
import json

class KafkaLogger:
    '''
    Logger class to publish messages to a specified Kafka topic.
    Utilizes KafkaProducer to send JSON-serialized messages.
    '''
    def __init__(self, topic='vitals_raw', bootstrap_servers=['localhost:9092']):
        self.topic = topic # store the topic name on the instance
        # create a KafkaProducer instance and store it
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers, # set Kafka bootstrap servers to connect to
            value_serializer=lambda v: json.dumps(v).encode('utf-8'), # serialize message values as JSON-encoded UTF-8 bytes
            retries=3, # retry on transient failures
            request_timeout_ms=10000 # timeout for requests
        )

    # method to publish a dictionary to the configured topic
    def publish(self, data: dict):
        try:
            future = self.producer.send(self.topic, value=data) # queue the message to be sent to the specified topic
            future.get(timeout=10) # surfaces delivery errors explicitly
            self.producer.flush() # block until all queued messages are sent
            print(f"[KafkaLogger] Published to {self.topic}: {data}")
        except KafkaError as e:
            print(f"[KafkaLogger] Kafka delivery failed: {e}")
        except Exception as e:
            print(f"[KafkaLogger] Error publishing to Kafka: {e}")
