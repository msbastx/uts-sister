import pathlib
import os

print("Memulai inisialisasi struktur proyek UTS...")

# 1. Tentukan semua direktori yang perlu dibuat
directories = [
    "src",
    "tests",
    "publisher",  # Untuk bonus Docker Compose
    "data"        # Untuk database SQLite
]

# 2. Tentukan semua file kosong yang ingin Anda buat
# (Anda bisa menambahkan isi default nanti jika mau)
files_to_create = [
    "src/__init__.py",
    "src/main.py",
    "src/consumer.py",
    "src/database.py",
    "src/models.py",
    "tests/__init__.py",
    "tests/test_main.py",
    "publisher/Dockerfile",
    "publisher/publish.py",
    "data/.gitkeep",  # File kosong agar folder 'data' bisa di-commit
    ".gitignore",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "README.md",
    "report.md"
]

# 3. Proses Pembuatan Direktori
print("\nMembuat direktori...")
for dir_path in directories:
    path = pathlib.Path(dir_path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] Direktori dibuat: {dir_path}/")
    except OSError as e:
        print(f"  [GAGAL] Membuat direktori {dir_path}: {e}")

# 4. Proses Pembuatan File
print("\nMembuat file...")
for file_path in files_to_create:
    path = pathlib.Path(file_path)
    try:
        # 'touch' akan membuat file jika belum ada
        path.touch(exist_ok=True)
        print(f"  [OK] File dibuat:      {file_path}")
    except OSError as e:
        print(f"  [GAGAL] Membuat file {file_path}: {e}")

print("\n--- Inisialisasi Selesai ---")