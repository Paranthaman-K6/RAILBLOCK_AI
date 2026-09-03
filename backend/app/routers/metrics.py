from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.metrics import calculate_metrics, get_all_metrics
import concurrent.futures as _cf

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("")
def all_metrics(db: Session = Depends(get_db)):
    # Timeout-guard entire metrics aggregation (postgres pooled latency * validate per plan)
    try:
        _ex = _cf.ThreadPoolExecutor(max_workers=1)
        _fut = _ex.submit(get_all_metrics, db)
        try:
            return _fut.result(timeout=4.0)
        except _cf.TimeoutError:
            try:
                _fut.cancel()
            except Exception:
                pass
            # Fallback: return latest single plan metrics quickly
            from app.models import BlockPlan
            latest = db.query(BlockPlan).order_by(BlockPlan.created_at.desc()).first()
            if latest:
                try:
                    m = calculate_metrics(db, latest.id)
                    return [m] if m else []
                except Exception:
                    return []
            return []
        finally:
            try:
                _ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                _ex.shutdown(wait=False)
    except Exception as _e:
        return []

@router.get("/{plan_id}")
def one_metrics(plan_id: str, db: Session = Depends(get_db)):
    try:
        _ex = _cf.ThreadPoolExecutor(max_workers=1)
        _fut = _ex.submit(calculate_metrics, db, plan_id.upper())
        try:
            m = _fut.result(timeout=3.0)
        except _cf.TimeoutError:
            try:
                _fut.cancel()
            except Exception:
                pass
            raise HTTPException(status_code=504, detail="Metrics timeout — please retry")
        finally:
            try:
                _ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                _ex.shutdown(wait=False)
    except HTTPException:
        raise
    except Exception as _e:
        raise HTTPException(status_code=500, detail=str(_e)[:300])
    if not m:
        raise HTTPException(status_code=404, detail="Plan not found")
    return m
