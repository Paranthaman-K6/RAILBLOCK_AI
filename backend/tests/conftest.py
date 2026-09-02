import pytest
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.database import SessionLocal, engine, Base
import app.models

@pytest.fixture(scope="module")
def client():
    # ensure tables exist
    Base.metadata.create_all(bind=engine)
    with TestClient(fastapi_app) as c:
        yield c

@pytest.fixture(autouse=True)
def clean_db():
    # clean tasks etc before each test? We do selective cleanup in each test for isolation
    yield
    # no auto clean, tests manage

def reset_db():
    # helper to clear transactional data - disable FK to allow truncation
    db = SessionLocal()
    try:
        # Use postgres-aware pragma handling
        try:
            from app.database import is_postgres
            pg = is_postgres()
        except Exception:
            pg = False
        if not pg:
            db.execute(__import__('sqlalchemy').text("PRAGMA foreign_keys=OFF"))
        # delete in any order (include Phase 1b source_cursors, provenance tables)
        for tbl in ["plan_changes","approvals","execution_records","block_tasks","blocks","plan_revisions","block_plans","task_window_candidates","task_groups","task_dependencies","task_resources","candidate_windows","import_runs","audit_events","notifications","resource_availabilities","goods_forecasts","train_movements","tasks","source_cursors"]:
            try:
                db.execute(__import__('sqlalchemy').text(f"DELETE FROM {tbl}"))
            except Exception as e:
                pass
        if not pg:
            db.execute(__import__('sqlalchemy').text("PRAGMA foreign_keys=ON"))
        db.commit()
    finally:
        db.close()
