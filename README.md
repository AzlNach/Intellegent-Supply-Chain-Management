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
│   │   ├── llm_client.py   # Klien OpenAI SDK direct ke OpenRouter + retry & fallback
│   │   ├── models.yaml     # Konfigurasi role model (primary: gpt-4o-mini, fallback: nemotron)
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
- **API Key OpenRouter**: [openrouter.ai](https://openrouter.ai)
- **Token Backend Stock Copilot**: `X-Dev-Token` dari backend Render

---

## 🚀 Konfigurasi Lingkungan (`.env`)

Buat berkas `.env` di root direktori proyek (`C:\Users\...\ISCM\.env`):

```env
# Token autentikasi ke backend data stok (Render)
DEV_TOKEN="masukkan_token_dev_anda"

# API Key OpenRouter untuk LLM IE Agent
OPENROUTER_API_KEY="sk-or-v1-xxxxxxxx"
```

---

## 💻 Panduan Menjalankan

Jalankan kedua layanan pada dua terminal terpisah:

### 1. Terminal 1 — Agent Service (FastAPI)

```powershell
# Pastikan dependencies Python terpasang:
pip install fastapi uvicorn httpx openai pyyaml pydantic pytest pytest-asyncio websockets

# Jalankan service pada port 8000:
python -m uvicorn app.main:app --app-dir agent-service --host 127.0.0.1 --port 8000 --reload
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
   - **Chip Balasan Cepat**: Tombol *Cek stok MIE-A*, *Hitung kebutuhan*, dll.
   - **Kartu Usulan (Proposal)**: Menampilkan diff stok fisik baru dengan tombol *Setuju* atau *Tolak*.
   - **Event Log**: Menampilkan 50 event sistem secara real-time (*agent_state*, *board_update*, *chat_message*, *solver_state*, dll).

---

## 🧪 Pengujian (Testing)

### 1. Unit & Mock Testing (Python)
Menguji deterministik solver, mock agent, dan sanitasi payload tanpa koneksi jaringan:

```powershell
$env:TEST_MODE = "mock"
$env:PYTHONPATH = ".\agent-service"
python -m pytest agent-service/tests -m mock -v
```

### 2. Live Contract & Probe Testing (Python)
Menguji koneksi langsung ke backend Render, OpenRouter, dan WebSocket service:

```powershell
$env:TEST_MODE = "live"
$env:PYTHONPATH = ".\agent-service"
python -m pytest agent-service/tests/test_live_qa.py -m live -v
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

---

## 🔒 Keamanan
- Kunci API dan token rahasia tidak pernah ditampilkan di log, respon chat, atau bundle frontend.
- Backend logging secara otomatis menyamarkan token header: `X-Dev-Token: ***`.
- Model AI tidak memiliki hak tool untuk menghapus data atau menyetujui usulan revisi secara sepihak. Persetujuan proposal mutlak memerlukan interaksi tombol manusia di antarmuka pengguna.
