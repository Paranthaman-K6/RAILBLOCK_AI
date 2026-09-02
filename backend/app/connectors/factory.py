"""
Factory — feature-flagged selection between synthetic (CSV adapter) and live connectors.

Constraints:
- Synthetic remains default until LIVE_MODE=true.
- LIVE_SOURCES controls allowlist (comma-separated). Empty → all sources live when LIVE_MODE true.
- Preserves backward compat: run_import(filepath, content) path unchanged.
"""
import os
from typing import Optional, List, Dict

from .base import BaseLiveConnector, SOURCE_MATURITY_SYNTHETIC
from .tms import TMSConnector
from .smms import SMMSConnector
from .tdms import TDMSConnector
from .coa import COAConnector
from .timetable import TimetableConnector
from .goods_forecast import GoodsForecastConnector

LIVE_MAP = {
    "TMS": TMSConnector,
    "SMMS": SMMSConnector,
    "TDMS": TDMSConnector,
    "COA": COAConnector,
    "CORRIDORS": COAConnector,
    "ASSETS": COAConnector,
    "TIMETABLE": TimetableConnector,
    "TRAINS": TimetableConnector,
    "GOODS_FORECAST": GoodsForecastConnector,
    "GOODS-FORECAST": GoodsForecastConnector,
    "GOODS": GoodsForecastConnector,
}

def _live_mode_enabled() -> bool:
    # Check config then env directly for immediate toggle without restart in tests
    try:
        from app.config import settings
        if getattr(settings, "live_mode", False):
            return True
    except Exception:
        pass
    return os.getenv("LIVE_MODE", "").lower() in ("1", "true", "yes", "on")

def _live_sources_allowlist() -> Optional[set]:
    raw = ""
    try:
        from app.config import settings
        raw = getattr(settings, "live_sources", "") or ""
    except Exception:
        pass
    env_raw = os.getenv("LIVE_SOURCES", "")
    # Env takes precedence if set
    if env_raw:
        raw = env_raw
    if not raw or raw.strip() == "":
        return None  # all sources allowed when live_mode true
    return {s.strip().upper().replace("-", "_") for s in raw.split(",") if s.strip()}

def get_live_connector(source_name: str) -> Optional[BaseLiveConnector]:
    """
    Returns live connector instance if feature-flagged and enabled, else None.
    None = caller should use synthetic CSV adapter path.
    """
    key = source_name.upper().replace("-", "_")
    if not _live_mode_enabled():
        return None
    allow = _live_sources_allowlist()
    # Normalize key for allowlist check (e.g., TRAINS maps to TIMETABLE allowlist)
    if allow is not None:
        # also consider alias
        if key not in allow:
            # check if any alias matches allowlist
            # e.g., TRAINS allowed when TIMETABLE in allowlist and vice versa
            alias_hit = False
            for k, cls in LIVE_MAP.items():
                if k == key and cls in [LIVE_MAP.get(a) for a in allow if a in LIVE_MAP]:
                    alias_hit = True
            if not alias_hit:
                return None
    cls = LIVE_MAP.get(key)
    if not cls:
        return None
    inst = cls()
    # Even in live_mode, instance may be disabled if its specific URL not set.
    # Return instance anyway so caller can inspect is_enabled() / raise helpful error.
    return inst

def list_live_connectors() -> List[str]:
    return sorted(set(LIVE_MAP.keys()))

def get_source_maturity(source_name: str) -> str:
    conn = get_live_connector(source_name)
    if conn is None:
        return SOURCE_MATURITY_SYNTHETIC
    return conn.maturity

def should_use_live(source_name: str) -> bool:
    return get_live_connector(source_name) is not None

def get_enabled_connectors() -> List[Dict]:
    """Additive helper for diagnostics: enumerate availability without triggering network."""
    import os
    enabled: List[Dict] = []
    for name in sorted(set(LIVE_MAP.keys())):
        conn = get_live_connector(name)
        # Determine URL presence for diagnostics
        url_env = f"{name}_API_URL"
        # Alias handling for TIMETABLE/GOODS variants
        url = os.getenv(url_env) or os.getenv(f"{name.replace('-','_')}_API_URL") or ""
        if name in ("TRAINS", "TIMETABLE"):
            url = os.getenv("TIMETABLE_API_URL") or os.getenv("NTES_API_URL") or url
        if name.startswith("GOODS"):
            url = os.getenv("GOODS_API_URL") or os.getenv("FOIS_API_URL") or url
        is_en = False
        try:
            is_en = conn.is_enabled() if conn else False
        except Exception:
            is_en = False
        enabled.append({
            "source_name": name,
            "available": conn is not None,
            "enabled": is_en,
            "url_present": bool(url),
            "maturity": conn.maturity if conn else SOURCE_MATURITY_SYNTHETIC,
        })
    return enabled
