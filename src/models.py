import datetime
from pydantic import BaseModel, Field
from typing import Dict, Any, List

class Event(BaseModel):
    """Model data untuk satu event log."""
    topic: str
    event_id: str = Field(..., min_length=1)
    timestamp: datetime.datetime
    source: str
    payload: Dict[str, Any]

class PublishRequest(BaseModel):
    """Model untuk request body di /publish."""
    events: List[Event]

class EventInDB(Event):
    """Model representasi event yang diambil dari DB."""
    payload: str # Disimpan sebagai JSON string di DB

class StatsResponse(BaseModel):
    """Model untuk response body di /stats."""
    uptime_seconds: float
    received_total: int
    unique_processed_total: int
    duplicate_dropped_total: int
    topics: Dict[str, int]