import asyncio
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query
from typing import List, Optional

from .models import PublishRequest, Event, StatsResponse
from .database import init_db, update_received_count, get_stats, get_events
from .consumer import event_consumer

START_TIME = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Mengelola startup dan shutdown event."""
    logger.info("Starting up...")
    
    app.state.event_queue = asyncio.Queue(maxsize=10000)
    
    # --- KEMBALIKAN BARIS INI ---
    # Ini penting untuk Docker dan juga aman untuk tes
    await init_db()
    
    consumer_task = asyncio.create_task(event_consumer(app.state.event_queue))
    
    yield
    
    logger.info("Shutting down...")
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        logger.info("Consumer task successfully cancelled.")

app = FastAPI(
    title="UTS Log Aggregator",
    description="Implementasi Pub-Sub Aggregator dengan Idempotency dan Deduplikasi",
    lifespan=lifespan
)

@app.post("/publish")
async def publish_events(body: PublishRequest, request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint untuk menerima (publish) satu atau lebih event.
    Bersifat asynchronous, merespon cepat, dan memproses di background.
    """
    events_received = len(body.events)
    
    if events_received == 0:
        raise HTTPException(status_code=400, detail="No events provided")
    
    queue = request.app.state.event_queue
    
    for event in body.events:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.error("Internal queue is full. Dropping event.")
            raise HTTPException(status_code=503, detail="Service busy, queue is full.")
    
    background_tasks.add_task(update_received_count, events_received)
    
    return {"message": f"Queued {events_received} events for processing."}

@app.get("/events", response_model=List[dict])
async def get_processed_events(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results")
):
    """Mengembalikan daftar event unik yang telah diproses dari DB."""
    events = await get_events(topic=topic, limit=limit)
    return events

@app.get("/stats", response_model=StatsResponse)
async def get_system_stats():
    """Mengembalikan statistik operasional dari sistem (persisten)."""
    uptime = time.time() - START_TIME
    db_stats = await get_stats()
    
    return StatsResponse(
        uptime_seconds=uptime,
        **db_stats
    )

@app.get("/")
def read_root():
    return {"message": "Log Aggregator is running. See /docs for API."}