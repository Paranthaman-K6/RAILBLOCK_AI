from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

def utcnow():
    return datetime.datetime.utcnow()

# Department is logically enum, but keep table for FK
class DepartmentModel(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True)  # CONTROL_OFFICE etc
    name = Column(String, nullable=False)

class UserContext(Base):
    __tablename__ = "user_contexts"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_user_contexts_department", "department_id"),)

class Corridor(Base):
    __tablename__ = "corridors"
    id = Column(String, primary_key=True)  # COR-*
    name = Column(String, nullable=False)
    corridor_type = Column(String, default="main")

class Section(Base):
    __tablename__ = "sections"
    id = Column(String, primary_key=True)  # SEC-*
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    name = Column(String, nullable=False)
    from_km = Column(Float, default=0)
    to_km = Column(Float, default=0)
    corridor = relationship("Corridor", backref="sections")
    __table_args__ = (Index("ix_sections_corridor", "corridor_id"),)

class Line(Base):
    __tablename__ = "lines"
    id = Column(String, primary_key=True)  # LIN-*
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    line_type = Column(String, nullable=False)  # UP, DOWN, SINGLE, LOOP
    name = Column(String, nullable=False)
    __table_args__ = (
        Index("ix_lines_section", "section_id"),
        Index("ix_lines_corridor", "corridor_id"),
    )

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)  # AST-*
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    asset_type = Column(String, nullable=False)
    asset_criticality = Column(Integer, default=50)
    location_km = Column(Float, default=0)
    __table_args__ = (
        Index("ix_assets_corridor", "corridor_id"),
        Index("ix_assets_section", "section_id"),
        Index("ix_assets_line", "line_id"),
        Index("ix_assets_type", "asset_type"),
    )

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)  # TSK-*
    source_system = Column(String, nullable=False)  # TMS, SMMS, TDMS, COA
    department = Column(String, nullable=False)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=True)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    location_from_km = Column(Float, default=0)
    location_to_km = Column(Float, default=0)
    task_type = Column(String, nullable=False)
    description = Column(Text, default="")
    severity = Column(String, default="MEDIUM")
    safety_score = Column(Float, default=50)
    urgency_score = Column(Float, default=50)
    asset_criticality = Column(Float, default=50)
    operational_impact = Column(Float, default=50)
    overdue_days = Column(Integer, default=0)
    coordination_value = Column(Float, default=50)
    resource_readiness = Column(Float, default=50)
    estimated_duration_minutes = Column(Integer, nullable=False, default=60)
    setup_duration_minutes = Column(Integer, default=15)
    required_block_type = Column(String, default="TRAFFIC")
    requires_traffic_block = Column(Boolean, default=True)
    requires_power_isolation = Column(Boolean, default=False)
    requires_signal_disconnection = Column(Boolean, default=False)
    earliest_start = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status = Column(String, default="ELIGIBLE")  # ELIGIBLE,SCHEDULED,LOCKED,IN_PROGRESS,COMPLETED,PARTIALLY_COMPLETED,DEFERRED,CANCELLED
    priority_score = Column(Float, default=0)
    priority_rank = Column(Integer, default=0)
    priority_reason = Column(Text, default="")
    priority_band = Column(String, default="MEDIUM")
    priority_breakdown = Column(Text, default="{}")  # JSON
    rule_configuration_version = Column(String, default="v1")
    # Phase 1a provenance — live vs synthetic tagging (nullable for backward compat)
    external_id = Column(String, nullable=True)
    source_updated_at = Column(String, nullable=True)
    source_maturity = Column(String, default="SYNTHETIC")
    source_hash = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_tasks_corridor", "corridor_id"),
        Index("ix_tasks_section", "section_id"),
        Index("ix_tasks_line", "line_id"),
        Index("ix_tasks_asset", "asset_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_department", "department"),
        Index("ix_tasks_priority", "priority_score"),
        Index("ix_tasks_earliest", "earliest_start"),
        Index("ix_tasks_deadline", "deadline"),
    )

class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    depends_on_task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    __table_args__ = (
        Index("ix_taskdep_task", "task_id"),
        Index("ix_taskdep_dep", "depends_on_task_id"),
    )

class TrainMovement(Base):
    __tablename__ = "train_movements"
    id = Column(String, primary_key=True)  # TRN-*
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    train_type = Column(String, default="PASSENGER")  # PASSENGER, GOODS
    service_date = Column(String, nullable=False)  # YYYY-MM-DD
    departure_time = Column(Integer, nullable=False)  # minutes from midnight
    arrival_time = Column(Integer, nullable=False)
    buffer_before = Column(Integer, default=15)
    buffer_after = Column(Integer, default=15)
    # Phase 1a provenance
    external_id = Column(String, nullable=True)
    source_updated_at = Column(String, nullable=True)
    source_maturity = Column(String, default="SYNTHETIC")
    source_hash = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_trains_corridor", "corridor_id"),
        Index("ix_trains_service_date", "service_date"),
        Index("ix_trains_section", "section_id"),
        Index("ix_trains_line", "line_id"),
        Index("ix_trains_corridor_date", "corridor_id", "service_date"),
    )

class GoodsForecast(Base):
    __tablename__ = "goods_forecasts"
    id = Column(String, primary_key=True)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    service_date = Column(String, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    confidence = Column(Float, default=0.5)
    risk_score = Column(Float, default=0)
    forecast_count = Column(Integer, default=1)
    # Phase 1a provenance
    external_id = Column(String, nullable=True)
    source_updated_at = Column(String, nullable=True)
    source_maturity = Column(String, default="SYNTHETIC")
    source_hash = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_goods_corridor", "corridor_id"),
        Index("ix_goods_service_date", "service_date"),
        Index("ix_goods_corridor_date", "corridor_id", "service_date"),
    )

class Resource(Base):
    __tablename__ = "resources"
    id = Column(String, primary_key=True)  # RES-*
    resource_type = Column(String, nullable=False)  # CREW, MACHINE, MATERIAL
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    capacity = Column(Integer, default=1)
    __table_args__ = (Index("ix_resources_dept", "department"),)

class ResourceAvailability(Base):
    __tablename__ = "resource_availabilities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(String, ForeignKey("resources.id"), nullable=False)
    service_date = Column(String, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    available = Column(Boolean, default=True)
    __table_args__ = (
        Index("ix_resavail_resource", "resource_id"),
        Index("ix_resavail_date", "service_date"),
        Index("ix_resavail_resource_date", "resource_id", "service_date"),
    )

# Many-to-many task_resources
from sqlalchemy import Table
task_resources = Table(
    "task_resources",
    Base.metadata,
    Column("task_id", String, ForeignKey("tasks.id"), primary_key=True),
    Column("resource_id", String, ForeignKey("resources.id"), primary_key=True),
)

class CandidateWindow(Base):
    __tablename__ = "candidate_windows"
    id = Column(String, primary_key=True)  # WND-*
    service_date = Column(String, nullable=False)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    available_minutes = Column(Integer, nullable=False)
    block_type = Column(String, nullable=False)
    requires_power_isolation = Column(Boolean, default=False)
    requires_signal_disconnection = Column(Boolean, default=False)
    expected_train_count = Column(Integer, default=0)
    goods_risk_score = Column(Float, default=0)
    risk_band = Column(String, default="LOW")
    availability_source = Column(String, default="Synthetic prototype windows, not official railway availability.")
    rejection_reason = Column(Text, nullable=True)
    status = Column(String, default="FEASIBLE")  # FEASIBLE, REJECTED
    __table_args__ = (
        Index("ix_windows_service_date", "service_date"),
        Index("ix_windows_corridor", "corridor_id"),
        Index("ix_windows_status", "status"),
        Index("ix_windows_corridor_date", "corridor_id", "service_date"),
        Index("ix_windows_section", "section_id"),
        Index("ix_windows_line", "line_id"),
    )

class TaskWindowCandidate(Base):
    __tablename__ = "task_window_candidates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    window_id = Column(String, ForeignKey("candidate_windows.id"), nullable=False)
    feasibility = Column(String, default="FEASIBLE")  # FEASIBLE, HARD_CONFLICT, SOFT_RISK
    reason = Column(Text, default="")
    __table_args__ = (
        Index("ix_twc_task", "task_id"),
        Index("ix_twc_window", "window_id"),
    )

class TaskGroup(Base):
    __tablename__ = "task_groups"
    id = Column(String, primary_key=True)  # GRP-*
    window_id = Column(String, ForeignKey("candidate_windows.id"), nullable=True)
    task_ids = Column(Text, default="[]")  # JSON list
    compatible = Column(Boolean, default=True)
    reasons = Column(Text, default="[]")
    __table_args__ = (Index("ix_taskgroup_window", "window_id"),)

class BlockPlan(Base):
    __tablename__ = "block_plans"
    id = Column(String, primary_key=True)  # PLAN-*
    horizon_type = Column(String, nullable=False)  # WEEKLY, MONTHLY
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    status = Column(String, default="DRAFT")  # DRAFT,UNDER_REVIEW,APPROVED,PUBLISHED,REVISION_REQUESTED,SUPERSEDED,REJECTED
    solver_status = Column(String, default="UNKNOWN")
    created_at = Column(DateTime, default=utcnow)
    version = Column(Integer, default=1)
    baseline_metrics = Column(Text, default="{}")
    optimized_metrics = Column(Text, default="{}")
    objective_breakdown = Column(Text, default="{}")
    unscheduled_reasons = Column(Text, default="[]")
    base_plan_id = Column(String, ForeignKey("block_plans.id"), nullable=True)
    __table_args__ = (
        Index("ix_plans_status", "status"),
        Index("ix_plans_horizon", "horizon_type"),
        Index("ix_plans_start", "start_date"),
        Index("ix_plans_created", "created_at"),
    )

class Block(Base):
    __tablename__ = "blocks"
    id = Column(String, primary_key=True)  # BLK-*
    plan_id = Column(String, ForeignKey("block_plans.id"), nullable=False)
    window_id = Column(String, ForeignKey("candidate_windows.id"), nullable=True)
    corridor_id = Column(String, ForeignKey("corridors.id"), nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=True)
    line_id = Column(String, ForeignKey("lines.id"), nullable=True)
    service_date = Column(String, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    block_type = Column(String, nullable=False)
    requires_power_isolation = Column(Boolean, default=False)
    requires_signal_disconnection = Column(Boolean, default=False)
    status = Column(String, default="GENERATED")  # GENERATED,UNDER_REVIEW,APPROVED,PUBLISHED,IN_PROGRESS,COMPLETED,PARTIALLY_COMPLETED,CANCELLED,REJECTED
    department = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_blocks_plan", "plan_id"),
        Index("ix_blocks_service_date", "service_date"),
        Index("ix_blocks_corridor", "corridor_id"),
        Index("ix_blocks_status", "status"),
        Index("ix_blocks_plan_date", "plan_id", "service_date"),
    )

class BlockTask(Base):
    __tablename__ = "block_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    block_id = Column(String, ForeignKey("blocks.id"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    status = Column(String, default="SCHEDULED")  # SCHEDULED,LOCKED,IN_PROGRESS,COMPLETED,PARTIALLY_COMPLETED,DEFERRED,CANCELLED
    sequence = Column(Integer, default=0)
    __table_args__ = (
        Index("ix_blocktasks_block", "block_id"),
        Index("ix_blocktasks_task", "task_id"),
    )

class PlanRevision(Base):
    __tablename__ = "plan_revisions"
    id = Column(String, primary_key=True)  # REV-*
    base_plan_id = Column(String, ForeignKey("block_plans.id"), nullable=False)
    new_plan_id = Column(String, ForeignKey("block_plans.id"), nullable=False)
    revision_number = Column(Integer, nullable=False)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(String, default="demo_user")
    __table_args__ = (
        Index("ix_revisions_base", "base_plan_id"),
        Index("ix_revisions_new", "new_plan_id"),
    )

class PlanChange(Base):
    __tablename__ = "plan_changes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    revision_id = Column(String, ForeignKey("plan_revisions.id"), nullable=False)
    change_type = Column(String, nullable=False)  # ADDED, REMOVED, MOVED, EDITED
    block_id = Column(String, nullable=True)
    task_id = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, default="")
    __table_args__ = (Index("ix_planchange_rev", "revision_id"),)

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String, ForeignKey("block_plans.id"), nullable=False)
    block_id = Column(String, ForeignKey("blocks.id"), nullable=True)
    approver_id = Column(String, nullable=False)
    approver_role = Column(String, nullable=False)
    decision = Column(String, nullable=False)  # APPROVED, REJECTED
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_approvals_plan", "plan_id"),)

class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id = Column(String, primary_key=True)  # EXE-*
    block_id = Column(String, ForeignKey("blocks.id"), nullable=False)
    plan_id = Column(String, ForeignKey("block_plans.id"), nullable=False)
    actual_start = Column(Integer, nullable=False)
    actual_end = Column(Integer, nullable=False)
    service_date = Column(String, nullable=False)
    status = Column(String, nullable=False)  # COMPLETED, PARTIALLY_COMPLETED, CANCELLED, DEFERRED
    completed_task_ids = Column(Text, default="[]")
    partially_completed_task_ids = Column(Text, default="[]")
    cancelled_task_ids = Column(Text, default="[]")
    reason = Column(Text, default="")
    asset_status = Column(String, default="")
    train_impact = Column(String, default="")
    notes = Column(Text, default="")
    recorded_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (
        Index("ix_exec_block", "block_id"),
        Index("ix_exec_plan", "plan_id"),
        Index("ix_exec_date", "service_date"),
    )

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String, nullable=False)
    plan_id = Column(String, nullable=True)
    block_id = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    type = Column(String, default="INFO")
    created_at = Column(DateTime, default=utcnow)
    read = Column(Boolean, default=False)
    __table_args__ = (Index("ix_notif_dept", "department"), Index("ix_notif_created", "created_at"),)

class RuleConfiguration(Base):
    __tablename__ = "rule_configurations"
    id = Column(String, primary_key=True)
    version = Column(String, nullable=False)
    priority_weights = Column(Text, default="{}")
    optimizer_weights = Column(Text, default="{}")
    hard_constraints = Column(Text, default="[]")
    ai_model = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)

class ImportRun(Base):
    __tablename__ = "import_runs"
    id = Column(String, primary_key=True)
    source_name = Column(String, nullable=False)
    received_count = Column(Integer, default=0)
    accepted_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    errors = Column(Text, default="[]")
    warnings = Column(Text, default="[]")
    started_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, default=utcnow)
    # Phase 1a/1b provenance + incremental cursor
    source_maturity = Column(String, default="SYNTHETIC")
    source_hash = Column(String, nullable=True)
    cursor_value = Column(String, nullable=True)
    # Incremental recovery outcome (additive, nullable for backward compat)
    outcome = Column(String, nullable=True)  # FETCH_FAILED, PARSE_FAILED, EMPTY_SUCCESS, PARTIAL_SUCCESS, SUCCESS
    __table_args__ = (Index("ix_import_source", "source_name"), Index("ix_import_started", "started_at"),)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    details = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_created", "created_at"),
    )

class SourceCursor(Base):
    """Phase 1b/1c — incremental cursor + Option A/B diagnostics (additive, nullable)."""
    __tablename__ = "source_cursors"
    source_name = Column(String, primary_key=True)
    cursor_value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=utcnow)
    # Option A diagnostics — all nullable/default 0 for backward compat
    last_success_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    fetch_attempts = Column(Integer, default=0)
    fetch_successes = Column(Integer, default=0)
    # Option B: explicit outcome of last attempt (FETCH_FAILED, PARSE_FAILED, EMPTY_SUCCESS, PARTIAL_SUCCESS, SUCCESS)
    last_outcome = Column(String, nullable=True)
    __table_args__ = (Index("ix_sourcecursor_updated", "updated_at"),)
