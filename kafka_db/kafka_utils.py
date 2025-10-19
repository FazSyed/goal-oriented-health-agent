from kafka import KafkaProducer 
import json

class KafkaLogger:  
    '''
    Logger class to publish messages to a specified Kafka topic.
    Utilizes KafkaProducer to send JSON-serialized messages.
    '''
    def __init__(self, topic='vitals_raw', bootstrap_servers=['localhost:9092']): 
        self.topic = topic  # store the topic name on the instance
        # create a KafkaProducer instance and store it
        self.producer = KafkaProducer(  
            bootstrap_servers=bootstrap_servers,  # set Kafka bootstrap servers to connect to
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # serialize message values as JSON-encoded UTF-8 bytes
        )

    # method to publish a dictionary to the configured topic
    def publish(self, data: dict ):  
        try: 
            self.producer.send(self.topic, value=data)  # queue the message to be sent to the specified topic
            self.producer.flush()  # block until all queued messages are sent
            print(f"[KafkaLogger] Published to {self.topic}: {data}") 
        except Exception as e:
            print(f"[KafkaLogger] Error publishing to Kafka: {e}")
