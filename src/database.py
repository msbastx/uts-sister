import aiosqlite
import os
import logging
import sqlite3
from .models import Event
from typing import List, Dict, Optional, Any

DB_PATH = os.environ.get("DB_PATH", "aggregator.db")
logging.info(f"Database path set to: {DB_PATH}")

async def init_db():
    """
    Versi ASYNC: Inisialisasi tabel database jika belum ada.
    Digunakan oleh aplikasi utama (Docker).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS dedup_store (
            event_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, topic)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            topic TEXT,
            timestamp TIMESTAMP,
            source TEXT,
            payload TEXT 
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            stat_name TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )""")
        await db.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('received_total', 0)")
        await db.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('unique_processed_total', 0)")
        await db.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('duplicate_dropped_total', 0)")
        await db.commit()
    logging.info("Database initialized successfully.")

def init_db_sync():
    """
    Versi SYNC: Membuat tabel JIKA BELUM ADA, lalu MENGOSONGKAN SEMUA DATA.
    Khusus untuk setup Pytest agar bersih.
    """
    logging.info(f"Re-initializing sync database at: {DB_PATH}")
    try:
        # sqlite3.connect akan membuat file jika belum ada.
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.cursor()
            # 1. Buat tabel (jika belum ada)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedup_store (
                event_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, topic)
            )""")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                topic TEXT,
                timestamp TIMESTAMP,
                source TEXT,
                payload TEXT 
            )""")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                stat_name TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )""")
            
            # 2. HAPUS SEMUA DATA LAMA (ini aman dari file lock)
            cursor.execute("DELETE FROM dedup_store")
            cursor.execute("DELETE FROM processed_events")
            
            # 3. RESET statistik
            cursor.execute("UPDATE statistics SET value = 0")
            
            # 4. Pastikan statistik ada
            cursor.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('received_total', 0)")
            cursor.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('unique_processed_total', 0)")
            cursor.execute("INSERT OR IGNORE INTO statistics (stat_name, value) VALUES ('duplicate_dropped_total', 0)")
            
            db.commit()
        logging.info("Sync database reset successfully.")
    except Exception as e:
        logging.error(f"Failed to init/reset sync DB: {e}")

# ... (sisa file database.py Anda tidak berubah) ...
async def store_processed_event(event: Event) -> bool:
    """
    Mencoba menyimpan event. Bersifat Idempotent.
    Mengembalikan True jika event baru diproses, False jika duplikat.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO dedup_store (event_id, topic) VALUES (?, ?)",
                (event.event_id, event.topic)
            )
            await db.execute(
                "INSERT OR IGNORE INTO processed_events (event_id, topic, timestamp, source, payload) VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.topic, event.timestamp, event.source, str(event.payload))
            )
            await db.execute("UPDATE statistics SET value = value + 1 WHERE stat_name = 'unique_processed_total'")
            await db.commit()
            return True # Event baru
            
        except aiosqlite.IntegrityError:
            await db.execute("UPDATE statistics SET value = value + 1 WHERE stat_name = 'duplicate_dropped_total'")
            await db.commit()
            return False # Duplikat terdeteksi
        except Exception as e:
            logging.error(f"Error storing event {event.event_id}: {e}")
            await db.rollback()
            return False

async def update_received_count(count: int):
    """Update statistik event yang diterima."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE statistics SET value = value + ? WHERE stat_name = 'received_total'", (count,))
        await db.commit()

async def get_stats() -> Dict[str, Any]:
    """Mengambil statistik dari DB."""
    stats = {}
    topics = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT stat_name, value FROM statistics") as cursor:
            async for row in cursor:
                stats[row[0]] = row[1]
        
        async with db.execute("SELECT topic, COUNT(*) FROM processed_events GROUP BY topic") as cursor:
            async for row in cursor:
                topics[row[0]] = row[1]
                
    stats["topics"] = topics
    return stats

async def get_events(topic: Optional[str] = None, limit: int = 100) -> List[Event]:
    """Mengambil daftar event unik yang telah diproses."""
    events = []
    query = "SELECT topic, event_id, timestamp, source, payload FROM processed_events"
    params = []
    
    if topic:
        query += " WHERE topic = ?"
        params.append(topic)
        
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cursor:
            async for row in cursor:
                event_data = {
                    "topic": row[0],
                    "event_id": row[1],
                    "timestamp": row[2],
                    "source": row[3],
                    "payload": row[4] 
                }
                events.append(event_data)
    return events