from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import time

class KafkaLogger:
    '''
    Logger class to publish messages to a specified Kafka topic.
    Utilizes KafkaProducer to send JSON-serialized messages.
    '''
    def __init__(self, topic='vitals_raw', bootstrap_servers=['localhost:9092']):
        self.topic = topic # store the topic name on the instance
        self.producer = None # initialize producer to None

        # create a KafkaProducer instance and store it
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers, # set Kafka bootstrap servers to connect to
                value_serializer=lambda v: json.dumps(v).encode('utf-8'), # serialize message values as JSON-encoded UTF-8 bytes
                retries=3, # retry on transient failures
                request_timeout_ms=10000 # timeout for requests
            )
        except KafkaError as e:
            print(f"[KafkaLogger] ERROR: Could not connect to Kafka broker: {e}")
        except Exception as e:
            print(f"[KafkaLogger] ERROR: Unexpected error initialising producer: {e}")

    
    def publish(self, data: dict, max_attempts: int = 3, retry_delay_sec: float = 2.0) -> bool:
        '''
        Publish a dictionary to the configured topic, retrying the full
        publish call up to max_attempts times if it fails completely.
    
            Parameters:
            - data: dictionary payload to publish
            - max_attempts: number of full publish attempts before giving up
            - retry_delay_sec: seconds to wait between attempts
    
            Returns:
            - True: if the message was successfully published
            - False: if all attempts failed
        '''
        if self.producer is None:
            print(f"[KafkaLogger] Cannot publish to {self.topic} — producer not initialised.")
            return False
        
        for attempt in range(1, max_attempts + 1):
            try:
                future = self.producer.send(self.topic, value=data) # queue the message to be sent to the specified topic
                future.get(timeout=10) # surfaces delivery errors explicitly
                self.producer.flush() # block until all queued messages are sent
                print(f"[KafkaLogger] Published to {self.topic}: {data}")
                return True # success, exit the method

            except KafkaError as e:
                print(f"[KafkaLogger] Attempt {attempt}/{max_attempts} failed "
                      f"(Kafka error) for topic {self.topic}: {e}")
            except Exception as e:
                print(f"[KafkaLogger] Attempt {attempt}/{max_attempts} failed "
                      f"(unexpected error) for topic {self.topic}: {e}")
                
            if attempt < max_attempts:
                time.sleep(retry_delay_sec)
 
        print(f"[KafkaLogger] FAILED to publish to {self.topic} after {max_attempts} attempts. Message lost: {data}")
        
        return False
