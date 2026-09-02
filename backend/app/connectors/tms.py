from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE_VERIFIED

class TMSConnector(BaseLiveConnector):
    """Track Management System — defects / overdue tasks for ENGINEERING."""
    source_name = "TMS"
    maturity = SOURCE_MATURITY_LIVE_VERIFIED
    expected_columns = ["task_id","corridor_id","section_id","line_id","asset_id","task_type","description","severity","estimated_duration_minutes","requires_traffic_block","earliest_start","deadline","department"]

    def _check_enabled(self) -> bool:
        # Enabled only via factory gate; instance-level check for URL presence
        return bool(os.getenv("TMS_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("TMS_API_URL")
        if not url:
            raise NotImplementedError("TMS live fetch not configured. Set TMS_API_URL and LIVE_MODE=true. Prototype CSV fallback remains default.")
        # Mock/dry-run path (explicit opt-in for tests)
        if os.getenv("TMS_MOCK_LIVE") == "1":
            return [{
                "task_id": "TSK-LIVE-001",
                "corridor_id": "COR-1",
                "asset_id": "AST-1",
                "task_type": "MAINTENANCE",
                "description": "Live TMS defect (mock)",
                "severity": "HIGH",
                "estimated_duration_minutes": 60,
                "earliest_start": "2026-09-03",
                "deadline": "2026-09-10",
                "department": "ENGINEERING",
                "external_id": "TMS-EXT-001",
                "source_updated_at": "2026-09-02T06:00:00Z",
            }]
        # Live HTTP fetch — cursor-aware incremental sync, safe no-op on error (returns [])
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
