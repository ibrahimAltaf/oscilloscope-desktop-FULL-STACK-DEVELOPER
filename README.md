# Oscilloscope Desktop (Cleaned Structure)

Real-time desktop signal analyzer with Electron + Python SDK bridge for Hantek hardware.

## Structure

```text
backend/
  sdk/
  services/
  api/
  schemas/
  docs/
  tests/

frontend/
  electron/
  renderer/
  components/
  styles/
  assets/
```

Active runtime implementation:

- Electron app: `desktop/oscilloscope-desktop-main`
- Hardware bridge service: `backend/services/hardware_service.py`

## Quick Start

1. `pip install -r requirements.txt`
2. `npm --prefix desktop/oscilloscope-desktop-main install`
3. `npm --prefix desktop/oscilloscope-desktop-main run electron:dev`

## Required Documents

- `SETUP_WINDOWS.md`
- `HARDWARE_VERIFICATION.md`
- `DEVELOPER_GUIDE.md`
- `API_DOCS.md`
