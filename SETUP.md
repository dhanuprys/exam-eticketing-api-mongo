# Panduan Instalasi dan Menjalankan Aplikasi Ticketing API

Dokumen ini berisi panduan lengkap untuk melakukan instalasi, konfigurasi, dan menjalankan aplikasi Ticketing API berbasis FastAPI dan MongoDB.

## 📋 Prasyarat

Sebelum memulai, pastikan Anda telah menginstal perangkat lunak berikut:

1.  **Python 3.10+**: Pastikan Python sudah terinstal. Cek dengan perintah `python --version`.
2.  **MongoDB**: Database lokal yang harus berjalan di port standar `27017` (bisa di-adjust pada file `.env`).
3.  **Git**: Untuk melakukan clone repository ini.

## 🛠️ Instalasi

Ikuti langkah-langkah berikut untuk menginstal aplikasi:

1.  **Clone Repository**
    ```bash
    git clone https://github.com/dhanuprys/exam-eticketing-api-mongo.git
    cd exam-eticketing-api-mongo
    ```

2.  **Buat Virtual Environment (Disarankan)**
    Agar dependency project tidak tercampur dengan system Python.
    ```bash
    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install Dependencies**
    Install semua paket yang dibutuhkan file `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Konfigurasi Environment

Aplikasi ini menggunakan environment variables untuk konfigurasi. Buat file `.env` di root folder proyek (sejajar dengan `app.py`).

**Contoh isi file `.env`:**

```env
# Koneksi Database MongoDB
DB_URL="mongodb://localhost:27017"
DB_NAME="ticketingsystem"

# Konfigurasi Server
HOST="0.0.0.0"
PORT=8050
```

*Catatan: Jika file `.env` tidak dibuat, aplikasi akan menggunakan nilai default seperti di atas.*

## 🚀 Menjalankan Aplikasi

Aplikasi dapat dijalankan dengan dua cara:

### Cara 1: Menggunakan Script Python (Direkomendasikan)
Cara ini paling mudah karena sudah disiapkan konfigurasi default.
```bash
python app.py
```

### Cara 2: Menggunakan Uvicorn (Manual)
Jika Anda ingin menggunakan _hot-reload_ saat development:
```bash
uvicorn app:main --port 8050 --reload
```

Jika berhasil, Anda akan melihat output seperti ini:
```
INFO:     Started server process [pid]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8050 (Press CTRL+C to quit)
```

## 📚 Dokumentasi API (Swagger UI)

FastAPI menyediakan dokumentasi interaktif secara otomatis. Setelah aplikasi berjalan, buka browser dan akses:

*   **Swagger UI**: [http://localhost:8050/docs](http://localhost:8050/docs)
*   **ReDoc**: [http://localhost:8050/redoc](http://localhost:8050/redoc)

## 🧪 Testing dengan Postman

Kami telah menyediakan koleksi Postman untuk pengujian API secara menyeluruh.

1.  Buka Postman.
2.  Import file `manbd-api-mongo-exported.postman_collection.json`.
3.  Jalankan request secara berurutan mulai dari folder **1. Pengecekan Sistem** hingga **6. Utilitas**.

### Endpoint Reset Database
Untuk kebutuhan testing ulang, Anda dapat mereset database (menghapus semua events dan tickets) dengan melakukan request:

*   **Endpoint**: `POST /api/v1/reset-database`
*   **Lokasi di Postman**: Folder _6. Utilitas (Utils)_ -> _Reset Database_

---

**Dibuat oleh Kelompok 6:**
1. I Kadek Sindu Arta
2. Made Marsel Biliana Wijaya
3. Gede Dhanu Purnayasa
