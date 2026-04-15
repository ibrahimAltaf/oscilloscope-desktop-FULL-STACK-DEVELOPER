# Oscilloscope Desktop – Full Stack System

A production-grade desktop oscilloscope application with real-time signal capture using Hantek 6000 series devices.

---

## 🚀 Overview

This system is built as a **full-stack desktop application**:

* **Backend (Python):** Handles hardware integration, signal capture, processing, and API.
* **Frontend (Electron + React):** Displays real-time waveform and provides user interface.

---

## 🧠 Architecture

```
Hantek Device → DLL (HTHardDll.dll) → Python Backend → WebSocket → Electron UI → uPlot Graph
```

---

## 🧰 Tech Stack

### Backend

* Python 3.11+
* FastAPI
* WebSocket
* ctypes (DLL integration)
* NumPy
* Threading

### Frontend

* Electron
* React (Vite)
* TypeScript
* uPlot (high-performance charting)

---

## 📁 Project Structure

```
oscilloscope-desktop-FULL-STACK-DEVELOPER/
│
├── oscilloscope_backend/
│   ├── api/
│   │   └── main.py              # FastAPI server
│   │
│   ├── core/
│   │   ├── device_manager.py   # Device lifecycle + reconnect logic
│   │   ├── capture_service.py  # Real-time capture loop
│   │   └── broadcaster.py      # WebSocket data streaming
│   │
│   ├── hantek/
│   │   ├── sdk.py              # DLL integration (ctypes)
│   │   ├── ht6000_api.h        # Reference header
│   │   ├── ht6000_errors.py    # Error mapping
│   │   └── HTHardDll.dll       # Hardware driver
│   │
│   ├── processing/
│   │   ├── buffer.py           # Circular buffer
│   │   └── signal.py           # Signal utilities
│   │
│   ├── utils/
│   │   ├── config.py           # Environment config
│   │   └── logging.py          # Logging system
│   │
│   ├── run_server.py           # Entry point
│   └── requirements.txt
│
├── oscilloscope-desktop/
│   ├── src/
│   │   ├── components/
│   │   │   ├── OscilloscopeChart.tsx
│   │   │   ├── ControlBar.tsx
│   │   │   └── DashboardLayout.tsx
│   │   │
│   │   ├── hooks/
│   │   │   └── useSignalWebSocket.ts
│   │   │
│   │   ├── lib/
│   │   │   └── rollingBuffers.ts
│   │   │
│   │   ├── types/
│   │   │   └── signal.ts
│   │   │
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── main.tsx
│   │
│   ├── electron/
│   │   ├── main.ts             # Electron main process
│   │   └── preload.js          # Secure bridge
│   │
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Backend Setup

```bash
cd oscilloscope_backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Set DLL Path

```bash
set OSCILLOSCOPE_HANTEK_DLL_PATH=oscilloscope_backend/hantek/HTHardDll.dll
```

### Run Backend

```bash
python run_server.py
```

Backend runs at:

```
http://127.0.0.1:8765
```

### Deploy Backend on Vercel

This repository includes the required Vercel backend config:

* `app.py` exports the FastAPI `app` for Vercel discovery.
* `vercel.json` marks this as a backend deployment.
* The backend automatically skips file logging on Vercel, so no Vercel environment variables are required for the simulation API.
* `.vercelignore` keeps desktop build files, logs, caches, and the Windows DLL out of the serverless bundle.

Deploy from the repository root:

```bash
npm i -g vercel
vercel login
vercel
```

For production:

```bash
vercel --prod
```

After deploy, test:

```bash
curl https://your-project.vercel.app/health
curl https://your-project.vercel.app/status
```

Important: Vercel cannot access a local USB oscilloscope or load the bundled Windows DLL. Vercel Functions also are not the right runtime for the persistent WebSocket stream used by `/ws/signal`. Use Vercel for the HTTP API/simulation deployment. For real Hantek hardware capture and live waveform streaming, run the backend on the Windows machine connected to the device.

---

### 2. Frontend Setup

```bash
cd oscilloscope-desktop
npm install
npm run dev
```

Or for Electron:

```bash
npm run electron
```

---

## 🔌 API Endpoints

| Endpoint  | Description           |
| --------- | --------------------- |
| `/start`  | Start capture         |
| `/stop`   | Stop capture          |
| `/status` | Device + system state |
| `/health` | Health check          |

---

## 📡 WebSocket

```
ws://127.0.0.1:8765/ws/signal
```

Streams:

```json
{
  "samples": [...],
  "rms": ...,
  "ptp": ...,
  "timestamp": ...
}
```

---

## 🎯 Features

### ✅ Phase 1 (Completed)

* Real hardware integration (DLL)
* Real-time signal capture
* WebSocket streaming
* Professional oscilloscope UI
* RMS / PTP calculations
* Buffer system
* Reconnect handling
* Logging + monitoring

---

## 🔜 Upcoming (Phase 2)

* FFT (frequency analysis)
* Cursor measurements
* Replay buffer
* Multi-channel support

---

## ⚠️ Notes

* Ensure correct DLL version
* Use 64-bit Python
* Hardware must be connected for real signal
* Simulation mode disabled when DLL is active

---

## 💪 Status

✅ Backend: Production-ready
✅ UI: Near production-ready
⚠️ Final validation: Hardware testing required

---

## 🧠 Developer Notes

* Uses ctypes for hardware integration
* Thread-safe capture system
* High-performance rendering with uPlot
* Designed for extensibility

---

## 📌 License

Private / Proprietary (as per project requirements)

---
