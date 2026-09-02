from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE

class TimetableConnector(BaseLiveConnector):
    """Train timetable — protected intervals [departure-buffer, arrival+buffer)."""
    source_name = "TIMETABLE"
    maturity = SOURCE_MATURITY_LIVE
    expected_columns = ["train_id","corridor_id","section_id","line_id","train_type","service_date","departure_time","arrival_time"]

    def _check_enabled(self) -> bool:
        return bool(os.getenv("TIMETABLE_API_URL") or os.getenv("NTES_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("TIMETABLE_API_URL") or os.getenv("NTES_API_URL")
        if not url:
            raise NotImplementedError("Timetable live fetch not configured. Set TIMETABLE_API_URL and LIVE_MODE=true.")
        if os.getenv("TIMETABLE_MOCK_LIVE") == "1":
            return [{
                "train_id": "TRN-LIVE-001",
                "corridor_id": "COR-1",
                "service_date": "2026-09-03",
                "departure_time": "02:00",
                "arrival_time": "02:45",
                "train_type": "PASSENGER",
                "external_id": "TT-EXT-001",
                "source_updated_at": "2026-09-02T09:00:00Z",
            }]
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
