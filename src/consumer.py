import asyncio
import logging
from .models import Event
from .database import store_processed_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def event_consumer(queue: asyncio.Queue):
    """Tugas background yang berjalan selamanya, memproses event dari antrian."""
    logger.info("Event consumer started...")
    while True:
        event: Event = None  # Inisialisasi di luar try block
        try:
            event = await queue.get()
            
            # Proses Idempotent
            is_new = await store_processed_event(event)
            
            if is_new:
                logger.info(f"Processed new event: {event.event_id} (Topic: {event.topic})")
            else:
                logger.warning(f"Detected duplicate event: {event.event_id} (Topic: {event.topic})")
            
            # Pindahkan task_done() ke DALAM try block
            # Ini memastikan task_done() HANYA dipanggil jika get() BERHASIL
            queue.task_done()
            
        except asyncio.CancelledError:
            logger.info("Event consumer shutting down...")
            break # Keluar dari loop
            
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            # JIKA event-nya berhasil di-get() TAPI gagal diproses,
            # kita tetap harus panggil task_done() agar queue tidak macet.
            if event is not None:
                queue.task_done()
            # Jika event adalah None, berarti queue.get() yang gagal,
            # jadi JANGAN panggil task_done().