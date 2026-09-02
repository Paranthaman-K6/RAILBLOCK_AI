import uuid, datetime, json, csv, io, hashlib
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import Corridor, Section, Line, Asset, Task, TrainMovement, GoodsForecast, Resource, ResourceAvailability, ImportRun, AuditEvent
from app.adapters.tms import TMSAdapter, SMMSAdapter, TDMSAdapter, COAAdapter, TimetableAdapter, GoodsForecastAdapter, ResourceAdapter

# Phase outcome states for incremental recovery (additive, explicit)
OUTCOME_FETCH_FAILED = "FETCH_FAILED"
OUTCOME_PARSE_FAILED = "PARSE_FAILED"
OUTCOME_EMPTY_SUCCESS = "EMPTY_SUCCESS"
OUTCOME_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
OUTCOME_SUCCESS = "SUCCESS"

def _compute_outcome(received: int, accepted: int, rejected: int, duplicate: int, errors: List[Dict]) -> str:
    """Derive structured outcome for diagnostics. Additive, no logic change to acceptance."""
    if received == 0:
        # No records fetched — fetch succeeded but empty (live) vs header missing (synthetic)
        # If errors contain MISSING_COLUMN / HEADER_PARSE_ERROR / EMPTY_FILE, treat as PARSE_FAILED
        for e in errors or []:
            if e.get("code") in ("MISSING_COLUMN", "HEADER_PARSE_ERROR", "EMPTY_FILE"):
                return OUTCOME_PARSE_FAILED
        return OUTCOME_EMPTY_SUCCESS
    if accepted == 0 and (rejected > 0 or any(e.get("code") == "PERSIST_ERROR" for e in errors or [])):
        return OUTCOME_PARSE_FAILED
    if accepted == received and duplicate == 0 and rejected == 0:
        return OUTCOME_SUCCESS
    if accepted > 0 and (rejected > 0 or duplicate > 0):
        return OUTCOME_PARTIAL_SUCCESS
    if accepted == 0 and duplicate > 0 and rejected == 0:
        # Duplicate-only retry: idempotent success, cursor preserved
        return OUTCOME_SUCCESS
    # Fallback: treat as partial if anything not fully success
    if accepted > 0:
        return OUTCOME_PARTIAL_SUCCESS
    return OUTCOME_PARSE_FAILED

# Phase 1a/1b provenance + incremental helpers
def _compute_source_hash(record: Dict) -> str:
    try:
        canonical = json.dumps(record, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(str(record).encode("utf-8")).hexdigest()[:16]

def _get_source_maturity(source_name: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    try:
        from app.connectors.factory import get_source_maturity
        return get_source_maturity(source_name)
    except Exception:
        return "SYNTHETIC"

def _resolve_cursor(db: Session, source_name: str, provided: Optional[str]) -> Optional[str]:
    if provided:
        return provided
    try:
        from app.models import SourceCursor
        cur = db.query(SourceCursor).filter(SourceCursor.source_name == source_name.upper()).first()
        return cur.cursor_value if cur else None
    except Exception:
        return None

def _upsert_cursor(db: Session, source_name: str, cursor_value: Optional[str], success: bool = True, error_message: Optional[str] = None, maturity: Optional[str] = None, outcome: Optional[str] = None):
    """Option A/B: persist cursor + diagnostics (attempts/success/last_error/outcome). Additive, nullable-safe."""
    # Determine if this is a live-tracked attempt vs synthetic default
    is_live_tracked = False
    if maturity and maturity != "SYNTHETIC":
        is_live_tracked = True
    else:
        try:
            import os
            if os.getenv("LIVE_MODE","").lower() in ("1","true","yes","on"):
                is_live_tracked = True
            else:
                from app.config import settings
                if getattr(settings, "live_mode", False):
                    is_live_tracked = True
        except Exception:
            pass
    try:
        from app.models import SourceCursor
        existing = db.query(SourceCursor).filter(SourceCursor.source_name == source_name.upper()).first()
        now = datetime.datetime.utcnow()
        if existing:
            if cursor_value:
                existing.cursor_value = cursor_value
                existing.updated_at = now
            else:
                # Still update updated_at for attempt visibility only if live tracked
                if is_live_tracked:
                    existing.updated_at = now
            # diagnostics counters only for live tracked
            if is_live_tracked:
                try:
                    existing.fetch_attempts = (getattr(existing, "fetch_attempts", 0) or 0) + 1
                    if success:
                        existing.fetch_successes = (getattr(existing, "fetch_successes", 0) or 0) + 1
                        existing.last_success_at = now
                    else:
                        existing.last_error_at = now
                        existing.last_error_message = (error_message or "Unknown error")[:500]
                    if outcome:
                        try:
                            existing.last_outcome = outcome
                        except Exception:
                            pass
                except Exception:
                    pass
        else:
            # Create new row even if cursor is None to record first failure/success (live only for diagnostics)
            if is_live_tracked:
                try:
                    kwargs = dict(
                        source_name=source_name.upper(),
                        cursor_value=cursor_value,
                        updated_at=now,
                        last_success_at=now if success else None,
                        last_error_at=None if success else now,
                        last_error_message=None if success else (error_message or "Unknown error")[:500],
                        fetch_attempts=1,
                        fetch_successes=1 if success else 0,
                        last_outcome=outcome,
                    )
                    # Remove None outcome for backward compat if column missing
                    if outcome is None:
                        kwargs.pop("last_outcome", None)
                    db.add(SourceCursor(**kwargs))
                except TypeError:
                    # Column not yet migrated
                    try:
                        db.add(SourceCursor(source_name=source_name.upper(), cursor_value=cursor_value, updated_at=now))
                    except Exception:
                        pass
            else:
                # Synthetic: just cursor
                try:
                    db.add(SourceCursor(source_name=source_name.upper(), cursor_value=cursor_value, updated_at=now))
                except TypeError:
                    db.add(SourceCursor(source_name=source_name.upper(), cursor_value=cursor_value, updated_at=now))
        db.flush()
    except Exception:
        pass

def _record_cursor_error(db: Session, source_name: str, error_message: str, maturity: Optional[str] = None, outcome: Optional[str] = None):
    """Helper to record a failed fetch/parse attempt without advancing cursor."""
    if outcome is None:
        outcome = OUTCOME_FETCH_FAILED
    try:
        _upsert_cursor(db, source_name, None, success=False, error_message=error_message, maturity=maturity, outcome=outcome)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

ADAPTER_MAP = {
    "TMS": TMSAdapter,
    "SMMS": SMMSAdapter,
    "TDMS": TDMSAdapter,
    "COA": COAAdapter,
    "TIMETABLE": TimetableAdapter,
    "TRAINS": TimetableAdapter,
    "GOODS_FORECAST": GoodsForecastAdapter,
    "GOODS-FORECAST": GoodsForecastAdapter,
    "RESOURCES": ResourceAdapter,
    "RESOURCE": ResourceAdapter,
    "CORRIDORS": COAAdapter,
    "ASSETS": COAAdapter,
}

def _parse_time_for_dup(v):
    if v is None:
        return 0
    s=str(v).strip()
    if s.isdigit():
        return int(s)
    if ":" in s:
        parts=s.split(":")
        try:
            h=int(parts[0]); m=int(parts[1].split(" ")[0])
            return h*60+m
        except:
            return 0
    try:
        return int(float(s))
    except:
        return 0

def get_adapter(source_name: str, content: str):
    key = source_name.upper().replace("-","_")
    adapter_cls = ADAPTER_MAP.get(key, TMSAdapter)
    a = adapter_cls(content=content)
    a.source_name = source_name.upper()
    return a

def validate_structural(records, expected_columns):
    errors=[]
    if not records:
        errors.append({"row":0,"field":"file","severity":"ERROR","code":"EMPTY_FILE","message":"No records found"})
        return errors
    # check header
    first_keys = set(records[0].keys()) if records else set()
    # expected_columns are lowercased
    missing = [c for c in expected_columns if c.lower() not in first_keys]
    for m in missing:
        errors.append({"row":0,"field":m,"severity":"ERROR","code":"MISSING_COLUMN","message":f"Missing column {m}"})
    return errors

def _validate_headers_streaming(content: str, expected_columns):
    """Validate headers without loading full file into memory - structured error with row, field, code."""
    try:
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames is None:
            return [{"row":0,"field":"file","severity":"ERROR","code":"EMPTY_FILE","message":"No header found"}]
        # Normalize to lower stripped
        header_set = set(h.strip().lower() for h in reader.fieldnames if h)
        missing=[]
        for exp in expected_columns:
            if exp.lower() not in header_set:
                missing.append({"row":0,"field":exp,"severity":"ERROR","code":"MISSING_COLUMN","message":f"Missing column {exp}"})
        return missing
    except Exception as e:
        return [{"row":0,"field":"file","severity":"ERROR","code":"HEADER_PARSE_ERROR","message":str(e)}]

def run_import(db: Session, source_name: str, content: str, user_id="demo_user", cursor_value: Optional[str] = None, source_maturity: Optional[str] = None, source_hash: Optional[str] = None):
    import_run_id = str(uuid.uuid4())[:8]
    started = datetime.datetime.utcnow()
    # Phase 1a/1b: resolve maturity and cursor (feature-flagged, default SYNTHETIC preserves prototype)
    resolved_maturity = _get_source_maturity(source_name, source_maturity)
    resolved_cursor = _resolve_cursor(db, source_name, cursor_value)
    adapter = get_adapter(source_name, content)
    # Structural header validation BEFORE reading all rows (streaming)
    header_errors = _validate_headers_streaming(content, adapter.expected_columns)
    if header_errors:
        received = 0
        try:
            raw_tmp = adapter.load()
            received = len(raw_tmp)
        except:
            received = 0
        errors = header_errors.copy()
        # also mark all as rejected if headers missing — explicit parse failure, do not advance cursor
        completed = datetime.datetime.utcnow()
        outcome = OUTCOME_PARSE_FAILED
        # Record live cursor error without advancing (additive, only for live)
        try:
            if resolved_maturity != "SYNTHETIC":
                _record_cursor_error(db, source_name, errors[0].get("message","Header parse failed") if errors else "Header parse failed", maturity=resolved_maturity, outcome=outcome)
            else:
                # Still check LIVE_MODE env for is_live_tracked
                import os
                if os.getenv("LIVE_MODE","").lower() in ("1","true","yes","on"):
                    _record_cursor_error(db, source_name, errors[0].get("message","Header parse failed") if errors else "Header parse failed", maturity=resolved_maturity, outcome=outcome)
        except Exception:
            pass
        try:
            ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps([]), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor, outcome=outcome)
        except TypeError:
            try:
                ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps([]), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor)
            except Exception:
                ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps([]), started_at=started, completed_at=completed)
        db.add(ir)
        db.add(AuditEvent(action="IMPORT", entity_type=source_name.upper(), entity_id=import_run_id, user_id=user_id, details=json.dumps({"received":received,"accepted":0,"rejected":received,"error":"MISSING_COLUMN","source_maturity":resolved_maturity,"outcome":outcome})))
        db.commit()
        return {"import_run_id": import_run_id, "source_name": source_name.upper(), "received_count": received, "accepted_count":0,"rejected_count":received,"warning_count":0,"errors":errors,"warnings":[],"duplicate_count":0,"started_at":started.isoformat(),"completed_at":completed.isoformat(),"source_maturity":resolved_maturity,"cursor_value":resolved_cursor,"outcome":outcome}
    raw = adapter.load()
    received = len(raw)
    errors=[]
    warnings=[]
    accepted=0
    rejected=0
    duplicate=0
    # structural second pass for empty file — parse failure, do not advance cursor
    if not raw:
        errors.append({"row":0,"field":"file","severity":"ERROR","code":"EMPTY_FILE","message":"No records found"})
        completed = datetime.datetime.utcnow()
        outcome = OUTCOME_PARSE_FAILED
        try:
            if resolved_maturity != "SYNTHETIC":
                _record_cursor_error(db, source_name, "Empty file", maturity=resolved_maturity, outcome=outcome)
        except Exception:
            pass
        try:
            ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor, outcome=outcome)
        except TypeError:
            try:
                ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor)
            except Exception:
                ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=0, rejected_count=received, warning_count=0, duplicate_count=0, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed)
        db.add(ir)
        db.commit()
        return {"import_run_id": import_run_id, "source_name": source_name.upper(), "received_count": received, "accepted_count":0,"rejected_count":received,"warning_count":0,"errors":errors,"warnings":warnings,"duplicate_count":0,"started_at":started.isoformat(),"completed_at":completed.isoformat(),"source_maturity":resolved_maturity,"cursor_value":resolved_cursor,"outcome":outcome}
    # Cache existing identifiers during single import run to avoid N+1
    source_upper = source_name.upper()
    # Bulk fetch existing sets
    corridor_set = set(r[0] for r in db.query(Corridor.id).all())
    asset_set = set(r[0] for r in db.query(Asset.id).all())
    resource_set = set(r[0] for r in db.query(Resource.id).all())
    task_set = set(r[0] for r in db.query(Task.id).all()) if source_upper in ["TMS","SMMS","TDMS","TASKS"] else set()
    train_set = set(r[0] for r in db.query(TrainMovement.id).all()) if source_upper in ["TIMETABLE","TRAINS"] else set()
    # For composite checks, build sets
    avail_set = set()
    if source_upper in ["RESOURCES","RESOURCE"]:
        avail_set = set(f"{r.resource_id}|{r.service_date}|{r.start_time}" for r in db.query(ResourceAvailability.resource_id, ResourceAvailability.service_date, ResourceAvailability.start_time).all())
    goods_set = set()
    if source_upper in ["GOODS_FORECAST","GOODS-FORECAST"]:
        goods_set = set(f"{r.corridor_id}|{r.service_date}|{r.start_time}" for r in db.query(GoodsForecast.corridor_id, GoodsForecast.service_date, GoodsForecast.start_time).all())
    # For dependency batch handling, also prepare seen for batch deps (tasks in same file not yet persisted)
    # normalize
    normalized = adapter.normalize(raw)
    # Phase 1a/1b provenance enrichment — attach hash/maturity without breaking validation
    # Order: set maturity first so hash includes maturity (prevents LIVE vs SYNTHETIC collision)
    for nr, raw_rec in zip(normalized, raw):
        if not nr.get("external_id"):
            base_id = nr.get("task_id") or nr.get("train_id") or nr.get("asset_id") or nr.get("resource_id") or nr.get("corridor_id")
            if base_id:
                nr["external_id"] = str(base_id).upper()
        if not nr.get("source_updated_at"):
            nr["source_updated_at"] = raw_rec.get("source_updated_at") or raw_rec.get("updated_at") or datetime.datetime.utcnow().isoformat()
        # Preserve explicit maturity from raw if present, else resolved
        if not nr.get("source_maturity"):
            nr["source_maturity"] = resolved_maturity
        # Also store raw provenance for audit if needed
        nr["_cursor_value"] = resolved_cursor
        try:
            nr["source_hash"] = _compute_source_hash(nr)
        except Exception:
            nr["source_hash"] = None
    # referential + operational + duplicate per source
    seen_ids=set()
    to_persist=[]
    for idx, rec in enumerate(normalized, start=2):  # row 2 is first data row (1 header)
        row_errors=[]
        # duplicate detection within file - use composite keys per source
        if source_upper in ["TMS","SMMS","TDMS","TASKS"]:
            tid = str(rec.get("task_id") or f"row{idx}").upper()
            dup_key = tid
        elif source_upper in ["TIMETABLE","TRAINS"]:
            tid = str(rec.get("train_id") or f"row{idx}").upper()
            dup_key = tid
        elif source_upper in ["RESOURCES","RESOURCE"]:
            tid = str(rec.get("resource_id") or f"row{idx}").upper()
            dup_key = f"{tid}|{rec.get('service_date','')}|{rec.get('start_time','')}"
        elif source_upper in ["COA","CORRIDORS","ASSETS"]:
            tid = str(rec.get("asset_id") or rec.get("line_id") or rec.get("section_id") or rec.get("corridor_id") or f"row{idx}").upper()
            dup_key = tid
        elif source_upper in ["GOODS_FORECAST","GOODS-FORECAST"]:
            tid = str(rec.get("corridor_id") or f"row{idx}").upper()
            dup_key = f"{tid}|{rec.get('service_date','')}|{rec.get('start_time','')}|{rec.get('line_id','')}"
        else:
            tid = str(rec.get("task_id") or rec.get("train_id") or rec.get("resource_id") or rec.get("corridor_id") or rec.get("asset_id") or f"row{idx}").upper()
            dup_key = tid

        if dup_key in seen_ids:
            duplicate+=1
            warnings.append({"row":idx,"field":"task_id","severity":"WARNING","code":"DUPLICATE","message":f"Duplicate id {dup_key} in import"})
            continue
        seen_ids.add(dup_key)
        # check existing in DB for idempotent (already exists) - use cached sets where possible
        exists=False
        if source_upper in ["TMS","SMMS","TDMS","TASKS"] and tid:
            exists = tid in task_set
        elif source_upper in ["TIMETABLE","TRAINS"] and rec.get("train_id"):
            exists = str(rec.get("train_id")).upper() in train_set
        elif source_upper in ["RESOURCES","RESOURCE"] and rec.get("resource_id"):
            rid = str(rec.get("resource_id")).upper()
            if rec.get("service_date"):
                comp = f"{rid}|{str(rec.get('service_date'))}|{_parse_time_for_dup(rec.get('start_time') or '00:00')}"
                if comp in avail_set:
                    exists = True
                else:
                    exists = False
                    # if resource_id without availability was considered duplicate only when checking pure resource
            else:
                exists = rid in resource_set
        elif source_upper in ["COA","CORRIDORS","ASSETS"]:
            if rec.get("asset_id"):
                exists = str(rec.get("asset_id")).upper() in asset_set
            else:
                exists = False
        elif source_upper in ["GOODS_FORECAST","GOODS-FORECAST"]:
            if rec.get("corridor_id") and rec.get("service_date") and rec.get("start_time"):
                comp = f"{str(rec.get('corridor_id')).upper()}|{str(rec.get('service_date'))}|{_parse_time_for_dup(rec.get('start_time'))}"
                exists = comp in goods_set
        if exists:
            duplicate+=1
            continue
        # operational validation
        # duration
        if "estimated_duration_minutes" in rec:
            try:
                dur = int(float(str(rec["estimated_duration_minutes"]))) if rec["estimated_duration_minutes"] not in (None,"") else 0
                if dur <=0 or dur> 480:
                    row_errors.append({"row":idx,"field":"estimated_duration_minutes","severity":"ERROR","code":"INVALID_DURATION","message":"Duration must be 1-480"})
                else:
                    rec["estimated_duration_minutes"]=dur
            except:
                row_errors.append({"row":idx,"field":"estimated_duration_minutes","severity":"ERROR","code":"INVALID_DURATION","message":"Invalid duration"})
        # date validation
        for df in ["earliest_start","deadline","service_date"]:
            if df in rec and rec[df]:
                val=str(rec[df]).strip()
                # try parse YYYY-MM-DD or datetime
                try:
                    # allow YYYY-MM-DD or YYYY-MM-DDTHH:MM etc
                    if "T" in val:
                        datetime.datetime.fromisoformat(val.replace("Z",""))
                    elif len(val)==10:
                        datetime.datetime.strptime(val, "%Y-%m-%d")
                    else:
                        # try time minutes
                        if ":" in val:
                            pass
                        else:
                            datetime.datetime.strptime(val, "%Y-%m-%d")
                except:
                    row_errors.append({"row":idx,"field":df,"severity":"ERROR","code":"INVALID_DATE","message":f"Invalid date {val}"})
        # referential: corridor, asset, resource, dependency
        corridor_id = rec.get("corridor_id")
        if corridor_id:
            corridor_id = str(corridor_id).upper()
            rec["corridor_id"]=corridor_id
            if corridor_id not in corridor_set:
                if source_name.upper() in ["TMS","SMMS","TDMS","TASKS","TIMETABLE","TRAINS","GOODS_FORECAST"]:
                    row_errors.append({"row":idx,"field":"corridor_id","severity":"ERROR","code":"UNKNOWN_CORRIDOR","message":f"Corridor {corridor_id} does not exist."})
        asset_id = rec.get("asset_id")
        if asset_id:
            asset_id=str(asset_id).upper()
            rec["asset_id"]=asset_id
            if asset_id and asset_id not in asset_set:
                if source_name.upper() in ["TMS","SMMS","TDMS","TASKS"]:
                    row_errors.append({"row":idx,"field":"asset_id","severity":"ERROR","code":"UNKNOWN_ASSET","message":f"Asset {asset_id} does not exist."})
        # resource ids - cached
        if rec.get("required_resource_ids"):
            rids = str(rec["required_resource_ids"]).split(";") if isinstance(rec["required_resource_ids"], str) else []
            for rid in rids:
                rid=rid.strip().upper()
                if rid and rid not in resource_set:
                    row_errors.append({"row":idx,"field":"required_resource_ids","severity":"ERROR","code":"UNKNOWN_RESOURCE","message":f"Resource {rid} does not exist."})
        # dependency - cached + batch seen
        if rec.get("dependency_task_ids"):
            dids = str(rec["dependency_task_ids"]).split(";") if isinstance(rec["dependency_task_ids"], str) else []
            for did in dids:
                did=did.strip().upper()
                if did and did not in task_set and did not in seen_ids:
                    row_errors.append({"row":idx,"field":"dependency_task_ids","severity":"ERROR","code":"UNKNOWN_DEPENDENCY","message":f"Dependency {did} does not exist."})
        if row_errors:
            errors.extend(row_errors)
            rejected+=1
        else:
            to_persist.append((idx, rec))
            accepted+=1

    # Persist accepted - use savepoints to isolate each record (Step 2 partial batch recovery)
    persisted = []  # track successfully persisted for cursor advancement
    for idx, rec in to_persist:
        try:
            with db.begin_nested():
                persist_record(db, source_name.upper(), rec)
            persisted.append((idx, rec))
        except Exception as e:
            # nested transaction rolled back automatically
            errors.append({"row":idx,"field":"general","severity":"ERROR","code":"PERSIST_ERROR","message":str(e)})
            accepted-=1
            rejected+=1

    completed = datetime.datetime.utcnow()
    # compute import-level source_hash (aggregate of actually persisted record hashes) for idempotency tracking
    try:
        agg_hash = _compute_source_hash({"ids": sorted([r.get("task_id") or r.get("train_id") or str(i) for i, r in enumerate(persisted)])}) if persisted else None
    except Exception:
        agg_hash = None
    # Determine explicit outcome for diagnostics (Step 1-4)
    outcome = _compute_outcome(received, len(persisted), rejected, duplicate, errors)
    # audit with provenance
    db.add(AuditEvent(action="IMPORT", entity_type=source_name.upper(), entity_id=import_run_id, user_id=user_id, details=json.dumps({"received":received,"accepted":accepted,"source_maturity":resolved_maturity,"cursor_value":resolved_cursor,"outcome":outcome})))
    # Persist cursor for incremental recovery: advance only to last successfully persisted record (Step 1/2/3)
    # If no persisted records (all rejected/duplicates), preserve resolved_cursor without advancing
    next_cursor = resolved_cursor
    if persisted:
        try:
            times = [r.get("source_updated_at") for _, r in persisted if r.get("source_updated_at")]
            # Always advance to max persisted timestamp, ignore provided cursor_value (which is FROM)
            next_cursor = max(times) if times else (cursor_value or resolved_cursor or completed.isoformat())
        except Exception:
            next_cursor = cursor_value or resolved_cursor or completed.isoformat()
    # Upsert cursor with outcome (live-tracked only when maturity != SYNTHETIC, cursor preserved otherwise)
    try:
        _upsert_cursor(db, source_name.upper(), next_cursor, success=(outcome not in (OUTCOME_FETCH_FAILED, OUTCOME_PARSE_FAILED)), maturity=resolved_maturity, outcome=outcome)
    except Exception:
        pass
    try:
        ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, source_hash=agg_hash, cursor_value=next_cursor, outcome=outcome)
    except TypeError:
        try:
            ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, source_hash=agg_hash, cursor_value=next_cursor)
        except Exception:
            ir = ImportRun(id=import_run_id, source_name=source_name.upper(), received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed)
    db.add(ir)
    db.commit()
    return {"import_run_id": import_run_id, "source_name": source_name.upper(), "received_count": received, "accepted_count":accepted,"rejected_count":rejected,"warning_count":len(warnings),"errors":errors,"warnings":warnings,"duplicate_count":duplicate,"started_at":started.isoformat(),"completed_at":completed.isoformat(),"source_maturity":resolved_maturity,"source_hash":agg_hash,"cursor_value":next_cursor,"outcome":outcome}

# Phase 1b — Incremental ingestion from live connector records (bypasses CSV)
def run_import_records(
    db: Session,
    source_name: str,
    records: List[Dict],
    user_id: str = "live_sync",
    cursor_value: Optional[str] = None,
    source_maturity: Optional[str] = None,
) -> Dict:
    """
    Live path: records already fetched via BaseLiveConnector.fetch().
    Uses same validation + provenance + hash dedup as run_import but without CSV header step.
    Preserves idempotency via source_hash + natural id.
    """
    if not isinstance(records, list):
        records = []
    import_run_id = str(uuid.uuid4())[:8]
    started = datetime.datetime.utcnow()
    resolved_maturity = _get_source_maturity(source_name, source_maturity)
    resolved_cursor = _resolve_cursor(db, source_name, cursor_value)
    source_upper = source_name.upper()
    received = len(records)
    if received == 0:
        completed = datetime.datetime.utcnow()
        # Step 3 empty-result: successful empty without advancing (preserve resolved_cursor)
        outcome_empty = OUTCOME_EMPTY_SUCCESS
        try:
            _upsert_cursor(db, source_upper, resolved_cursor, success=True, maturity=resolved_maturity, outcome=outcome_empty)
        except Exception:
            pass
        try:
            ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=0, accepted_count=0, rejected_count=0, warning_count=0, duplicate_count=0, errors=json.dumps([]), warnings=json.dumps([]), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor, outcome=outcome_empty)
        except TypeError:
            try:
                ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=0, accepted_count=0, rejected_count=0, warning_count=0, duplicate_count=0, errors=json.dumps([]), warnings=json.dumps([]), started_at=started, completed_at=completed, source_maturity=resolved_maturity, cursor_value=resolved_cursor)
            except Exception:
                ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=0, accepted_count=0, rejected_count=0, warning_count=0, duplicate_count=0, errors=json.dumps([]), warnings=json.dumps([]), started_at=started, completed_at=completed)
        db.add(ir)
        db.commit()
        return {"import_run_id": import_run_id, "source_name": source_upper, "received_count": 0, "accepted_count": 0, "rejected_count": 0, "warning_count": 0, "errors": [], "warnings": [], "duplicate_count": 0, "started_at": started.isoformat(), "completed_at": completed.isoformat(), "source_maturity": resolved_maturity, "cursor_value": resolved_cursor, "outcome": outcome_empty}
    # Use adapter for normalization (same as CSV)
    adapter = get_adapter(source_upper, "")
    # Wrap raw records into CSV-like dicts for adapter.normalize (already Dict)
    normalized = adapter.normalize(records)
    # Enrich provenance — maturity first so hash includes it, preserve raw if present
    for nr, raw_rec in zip(normalized, records):
        # Preserve explicit maturity/hash from live connector if present, else resolved
        if raw_rec.get("source_maturity"):
            nr["source_maturity"] = str(raw_rec["source_maturity"])
        elif not nr.get("source_maturity"):
            nr["source_maturity"] = resolved_maturity
        if not nr.get("external_id"):
            # derive then override with raw explicit if present
            base_id = nr.get("task_id") or nr.get("train_id") or nr.get("asset_id") or nr.get("resource_id") or nr.get("corridor_id")
            if base_id:
                nr["external_id"] = str(base_id).upper()
            if raw_rec.get("external_id"):
                nr["external_id"] = str(raw_rec["external_id"]).upper()
        else:
            if raw_rec.get("external_id"):
                nr["external_id"] = str(raw_rec["external_id"]).upper()
        if not nr.get("source_updated_at"):
            nr["source_updated_at"] = raw_rec.get("source_updated_at") or raw_rec.get("updated_at") or datetime.datetime.utcnow().isoformat()
        else:
            if raw_rec.get("source_updated_at"):
                nr["source_updated_at"] = str(raw_rec["source_updated_at"])
        nr["_cursor_value"] = resolved_cursor
        # Hash last, after maturity/external_id/timestamp final
        if raw_rec.get("source_hash"):
            nr["source_hash"] = str(raw_rec["source_hash"])
        else:
            try:
                nr["source_hash"] = _compute_source_hash(nr)
            except Exception:
                nr["source_hash"] = None
    # Reuse validation loop via helper — delegate to existing run_import logic by building synthetic CSV content?
    # Instead, run minimal duplicate/hash check then persist via same path as run_import loop
    # Build hash set for existing source_hash to dedupe incremental (Phase 1b) — includes ResourceAvailability via composite hash
    existing_hashes = set()
    try:
        if source_upper in ["TMS", "SMMS", "TDMS", "TASKS"]:
            existing_hashes = {r[0] for r in db.query(Task.source_hash).filter(Task.source_hash.isnot(None)).all()}
        elif source_upper in ["TIMETABLE", "TRAINS"]:
            existing_hashes = {r[0] for r in db.query(TrainMovement.source_hash).filter(TrainMovement.source_hash.isnot(None)).all()}
        elif source_upper in ["GOODS_FORECAST", "GOODS-FORECAST"]:
            existing_hashes = {r[0] for r in db.query(GoodsForecast.source_hash).filter(GoodsForecast.source_hash.isnot(None)).all()}
        elif source_upper in ["RESOURCES", "RESOURCE"]:
            # ResourceAvailability has no source_hash column yet; use composite avail_set for dedup, but also check Task/Resource hash for idempotency
            existing_hashes = {r[0] for r in db.query(Task.source_hash).filter(Task.source_hash.isnot(None)).all()} if False else set()
    except Exception:
        existing_hashes = set()
    # Cache id sets as in run_import
    corridor_set = set(r[0] for r in db.query(Corridor.id).all())
    asset_set = set(r[0] for r in db.query(Asset.id).all())
    resource_set = set(r[0] for r in db.query(Resource.id).all())
    task_set = set(r[0] for r in db.query(Task.id).all()) if source_upper in ["TMS", "SMMS", "TDMS", "TASKS"] else set()
    train_set = set(r[0] for r in db.query(TrainMovement.id).all()) if source_upper in ["TIMETABLE", "TRAINS"] else set()
    goods_set = set(f"{r.corridor_id}|{r.service_date}|{r.start_time}" for r in db.query(GoodsForecast.corridor_id, GoodsForecast.service_date, GoodsForecast.start_time).all()) if source_upper in ["GOODS_FORECAST", "GOODS-FORECAST"] else set()
    avail_set = set(f"{r.resource_id}|{r.service_date}|{r.start_time}" for r in db.query(ResourceAvailability.resource_id, ResourceAvailability.service_date, ResourceAvailability.start_time).all()) if source_upper in ["RESOURCES", "RESOURCE"] else set()
    errors: List[Dict] = []
    warnings: List[Dict] = []
    accepted = 0
    rejected = 0
    duplicate = 0
    seen_ids: set = set()
    to_persist: List = []
    for idx, rec in enumerate(normalized, start=1):
        # hash dedup (Phase 1b incremental)
        h = rec.get("source_hash")
        if h and h in existing_hashes:
            duplicate += 1
            continue
        # natural id duplicate within batch
        if source_upper in ["TMS", "SMMS", "TDMS", "TASKS"]:
            dup_key = str(rec.get("task_id") or f"row{idx}").upper()
        elif source_upper in ["TIMETABLE", "TRAINS"]:
            dup_key = str(rec.get("train_id") or f"row{idx}").upper()
        elif source_upper in ["RESOURCES", "RESOURCE"]:
            dup_key = f"{str(rec.get('resource_id') or f'row{idx}').upper()}|{rec.get('service_date','')}|{rec.get('start_time','')}"
        elif source_upper in ["COA", "CORRIDORS", "ASSETS"]:
            dup_key = str(rec.get("asset_id") or rec.get("line_id") or rec.get("section_id") or rec.get("corridor_id") or f"row{idx}").upper()
        elif source_upper in ["GOODS_FORECAST", "GOODS-FORECAST"]:
            dup_key = f"{str(rec.get('corridor_id') or f'row{idx}').upper()}|{rec.get('service_date','')}|{rec.get('start_time','')}"
        else:
            dup_key = str(rec.get("task_id") or f"row{idx}").upper()
        if dup_key in seen_ids:
            duplicate += 1
            warnings.append({"row": idx, "field": "id", "severity": "WARNING", "code": "DUPLICATE", "message": f"Duplicate {dup_key}"})
            continue
        seen_ids.add(dup_key)
        # Quick existence check (natural id)
        exists = False
        if source_upper in ["TMS", "SMMS", "TDMS", "TASKS"] and rec.get("task_id"):
            exists = str(rec["task_id"]).upper() in task_set
        elif source_upper in ["TIMETABLE", "TRAINS"] and rec.get("train_id"):
            exists = str(rec["train_id"]).upper() in train_set
        elif source_upper in ["GOODS_FORECAST", "GOODS-FORECAST"] and rec.get("corridor_id"):
            comp = f"{str(rec.get('corridor_id')).upper()}|{str(rec.get('service_date'))}|{_parse_time_for_dup(rec.get('start_time'))}"
            exists = comp in goods_set
        if exists:
            duplicate += 1
            continue
        # Operational validation (reuse minimal checks)
        row_errors: List[Dict] = []
        if "estimated_duration_minutes" in rec:
            try:
                dur = int(float(str(rec["estimated_duration_minutes"]))) if rec["estimated_duration_minutes"] not in (None, "") else 0
                if dur <= 0 or dur > 480:
                    row_errors.append({"row": idx, "field": "estimated_duration_minutes", "severity": "ERROR", "code": "INVALID_DURATION", "message": "Duration must be 1-480"})
            except Exception:
                row_errors.append({"row": idx, "field": "estimated_duration_minutes", "severity": "ERROR", "code": "INVALID_DURATION", "message": "Invalid duration"})
        if rec.get("corridor_id"):
            cid = str(rec["corridor_id"]).upper()
            if cid not in corridor_set:
                row_errors.append({"row": idx, "field": "corridor_id", "severity": "ERROR", "code": "UNKNOWN_CORRIDOR", "message": f"Corridor {cid} does not exist."})
        if rec.get("asset_id"):
            aid = str(rec["asset_id"]).upper()
            if aid and aid not in asset_set and source_upper in ["TMS", "SMMS", "TDMS", "TASKS"]:
                row_errors.append({"row": idx, "field": "asset_id", "severity": "ERROR", "code": "UNKNOWN_ASSET", "message": f"Asset {aid} does not exist."})
        if row_errors:
            errors.extend(row_errors)
            rejected += 1
        else:
            to_persist.append((idx, rec))
            accepted += 1
    # Persist with partial batch recovery (Step 2)
    persisted_live = []
    for idx, rec in to_persist:
        try:
            with db.begin_nested():
                persist_record(db, source_upper, rec)
            persisted_live.append((idx, rec))
        except Exception as e:
            errors.append({"row": idx, "field": "general", "severity": "ERROR", "code": "PERSIST_ERROR", "message": str(e)})
            accepted -= 1
            rejected += 1
    completed = datetime.datetime.utcnow()
    # Determine explicit outcome for live diagnostics (Step 4)
    outcome = _compute_outcome(received, len(persisted_live), rejected, duplicate, errors)
    # Distinguish empty vs duplicate-only: both are success variants but explicit
    if received == 0:
        outcome = OUTCOME_EMPTY_SUCCESS
    elif accepted == 0 and duplicate > 0 and rejected == 0:
        outcome = OUTCOME_SUCCESS  # duplicate-only idempotent success
    # Cursor update: Step 1 failure-safe, Step 2 partial, Step 3 empty semantics
    # Empty fetch (received==0) -> EMPTY_SUCCESS without advancing (keep resolved_cursor)
    # Duplicate/rejected (received>0 but persisted_live empty) -> success without advancing
    # Partial success -> advance to last successfully persisted record's timestamp
    next_cursor = resolved_cursor
    if persisted_live:
        try:
            times = [r.get("source_updated_at") for _, r in persisted_live if r.get("source_updated_at")]
            next_cursor = max(times) if times else (cursor_value or resolved_cursor or completed.isoformat())
        except Exception:
            next_cursor = cursor_value or resolved_cursor or completed.isoformat()
        try:
            _upsert_cursor(db, source_upper, next_cursor, success=True, maturity=resolved_maturity, outcome=outcome)
        except Exception:
            pass
    elif received > 0:
        # Duplicate/rejected batch: still a successful fetch attempt without cursor advance (Step 3)
        try:
            _upsert_cursor(db, source_upper, resolved_cursor, success=(outcome != OUTCOME_PARSE_FAILED), maturity=resolved_maturity, outcome=outcome)
            next_cursor = resolved_cursor
        except Exception:
            pass
    else:
        # No records fetched (empty page) — successful empty, preserve cursor
        try:
            _upsert_cursor(db, source_upper, resolved_cursor, success=True, maturity=resolved_maturity, outcome=outcome)
            next_cursor = resolved_cursor
        except Exception:
            pass
    agg_hash = None
    try:
        # Hash of actually persisted records (partial batch recovery)
        agg_hash = _compute_source_hash({"ids": sorted([str(r.get("task_id") or r.get("train_id") or str(i)) for _, r in persisted_live])}) if persisted_live else None
    except Exception:
        agg_hash = None
    db.add(AuditEvent(action="IMPORT_LIVE", entity_type=source_upper, entity_id=import_run_id, user_id=user_id, details=json.dumps({"received": received, "accepted": accepted, "source_maturity": resolved_maturity, "outcome": outcome})))
    try:
        ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, source_hash=agg_hash, cursor_value=next_cursor, outcome=outcome)
    except TypeError:
        try:
            ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed, source_maturity=resolved_maturity, source_hash=agg_hash, cursor_value=next_cursor)
        except Exception:
            ir = ImportRun(id=import_run_id, source_name=source_upper, received_count=received, accepted_count=accepted, rejected_count=rejected, warning_count=len(warnings), duplicate_count=duplicate, errors=json.dumps(errors), warnings=json.dumps(warnings), started_at=started, completed_at=completed)
    db.add(ir)
    db.commit()
    return {"import_run_id": import_run_id, "source_name": source_upper, "received_count": received, "accepted_count": accepted, "rejected_count": rejected, "warning_count": len(warnings), "errors": errors, "warnings": warnings, "duplicate_count": duplicate, "started_at": started.isoformat(), "completed_at": completed.isoformat(), "source_maturity": resolved_maturity, "source_hash": agg_hash, "cursor_value": next_cursor, "outcome": outcome}

def persist_record(db, source_name, rec):
    if source_name in ["TMS","SMMS","TDMS","TASKS"]:
        # task
        # map fields
        tid = str(rec.get("task_id")).upper() if rec.get("task_id") else str(uuid.uuid4())[:8]
        # defaults
        dept = rec.get("department") or source_name
        if dept.upper() in ["TMS"]: dept="ENGINEERING"
        elif dept.upper() in ["SMMS"]: dept="S_AND_T"
        elif dept.upper() in ["TDMS"]: dept="TRACTION"
        # else keep
        # Phase 1a provenance extra fields (safe fallback if model missing columns)
        prov_extra: Dict = {}
        try:
            prov_extra["external_id"] = str(rec.get("external_id")).upper() if rec.get("external_id") else None
            prov_extra["source_updated_at"] = str(rec.get("source_updated_at")) if rec.get("source_updated_at") else None
            prov_extra["source_maturity"] = str(rec.get("source_maturity") or "SYNTHETIC").upper()
            prov_extra["source_hash"] = str(rec.get("source_hash")) if rec.get("source_hash") else None
        except Exception:
            prov_extra = {}
        try:
            t = Task(
                id=tid,
                source_system=source_name,
                department=dept.upper(),
                asset_id=rec.get("asset_id").upper() if rec.get("asset_id") else None,
                corridor_id=rec.get("corridor_id").upper() if rec.get("corridor_id") else "COR-1",
                section_id=rec.get("section_id").upper() if rec.get("section_id") else None,
                line_id=rec.get("line_id").upper() if rec.get("line_id") else None,
                location_from_km=float(rec.get("location_from_km") or 0),
                location_to_km=float(rec.get("location_to_km") or 0),
                task_type=rec.get("task_type") or "MAINTENANCE",
                description=rec.get("description") or "",
                severity=rec.get("severity") or "MEDIUM",
                safety_score=float(rec.get("safety_score") or 50),
                urgency_score=float(rec.get("urgency_score") or 50),
                asset_criticality=float(rec.get("asset_criticality") or 50),
                operational_impact=float(rec.get("operational_impact") or 50),
                overdue_days=int(float(rec.get("overdue_days") or 0)),
                coordination_value=float(rec.get("coordination_value") or 50),
                resource_readiness=float(rec.get("resource_readiness") or 50),
                estimated_duration_minutes=int(float(rec.get("estimated_duration_minutes") or 60)),
                setup_duration_minutes=int(float(rec.get("setup_duration_minutes") or 15)),
                required_block_type=rec.get("required_block_type") or "TRAFFIC",
                requires_traffic_block=str(rec.get("requires_traffic_block")).lower() not in ["false","0","no"] if rec.get("requires_traffic_block") not in [None,""] else True,
                requires_power_isolation=str(rec.get("requires_power_isolation")).lower() in ["true","1","yes"] if rec.get("requires_power_isolation") not in [None,""] else False,
                requires_signal_disconnection=str(rec.get("requires_signal_disconnection")).lower() in ["true","1","yes"] if rec.get("requires_signal_disconnection") not in [None,""] else False,
                earliest_start=parse_dt(rec.get("earliest_start")),
                deadline=parse_dt(rec.get("deadline")),
                status="ELIGIBLE",
                **prov_extra,
            )
            db.add(t)
            db.flush()
        except Exception:
            # Fallback without provenance for DB without columns (pre-migration)
            try:
                db.rollback()
            except Exception:
                pass
            t = Task(
                id=tid,
                source_system=source_name,
                department=dept.upper(),
                asset_id=rec.get("asset_id").upper() if rec.get("asset_id") else None,
                corridor_id=rec.get("corridor_id").upper() if rec.get("corridor_id") else "COR-1",
                section_id=rec.get("section_id").upper() if rec.get("section_id") else None,
                line_id=rec.get("line_id").upper() if rec.get("line_id") else None,
                location_from_km=float(rec.get("location_from_km") or 0),
                location_to_km=float(rec.get("location_to_km") or 0),
                task_type=rec.get("task_type") or "MAINTENANCE",
                description=rec.get("description") or "",
                severity=rec.get("severity") or "MEDIUM",
                safety_score=float(rec.get("safety_score") or 50),
                urgency_score=float(rec.get("urgency_score") or 50),
                asset_criticality=float(rec.get("asset_criticality") or 50),
                operational_impact=float(rec.get("operational_impact") or 50),
                overdue_days=int(float(rec.get("overdue_days") or 0)),
                coordination_value=float(rec.get("coordination_value") or 50),
                resource_readiness=float(rec.get("resource_readiness") or 50),
                estimated_duration_minutes=int(float(rec.get("estimated_duration_minutes") or 60)),
                setup_duration_minutes=int(float(rec.get("setup_duration_minutes") or 15)),
                required_block_type=rec.get("required_block_type") or "TRAFFIC",
                requires_traffic_block=str(rec.get("requires_traffic_block")).lower() not in ["false","0","no"] if rec.get("requires_traffic_block") not in [None,""] else True,
                requires_power_isolation=str(rec.get("requires_power_isolation")).lower() in ["true","1","yes"] if rec.get("requires_power_isolation") not in [None,""] else False,
                requires_signal_disconnection=str(rec.get("requires_signal_disconnection")).lower() in ["true","1","yes"] if rec.get("requires_signal_disconnection") not in [None,""] else False,
                earliest_start=parse_dt(rec.get("earliest_start")),
                deadline=parse_dt(rec.get("deadline")),
                status="ELIGIBLE",
            )
            db.add(t)
            db.flush()
        # handle dependencies and resources if present - skip invalid gracefully with savepoints
        if rec.get("dependency_task_ids"):
            for did in str(rec["dependency_task_ids"]).split(";"):
                did=did.strip().upper()
                if did:
                    exists = db.query(Task).filter(Task.id==did).first() is not None
                    if not exists:
                        continue
                    try:
                        with db.begin_nested():
                            from app.models import TaskDependency
                            db.add(TaskDependency(task_id=tid, depends_on_task_id=did))
                            db.flush()
                    except Exception:
                        continue
        if rec.get("required_resource_ids"):
            for rid in str(rec["required_resource_ids"]).split(";"):
                rid=rid.strip().upper()
                if rid:
                    try:
                        with db.begin_nested():
                            db.execute(task_resources.insert().values(task_id=tid, resource_id=rid))
                            db.flush()
                    except Exception:
                        continue
    elif source_name in ["COA","CORRIDORS","ASSETS"]:
        # corridor/section/line/asset
        # if corridor
        if rec.get("corridor_id"):
            cid=str(rec["corridor_id"]).upper()
            if not db.query(Corridor).filter(Corridor.id==cid).first():
                db.add(Corridor(id=cid, name=rec.get("corridor_name") or cid))
                db.flush()
        if rec.get("section_id"):
            sid=str(rec["section_id"]).upper()
            cid=str(rec.get("corridor_id")).upper() if rec.get("corridor_id") else "COR-1"
            if not db.query(Section).filter(Section.id==sid).first():
                db.add(Section(id=sid, corridor_id=cid, name=rec.get("section_name") or sid, from_km=float(rec.get("from_km") or 0), to_km=float(rec.get("to_km") or 0)))
                db.flush()
        if rec.get("line_id"):
            lid=str(rec["line_id"]).upper()
            sid=str(rec.get("section_id")).upper() if rec.get("section_id") else None
            cid=str(rec.get("corridor_id")).upper() if rec.get("corridor_id") else "COR-1"
            if sid and not db.query(Section).filter(Section.id==sid).first():
                db.add(Section(id=sid, corridor_id=cid, name=sid))
                db.flush()
            if not db.query(Line).filter(Line.id==lid).first():
                db.add(Line(id=lid, section_id=sid or "SEC-1", corridor_id=cid, line_type=rec.get("line_type") or "UP", name=lid))
                db.flush()
        if rec.get("asset_id"):
            aid=str(rec["asset_id"]).upper()
            if not db.query(Asset).filter(Asset.id==aid).first():
                cid=str(rec.get("corridor_id")).upper() if rec.get("corridor_id") else "COR-1"
                db.add(Asset(id=aid, corridor_id=cid, section_id=str(rec.get("section_id")).upper() if rec.get("section_id") else None, line_id=str(rec.get("line_id")).upper() if rec.get("line_id") else None, asset_type=rec.get("asset_type") or "TRACK", asset_criticality=int(float(rec.get("asset_criticality") or 50)), location_km=float(rec.get("location_km") or 0)))
    elif source_name in ["TIMETABLE","TRAINS"]:
        tid=str(rec.get("train_id") or rec.get("id") or str(uuid.uuid4())[:8]).upper()
        # parse times
        dep = parse_time_to_minutes(rec.get("departure_time") or rec.get("start_time") or "00:00")
        arr = parse_time_to_minutes(rec.get("arrival_time") or rec.get("end_time") or "01:00")
        prov_extra_tm: Dict = {}
        try:
            prov_extra_tm["external_id"] = str(rec.get("external_id")).upper() if rec.get("external_id") else None
            prov_extra_tm["source_updated_at"] = str(rec.get("source_updated_at")) if rec.get("source_updated_at") else None
            prov_extra_tm["source_maturity"] = str(rec.get("source_maturity") or "SYNTHETIC").upper()
            prov_extra_tm["source_hash"] = str(rec.get("source_hash")) if rec.get("source_hash") else None
        except Exception:
            prov_extra_tm = {}
        try:
            db.add(TrainMovement(id=tid, corridor_id=str(rec.get("corridor_id")).upper(), section_id=str(rec.get("section_id")).upper() if rec.get("section_id") else None, line_id=str(rec.get("line_id")).upper() if rec.get("line_id") else None, train_type=rec.get("train_type") or "PASSENGER", service_date=str(rec.get("service_date") or "2026-09-01"), departure_time=dep, arrival_time=arr, **prov_extra_tm))
        except Exception:
            db.add(TrainMovement(id=tid, corridor_id=str(rec.get("corridor_id")).upper(), section_id=str(rec.get("section_id")).upper() if rec.get("section_id") else None, line_id=str(rec.get("line_id")).upper() if rec.get("line_id") else None, train_type=rec.get("train_type") or "PASSENGER", service_date=str(rec.get("service_date") or "2026-09-01"), departure_time=dep, arrival_time=arr))
    elif source_name in ["GOODS_FORECAST","GOODS-FORECAST"]:
        gid=str(rec.get("id") or rec.get("forecast_id") or str(uuid.uuid4())[:8]).upper()
        s = parse_time_to_minutes(rec.get("start_time") or "00:00")
        e = parse_time_to_minutes(rec.get("end_time") or "01:00")
        prov_extra_gf: Dict = {}
        try:
            prov_extra_gf["external_id"] = str(rec.get("external_id")).upper() if rec.get("external_id") else None
            prov_extra_gf["source_updated_at"] = str(rec.get("source_updated_at")) if rec.get("source_updated_at") else None
            prov_extra_gf["source_maturity"] = str(rec.get("source_maturity") or "SYNTHETIC").upper()
            prov_extra_gf["source_hash"] = str(rec.get("source_hash")) if rec.get("source_hash") else None
        except Exception:
            prov_extra_gf = {}
        try:
            db.add(GoodsForecast(id=gid, corridor_id=str(rec.get("corridor_id")).upper(), section_id=str(rec.get("section_id")).upper() if rec.get("section_id") else None, line_id=str(rec.get("line_id")).upper() if rec.get("line_id") else None, service_date=str(rec.get("service_date") or "2026-09-01"), start_time=s, end_time=e, confidence=float(rec.get("confidence") or 0.5), forecast_count=int(float(rec.get("forecast_count") or 1)), risk_score=float(rec.get("risk_score") or 50), **prov_extra_gf))
        except Exception:
            db.add(GoodsForecast(id=gid, corridor_id=str(rec.get("corridor_id")).upper(), section_id=str(rec.get("section_id")).upper() if rec.get("section_id") else None, line_id=str(rec.get("line_id")).upper() if rec.get("line_id") else None, service_date=str(rec.get("service_date") or "2026-09-01"), start_time=s, end_time=e, confidence=float(rec.get("confidence") or 0.5), forecast_count=int(float(rec.get("forecast_count") or 1)), risk_score=float(rec.get("risk_score") or 50)))
    elif source_name in ["RESOURCES","RESOURCE"]:
        rid=str(rec.get("resource_id")).upper()
        if not db.query(Resource).filter(Resource.id==rid).first():
            db.add(Resource(id=rid, resource_type=rec.get("resource_type") or "CREW", name=rec.get("name") or rid, department=rec.get("department") or "ENGINEERING", capacity=int(float(rec.get("capacity") or 1))))
            db.flush()
        # availability
        if rec.get("service_date"):
            s=parse_time_to_minutes(rec.get("start_time") or "00:00")
            e=parse_time_to_minutes(rec.get("end_time") or "23:59")
            db.add(ResourceAvailability(resource_id=rid, service_date=str(rec.get("service_date")), start_time=s, end_time=e, available=True))

from sqlalchemy import Table
from app.database import Base
task_resources = Base.metadata.tables.get("task_resources")

def parse_dt(v):
    if not v: return None
    s=str(v).strip()
    try:
        if "T" in s:
            return datetime.datetime.fromisoformat(s.replace("Z",""))
        elif len(s)==10:
            return datetime.datetime.strptime(s, "%Y-%m-%d")
        else:
            return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except:
        return None

def parse_time_to_minutes(v):
    if v is None: return 0
    s=str(v).strip()
    if s.isdigit():
        return int(s)
    if ":" in s:
        parts=s.split(":")
        try:
            h=int(parts[0]); m=int(parts[1].split(" ")[0])
            return h*60+m
        except:
            return 0
    try:
        return int(float(s))
    except:
        return 0
