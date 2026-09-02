from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE_VERIFIED

class SMMSConnector(BaseLiveConnector):
    """Signalling Maintenance & Mgmt System — S&T defects."""
    source_name = "SMMS"
    maturity = SOURCE_MATURITY_LIVE_VERIFIED
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_signal_disconnection","earliest_start","deadline"]

    def _check_enabled(self) -> bool:
        return bool(os.getenv("SMMS_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("SMMS_API_URL")
        if not url:
            raise NotImplementedError("SMMS live fetch not configured. Set SMMS_API_URL and LIVE_MODE=true.")
        if os.getenv("SMMS_MOCK_LIVE") == "1":
            return [{
                "task_id": "TSK-LIVE-002",
                "corridor_id": "COR-1",
                "asset_id": "AST-3",
                "task_type": "SIGNAL_MAINTENANCE",
                "severity": "MEDIUM",
                "estimated_duration_minutes": 45,
                "requires_signal_disconnection": True,
                "external_id": "SMMS-EXT-002",
                "source_updated_at": "2026-09-02T07:00:00Z",
            }]
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
