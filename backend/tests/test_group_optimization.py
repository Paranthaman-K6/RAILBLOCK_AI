from tests.conftest import reset_db
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Task, TaskGroup, Block, BlockTask, CandidateWindow
import json
from sqlalchemy import text

def setup_with_synthetic(client):
    reset_db()
    import pathlib
    from app.services.ingestion import run_import
    from app.database import SessionLocal as SL
    # Use project-relative path for cross-platform (Linux CI and Windows)
    project_root = pathlib.Path(__file__).parent.parent.parent
    sample_dir = project_root / "data" / "sample"
    # Fallback to legacy Windows path if needed
    if not sample_dir.exists():
        sample_dir = pathlib.Path("D:/PROJECT2/MAYBE/RAIL/data/sample")
    db = SL()
    for fname, src in [("corridors.csv","COA"),("resources.csv","RESOURCES"),("trains.csv","TIMETABLE"),("goods_forecast.csv","GOODS_FORECAST"),("tasks.csv","TMS")]:
        p = sample_dir / fname
        if p.exists():
            content = p.read_text(encoding="utf-8")
            db2 = SL()
            run_import(db2, src, content, user_id="test")
            db2.close()
        else:
            # Also try legacy absolute as fallback
            p2 = pathlib.Path(f"D:/PROJECT2/MAYBE/RAIL/data/sample/{fname}")
            if p2.exists():
                content = p2.read_text(encoding="utf-8")
                db2 = SL()
                run_import(db2, src, content, user_id="test")
                db2.close()
    db.close()
    client.post("/api/windows/generate?horizon_start=2026-09-01&horizon_end=2026-09-07")
    from app.services.priority import recalculate_all
    db = SessionLocal()
    recalculate_all(db)
    db.close()

def test_single_task_cpsat_assignment(client):
    setup_with_synthetic(client)
    r = client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    assert r.status_code==200
    j=r.json()
    assert j['solver_status'] in ['OPTIMAL','FEASIBLE']
    singles = [b for b in j['blocks'] if len(b['tasks'])==1]
    assert len(singles)>=1
    all_tids = [t for b in j['blocks'] for t in b['tasks']]
    assert len(all_tids)==len(set(all_tids))
    v=client.post(f"/api/plans/{j['plan_id']}/validate").json()
    assert v['valid']==True

def test_two_task_integrated_cpsat_assignment(client):
    setup_with_synthetic(client)
    r = client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    assert r.status_code==200
    j=r.json()
    inte = [b for b in j['blocks'] if len(b['tasks'])>1]
    assert len(inte)>=1, "Expected at least one integrated block via CP-SAT group-window variables"
    r2=client.get(f"/api/plans/{j['plan_id']}")
    plan=r2.json()
    found=False
    for b in plan['blocks']:
        if len(b['tasks'])>1:
            db=SessionLocal()
            depts=set()
            for t in b['tasks']:
                tid=t['task_id'] if isinstance(t, dict) else t
                task=db.query(Task).filter(Task.id==tid).first()
                if task:
                    depts.add(task.department)
            db.close()
            assert len(depts)>1, "Integrated block must have >1 department"
            found=True
            break
    assert found
    v=client.post(f"/api/plans/{j['plan_id']}/validate").json()
    assert v['valid']==True
    assert 'integrated_groups' in j.get('objective_breakdown',{}) or j.get('objective_breakdown',{}).get('integrated_groups',0)>=1

def test_three_task_compatible_group(client):
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.models import Task
    import datetime
    from sqlalchemy import text
    db=SessionLocal()
    for i, tid in enumerate(['TSK-GRP1','TSK-GRP2','TSK-GRP3']):
        t=Task(id=tid, source_system='TMS', department=['ENGINEERING','S_AND_T','TRACTION'][i], corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='Group test', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
        db.add(t)
    db.commit()
    for i, tid in enumerate(['TSK-GRP1','TSK-GRP2','TSK-GRP3']):
        db.execute(text(f"INSERT OR IGNORE INTO task_resources (task_id, resource_id) VALUES ('{tid}', 'RES-{i+1}')"))
    db.commit()
    db.close()
    from app.services.grouping import generate_candidate_groups
    db=SessionLocal()
    tasks=[db.query(Task).filter(Task.id==tid).first() for tid in ['TSK-GRP1','TSK-GRP2','TSK-GRP3']]
    tasks=[t for t in tasks if t]
    windows=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    groups=generate_candidate_groups(db, tasks, windows, "2026-09-01", "2026-09-07")
    for g in groups:
        assert len(g['task_ids'])<=3
    db.close()
    db=SessionLocal()
    for tid in ['TSK-GRP1','TSK-GRP2','TSK-GRP3']:
        db.execute(text(f"DELETE FROM task_resources WHERE task_id='{tid}'"))
        db.execute(text(f"DELETE FROM tasks WHERE id='{tid}'"))
    db.commit()
    db.close()

def test_power_conflict_not_grouped(client):
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.models import Task
    import datetime
    db=SessionLocal()
    t1=Task(id='TSK-PWR1', source_system='TMS', department='TRACTION', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='Power', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=True, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    t2=Task(id='TSK-PWR2', source_system='TMS', department='ENGINEERING', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='NoPower', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    db.add(t1); db.add(t2); db.commit()
    db.close()
    from app.services.grouping import generate_candidate_groups
    db=SessionLocal()
    tasks=[db.query(Task).filter(Task.id=='TSK-PWR1').first(), db.query(Task).filter(Task.id=='TSK-PWR2').first()]
    windows=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    groups=generate_candidate_groups(db, tasks, windows, "2026-09-01", "2026-09-07")
    for g in groups:
        assert not ('TSK-PWR1' in g['task_ids'] and 'TSK-PWR2' in g['task_ids'])
    db.close()
    db=SessionLocal()
    db.execute(text("DELETE FROM tasks WHERE id IN ('TSK-PWR1','TSK-PWR2')"))
    db.commit()
    db.close()

def test_signalling_conflict_not_grouped(client):
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.models import Task
    import datetime
    db=SessionLocal()
    t1=Task(id='TSK-SIG1', source_system='TMS', department='S_AND_T', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='Sig', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=True, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    t2=Task(id='TSK-SIG2', source_system='TMS', department='ENGINEERING', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='NoSig', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    db.add(t1); db.add(t2); db.commit()
    db.close()
    from app.services.grouping import generate_candidate_groups
    db=SessionLocal()
    tasks=[db.query(Task).filter(Task.id=='TSK-SIG1').first(), db.query(Task).filter(Task.id=='TSK-SIG2').first()]
    windows=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    groups=generate_candidate_groups(db, tasks, windows, "2026-09-01", "2026-09-07")
    for g in groups:
        assert not ('TSK-SIG1' in g['task_ids'] and 'TSK-SIG2' in g['task_ids'])
    db.close()
    db=SessionLocal()
    db.execute(text("DELETE FROM tasks WHERE id IN ('TSK-SIG1','TSK-SIG2')"))
    db.commit()
    db.close()

def test_different_corridor_not_grouped(client):
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.models import Task
    import datetime
    db=SessionLocal()
    t1=Task(id='TSK-COR1', source_system='TMS', department='ENGINEERING', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='C1', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    t2=Task(id='TSK-COR2', source_system='TMS', department='ENGINEERING', corridor_id='COR-2', section_id='SEC-3', line_id='LIN-5', task_type='MAINT', description='C2', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=30, setup_duration_minutes=10, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    db.add(t1); db.add(t2); db.commit()
    db.close()
    from app.services.grouping import generate_candidate_groups
    db=SessionLocal()
    tasks=[db.query(Task).filter(Task.id=='TSK-COR1').first(), db.query(Task).filter(Task.id=='TSK-COR2').first()]
    windows=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    groups=generate_candidate_groups(db, tasks, windows, "2026-09-01", "2026-09-07")
    for g in groups:
        assert not ('TSK-COR1' in g['task_ids'] and 'TSK-COR2' in g['task_ids'])
    db.close()
    db=SessionLocal()
    db.execute(text("DELETE FROM tasks WHERE id IN ('TSK-COR1','TSK-COR2')"))
    db.commit()
    db.close()

def test_duration_overflow_not_grouped(client):
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.models import Task
    import datetime
    db=SessionLocal()
    t1=Task(id='TSK-DUR1', source_system='TMS', department='ENGINEERING', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='Dur1', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=180, setup_duration_minutes=20, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    t2=Task(id='TSK-DUR2', source_system='TMS', department='S_AND_T', corridor_id='COR-1', section_id='SEC-1', line_id='LIN-1', task_type='MAINT', description='Dur2', severity='MEDIUM', safety_score=70, urgency_score=70, asset_criticality=70, operational_impact=70, overdue_days=0, coordination_value=70, resource_readiness=70, estimated_duration_minutes=180, setup_duration_minutes=20, required_block_type='TRAFFIC', requires_traffic_block=True, requires_power_isolation=False, requires_signal_disconnection=False, earliest_start=datetime.datetime(2026,9,1), deadline=datetime.datetime(2026,9,10), status='ELIGIBLE')
    db.add(t1); db.add(t2); db.commit()
    db.close()
    from app.services.grouping import generate_candidate_groups
    db=SessionLocal()
    tasks=[db.query(Task).filter(Task.id=='TSK-DUR1').first(), db.query(Task).filter(Task.id=='TSK-DUR2').first()]
    windows=db.query(CandidateWindow).filter(CandidateWindow.status=="FEASIBLE").all()
    groups=generate_candidate_groups(db, tasks, windows, "2026-09-01", "2026-09-07")
    for g in groups:
        assert not ('TSK-DUR1' in g['task_ids'] and 'TSK-DUR2' in g['task_ids'])
    db.close()
    db=SessionLocal()
    db.execute(text("DELETE FROM tasks WHERE id IN ('TSK-DUR1','TSK-DUR2')"))
    db.commit()
    db.close()

def test_task_at_most_once(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    assert r.status_code==200
    pid=r.json()['plan_id']
    from app.database import SessionLocal
    from app.models import BlockTask, Block
    db=SessionLocal()
    bts=db.query(BlockTask).join(Block, BlockTask.block_id==Block.id).filter(Block.plan_id==pid).all()
    tids=[bt.task_id for bt in bts]
    assert len(tids)==len(set(tids))
    db.close()

def test_group_at_most_once(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    assert r.status_code==200
    j=r.json()
    from app.database import SessionLocal
    from app.models import Block
    db=SessionLocal()
    blocks=db.query(Block).filter(Block.plan_id==j['plan_id']).all()
    window_ids=[b.window_id for b in blocks]
    assert len(window_ids)==len(set(window_ids))
    db.close()

def test_invalid_solver_not_saved(client):
    reset_db()
    setup_with_synthetic(client)
    from app.database import SessionLocal
    from app.services.optimizer import run_cpsat_optimizer
    db=SessionLocal()
    plan, status, comp, runtime = run_cpsat_optimizer(db, "2099-01-01", "2099-01-02", "WEEKLY", time_limit=1)
    assert plan is None or status in ["INFEASIBLE","UNKNOWN"]
    db.close()

def test_fallback_grouping(client):
    setup_with_synthetic(client)
    from app.services.fallback import generate_fallback_plan
    from app.database import SessionLocal
    db=SessionLocal()
    plan=generate_fallback_plan(db, "2026-09-01", "2026-09-07", "WEEKLY")
    assert plan is not None
    assert plan.solver_status in ["FALLBACK_USED","VALIDATION_FAILED"]
    if plan.solver_status=="FALLBACK_USED":
        from app.services.plan_validator import validate_plan
        v=validate_plan(db, plan.id)
        assert v['valid']==True
    db.close()

def test_weekly_monthly_integrated(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    assert r.status_code==200
    j=r.json()
    assert j['solver_status'] in ['OPTIMAL','FEASIBLE']
    assert any(len(b['tasks'])>1 for b in j['blocks'])
    r2=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-30','horizon_type':'MONTHLY'})
    assert r2.status_code==200
    j2=r2.json()
    assert j2['solver_status'] in ['OPTIMAL','FEASIBLE','FALLBACK_USED']

def test_replanning_with_completed_grouped(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    pid=r.json()['plan_id']
    plan=client.get(f'/api/plans/{pid}').json()
    blk=None
    for b in plan['blocks']:
        if len(b['tasks'])>1:
            blk=b
            break
    if not blk:
        blk=plan['blocks'][0]
    client.post(f'/api/plans/{pid}/submit-review')
    client.post(f'/api/plans/{pid}/approve', json={'approver_id':'officer1','approver_role':'CONTROL_OFFICE','reason':'ok'})
    tsk=blk['tasks'][0]['task_id'] if isinstance(blk['tasks'][0], dict) else blk['tasks'][0]
    ex=client.post(f"/api/blocks/{blk['block_id']}/execution", json={'actual_start':60,'actual_end':120,'status':'COMPLETED','completed_task_ids':[tsk],'recorded_by':'eng1','service_date':blk['service_date']})
    assert ex.status_code in [200,201]
    rp=client.post(f'/api/plans/{pid}/replan', json={'reason':'Emergency'})
    assert rp.status_code==200
    from app.database import SessionLocal
    from app.models import ExecutionRecord
    db=SessionLocal()
    assert db.query(ExecutionRecord).filter(ExecutionRecord.block_id==blk['block_id']).count()==1
    db.close()

def test_approved_grouped_immutable(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    pid=r.json()['plan_id']
    client.post(f'/api/plans/{pid}/submit-review')
    client.post(f'/api/plans/{pid}/approve', json={'approver_id':'officer1','approver_role':'CONTROL_OFFICE','reason':'ok'})
    blk=client.get(f'/api/plans/{pid}').json()['blocks'][0]['block_id']
    er=client.patch(f'/api/plans/{pid}/draft-blocks/{blk}', json={'service_date':'2026-09-05','reason':'test','editor':'x'})
    assert er.status_code==400

def test_execution_of_integrated_block(client):
    setup_with_synthetic(client)
    r=client.post('/api/plans/generate', json={'horizon_start':'2026-09-01','horizon_end':'2026-09-07','horizon_type':'WEEKLY'})
    pid=r.json()['plan_id']
    client.post(f'/api/plans/{pid}/submit-review')
    client.post(f'/api/plans/{pid}/approve', json={'approver_id':'officer1','approver_role':'CONTROL_OFFICE','reason':'ok'})
    plan=client.get(f'/api/plans/{pid}').json()
    blk=None
    for b in plan['blocks']:
        if len(b['tasks'])>1:
            blk=b
            break
    assert blk is not None, "Need integrated block for this test"
    tids=[t['task_id'] if isinstance(t, dict) else t for t in blk['tasks']]
    ex=client.post(f"/api/blocks/{blk['block_id']}/execution", json={'actual_start':blk['start_time'],'actual_end':blk['end_time'],'status':'COMPLETED','completed_task_ids':tids,'recorded_by':'eng1','service_date':blk['service_date']})
    assert ex.status_code in [200,201]
    v=client.post(f"/api/plans/{pid}/validate").json()
    assert v['valid']==True
