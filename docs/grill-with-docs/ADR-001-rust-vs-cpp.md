# ADR-001: Performance Architecture — Native Extensions for Heavy Calculations

**Date:** 2026-09-20
**Status:** Accepted — **Rust (PyO3) primary**, C++ fallback, C rejected
**Context:** `POST /api/plans/generate` `CP-SAT 5s 8 workers` `1.40s` → target `<0.40s`; Supabase pooled connection handling; frontend responsiveness for `Submit`/`Approve`.

---

## 1. Why Not Plain C?

- Manual memory management, no safety guarantees, fragile interop — would duplicate existing C++ optimizer wrapper for minimal gain. **Rejected.**

**Why not pure Python only?**
- Priority scoring `P=0.30S+…` and candidate window generation (`720` windows × `133` trains) are tight loops — native parallelization yields `~4×` improvement.

---

## 2. Options Considered

| Option | Strengths | Trade-offs | Build |
|--------|-----------|------------|-------|
| **Rust + PyO3 + maturin** | Memory-safe, parallel execution, fast builds, stable interop, reusable | Requires toolchain | `backend/Cargo.toml` |
| **C++ + pybind11** | Direct optimizer API, zero-copy | Larger build, manual safety | `backend/optimizer_cpp/CMakeLists.txt` |
| **C** | Minimal overhead | No safety, fragile | `CFFI` |

---

## 3. Decision — Deep Module Design

**Interface:** `backend/app/services/heavy_calc.py` — three methods: `recalc_priority()`, `feasible_windows()`, `validate_plan()` — small surface, large implementation behind.

**Implementation:** `Rust` `src/lib.rs` with parallel iterators for protected interval checks `[departure-buffer, arrival+buffer)`; `C++` `optimizer_cpp` wraps `ortools/sat/cp_model.h` (`5s`, `8 workers`).

**Fallback:** Pure Python if native extension unavailable — same contract, no breaking change.

**Build:** Disabled on free-tier container to keep `<30s` builds; enabled locally and for production where toolchain is available.

---

## Glossary

- **Module:** `heavy_calc` — encapsulated unit with interface + implementation
- **Interface:** What callers must know (`validate_plan()` returns `valid` + `violations`, does not mutate)
- **Seam:** Location where implementation varies (`heavy_calc.py`)
- **Adapter:** `railblock_rs` (Rust) vs pure Python
- **Depth:** Large implementation behind small interface — high leverage, high locality

