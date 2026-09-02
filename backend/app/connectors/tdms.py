from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE_VERIFIED

class TDMSConnector(BaseLiveConnector):
    """Traction Distribution Mgmt System — OHE/traction defects."""
    source_name = "TDMS"
    maturity = SOURCE_MATURITY_LIVE_VERIFIED
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_power_isolation","earliest_start","deadline"]

    def _check_enabled(self) -> bool:
        return bool(os.getenv("TDMS_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("TDMS_API_URL")
        if not url:
            raise NotImplementedError("TDMS live fetch not configured. Set TDMS_API_URL and LIVE_MODE=true.")
        if os.getenv("TDMS_MOCK_LIVE") == "1":
            return [{
                "task_id": "TSK-LIVE-003",
                "corridor_id": "COR-2",
                "asset_id": "AST-7",
                "task_type": "OHE_MAINTENANCE",
                "severity": "CRITICAL",
                "estimated_duration_minutes": 90,
                "requires_power_isolation": True,
                "external_id": "TDMS-EXT-003",
                "source_updated_at": "2026-09-02T08:00:00Z",
            }]
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
