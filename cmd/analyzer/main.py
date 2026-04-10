import os
import pika
import json
import logging
import time
from dotenv import load_dotenv
from internal.intelligence.processor import IntelligenceProcessor

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ANALYZER] - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load Configuration from .env
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
        logger.error("❌ GEMINI_API_KEY is missing in .env file.")
        return

    # initialize Intelligence processor 
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

        channel.queue_declare(queue='candidate.ingested', durable=True)
        
        channel.basic_qos(prefetch_count=1)

        logger.info("Analyzer Worker is listening for candidates...")

        def on_message(ch, method, properties, body):
            try:
                data = json.loads(body)
                
                # ROUTING LOGIC: determine if this is a New App or a Reply
                if method.routing_key == 'candidate.ingested':
                    logger.info(f" ROUND 1: Analyzing New Application - {data.get('name')}")
                    processor.process_and_save(data)
                
                elif method.routing_key == 'candidate.replied':
                    logger.info(f"ROUND 2: Evaluating Technical Reply - {data.get('external_id')}")
                    processor.process_reply(data)
                
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"⚠️ Pipeline Error: {e}")
                time.sleep(5)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        # Start consuming from BOTH queues
        channel.basic_consume(queue='candidate.ingested', on_message_callback=on_message)
        channel.basic_consume(queue='candidate.replied', on_message_callback=on_message)

        logger.info(" Brain is active. Listening for New Apps and Replies...")
        channel.start_consuming()

    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

        # Start Consuming
        channel.basic_consume(queue='candidate.ingested', on_message_callback=on_message)
        channel.start_consuming()

    except Exception as e:
        logger.error(f"❌ RabbitMQ Connection Error: {e}")
    finally:
        processor.close()

if __name__ == "__main__":
    main()