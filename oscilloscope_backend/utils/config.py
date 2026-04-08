from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    Override via environment variables with prefix ``OSCILLOSCOPE_`` (e.g.
    ``OSCILLOSCOPE_HANTEK_DLL_PATH``) or a ``.env`` file beside the working directory.
    """

    model_config = SettingsConfigDict(
        env_prefix="OSCILLOSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API (FastAPI / Uvicorn) ---
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"

    # --- Logging ---
    log_file_enabled: bool = True
    log_file_path: Optional[str] = Field(
        default=None,
        description="Rotating log file path. Default: <project>/logs/oscilloscope.log",
    )
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 5
    log_json_file: bool = Field(
        default=True,
        description="If True, file handler writes one JSON object per line (structured).",
    )

    # --- Hantek HT6000.dll ---
    hantek_dll_path: Optional[str] = Field(
        default=None,
        description="Path to HT6000.dll (relative to process CWD or absolute). If unset, simulation only.",
    )
    hantek_device_index: int = Field(
        default=0,
        description="Device index passed to HT6000_Open (usually 0 for first scope).",
    )
    hantek_adc_volts_full_scale: float = Field(
        default=8.0,
        description="Full-scale voltage used to scale int16 ADC codes to volts in read_data().",
    )
    hantek_stdcall: bool = Field(
        default=True,
        description="True = WinDLL (__stdcall). False = CDLL (__cdecl); must match vendor exports.",
    )

    # --- Capture ---
    sample_rate_hz: float = 1_000_000.0
    read_chunk_samples: int = 4096
    capture_interval_s: float = 0.0
    reconnect_interval_s: float = 2.0
    reconnect_max_attempts: int = 0  # 0 = unlimited hardware reconnect attempts (no simulation if DLL set)
    reconnect_jitter_s: float = 0.5

    # --- Circular buffer: default 2 minutes of history ---
    buffer_seconds: float = 120.0

    ws_queue_max_batches: int = 256

    # --- Display scaling (basic defaults, per-channel when multi-channel arrives) ---
    volt_div: float = 0.5  # volts per division
    time_div_s: float = 1e-3  # seconds per division (nominal)

    # --- Simulation (no hardware) ---
    simulation_enabled: bool = True
    simulation_frequency_hz: float = 10_000.0
    simulation_amplitude: float = 1.0

    @property
    def project_root(self) -> Path:
        # oscilloscope_backend/utils/config.py → repository root (parent of package)
        return Path(__file__).resolve().parents[2]

    def resolved_log_file_path(self) -> Path:
        if self.log_file_path:
            return Path(self.log_file_path)
        return self.project_root / "logs" / "oscilloscope.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
