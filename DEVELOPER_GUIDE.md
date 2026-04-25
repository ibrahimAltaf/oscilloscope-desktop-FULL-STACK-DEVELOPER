# Developer Guide

## Backend

- SDK wrappers: `backend/sdk`
- Hardware runtime service: `backend/services/hardware_service.py`
- API contract: `backend/api/main.py`
- OpenAPI doc: `backend/docs/openapi.yaml`

## Frontend

- Electron main/preload: `desktop/oscilloscope-desktop-main/electron`
- Renderer: `desktop/oscilloscope-desktop-main/renderer/src`

## Key Runtime Flow

1. Electron starts Python bridge process.
2. Renderer sends RPC (`select_dll`, `inspect_dll`, `connect_device`, `start_capture`).
3. Python service emits `status`, `sample_batch`, `log`.
4. Renderer updates charts/report and supports TXT/JSON export.

## Quality Gates

- `python3 -m compileall backend sdk`
- `npm --prefix desktop/oscilloscope-desktop-main run build`
