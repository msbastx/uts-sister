# UTS Sistem Terdistribusi: Pub-Sub Log Aggregator

Proyek ini adalah implementasi log aggregator sederhana dengan arsitektur Pub-Sub, idempotent consumer, dan deduplikasi, yang berjalan di dalam Docker.

**Link Video Demo YouTube (5-8 Menit):**
[CANTUMKAN LINK YOUTUBE PUBLIK ANDA DI SINI]

---

## Arsitektur

* **API (FastAPI)**: Menerima log di `POST /publish` dan memasukkannya ke antrian.
* **Antrian (asyncio.Queue)**: Antrian in-memory untuk memisahkan penerimaan dan pemrosesan.
* **Consumer (Background Task)**: Mengambil dari antrian, melakukan deduplikasi.
* **Database (SQLite)**: Menyimpan event unik dan status deduplikasi secara persisten di volume Docker (`/data/aggregator.db`).

---

## Cara Menjalankan (Docker Wajib)

Pastikan Docker sudah terinstal dan berjalan.

### 1. Build Image

```bash
docker build -t uts-aggregator .