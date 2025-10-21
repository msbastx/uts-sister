### `Dockerfile` (Wajib)
# Gunakan base image Python yang ramping
FROM python:3.11-slim

# Tentukan direktori kerja
WORKDIR /app

# Buat pengguna non-root untuk keamanan
RUN adduser --disabled-password --gecos '' appuser

# Buat direktori untuk data persisten (SQLite DB)
# dan berikan kepemilikan ke pengguna non-root
RUN mkdir /data && chown -R appuser:appuser /data

# Salin file dependensi terlebih dahulu untuk caching layer
COPY requirements.txt ./

# Instal dependensi
RUN pip install --no-cache-dir -r requirements.txt

# Ganti ke pengguna non-root
USER appuser

# Salin kode aplikasi
COPY src/ ./src/

# Tentukan path DB melalui environment variable (menunjuk ke volume)
ENV DB_PATH="/data/aggregator.db"
ENV PYTHONUNBUFFERED=1

# Ekspos port yang digunakan aplikasi
EXPOSE 8080

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]