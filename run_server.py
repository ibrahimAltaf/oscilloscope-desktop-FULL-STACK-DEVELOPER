"""
Launch the FastAPI oscilloscope server.

Usage (from this directory):
  python run_server.py

Or:
  uvicorn oscilloscope_backend.api.main:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without installing the package as editable
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __name__ == "__main__":
    import uvicorn

    from oscilloscope_backend.utils.config import get_settings

    s = get_settings()
    uvicorn.run(
        "oscilloscope_backend.api.main:app",
        host=s.host,
        port=s.port,
        log_level=s.log_level.lower(),
        reload=False,
    )
