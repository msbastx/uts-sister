# UTS Sistem Terdistribusi: Pub-Sub Log Aggregator

**Nama: Muhammad Shadam Bastian NIM: 11221042 Mata Kuliah: Sistem Paralel dan Terdistribusi**

Proyek ini adalah implementasi log aggregator sederhana dengan arsitektur Pub-Sub, idempotent consumer, dan deduplikasi, yang berjalan di dalam Docker.

**Link Video Demo YouTube (5-8 Menit):**
[CANTUMKAN LINK YOUTUBE PUBLIK ANDA DI SINI]

---

## 1. Ringkasan Sistem dan Arsitektur

Sistem ini adalah sebuah Log Aggregator dengan arsitektur Publish-Subscribe yang dirancang untuk berjalan dalam kontainer Docker. Sistem ini memisahkan (decoupling) proses penerimaan log (publishing) dari proses penyimpanan dan deduplikasi (subscribing), sehingga mencapai high throughput dan resiliensi.

Arsitektur ini terdiri dari tiga komponen utama:

**1. API Endpoint (FastAPI):** Berfungsi sebagai broker sederhana. Publisher mengirimkan event log ke `POST /publish`. Endpoint ini hanya melakukan validasi data dan memasukkannya ke antrian internal.
**2. Antrian Interval (`asyncio.Queue`):** Berfungsi sebagai buffer in-memory yang memisahkan publisher (API) dari consumer. Ini memungkinkan API untuk merespons `200 OK` dengan sangat cepat tanpa harus menunggu data ditulis ke database.
**3. Background Consumer (Subscriber):** Sebuah background task (`asyncio`) yang berjalan di dalam layanan yang sama. Consumer ini secara kontinu mengambil event dari antrian, melakukan deduplikasi, dan menyimpannya ke storage persisten.
**4. Persistent Storage (SQLite):** Berfungsi sebagai deduplication store dan penyimpanan event unik. Dijalankan dalam volume Docker (`/data`) agar data tetap ada (persisten) bahkan jika container di-restart.

---

## Cara Menjalankan (Docker Wajib)

Pastikan Docker sudah terinstal dan berjalan.

### 1. Build Image

```bash
docker build -t uts-aggregator .