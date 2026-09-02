from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str = "sqlite:///./railblock.db"
    app_name: str = "RailBlock AI"
    timezone: str = "Asia/Kolkata"
    max_block_minutes: int = 240
    min_buffer_minutes: int = 15
    cp_sat_time_limit_seconds: int = 10
    goods_risk_high_threshold: float = 70.0
    # Phase 1a — Live connector feature flags (default OFF → synthetic prototype preserved)
    live_mode: bool = False
    live_sources: str = ""  # comma-separated allowlist, empty = all when live_mode true
    database_mode: str = "sqlite"  # sqlite | postgres
    # Live source endpoints (optional, only used when live_mode true)
    tms_api_url: str = ""
    smms_api_url: str = ""
    tdms_api_url: str = ""
    coa_api_url: str = ""
    timetable_api_url: str = ""
    goods_api_url: str = ""
    # Incremental cursors (opaque ISO token per source)
    live_cursor_enabled: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
# Ensure SQLite WAL mode handling in database.py
