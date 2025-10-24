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