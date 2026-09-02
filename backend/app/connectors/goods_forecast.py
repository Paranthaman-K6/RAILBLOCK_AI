from typing import List, Dict, Optional
import os
from .base import BaseLiveConnector, SOURCE_MATURITY_LIVE

class GoodsForecastConnector(BaseLiveConnector):
    """Goods forecast — confidence ≥0.7 HARD, ≥0.4 SOFT."""
    source_name = "GOODS_FORECAST"
    maturity = SOURCE_MATURITY_LIVE
    expected_columns = ["corridor_id","section_id","line_id","service_date","start_time","end_time","confidence","forecast_count"]

    def _check_enabled(self) -> bool:
        return bool(os.getenv("GOODS_API_URL") or os.getenv("FOIS_API_URL"))

    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        url = os.getenv("GOODS_API_URL") or os.getenv("FOIS_API_URL")
        if not url:
            raise NotImplementedError("Goods forecast live fetch not configured. Set GOODS_API_URL and LIVE_MODE=true.")
        if os.getenv("GOODS_MOCK_LIVE") == "1":
            return [{
                "corridor_id": "COR-1",
                "service_date": "2026-09-03",
                "start_time": "01:30",
                "end_time": "03:00",
                "confidence": 0.85,
                "forecast_count": 3,
                "external_id": "GOODS-EXT-001",
                "source_updated_at": "2026-09-02T10:00:00Z",
            }]
        params = self._build_cursor_params(cursor)
        return self._http_get(url, params=params)
