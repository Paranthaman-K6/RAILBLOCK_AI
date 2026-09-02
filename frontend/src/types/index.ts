export type Department =
  | 'CONTROL_OFFICE'
  | 'ENGINEERING'
  | 'S_AND_T'
  | 'TRACTION'
  | 'PROJECTS'
  | 'VIEWER'
  | 'ADMIN'

export interface Task {
  task_id: string
  source_system?: string
  department: Department | string
  asset_id?: string | null
  corridor_id: string
  section_id?: string | null
  line_id?: string | null
  location_from_km?: number
  location_to_km?: number
  task_type?: string
  description?: string
  severity?: string
  safety_score?: number
  urgency_score?: number
  asset_criticality?: number
  operational_impact?: number
  coordination_value?: number
  resource_readiness?: number
  estimated_duration_minutes?: number
  setup_duration_minutes?: number
  required_block_type?: string
  requires_traffic_block?: boolean
  requires_power_isolation?: boolean
  requires_signal_disconnection?: boolean
  earliest_start?: string | null
  deadline?: string | null
  overdue_days?: number
  status?: string
  priority_score: number
  priority_rank?: number
  priority_band: string
  priority_reason?: string
  priority_breakdown?: Record<string, unknown>
  factor_values?: Record<string, number>
  factor_weights?: Record<string, number>
  rule_configuration_version?: string
}

export interface BlockTask {
  task_id: string
  status?: string
  department?: string
  sequence?: number
}

export interface Block {
  block_id: string
  plan_id?: string
  window_id?: string | null
  service_date: string
  start_time: number
  end_time: number
  corridor_id: string
  section_id?: string | null
  line_id?: string | null
  block_type?: string
  requires_power_isolation?: boolean
  requires_signal_disconnection?: boolean
  status?: string
  department?: string | null
  tasks?: BlockTask[]
}

export interface ApprovalInfo {
  approver_id: string
  approver_role: string
  reason?: string
  created_at?: string
}

export interface BlockPlan {
  plan_id: string
  horizon_type: string
  start_date: string
  end_date: string
  status: string
  solver_status: string
  version?: number
  created_at?: string
  baseline_metrics?: Record<string, unknown>
  optimized_metrics?: Record<string, unknown>
  objective_breakdown?: Record<string, unknown>
  unscheduled_reasons?: unknown[]
  validation?: ValidationResult
  blocks?: Block[]
  required_departments?: string[]
  approved_departments?: string[]
  pending_departments?: string[]
  approvals?: ApprovalInfo[]
}

export interface ValidationViolation {
  code: string
  message: string
  field?: string
  severity?: string
}

export interface ValidationResult {
  valid: boolean
  violations: ValidationViolation[]
  warnings?: ValidationViolation[]
}

export interface Corridor {
  corridor_id: string
  name: string
  corridor_type?: string
}

export interface Asset {
  asset_id: string
  corridor_id: string
  section_id?: string | null
  line_id?: string | null
  asset_type: string
  asset_criticality?: number
  location_km?: number
}

export interface TrainMovement {
  train_id: string
  corridor_id: string
  section_id?: string | null
  line_id?: string | null
  train_type?: string
  service_date: string
  departure_time: number
  arrival_time: number
  buffer_before?: number
  buffer_after?: number
}

export interface CandidateWindow {
  window_id: string
  service_date: string
  corridor_id: string
  section_id?: string | null
  line_id?: string | null
  start_time: number
  end_time: number
  available_minutes: number
  block_type: string
  requires_power_isolation?: boolean
  requires_signal_disconnection?: boolean
  status: string
  goods_risk_score?: number
  risk_band?: string
}

export interface MetricsData {
  plan_id: string
  blocks?: number
  scheduled_tasks?: number
  critical_tasks?: number
  integrated_groups?: number
  conflicts?: number
  unused_time?: number
  resource_utilization?: number
  baseline?: Record<string, unknown>
  optimized?: Record<string, unknown>
  baseline_metrics?: Record<string, unknown>
  optimized_metrics?: Record<string, unknown>
  improvement?: Record<string, unknown>
  objective_breakdown?: Record<string, unknown>
  asset_metrics?: Record<string, { downtime_minutes: number; available_minutes: number; availability_pct: number }>
  asset_downtime_minutes?: number
  asset_available_minutes?: number
  asset_availability_pct?: number
  critical_asset_availability_pct?: number
  maintenance_completion_rate?: number
  planned_duration_minutes?: number
  actual_duration_minutes?: number
  duration_variance_minutes?: number
  dataset?: string
  validation?: ValidationResult
  planned_vs_actual?: Array<{ block_id: string; planned: number; actual: number; delta: number }>
  formulas?: Record<string, unknown>
  // compat for snake vs camel and dynamic backend fields
  [key: string]: unknown
}
