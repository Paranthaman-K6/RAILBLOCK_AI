from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db, get_diagnostics, DATABASE_URL, is_postgres
import json

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/postgres/status")
def postgres_status(db: Session = Depends(get_db)):
    """Check PostgreSQL connection and export readiness via backend API"""
    diag = get_diagnostics()
    # Count tables
    tables = ["tasks","blocks","block_plans","train_movements","goods_forecasts","resources","corridors"]
    counts = {}
    for t in tables:
        try:
            cnt = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            counts[t] = int(cnt)
        except Exception as e:
            counts[t] = f"error: {str(e)[:100]}"
    return {
        "database": diag.get("database"),
        "database_mode": diag.get("database_mode"),
        "path": diag.get("path"),
        "database_url_redacted": diag.get("database_url"),
        "is_postgres": is_postgres(),
        "counts": counts,
        "export_ready": diag.get("database") == "PostgreSQL" or diag.get("database_mode") == "postgres",
        "instructions": "Use POST /api/export/postgres/dump to get full dump, or GET /api/export/postgres/csv?table=tasks"
    }

@router.get("/postgres/dump")
def postgres_dump(db: Session = Depends(get_db)):
    """Export full database as JSON dump via backend API -> PostgreSQL"""
    tables = ["departments","corridors","sections","lines","assets","tasks","train_movements","goods_forecasts","resources","resource_availabilities","candidate_windows","block_plans","blocks","block_tasks","approvals","execution_records","audit_events","import_runs","source_cursors","rule_configurations"]
    dump = {}
    for t in tables:
        try:
            rows = db.execute(text(f"SELECT * FROM {t} LIMIT 1000")).mappings().all()
            dump[t] = [dict(r) for r in rows]
        except Exception as e:
            dump[t] = {"error": str(e)[:200]}
    return {"database": "PostgreSQL" if is_postgres() else "SQLite", "dump": dump, "tables_exported": len(dump)}

@router.get("/postgres/csv")
def postgres_csv(table: str = "tasks", db: Session = Depends(get_db)):
    """Export single table as CSV via backend API -> PostgreSQL"""
    from fastapi.responses import PlainTextResponse
    import csv, io
    allowed = ["tasks","blocks","block_plans","train_movements","goods_forecasts","resources","corridors","assets","audit_events"]
    if table not in allowed:
        raise HTTPException(status_code=400, detail=f"Table {table} not allowed. Allowed: {allowed}")
    try:
        rows = db.execute(text(f"SELECT * FROM {table} LIMIT 1000")).mappings().all()
        if not rows:
            return PlainTextResponse("", media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={table}.csv"})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            # handle datetime
            d = dict(r)
            for k,v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            writer.writerow(d)
        return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={table}.csv"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])

@router.post("/postgres/restore")
def postgres_restore(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Restore/Upsert data into PostgreSQL via backend API (for migration from SQLite)"""
    # Expects {"table": "tasks", "rows": [{...}]}
    table = payload.get("table")
    rows = payload.get("rows") or []
    if not table or not rows:
        raise HTTPException(status_code=400, detail="Need table and rows")
    allowed = ["tasks","blocks","block_plans","train_movements","goods_forecasts"]
    if table not in allowed:
        raise HTTPException(status_code=400, detail=f"Table not allowed")
    inserted = 0
    for row in rows[:100]:
        try:
            cols = ", ".join(row.keys())
            placeholders = ", ".join([f":{k}" for k in row.keys()])
            db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"), row)
            inserted += 1
        except Exception:
            continue
    db.commit()
    return {"table": table, "inserted": inserted, "total": len(rows)}
