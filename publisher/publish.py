import requests
import uuid
import time
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGGREGATOR_URL = "http://aggregator:8080/publish"
NUM_UNIQUE_EVENTS = 4000
NUM_DUPLICATES = 1000 # Total 5000, 20% duplikasi
BATCH_SIZE = 100

def create_event(topic: str, event_id: str = None) -> dict:
    """Helper untuk membuat event valid."""
    return {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "compose-publisher",
        "payload": {"value": random.randint(1, 1000)}
    }

def wait_for_aggregator():
    """Tunggu aggregator siap menerima koneksi."""
    retries = 10
    wait = 2
    for i in range(retries):
        try:
            response = requests.get("http://aggregator:8080/")
            if response.status_code == 200:
                logger.info("Aggregator is up!")
                return True
        except requests.ConnectionError:
            logger.info(f"Aggregator not ready. Retrying in {wait}s...")
            time.sleep(wait)
    logger.error("Aggregator did not start. Exiting.")
    return False

def send_batch(batch: list):
    try:
        response = requests.post(AGGREGATOR_URL, json={"events": batch})
        if response.status_code == 200:
            logger.info(f"Successfully sent batch of {len(batch)} events.")
        else:
            logger.warning(f"Failed to send batch. Status: {response.status_code}, Body: {response.text}")
    except requests.ConnectionError as e:
        logger.error(f"Connection error sending batch: {e}")

def main():
    if not wait_for_aggregator():
        return

    logger.info(f"Starting publisher. Sending {NUM_UNIQUE_EVENTS + NUM_DUPLICATES} total events...")
    
    unique_events = [create_event(random.choice(["topic-x", "topic-y"])) for _ in range(NUM_UNIQUE_EVENTS)]
    
    # Ambil 1000 event pertama untuk dijadikan duplikat
    duplicate_events = [unique_events[i] for i in range(NUM_DUPLICATES)]
    
    all_events = unique_events + duplicate_events
    random.shuffle(all_events) # Acak urutan
    
    total_sent = 0
    for i in range(0, len(all_events), BATCH_SIZE):
        batch = all_events[i:i+BATCH_SIZE]
        send_batch(batch)
        total_sent += len(batch)
        time.sleep(0.1) # Beri nafas sedikit
        
    logger.info(f"--- Publishing complete ---")
    logger.info(f"Total events sent: {total_sent}")
    logger.info(f"Expected unique: {NUM_UNIQUE_EVENTS}")
    logger.info(f"Expected duplicates: {NUM_DUPLICATES}")
    logger.info("Publisher finished. Cek 'GET /stats' di aggregator.")

if __name__ == "__main__":
    main()