# Stock Memory Copilot — Virtual Office & IE Agent (ISCM)

Sistem asisten inventaris cerdas divisi **SCDS-OR (Supply Chain & Operations Research)** dengan scene visual kantor isometrik pixel art dan agent berbasis LLM untuk audit stok, validasi kebutuhan, serta kalkulasi gap inventaris.

---

## 🏛️ Arsitektur Proyek

```text
ISCM/
├── agent-service/          # Backend agent FastAPI (Python 3.12+)
│   ├── app/
│   │   ├── main.py         # REST (/chat, /proposals) & WebSocket (/ws)
│   │   ├── ie_agent.py     # IE Agent core, loop tools, validasi & deteksi konflik
│   │   ├── llm_client.py   # Klien OpenAI-compatible ke 9Router/OpenRouter + retry
│   │   ├── models.yaml     # Konfigurasi role model (IE Agent: cx/gpt-6-luna)
│   │   ├── tools.py        # Pydantic schemas & tool dispatcher
│   │   ├── memory.py       # Explicit session memory & table snapshot
│   │   ├── events.py       # WebSocket broadcaster & event lifecycle
│   │   ├── backend_client.py # REST client ke Stock Copilot Backend Render
│   │   └── solver/         # Solver engine deterministik (pure Python, non-LLM)
│   └── tests/              # Pytest mock & live test suite
├── frontend/               # Frontend React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── scene/          # PixiJS v8 2:1 isometric pixel art virtual office
│   │   ├── components/     # DebugPanel (Mock) & LivePanel (Chat, Proposals, Event Log)
│   │   ├── store/          # Zustand stores (useOfficeStore & useLiveStore)
│   │   └── lib/            # agentClient (REST) & useAgentSocket (WebSocket)
│   └── tests/e2e/          # Playwright test suite (Mock & Live)
├── scripts/                # Helper tools (list_models.py, probe_live.py)
├── .env                    # Konfigurasi token & API key (di-ignore git)
├── .gitignore              # Proteksi secrets & build artifacts
└── Handoff_Backend_...md   # Spesifikasi backend Stock Copilot API
```

---

## ⚙️ Persyaratan Sistem

- **Python**: 3.11+ (disarankan 3.12+)
- **Node.js**: v20+ atau v24+
- **API key/token 9Router atau OpenRouter** sesuai base URL yang digunakan
- **Token Backend Stock Copilot**: `X-Dev-Token` dari backend Render

---

## 🚀 Konfigurasi Lingkungan (`.env`)

Buat berkas `.env` di root direktori proyek (`C:\Users\...\ISCM\.env`):

```env
# Token autentikasi ke backend data stok (Render)
DEV_TOKEN="masukkan_token_dev_anda"

# Base URL OpenAI-compatible 9Router lokal.
# Gunakan https://openrouter.ai/api/v1 jika memakai OpenRouter langsung.
OPENROUTER_BASE_URL="http://localhost:20128/v1"

# API key/token untuk provider pada base URL di atas
OPENROUTER_API_KEY="masukkan_api_key_atau_token_anda"
```

> Kredensial disimpan hanya di agent-service. Jangan menaruhnya di `frontend/.env.local`,
> mengirimkannya melalui chat, atau melakukan commit terhadap file `.env`.

### Backend data dan Firebase

Aplikasi ini tidak terhubung langsung ke Firebase. Agent-service memanggil Stock Copilot
Backend melalui REST API dengan header `X-Dev-Token`; backend tersebut yang menyimpan data
di Firestore. Alurnya:

```text
Frontend → agent-service → Stock Copilot Backend → Firestore
                         └→ 9Router/OpenRouter (IE Agent)
```

---

## 💻 Panduan Menjalankan

Jalankan kedua layanan pada dua terminal terpisah:

### 1. Terminal 1 — Agent Service (FastAPI)

```powershell
# Pastikan dependencies Python terpasang pada virtual environment:
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn httpx openai pyyaml pydantic pytest pytest-asyncio websockets

# Jalankan service pada port 8000:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir agent-service --host 127.0.0.1 --port 8000 --reload
```

Verifikasi endpoint:
- Health check: `http://127.0.0.1:8000/health`
- LLM status: `http://127.0.0.1:8000/health/llm`
- Swagger UI: `http://127.0.0.1:8000/docs`

### 2. Terminal 2 — Frontend (Vite + React + PixiJS)

```powershell
cd frontend

# Pasang dependencies:
npm install

# Jalankan development server:
npm run dev
```

Buka peramban di `http://localhost:5173`.

---

## 🎮 Penggunaan Aplikasi

1. **Header Switch (MOCK / LIVE)**:
   - **MOCK**: Mengaktifkan *Office 3D Debug Panel* untuk menguji animasi visual karakter (*Idle*, *Reading Board*, *Working*, *Waiting*, *Reporting*), papan tulis (*defined*, *conflict*), dan lampu neon solver secara lokal tanpa koneksi jaringan.
   - **LIVE**: Mengaktifkan *IE Agent Live Panel* yang terhubung ke `ws://127.0.0.1:8000/ws/{session}`.
2. **Fitur Panel Live**:
   - **Live Chat**: Berkomunikasi langsung dengan IE Agent dalam bahasa Indonesia.
   - **Multi-pesan**: Beberapa pesan dapat dikirim berturut-turut. Frontend menampilkannya
     sebagai bubble langsung dan mengantrikan request secara berurutan agar session memory
     agent tetap konsisten.
   - **Chip Balasan Cepat**: Tombol *Cek stok MIE-A*, *Hitung kebutuhan*, dll.
   - **Kartu Usulan (Proposal)**: Menampilkan diff stok fisik baru dengan tombol *Setuju* atau *Tolak*.
   - **Event Log**: Menampilkan 50 event sistem secara real-time (*agent_state*, *board_update*, *chat_message*, *solver_state*, dll).

### Session dan klarifikasi

Live chat menggunakan `session_id` yang disimpan di `localStorage` browser. Session menyimpan
riwayat percakapan dan parameter inventaris selama agent-service berjalan. Batas klarifikasi
default adalah 3 putaran, tetapi ini merupakan soft limit: setelah tercapai, sesi tidak
dihentikan. Agent diminta merangkum data dan meminta langkah paling penting berikutnya tanpa
mengulang pertanyaan yang sama.

Jika perlu memulai konteks browser baru, hapus `vo_session_id` dari `localStorage` lalu
muat ulang halaman. Restart agent-service menghapus seluruh session yang tersimpan di memory.

---

## 🧪 Pengujian (Testing)

### 1. Unit & Mock Testing (Python)
Menguji deterministik solver, mock agent, dan sanitasi payload tanpa koneksi jaringan:

```powershell
$env:TEST_MODE = "mock"
$env:PYTHONPATH = ".\agent-service"
.\.venv\Scripts\python.exe -m pytest agent-service/tests -m mock -v
```

### 2. Live Contract & Probe Testing (Python)
Menguji koneksi langsung ke backend Render, OpenRouter, dan WebSocket service:

```powershell
$env:TEST_MODE = "live"
$env:PYTHONPATH = ".\agent-service"
.\.venv\Scripts\python.exe -m pytest agent-service/tests/test_live_qa.py -m live -v
```

### 3. Frontend End-to-End Testing (Playwright)
```powershell
cd frontend

# Test E2E Mode Mock:
npm run test:e2e

# Test E2E Mode Live:
npm run test:e2e:live

# Production build check:
npm run build
```

Validasi terakhir pada lingkungan pengembangan:

```text
Python non-live tests: 65 passed, 7 deselected
Frontend production build: passed
Frontend MOCK E2E: 6 passed
Frontend lint: passed with pre-existing warnings in OfficeScene.tsx
```

E2E LIVE memerlukan agent-service aktif, 9Router aktif, kredensial valid, dan akses ke
backend stok eksternal.

---

## 🔒 Keamanan
- Kunci API dan token rahasia tidak pernah ditampilkan di log, respon chat, atau bundle frontend.
- Backend logging secara otomatis menyamarkan token header: `X-Dev-Token: ***`.
- Model AI tidak memiliki hak tool untuk menghapus data atau menyetujui usulan revisi secara sepihak. Persetujuan proposal mutlak memerlukan interaksi tombol manusia di antarmuka pengguna.
