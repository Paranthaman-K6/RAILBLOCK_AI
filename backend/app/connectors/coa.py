from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE_VERIFIED

class COAConnector(BaseLiveConnector):
    """Control Office Application — corridor/asset master + official possession windows.

    In production COA is authoritative for block availability.
    Synthetic prototype windows remain default until COA_API_URL enabled.
    """
    source_name = "COA"
    maturity = SOURCE_MATURITY_LIVE_VERIFIED
    expected_columns = ["corridor_id","section_id","line_id","asset_id","corridor_name","section_name","line_type"]

    def _check_enabled(self) -> bool:
        return bool(os.getenv("COA_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("COA_API_URL")
        if not url:
            raise NotImplementedError("COA live fetch not configured. Set COA_API_URL and LIVE_MODE=true. Prototype synthetic windows continue.")
        if os.getenv("COA_MOCK_LIVE") == "1":
            return [{
                "corridor_id": "COR-1",
                "corridor_name": "Delhi-Howrah (Live)",
                "section_id": "SEC-1",
                "line_id": "LIN-1",
                "external_id": "COA-EXT-COR1",
                "source_updated_at": "2026-09-02T05:00:00Z",
            }]
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
