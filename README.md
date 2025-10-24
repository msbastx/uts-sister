# Sistem Terdistribusi: Pub-Sub Log Aggregator

## Cara Menjalankan (Docker Wajib)

Pastikan Docker sudah terinstal dan berjalan.

### 1. Build Image

```bash
docker build -t uts-aggregator .
```

### 2. Buat Volume

```bash
docker volume create aggregator-data
```

### 3. Jalankan Container

```bash
docker run -d --rm -p 8080:8080 -v aggregator-data:/data --name my-aggregator uts-aggregator
```

### 4. Uji Idempotency (Deduplikasi)

Buka `http://localhost:8080/docs`di browser.
1. Cek Awal: Buka `GET /stats`. Pastikan semua counter bernilai 0.
2. Kirim Event Unik:
- Buka `POST /publish`.
- Gunakan body berikut untuk mengirim event pertama:
```bash
{
  "events": [
    {
      "topic": "demo",
      "event_id": "demo-123",
      "timestamp": "2025-10-24T10:00:00Z",
      "source": "demo-video",
      "payload": { "message": "Event pertama" }
    }
  ]
}
```
- Jalankan. Cek `GET /stats`: `received_total: 1`, `unique_processed_total: 1`.
3. Kirim Event Duplikat:
- Jalankan `POST /publish` lagi dengan body yang sama persis.
- Jalankan. Cek `GET /stats: received_total: 2`, `unique_processed_total: 1`, `duplicate_dropped_total: 1`.

### 5. Uji Persistensi (Tahan Restart)

1. Stop Container.

```bash
docker stop my-aggregator
```

2. Restart Container: Jalankan kembali container dengan perintah yang sama

```bash
docker run -d --rm -p 8080:8080 -v aggregator-data:/data --name my-aggregator uts-aggregator
```

3. Verifikasi State:
- Tunggu beberapa detik, buka `GET /stats`.
- Statistik masih ada: `received_total: 2`, `unique_processed_total: 1`, `duplicate_dropped_total: 1`.

4. Kirim Duplikasi Lagi:
- Kirim event `demo-123` lagi dari  `POST /publish`.
- Cek `GET /stats`: `received_total: 3`, `unique_processed_total: 1`, `duplicate_dropped_total: 2`.