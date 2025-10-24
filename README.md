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

Diagram Alur Sederhana: `Publisher` -> `POST /publish` (FastAPI) -> `asyncio.Queue` (In-Memory) -> `Background Consumer` -> `Cek Deduplikasi (SQLite)` -> `Simpan Event Unik (SQLite)`

---

## 2. Keputusan Desain

Desain sistem ini berfokus pada ketentuan tugas, terutama idempotency dan deduplication yang tangguh.

- Idempotency & Deduplication Store:
    - Idempotency tercapai pada level database (SQLite) menggunakan composite primary key `(event_id, topic)` pada tabel `dedup_store`.
    - Ketika consumer mencoba memasukkan event duplikat `(INSERT INTO dedup_store ...)`, database akan melempar `IntegrityError`.
    - Consumer menangkap error ini dan menanganinya sebagai event duplikat yang terdeteksi, lalu memperbarui counter `duplicate_dropped_total`. Ini menjamin satu event hanya diproses (disimpan) satu kali, bahkan jika diterima berkali-kali (at-least-once delivery).
    - Penyimpanan menggunakan SQLite karena merupakan database embedded (tanpa server) yang ringan dan dapat dibuat persisten dengan mudah menggunakan volume Docker.

- Ordering dan Retry:
    - Sistem ini tidak menjamin total ordering. Event diproses roughly berdasarkan urutan kedatangan di `asyncio.Queue`, yang cukup untuk kasus penggunaan log aggregation.
    - Sistem ini dirancang untuk menangani skenario at-least-once delivery (di mana publisher mungkin melakukan retry). Mekanisme idempotency di atas secara eksplisit menangani retry dan duplikasi yang diakibatkannya.

---

## 3. Analisis dan Performa Metrik

Sistem ini dievaluasi berdasarkan metrik-metrik berikut:

1. Throughput (Penerimaan): Diukur dari seberapa cepat endpoint `POST /publish` dapat menerima event. Berkat arsitektur async FastAPI dan decoupling menggunakan `asyncio.Queue`, endpoint ini sangat cepat. Ia hanya melakukan validasi Pydantic dan `queue.put()`, lalu langsung merespons.
2. Processing Latency: Waktu yang dibutuhkan dari event diterima (`/publish`) hingga diproses oleh consumer dan disimpan di SQLite. Latensi ini akan meningkat jika burst event (misalnya 5.000 event sekaligus) melebihi kecepatan consumer dalam melakukan write ke SQLite.
3. Duplicate Drop Rate: Metrik kunci untuk correctness (`duplicate_dropped / received_total`). Dalam stress test (via `docker-compose`), kita memverifikasi bahwa 20% event duplikat (1.000 dari 5.000) berhasil dideteksi dan dibuang.
4. Observability: Endpoint `GET /stats` (menampilkan `received_total`, `unique_processed_total`, `duplicate_dropped_total`) menyediakan visibilitas real-time ke dalam kinerja sistem dan kebenaran deduplikasi.

---

## 4. Teori

### 1. T1 (Bab 1): Karakteristik Sistem Terdistribusi dan Trade-off
Karakteristik utama sistem terdistribusi adalah kumpulan komputer independen yang tampak bagi penggunanya sebagai satu sistem koheren tunggal (Tanenbaum & Van Steen, 2023, Bab 1). Karakteristik kunci meliputi: (1) Concurrency: Komponen berjalan secara paralel; (2) No Global Clock: Setiap node memiliki clock sendiri; (3) Independent Failures: Kegagalan satu node tidak serta-merta menghentikan sistem; dan (4) Transparency: Menyembunyikan kompleksitas distribusi dari pengguna (misalnya access, location, failure transparency).

Pada desain log aggregator Pub-Sub ini, trade-off utamanya adalah antara Throughput/Scalability dan Consistency/Ordering.
- Untuk mencapai throughput tinggi, kita menggunakan asynchronous processing (antrian internal), yang berarti publisher tidak perlu menunggu event ditulis ke database.
- Ini mengorbankan strong consistency; ada jeda (latensi) sebelum event muncul di `GET /events`. Sistem ini mengadopsi eventual consistency (Tanenbaum & Van Steen, 2023, Bab 7).
- Kita juga mengorbankan total ordering demi performa. Log dari source berbeda tidak dijamin diproses sesuai urutan timestamp global.

### 2. T2 (Bab 2): Arsitektur Client-Server vs. Publish-Subscribe
Arsitektur Client-Server tradisional (Tanenbaum & Van Steen, 2023, Bab 2) melibatkan komunikasi sinkron dan tight coupling. Client (sumber log) membuat permintaan langsung ke Server (aggregator) dan seringkali menunggu respons.

Sebaliknya, arsitektur Publish-Subscribe (Pub-Sub) bersifat asynchronous dan loosely coupled. Publisher (sumber log) mengirimkan event ke topic tertentu tanpa mengetahui siapa subscriber (aggregator)-nya. Ini memberikan beberapa keunggulan teknis untuk log aggregator:
1. Scalability: Kita dapat menambahkan lebih banyak publisher atau consumer tanpa memodifikasi komponen lain.

2. Decoupling (Pemisahan): Publisher tidak perlu tahu lokasi aggregator (via topic). Publisher hanya perlu "membuang" log dan lanjut bekerja (fire-and-forget), yang krusial untuk aplikasi berkinerja tinggi.

3. Resilience: Dalam implementasi kami, decoupling ini terjadi antara API dan consumer internal melalui `asyncio.Queue`, sehingga API tetap responsif meskipun consumer sedang sibuk.

### 3. T3 (Bab 3): At-Least-Once vs. Exactly-Once dan Idempotency
Delivery semantics (semantik pengiriman) mendefinisikan jaminan berapa kali sebuah pesan dapat dikirimkan.
1. At-Least-Once (Paling Tidak Sekali): Sistem menjamin bahwa pesan akan dikirimkan, tetapi bisa saja terkirim lebih dari sekali. Ini biasanya dicapai melalui retries (pengiriman ulang) oleh publisher jika tidak ada konfirmasi penerimaan (Tanenbaum & Van Steen, 2023, Bab 6).

2. Exactly-Once (Tepat Sekali): Jaminan ideal bahwa pesan dikirim dan diproses tepat satu kali. Ini sangat sulit dan mahal untuk dicapai dalam sistem terdistribusi (Tanenbaum & Van Steen, 2023, Bab 7).

Dalam skenario at-least-once (karena adanya retries), consumer (aggregator) mungkin menerima event yang sama berkali-kali. Idempotent Consumer menjadi krusial karena idempotency memastikan bahwa memproses event yang sama berulang kali memiliki efek yang sama persis dengan memprosesnya satu kali. Dalam aggregator kami, operasi "simpan ke DB" bersifat idempotent berkat primary key (`event_id, topic`). Jika event duplikat tiba, `INSERT` akan gagal, dan status sistem tetap konsisten.

### 4. T4 (Bab 4): Skema Penamaan Topic dan Event ID
Skema penamaan (Tanenbaum & Van Steen, 2023, Bab 4) sangat penting untuk routing (via topic) dan deduplication (via event_id).
1. Topic: Skema penamaan hierarkis berbasis string disarankan, mirip dengan path URL. Format: `environment.application.module.level.` Contoh: `production.api-gateway.auth-service.error.` Ini memungkinkan filtering yang fleksibel.
2. Event ID (Unik & Collision-Resistant): Kunci dari deduplication adalah event_id yang unik secara global yang dibuat oleh publisher (sumber log).
    - Pilihan Terbaik: UUIDv4 (Universally Unique Identifier). Peluang collision (tabrakan) sangat rendah dan dapat dibuat secara independen oleh publisher mana pun tanpa koordinasi.
    - Dampak pada Dedup: Skema ini memindahkan tanggung jawab keunikan ke publisher. Aggregator hanya perlu menyimpan set (`topic, event_id`) yang terlihat.

### 5. T5 (Bab 5): Ordering dan Pendekatan Praktis
Total Ordering (urutan total), di mana setiap komponen dalam sistem melihat setiap event dalam urutan global yang sama persis (Tanenbaum & Van Steen, 2023, Bab 5), tidak diperlukan untuk kasus penggunaan log aggregator ini. Mencapai total ordering sangat mahal dan akan menjadi bottleneck performa.

Kami tidak peduli jika log dari source-A diproses sebelum log dari source-B meskipun timestamp source-B lebih awal. Kami hanya peduli bahwa:
1. Semua event unik akhirnya diproses (eventual consistency).
2. Tidak ada duplikat.

Pendekatan praktis yang digunakan adalah tidak ada jaminan ordering antar-publisher. Kita hanya mengandalkan event timestamp yang disediakan oleh publisher untuk informasi kapan event itu terjadi, bukan untuk mengurutkan pemrosesan. Event diproses roughly dalam urutan kedatangan di antrian.

### 6. T6 (Bab 6): Failure Modes dan Mitigasi
Dalam sistem Pub-Sub ini, beberapa mode kegagalan (Tanenbaum & Van Steen, 2023, Bab 6) dapat terjadi:
1. Publisher Crash/Retry: Publisher mengirim event, tidak mendapat konfirmasi, lalu mengirim ulang. Ini menciptakan duplikasi event.
    - Mitigasi: Idempotent consumer dan deduplication store (SQLite) kami menangani ini dengan aman.
2. Aggregator (Consumer) Crash: Consumer mengambil event dari antrian in-memory (`asyncio.Queue`) tetapi crash sebelum menyimpannya ke SQLite.
    - Mitigasi (Kelemahan Desain): Karena antrian bersifat in-memory, event ini akan hilang. Ini adalah trade-off untuk kesederhanaan (tidak menggunakan broker eksternal). Sistem ini menjamin at-most-once jika consumer crash.
3. Aggregator (Consumer) Crash (setelah simpan DB, sebelum ack queue): Dalam sistem yang lebih canggih, broker akan mengirim ulang event tersebut.
    - Mitigasi: Durable deduplication store (SQLite) kami akan menangkap duplikat ini saat consumer memprosesnya lagi.

### 7. T7 (Bab 7): Eventual Consistency dan Peran Idempotency/Dedup
Eventual Consistency (Konsistensi Akhirnya) (Tanenbaum & Van Steen, 2023, Bab 7) adalah model konsistensi yang menjamin bahwa jika tidak ada pembaruan baru yang dilakukan, database akan akhirnya menyatu ke nilai yang sama.

Dalam aggregator kami, ini berarti ada jeda waktu (latensi) antara event diterima oleh `POST /publish` dan event tersebut muncul di `GET /events` (karena antrian async). Sistem mungkin sementara dalam keadaan tidak konsisten, namun dijamin bahwa akhirnya semua event unik akan diproses dan disimpan.

Peran Idempotency + Deduplication: Keduanya adalah mekanisme kunci untuk mencapai eventual consistency yang benar. Dalam sistem at-least-once yang penuh dengan retries, state bisa menjadi korup.
- Deduplication (menggunakan database persisten) bertindak sebagai "penjaga gerbang" ke state akhir.
- Idempotency adalah prinsip desain yang memungkinkan consumer untuk secara aman memproses ulang event tanpa merusak state tersebut.

### 8. T8 (Bab 1–7): Metrik Evaluasi Sistem dan Keputusan Desain
Metrik evaluasi kunci untuk sistem aggregator ini adalah:
1. Throughput (Penerimaan): Berapa banyak event per detik yang dapat ditangani oleh endpoint `POST /publish`.
    - Keputusan Desain: Menggunakan FastAPI (async) dan memindahkan pemrosesan ke background task (via `asyncio.Queue`) memaksimalkan throughput penerimaan.
2. Processing Latency (Latensi Pemrosesan): Waktu rata-rata dari event diterima (`/publish`) hingga diproses oleh consumer dan disimpan di SQLite.
    - Keputusan Desain: Ini adalah trade-off dari throughput. Jika publisher mengirim 5.000 event dalam 1 detik, latensi ini akan meningkat.
3. Duplicate Drop Rate (Tingkat Duplikasi): Persentase event yang diterima yang ditandai sebagai duplikat (`duplicate_dropped / received_total`).
    - Keputusan Desain: Ini adalah metrik correctness. Menggunakan database (SQLite) untuk deduplication memastikan kebenaran data, yang diverifikasi dalam stress test `docker-compose`.


---

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