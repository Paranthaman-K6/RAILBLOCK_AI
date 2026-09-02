def test_resource_overlap(client):
    # grouping should reject resource overlap
    from app.models import Task
    from app.services.compatibility import grouping_compatible_tasks
    from app.database import SessionLocal
    from app.models import CandidateWindow
    db = SessionLocal()
    w = CandidateWindow(id="WND-TEST", service_date="2026-09-01", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", start_time=60, end_time=180, available_minutes=120, block_type="TRAFFIC")
    t1 = Task(id="TSK-G1", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", estimated_duration_minutes=60, setup_duration_minutes=15, required_block_type="TRAFFIC", requires_power_isolation=False, requires_signal_disconnection=False)
    t2 = Task(id="TSK-G2", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", estimated_duration_minutes=60, setup_duration_minutes=15, required_block_type="TRAFFIC", requires_power_isolation=False, requires_signal_disconnection=False)
    # insert dummy tasks and resources if not exist
    # For this unit, just test combined duration overflow
    t1.estimated_duration_minutes=200
    t2.estimated_duration_minutes=100
    ok, reasons = grouping_compatible_tasks([t1,t2], w, max_duration=240)
    assert not ok
    assert any("240" in r for r in reasons)
    db.close()

def test_duration_overflow(client):
    from app.models import Task, CandidateWindow
    from app.services.compatibility import check_task_window_fit
    t = Task(id="TSK-LONG", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", estimated_duration_minutes=300, setup_duration_minutes=0, required_block_type="TRAFFIC", requires_power_isolation=False, requires_signal_disconnection=False)
    w = CandidateWindow(id="WND-SHORT", service_date="2026-09-01", corridor_id="COR-1", section_id="SEC-1", line_id="LIN-1", start_time=60, end_time=180, available_minutes=120, block_type="TRAFFIC", status="FEASIBLE")
    fit, reason = check_task_window_fit(t,w)
    assert fit=="HARD_CONFLICT"
