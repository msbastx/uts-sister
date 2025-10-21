import pytest
import time
import uuid
import os
from fastapi.testclient import TestClient

from src.main import app
from src.database import DB_PATH, init_db_sync # <--- Import init_db_sync

# --- Setup Test ---

TEST_DB_PATH = "./test_aggregator.db"
os.environ["DB_PATH"] = TEST_DB_PATH

@pytest.fixture(scope="function", autouse=True)
def setup_teardown_db():
    """
    Fixture untuk MENGOSONGKAN DB sebelum SETIAP tes.
    Ini memanggil init_db_sync (yang sekarang membersihkan tabel).
    """
    init_db_sync()
    
    yield # Jalankan tes
    
    # Kita tidak perlu melakukan apa-apa di teardown.
    # Setup tes berikutnya akan membersihkan lagi.

@pytest.fixture(scope="function")
def client():
    """Fixture untuk Test Client SINKRON."""
    with TestClient(app) as c:
        yield c

# --- Utility ---

def create_event(topic: str, event_id: str = None) -> dict:
    """Helper untuk membuat event valid."""
    return {
        "topic": topic,
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": "2025-10-20T10:00:00Z",
        "source": "test-suite",
        "payload": {"test": "data"}
    }

# --- FUNGSI 'WAIT' BARU YANG ANDAL ---
def wait_for_processing(client: TestClient, expected_count: int, timeout: int = 5):
    """
    Menunggu (dengan polling) sampai consumer selesai memproses
    jumlah event yang diharapkan.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            stats = client.get("/stats").json()
            processed_count = stats["unique_processed_total"] + stats["duplicate_dropped_total"]
            if processed_count == expected_count:
                return # Sukses! Consumer sudah selesai.
        except Exception as e:
            # Stats mungkin belum siap, tidak apa-apa
            print(f"Polling stats, error: {e}")
            
        time.sleep(0.05) # Poll setiap 50ms
        
    # Jika loop selesai tanpa return, berarti timeout
    raise TimeoutError(
        f"Consumer tidak memproses {expected_count} event dalam {timeout} detik. "
        f"Hanya memproses {processed_count}."
    )

# --- Test Cases ---

def test_publish_single_event(client: TestClient):
    """T1: Tes kirim 1 event, cek status."""
    event = create_event("topic-a")
    response = client.post("/publish", json={"events": [event]})
    assert response.status_code == 200
    
    # Tunggu sampai 1 event diproses
    wait_for_processing(client, 1)

    stats = client.get("/stats")
    assert stats.status_code == 200
    data = stats.json()
    assert data["received_total"] == 1
    assert data["unique_processed_total"] == 1
    assert data["duplicate_dropped_total"] == 0

def test_deduplication_idempotency(client: TestClient):
    """T2: Tes dedup: kirim event yang sama 2x."""
    event_id = str(uuid.uuid4())
    event1 = create_event("topic-b", event_id)
    
    # Kirim pertama
    client.post("/publish", json={"events": [event1]})
    wait_for_processing(client, 1) # Tunggu 1 event
    
    stats1 = client.get("/stats").json()
    assert stats1["received_total"] == 1
    assert stats1["unique_processed_total"] == 1
    assert stats1["duplicate_dropped_total"] == 0

    # Kirim kedua (duplikat)
    client.post("/publish", json={"events": [event1]})
    wait_for_processing(client, 2) # Tunggu total 2 event

    stats2 = client.get("/stats").json()
    assert stats2["received_total"] == 2
    assert stats2["unique_processed_total"] == 1 # Tetap 1
    assert stats2["duplicate_dropped_total"] == 1 # Bertambah 1
        
    events_resp = client.get("/events?topic=topic-b")
    assert len(events_resp.json()) == 1

def test_schema_validation_failure(client: TestClient):
    """T3: Tes validasi skema (event_id hilang)."""
    bad_event = {
        "topic": "bad-topic",
        "timestamp": "2025-10-20T10:00:00Z",
        "source": "test-suite",
        "payload": {}
    }
    response = client.post("/publish", json={"events": [bad_event]})
    assert response.status_code == 422 

def test_get_events_filtering(client: TestClient):
    """T4: Tes filtering di GET /events?topic=..."""
    client.post("/publish", json={"events": [create_event("filter-a")]})
    client.post("/publish", json={"events": [create_event("filter-b")]})
    client.post("/publish", json={"events": [create_event("filter-a")]})
    
    wait_for_processing(client, 3) # Tunggu 3 event
    
    stats = client.get("/stats").json()
    assert stats["received_total"] == 3
    assert stats["unique_processed_total"] == 3
    assert stats["topics"]["filter-a"] == 2
    assert stats["topics"]["filter-b"] == 1
    
    resp_a = client.get("/events?topic=filter-a")
    assert len(resp_a.json()) == 2
    
    resp_b = client.get("/events?topic=filter-b")
    assert len(resp_b.json()) == 1

def test_dedup_store_persistence():
    """T5: Tes persistensi dedup store (simulasi restart)."""
    
    event_id = str(uuid.uuid4())
    event = create_event("persistent-topic", event_id)
    
    # === Sesi 1: Kirim event ===
    with TestClient(app) as client1:
        client1.post("/publish", json={"events": [event]})
        wait_for_processing(client1, 1) # Tunggu 1 event
        
        stats1 = client1.get("/stats").json()
        assert stats1["received_total"] == 1
        assert stats1["unique_processed_total"] == 1
        assert stats1["duplicate_dropped_total"] == 0

    # === Sesi 2: "Restart" (Client baru, DB sama) ===
    # Fixture setup_teardown_db TIDAK berjalan di sini, 
    # jadi DB persisten dari Sesi 1 masih ada.
    
    with TestClient(app) as client2:
        # Kirim event yang SAMA persis
        client2.post("/publish", json={"events": [event]})
        # Harapkan total 2 event (1 dari sesi1 + 1 dari sesi2)
        wait_for_processing(client2, 2) 

        stats2 = client2.get("/stats").json()
        assert stats2["received_total"] == 2
        assert stats2["unique_processed_total"] == 1
        assert stats2["duplicate_dropped_total"] == 1
        
def test_stress_test_batch(client: TestClient):
    """T6: Tes performance/stress kecil (500 event, 20% duplikat)."""
    num_events = 500
    num_dupes = 100
    
    unique_events = [create_event("stress-test") for _ in range(num_events - num_dupes)]
    duplicate_events = [unique_events[i] for i in range(num_dupes)]
    all_events = unique_events + duplicate_events
    
    start_time = time.time()
    response = client.post("/publish", json={"events": all_events})
    assert response.status_code == 200
    
    # Tunggu consumer memproses SEMUA 500 event
    wait_for_processing(client, num_events, timeout=20) # Beri waktu 10d
    
    end_time = time.time()
    print(f"Stress test (500 events) processing time: {end_time - start_time:.2f}s")
    
    stats = client.get("/stats").json()
    assert stats["received_total"] == num_events
    assert stats["unique_processed_total"] == (num_events - num_dupes) # 400
    assert stats["duplicate_dropped_total"] == num_dupes # 100
    assert stats["topics"]["stress-test"] == (num_events - num_dupes)