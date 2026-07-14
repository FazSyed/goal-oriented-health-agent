import json
import time
import os
import sys

from kafka import KafkaProducer
from kafka.errors import KafkaError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerting.alert_mailer import report_fallback
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")  # Default to localhost if not set
class KafkaLogger:
    '''
    Logger class to publish messages to a specified Kafka topic.
    Utilizes KafkaProducer to send JSON-serialized messages.
    '''
    def __init__(self, topic='vitals_raw', bootstrap_servers=None):
        # Kafka Bootstrap server is read from .env
        self.topic = topic # store the topic name on the instance
        self.producer = None # initialize producer to None

        # Use env var if no explicit bootstrap_servers passed
        if bootstrap_servers is None:
            bootstrap_servers = [KAFKA_SERVER]

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

        reason = f"publish failed after {max_attempts} attempts"
 
        print(f"[KafkaLogger] FAILED to publish to {self.topic} after {max_attempts} attempts. Message lost: {data}")

        self._report_failure(data, reason=reason)
        
        return False

    def _report_failure(self, data: dict, reason: str):
        '''Report Kafka publish failure to alert_mailer.'''
        try:
            patient_id = data.get("patient_id") if isinstance(data, dict) else None
            report_fallback("kafka", reason, patient_id)
        except Exception:
            pass  # never let alerting crash the publisher