import os
import pika
import json
import logging
from dotenv import load_dotenv
from internal.intelligence.processor import IntelligenceProcessor

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ANALYZER] - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load Configuration from .env
    load_dotenv()
    
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "hiring_agent_db"),
        "user": os.getenv("DB_USER", "postgres"), # Default to postgres
        "password": os.getenv("DB_PASS", ""),
        "port": os.getenv("DB_PORT", 5432)
    }
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.error("❌ GEMINI_API_KEY is missing in .env file.")
        return

    # Initialize Intelligence processor 
    try:
        processor = IntelligenceProcessor(db_params, gemini_key)
        logger.info(" Brain Initialized: Gemini + pgvector are ready.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Brain: {e}")
        return

    # Connect to RabbitMQ
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

        # Declare the queue we expect Go to publish to
        channel.queue_declare(queue='candidate.ingested', durable=True)
        
        # Ensure "Fair Dispatch" (One candidate at a time per worker)
        channel.basic_qos(prefetch_count=1)

        logger.info("Analyzer Worker is listening for candidates...")

        def on_message(ch, method, properties, body):
            """
            This function runs every time a new candidate is 'Ingested' by Go.
            """
            try:
                # A. Parse the candidate data
                candidate_data = json.loads(body)

                logger.info(f"ANALYZING: {candidate_data.get('name')}")

                # B. Execute the full Pipeline (Embedding -> Anti-Cheat -> Scoring -> DB Save)
                processor.process_and_save(candidate_data)

                # C. Confirm completion to RabbitMQ
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"✅ Successfully Vetted: {candidate_data.get('name')}")

            except Exception as e:
                logger.error(f"⚠️ Error in Analysis Pipeline: {e}")
                # Reject the message and put it back in the queue to try again
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        # 5. Start Consuming
        channel.basic_consume(queue='candidate.ingested', on_message_callback=on_message)
        channel.start_consuming()

    except Exception as e:
        logger.error(f"❌ RabbitMQ Connection Error: {e}")
    finally:
        processor.close()

if __name__ == "__main__":
    main()