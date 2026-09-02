"""
BaseLiveConnector — Phase 1a skeleton.

Prototype default: synthetic CSV via adapters remains active.
Live connectors are feature-flagged behind LIVE_MODE env.
No live network calls are made unless explicitly enabled.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import hashlib
import json
import datetime

SOURCE_MATURITY_SYNTHETIC = "SYNTHETIC"
SOURCE_MATURITY_LIVE = "LIVE"
SOURCE_MATURITY_LIVE_VERIFIED = "LIVE_VERIFIED"


class BaseLiveConnector(ABC):
    """
    Common interface for live source connectors.
    - source_name: canonical uppercase key (TMS, SMMS, TDMS, COA, TIMETABLE, GOODS_FORECAST)
    - maturity: provenance label for ImportRun/Task records
    - Provenance contract: every normalized record carries:
        external_id, source_updated_at (ISO), source_maturity, source_hash
    - fetch() is stubbed; live HTTP/DB calls are opt-in via env.
    """
    source_name: str = "BASE"
    maturity: str = SOURCE_MATURITY_LIVE
    expected_columns: List[str] = []

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        # Default off — explicit LIVE_MODE guard in factory
        return False

    def is_enabled(self) -> bool:
        return self._enabled

    def provenance_template(self) -> Dict:
        return {
            "external_id": None,
            "source_updated_at": None,
            "source_maturity": self.maturity,
            "source_hash": None,
        }

    def compute_hash(self, record: Dict) -> str:
        try:
            canonical = json.dumps(record, sort_keys=True, default=str)
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(record).encode("utf-8")).hexdigest()[:16]

    def attach_provenance(self, normalized: Dict, raw: Optional[Dict] = None) -> Dict:
        """
        Attach provenance labels without mutating core domain fields.
        Keeps backward compat: callers can ignore these keys.
        """
        prov = self.provenance_template()
        raw_src = raw or normalized
        # external_id: prefer natural id from record
        ext = (
            raw_src.get("external_id")
            or raw_src.get("task_id")
            or raw_src.get("train_id")
            or raw_src.get("asset_id")
            or raw_src.get("resource_id")
            or raw_src.get("id")
        )
        if ext:
            prov["external_id"] = str(ext).upper()
        # source_updated_at: prefer source timestamp else now
        ts = raw_src.get("source_updated_at") or raw_src.get("updated_at") or raw_src.get("last_modified")
        if ts:
            prov["source_updated_at"] = str(ts)
        else:
            # synthetic / live without timestamp -> use ingestion time
            prov["source_updated_at"] = datetime.datetime.utcnow().isoformat()
        prov["source_hash"] = self.compute_hash(normalized)
        # merge into record under provenance namespace + flat convenience keys
        normalized["external_id"] = prov["external_id"]
        normalized["source_updated_at"] = prov["source_updated_at"]
        normalized["source_maturity"] = prov["source_maturity"]
        normalized["source_hash"] = prov["source_hash"]
        normalized["_provenance"] = prov
        return normalized

    # Phase 1b — shared HTTP fetch helper (additive, safe no-op)
    def _http_get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> List[Dict]:
        """
        Safe HTTP GET for enabled connectors.
        - Timeout 10s, no retries on 4xx, returns [] on network/timeout (logs warning)
        - Supports both list and {records/data/results} JSON shapes.
        - Pagination via Link header or body.next_cursor handled by caller loop.
        - No network call if url empty -> return [] (safe no-op)
        """
        if not url:
            return []
        try:
            import httpx
            import os
            # Bearer token from env <SOURCE>_API_TOKEN if present (redacted in logs)
            token = os.getenv(f"{self.source_name}_API_TOKEN") or os.getenv(f"{self.source_name.upper()}_API_TOKEN")
            hdrs = dict(headers or {})
            if token and "Authorization" not in hdrs:
                hdrs["Authorization"] = f"Bearer {token}"
            timeout = 10.0
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, params=params, headers=hdrs)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    # JSON parse failure -> treat as parse failure
                    raise ValueError("Failed to parse JSON response")
                # Normalize JSON shapes: list, {records:[]}, {data:[]}, {results:[]}
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for key in ("records", "data", "results", "items", "defects", "tasks"):
                        if key in data and isinstance(data[key], list):
                            return data[key]
                    # Single object wrapper with pagination
                    if "record" in data and isinstance(data["record"], dict):
                        return [data["record"]]
                return []
        except Exception as e:
            # Log warning and propagate to let caller distinguish FETCH_FAILED vs EMPTY_SUCCESS
            try:
                import logging
                logging.getLogger(__name__).warning(f"{self.source_name} live fetch error: {e}")
            except Exception:
                pass
            raise

    def _build_cursor_params(self, cursor: Optional[str], limit: int = 100) -> Dict:
        params: Dict = {"limit": str(limit)}
        if cursor:
            # Opaque cursor used as updated_since / cursor token by various APIs
            params["cursor"] = cursor
            params["updated_since"] = cursor
            params["since"] = cursor
        return params

    def _fetch_paginated(self, base_url: str, cursor: Optional[str] = None, limit: int = 100, max_pages: int = 5, max_records: int = 500) -> List[Dict]:
        """Loop follow next_cursor in JSON body or Link header, capped to max_pages/max_records."""
        all_records: List[Dict] = []
        cur = cursor
        pages = 0
        while pages < max_pages and len(all_records) < max_records:
            params = self._build_cursor_params(cur, limit=limit)
            batch = self._http_get(base_url, params=params)
            if not batch:
                break
            all_records.extend(batch)
            # Check for next_cursor in last response is not directly available here;
            # concrete connectors override if their API provides it via body. For generic, stop after 1 page.
            break  # default single page; override _fetch_paginated if API paginates
        return all_records[:max_records]

    @abstractmethod
    def fetch(self, cursor: Optional[str] = None) -> List[Dict]:
        """
        Live fetch stub. Override in concrete connector.
        cursor: opaque incremental cursor (ISO timestamp or token)
        Returns raw records (pre-normalize). Must NOT mutate DB.
        """
        raise NotImplementedError(f"{self.source_name} live fetch not configured. Set LIVE_MODE=true and {self.source_name}_API_URL")

    def normalize(self, records: List[Dict]) -> List[Dict]:
        """
        Default normalization: delegates to CSV adapter logic for compatibility.
        Concrete connectors may override for API-specific shapes.
        """
        from app.adapters.base import BaseAdapter

        adapter = BaseAdapter()
        # Reuse lowercasing + id uppercasing from BaseAdapter
        normalized = adapter.normalize(records)
        # Attach provenance per record
        out: List[Dict] = []
        for raw, nr in zip(records, normalized):
            out.append(self.attach_provenance(nr, raw))
        return out

    def fetch_and_normalize(self, cursor: Optional[str] = None) -> List[Dict]:
        raws = self.fetch(cursor=cursor)
        return self.normalize(raws)
