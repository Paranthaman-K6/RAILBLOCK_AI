# Problem Understanding — RailBlock AI

**Prototype disclaimer:** This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Synthetic prototype windows, not official railway availability.

## 1. Business Context

Indian Railways’ rolling-block guidance emphasizes advance block planning, integration of civil, electrical, S&T, and project work, and avoiding separate blocks in the same section when work can be coordinated. Research supports combining work, crew, possession, and cost in one planning model. This prototype implements that guidance as a human-approved decision-support system (not autonomous control).

## 2. Current vs Required

### Current (as observed)

- Maintenance for Engineering, Traction Distribution, and Signal & Telecommunication departments is planned independently through decentralized/manual block requests.
- Maintenance data exists separately in TMS, SMMS, TDMS, while COA provides corridor/block availability.
- Timetable and goods-train information affects feasible windows but is not centrally integrated.
- Block requests are not systematically coordinated for corridor/section/line, power/signalling, resources.

### Required (via RailBlock AI)

- Integrate 7 source domains + historical execution (8th): `TMS→ENGINEERING, SMMS→S_AND_T, TDMS→TRACTION, COA→assets, timetable, goods forecast, resources, historical execution`.
- Validate structurally/referentially/operationally with `ImportRun` and row-level errors.
- Map tasks to assets/corridors/sections/lines.
- Prioritize explainably `P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R` with historical delta.
- Generate feasible candidate windows with buffers, train/goods checks.
- Group multi-department compatible tasks (max 3) to create integrated blocks.
- Optimize weekly (2026-09-01→07) and monthly (→30) and DAILY (single day) via CP-SAT (5s, 8 workers) + baseline FCFS + fallback, independently validated.
- Support officer editing, approval/publication (CONTROL_OFFICE/ADMIN final), department-wise visibility, execution tracking, replanning with preservation, audit, metrics, export.
- Remain a human-approved prototype, not safety-certified, not live-integrated unless authorized.

## 3. Rolling-Block Concept

Rolling block → advance planning of maintenance possessions, integration of Engineering, Electrical, S&T, and project work in same section/line when compatible, avoiding duplicate possessions, coordinating crew/machines/materials, and respecting timetable/goods buffers and power/signalling isolation.

## 4. Integration Points

- TMS maintenance and defects → `Task` (ENGINEERING)
- SMMS signalling maintenance → `Task` (S_AND_T)
- TDMS traction/OHE maintenance → `Task` (TRACTION)
- COA corridor and asset availability → `Corridor, Section, Line, Asset`
- Timetable → `TrainMovement` protected intervals
- Goods forecast → `GoodsForecast` risk
- Resources → `Resource, ResourceAvailability`
- Historical execution → `ExecutionRecord` delta

## 5. Success Criteria (Current, Not Invented)

Same as `AGENTS.md` §7 — 52 tests pass, 907 modules build, WAL verified, weekly/monthly/daily `OPTIMAL` valid, approval workflow, department views, editing, execution (201/409/400/404/422), replan preservation, metrics from DB, export contains `PLAN-*`.

## 6. Explicit Non-Goals

Autonomous control, signal operation, power isolation, train dispatching, final safety authorization, unsupervised publication, live deployment without authorization.

## 7. Limitations

Synthetic windows, single-node SQLite WAL, no live APIs, no safety certification, notifications in-app only.

