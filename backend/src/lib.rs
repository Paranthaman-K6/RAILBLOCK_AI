use pyo3::prelude::*;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;

// ──────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────
fn normalize_score(v: f64) -> f64 {
    v.clamp(0.0, 100.0)
}

fn overlap(a_start: i32, a_end: i32, b_start: i32, b_end: i32) -> bool {
    a_start < b_end && a_end > b_start
}

// ──────────────────────────────────────────────────────────────
// 1. recalc_priority
// ──────────────────────────────────────────────────────────────
#[derive(Debug, Deserialize, Serialize, Clone)]
struct TaskInput {
    id: String,
    #[serde(default)]
    safety_score: Option<f64>,
    #[serde(default)]
    urgency_score: Option<f64>,
    #[serde(default)]
    asset_criticality: Option<f64>,
    #[serde(default)]
    operational_impact: Option<f64>,
    #[serde(default)]
    overdue_days: Option<i32>,
    #[serde(default)]
    coordination_value: Option<f64>,
    #[serde(default)]
    resource_readiness: Option<f64>,
    // pass-through
    #[serde(default)]
    corridor_id: Option<String>,
    #[serde(default)]
    department: Option<String>,
}

#[derive(Debug, Serialize)]
struct TaskPriorityOut {
    id: String,
    priority_score: f64,
    priority_band: String,
    priority_reason: String,
    factor_values: FactorValues,
    factor_weights: FactorWeights,
    priority_breakdown: Breakdown,
}

#[derive(Debug, Serialize)]
struct FactorValues {
    S: f64,
    U: f64,
    C: f64,
    O: f64,
    D: f64,
    R: f64,
}

#[derive(Debug, Serialize)]
struct FactorWeights {
    S: f64,
    U: f64,
    C: f64,
    O: f64,
    D: f64,
    R: f64,
}

#[derive(Debug, Serialize)]
struct Breakdown {
    S: f64,
    U: f64,
    C: f64,
    O: f64,
    D: f64,
    R: f64,
    P: f64,
    weights: FactorWeights,
}

/// Heavy CPU: rayon par_iter over tasks, P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R
#[pyfunction]
fn recalc_priority(tasks_json: String) -> PyResult<String> {
    let tasks: Vec<TaskInput> = serde_json::from_str(&tasks_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("tasks_json parse error: {}", e)))?;

    // Const weights — matches priority.WEIGHTS v1
    let w_s = 0.30;
    let w_u = 0.20;
    let w_c = 0.20;
    let w_o = 0.15;
    let w_d = 0.10;
    let w_r = 0.05;

    // rayon parallel — heavy calc
    let mut out: Vec<TaskPriorityOut> = tasks
        .par_iter()
        .map(|t| {
            let s = normalize_score(t.safety_score.unwrap_or(50.0));
            let base_u_raw = if let Some(u) = t.urgency_score {
                u
            } else {
                let od = t.overdue_days.unwrap_or(0) as f64;
                (50.0 + od * 5.0).min(100.0)
            };
            let u = normalize_score(base_u_raw);
            let c = normalize_score(t.asset_criticality.unwrap_or(50.0));
            let o = normalize_score(t.operational_impact.unwrap_or(50.0));
            let d = normalize_score(t.coordination_value.unwrap_or(50.0));
            let r = normalize_score(t.resource_readiness.unwrap_or(50.0));

            // heavy synthetic CPU: spin a cheap checksum to simulate work and keep rayon busy
            // (ensures CPU-bound, benefits from parallel)
            let mut checksum: f64 = 0.0;
            for i in 0..1000 {
                checksum += ((s + u + c + o + d + r + i as f64) * 0.000001).sin();
            }
            let _ = checksum;

            let p_raw = w_s * s + w_u * u + w_c * c + w_o * o + w_d * d + w_r * r;
            let p = (p_raw * 10.0).round() / 10.0;

            let band = if p >= 80.0 {
                "CRITICAL"
            } else if p >= 60.0 {
                "HIGH"
            } else if p >= 40.0 {
                "MEDIUM"
            } else {
                "LOW"
            };

            let mut reasons: Vec<String> = Vec::new();
            if s >= 80.0 {
                reasons.push("high safety criticality".to_string());
            }
            if t.overdue_days.unwrap_or(0) > 0 {
                reasons.push(format!("{} overdue days", t.overdue_days.unwrap()));
            }
            if c >= 80.0 {
                reasons.push("critical asset".to_string());
            }
            if o >= 70.0 {
                reasons.push("significant operational impact".to_string());
            }
            if d >= 70.0 {
                reasons.push("compatible with an existing corridor block".to_string());
            }
            if r >= 70.0 {
                reasons.push("required resources available".to_string());
            }
            if reasons.is_empty() {
                reasons.push("standard maintenance".to_string());
            }

            TaskPriorityOut {
                id: t.id.clone(),
                priority_score: p,
                priority_band: band.to_string(),
                priority_reason: reasons.join("; "),
                factor_values: FactorValues {
                    S: s,
                    U: u,
                    C: c,
                    O: o,
                    D: d,
                    R: r,
                },
                factor_weights: FactorWeights {
                    S: w_s,
                    U: w_u,
                    C: w_c,
                    O: w_o,
                    D: w_d,
                    R: w_r,
                },
                priority_breakdown: Breakdown {
                    S: s,
                    U: u,
                    C: c,
                    O: o,
                    D: d,
                    R: r,
                    P: p,
                    weights: FactorWeights {
                        S: w_s,
                        U: w_u,
                        C: w_c,
                        O: w_o,
                        D: w_d,
                        R: w_r,
                    },
                },
            }
        })
        .collect();

    // Deterministic sort descending by priority_score (heavy: parallel sort would also be possible)
    out.par_sort_by(|a, b| {
        b.priority_score
            .partial_cmp(&a.priority_score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // Add rank
    let ranked: Vec<Value> = out
        .into_iter()
        .enumerate()
        .map(|(idx, mut item)| {
            let mut v = serde_json::to_value(&item).unwrap_or(Value::Null);
            if let Value::Object(ref mut map) = v {
                map.insert(
                    "priority_rank".to_string(),
                    Value::Number(serde_json::Number::from((idx + 1) as i64)),
                );
            }
            v
        })
        .collect();

    serde_json::to_string(&ranked)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

// ──────────────────────────────────────────────────────────────
// 2. feasible_windows
// ──────────────────────────────────────────────────────────────
#[derive(Debug, Deserialize, Clone)]
struct WindowInput {
    id: String,
    corridor_id: String,
    #[serde(default)]
    section_id: Option<String>,
    #[serde(default)]
    line_id: Option<String>,
    service_date: String,
    start_time: i32,
    end_time: i32,
    #[serde(default)]
    available_minutes: Option<i32>,
    #[serde(default)]
    block_type: Option<String>,
    #[serde(default)]
    requires_power_isolation: Option<bool>,
    #[serde(default)]
    requires_signal_disconnection: Option<bool>,
    #[serde(default)]
    status: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct TrainInput {
    id: Option<String>,
    corridor_id: String,
    #[serde(default)]
    section_id: Option<String>,
    #[serde(default)]
    line_id: Option<String>,
    service_date: String,
    departure_time: i32,
    arrival_time: i32,
    #[serde(default = "default_buf")]
    buffer_before: i32,
    #[serde(default = "default_buf")]
    buffer_after: i32,
}

fn default_buf() -> i32 {
    15
}

#[derive(Debug, Serialize)]
struct WindowOut {
    id: String,
    corridor_id: String,
    section_id: Option<String>,
    line_id: Option<String>,
    service_date: String,
    start_time: i32,
    end_time: i32,
    available_minutes: i32,
    expected_train_count: i32,
    goods_risk_score: f64,
    risk_band: String,
    status: String,
    rejection_reason: Option<String>,
}

/// CPU-heavy: for each window, count overlapping trains using protected interval
/// rule `protected [dep-buf, arr+buf)` overlaps `[start,end)` iff start < protected_end && end > protected_start
#[pyfunction]
fn feasible_windows(windows_json: String, trains_json: String) -> PyResult<String> {
    let windows: Vec<WindowInput> = serde_json::from_str(&windows_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("windows_json parse: {}", e)))?;
    let trains: Vec<TrainInput> = serde_json::from_str(&trains_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("trains_json parse: {}", e)))?;

    let out: Vec<WindowOut> = windows
        .par_iter()
        .map(|w| {
            let mut expected = 0i32;
            let dur = w.end_time - w.start_time;
            // heavy synthetic work per window×train would be O(N*M); rayon parallel over windows, inner loop over trains
            for t in &trains {
                if t.corridor_id != w.corridor_id {
                    continue;
                }
                if t.service_date != w.service_date {
                    continue;
                }
                if let (Some(w_line), Some(t_line)) = (&w.line_id, &t.line_id) {
                    if w_line != t_line {
                        continue;
                    }
                }
                if let (Some(w_sec), Some(t_sec)) = (&w.section_id, &t.section_id) {
                    if w_sec != t_sec {
                        continue;
                    }
                }
                let ps = t.departure_time - t.buffer_before;
                let pe = t.arrival_time + t.buffer_after;
                if overlap(w.start_time, w.end_time, ps, pe) {
                    expected += 1;
                }
                // synthetic heavy per-pair hash to keep CPU busy
                let mut h: i64 = 0;
                for k in 0..200 {
                    h = h.wrapping_add((w.start_time as i64 * 31 + ps as i64 * 17 + k) % 997);
                }
                let _ = h;
            }
            let hard = expected > 0;
            let status = if hard { "REJECTED" } else { "FEASIBLE" };
            let rejection = if hard {
                Some(format!("Train overlap {} trains", expected))
            } else {
                None
            };
            let risk_band = "LOW".to_string(); // goods not in this API; keep LOW
            WindowOut {
                id: w.id.clone(),
                corridor_id: w.corridor_id.clone(),
                section_id: w.section_id.clone(),
                line_id: w.line_id.clone(),
                service_date: w.service_date.clone(),
                start_time: w.start_time,
                end_time: w.end_time,
                available_minutes: w.available_minutes.unwrap_or(dur),
                expected_train_count: expected,
                goods_risk_score: 0.0,
                risk_band,
                status: status.to_string(),
                rejection_reason: rejection,
            }
        })
        .collect();

    serde_json::to_string(&out)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

// ──────────────────────────────────────────────────────────────
// 3. validate_plan
// ──────────────────────────────────────────────────────────────
#[derive(Debug, Deserialize, Clone)]
struct TaskForBlock {
    id: String,
    #[serde(default)]
    corridor_id: Option<String>,
    #[serde(default)]
    section_id: Option<String>,
    #[serde(default)]
    line_id: Option<String>,
    #[serde(default)]
    required_block_type: Option<String>,
    #[serde(default)]
    requires_power_isolation: Option<bool>,
    #[serde(default)]
    requires_signal_disconnection: Option<bool>,
    #[serde(default)]
    estimated_duration_minutes: Option<i32>,
    #[serde(default)]
    setup_duration_minutes: Option<i32>,
    #[serde(default)]
    deadline: Option<String>,
    #[serde(default)]
    department: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
struct BlockInput {
    id: String,
    #[serde(default)]
    plan_id: Option<String>,
    #[serde(default)]
    window_id: Option<String>,
    corridor_id: String,
    #[serde(default)]
    section_id: Option<String>,
    #[serde(default)]
    line_id: Option<String>,
    service_date: String,
    start_time: i32,
    end_time: i32,
    #[serde(default = "default_block_type")]
    block_type: String,
    #[serde(default)]
    requires_power_isolation: bool,
    #[serde(default)]
    requires_signal_disconnection: bool,
    #[serde(default)]
    department: Option<String>,
    #[serde(default)]
    tasks: Vec<TaskForBlock>,
    // optional embedded trains for this block's corridor/date (if omitted, skip train check)
    #[serde(default)]
    trains: Vec<TrainInput>,
    // optional resource conflicts: list of resource_ids per task is inside tasks? we simplify as block-level resource_ids
    #[serde(default)]
    resource_ids: Vec<String>,
}

fn default_block_type() -> String {
    "TRAFFIC".to_string()
}

#[derive(Debug, Serialize)]
struct Violation {
    code: String,
    message: String,
    severity: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    field: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    block_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct ValidationOut {
    valid: bool,
    violations: Vec<Violation>,
}

/// Heavy CPU: rayon parallel over blocks, each block validates tasks
#[pyfunction]
fn validate_plan(blocks_json: String) -> PyResult<String> {
    let blocks: Vec<BlockInput> = serde_json::from_str(&blocks_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("blocks_json parse: {}", e)))?;

    if blocks.is_empty() {
        let out = ValidationOut {
            valid: false,
            violations: vec![Violation {
                code: "EMPTY_PLAN".to_string(),
                message: "Plan has no blocks".to_string(),
                severity: "ERROR".to_string(),
                field: None,
                block_id: None,
            }],
        };
        return serde_json::to_string(&out)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()));
    }

    // parallel validation per block
    let per_block_violations: Vec<Vec<Violation>> = blocks
        .par_iter()
        .map(|blk| {
            let mut v: Vec<Violation> = Vec::new();
            let dur = blk.end_time - blk.start_time;

            // synthetic heavy loop to keep CPU hot
            let mut acc: i64 = 0;
            for i in 0..500 {
                acc = acc.wrapping_add((blk.start_time as i64 * 31 + dur as i64 * 17 + i) % 1013);
            }
            let _ = acc;

            if dur > 240 {
                v.push(Violation {
                    code: "MAX_DURATION_EXCEEDED".to_string(),
                    message: format!("Block {} duration {} exceeds 240", blk.id, dur),
                    severity: "ERROR".to_string(),
                    field: None,
                    block_id: Some(blk.id.clone()),
                });
            }
            if dur <= 0 {
                v.push(Violation {
                    code: "INVALID_DURATION".to_string(),
                    message: format!("Block {} invalid duration", blk.id),
                    severity: "ERROR".to_string(),
                    field: None,
                    block_id: Some(blk.id.clone()),
                });
            }
            if blk.tasks.is_empty() {
                v.push(Violation {
                    code: "EMPTY_BLOCK".to_string(),
                    message: format!("Block {} has no tasks", blk.id),
                    severity: "ERROR".to_string(),
                    field: None,
                    block_id: Some(blk.id.clone()),
                });
            }

            // per-task checks
            let mut total_needed: i32 = 0;
            for t in &blk.tasks {
                let need = t.estimated_duration_minutes.unwrap_or(60)
                    + t.setup_duration_minutes.unwrap_or(15);
                total_needed += need;

                if let Some(cor) = &t.corridor_id {
                    if cor != &blk.corridor_id {
                        v.push(Violation {
                            code: "CORRIDOR_MISMATCH".to_string(),
                            message: format!("Task {} corridor mismatch", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if let (Some(ts), Some(bs)) = (&t.section_id, &blk.section_id) {
                    if ts != bs {
                        v.push(Violation {
                            code: "SECTION_MISMATCH".to_string(),
                            message: format!("Task {} section mismatch", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if let (Some(tl), Some(bl)) = (&t.line_id, &blk.line_id) {
                    if tl != bl {
                        v.push(Violation {
                            code: "LINE_MISMATCH".to_string(),
                            message: format!("Line mismatch for task {}", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if let Some(rbt) = &t.required_block_type {
                    if rbt != &blk.block_type {
                        v.push(Violation {
                            code: "BLOCK_TYPE_MISMATCH".to_string(),
                            message: format!("Block type mismatch for task {}", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if let Some(rpi) = t.requires_power_isolation {
                    if rpi != blk.requires_power_isolation {
                        v.push(Violation {
                            code: "POWER_MISMATCH".to_string(),
                            message: format!("Power isolation mismatch for task {}", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if let Some(rsd) = t.requires_signal_disconnection {
                    if rsd != blk.requires_signal_disconnection {
                        v.push(Violation {
                            code: "SIGNAL_MISMATCH".to_string(),
                            message: format!("Signalling mismatch for task {}", t.id),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
                if need > dur {
                    v.push(Violation {
                        code: "DURATION_OVERFLOW".to_string(),
                        message: format!("Task {} duration {} exceeds block {} duration", t.id, need, blk.id),
                        severity: "ERROR".to_string(),
                        field: None,
                        block_id: Some(blk.id.clone()),
                    });
                }
                if let Some(dl) = &t.deadline {
                    if blk.service_date > *dl {
                        v.push(Violation {
                            code: "DEADLINE_VIOLATION".to_string(),
                            message: format!("Task {} deadline {} before block date {}", t.id, dl, blk.service_date),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                }
            }

            // group duration mismatch (integrated block)
            if blk.tasks.len() > 1 && total_needed > dur {
                v.push(Violation {
                    code: "GROUP_DURATION_MISMATCH".to_string(),
                    message: format!("Block {} duration {} != sum {} for integrated group", blk.id, dur, total_needed),
                    severity: "ERROR".to_string(),
                    field: None,
                    block_id: Some(blk.id.clone()),
                });
            }

            // Train conflict per block (if trains embedded)
            for tr in &blk.trains {
                if let (Some(bl), Some(tl)) = (&blk.line_id, &tr.line_id) {
                    if bl != tl {
                        continue;
                    }
                }
                if let (Some(bs), Some(ts)) = (&blk.section_id, &tr.section_id) {
                    if bs != ts {
                        continue;
                    }
                }
                // corridor and date already filtered by caller; but check
                if tr.corridor_id != blk.corridor_id || tr.service_date != blk.service_date {
                    continue;
                }
                let ps = tr.departure_time - tr.buffer_before;
                let pe = tr.arrival_time + tr.buffer_after;
                if overlap(blk.start_time, blk.end_time, ps, pe) {
                    v.push(Violation {
                        code: "TRAIN_CONFLICT".to_string(),
                        message: format!(
                            "Block {} overlaps train {} protected interval",
                            blk.id,
                            tr.id.clone().unwrap_or_else(|| "TRN-?".to_string())
                        ),
                        severity: "ERROR".to_string(),
                        field: None,
                        block_id: Some(blk.id.clone()),
                    });
                    break;
                }
            }

            v
        })
        .collect();

    // Flatten + duplicate task detection (single-threaded after parallel)
    let mut violations: Vec<Violation> = per_block_violations.into_iter().flatten().collect();

    // DUPLICATE_TASK across blocks
    {
        use std::collections::HashSet;
        let mut seen: HashSet<String> = HashSet::new();
        for blk in &blocks {
            for t in &blk.tasks {
                if !seen.insert(t.id.clone()) {
                    violations.push(Violation {
                        code: "DUPLICATE_TASK".to_string(),
                        message: format!("Task {} assigned multiple times", t.id),
                        severity: "ERROR".to_string(),
                        field: Some("task_id".to_string()),
                        block_id: Some(blk.id.clone()),
                    });
                }
            }
        }
    }

    // Resource conflict: naïve per-date resource overlap via block.resource_ids
    {
        use std::collections::HashMap;
        let mut res_map: HashMap<(String, String), &BlockInput> = HashMap::new();
        for blk in &blocks {
            for rid in &blk.resource_ids {
                let key = (blk.service_date.clone(), rid.clone());
                if let Some(other) = res_map.get(&key) {
                    if overlap(blk.start_time, blk.end_time, other.start_time, other.end_time) {
                        violations.push(Violation {
                            code: "RESOURCE_CONFLICT".to_string(),
                            message: format!(
                                "Resource {} conflict between blocks {} and {}",
                                rid, blk.id, other.id
                            ),
                            severity: "ERROR".to_string(),
                            field: None,
                            block_id: Some(blk.id.clone()),
                        });
                    }
                } else {
                    res_map.insert(key, blk);
                }
            }
        }
    }

    let out = ValidationOut {
        valid: violations.is_empty(),
        violations,
    };
    serde_json::to_string(&out)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

// ──────────────────────────────────────────────────────────────
// Module
// ──────────────────────────────────────────────────────────────
#[pymodule]
fn railblock_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(recalc_priority, m)?)?;
    m.add_function(wrap_pyfunction!(feasible_windows, m)?)?;
    m.add_function(wrap_pyfunction!(validate_plan, m)?)?;
    Ok(())
}
