import os
import pika
import json
import time
import logging
from dotenv import load_dotenv
from internal.intelligence.processor import IntelligenceProcessor

# Setup Logging 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load Configuration
    load_dotenv()
    
    db_params = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432))
}
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.error("GEMINI_API_KEY is not set in .env")
        return

    # Initialize the intelligence processor 
    try:
        processor = IntelligenceProcessor(db_params, gemini_key)
        logger.info("Intelligence Processor Initialized (Postgres + Gemini)")
    except Exception as e:
        logger.error(f"Failed to initialize Processor: {e}")
        return

    # Connect to RabbitMQ 
    try:
        # local RabbitMQ instance
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

    
        channel.queue_declare(queue='candidate.ingested', durable=True)
        
      
        channel.basic_qos(prefetch_count=1)

        logger.info(" Python Intelligence Worker is waiting for events...")

        def callback(ch, method, properties, body):
            """
            The Core Pipeline Trigger
            """
            try:
                # Parse Ingested Data from Go
                candidate_data = json.loads(body)
                logger.info(f" Processing: {candidate_data.get('name', 'Unknown')}")

               
                processor.process_and_save(candidate_data)

                # Acknowledge RabbitMQ 
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Finished: {candidate_data.get('name')}")

            except Exception as e:
                logger.error(f"⚠️ Error processing candidate: {e}")
                # Re-queue the message if it's a temporary failure 
                time.Sleep(5) 
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        # Start the consumer
        channel.basic_consume(queue='candidate.ingested', on_message_callback=callback)
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError:
        logger.error(" Could not connect to RabbitMQ. Is it running in Docker?")
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        processor.close()

if __name__ == "__main__":
    main()