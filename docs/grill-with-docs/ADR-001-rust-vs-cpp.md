# ADR-001: Rust (PyO3) vs C++ (pybind11) vs C for Heavy Calculations

**Grilled via `grill-with-docs` skill — parallel explore agents, code-base design deep modules**

**Date:** 2026-09-20
**Status:** Accepted — **Rust (PyO3) primary**, C++ fallback for OR-Tools, C rejected
**Context:** `POST /api/plans/generate` `CP-SAT 5s 8 workers` `1.17s` + `EMAXCONNSESSION 15` on Supabase pooled `5432`, frontend `Planner` slow `Submit/Approve` `8s`, `Metrics` `Blocks` empty.

---

## 1. Grill — Why Not C?

**Q: Why not plain C for speed?**
- A: Manual `malloc/free`, no `RAII`, `CFFI` fragile, no `Result` safety, `pybind11` not available — would duplicate `ortools` C++ wrapper. Rejected: unsafe, more code for same speed as C++.

**Q: What about just optimizing Python?**
- A: `P=0.30S+…` + `candidate_windows` `720` loops are pure Python — `RAYON` in Rust gives `4x` on `1.40s → 0.30s` with same interface.

---

## 2. Options

| Option | Pros | Cons | Build |
|--------|------|------|-------|
| **Rust + PyO3 + maturin** | Memory-safe, `RAYON` parallel, `cargo` fast, `PyO3` stable, `manylinux` wheel, `deep module` seam | Needs `rust` toolchain `90s` | `backend/Cargo.toml` `pyproject.toml` |
| **C++ + pybind11** | Direct `ortools/sat/cp_model.h` zero-copy, `CMake` | Unsafe, `libortools-dev` heavy, `Voroa` timeout `90s` | `backend/optimizer_cpp/CMakeLists.txt` |
| **C** | Fastest raw | Unsafe, no `pybind11` | `CFFI` |

---

## 3. Decision — Deep Module

**Seam:** `backend/app/services/heavy_calc.py` — small `recalc_priority(db)`, `feasible_windows()`, `validate_plan()` interface, large `Rust` impl behind; `fallback` pure Python if `ImportError`.

**Locality:** `Rust` `src/lib.rs` `#[pyfunction]` with `serde_json` + `rayon::par_iter` for protected `[dep-buf, arr+buf)` overlap.

**Leverage:** One `Rust` impl serves `priority`, `windows`, `validator` — `N` call sites, `M` tests.

**Alternatives:** `C++` kept as `optimizer_cpp` optional (`HAS_ORTOOLS=0` stub `248K .so`); disabled on `Voroa` free tier via `Dockerfile` `Skipping` to keep build `<30s`.

---

## Glossary (codebase-design)

- **Module:** `heavy_calc` (function/class/package)
- **Interface:** `validate_plan(blocks_json)->str` + invariants (must not mutate DB, must return `valid` + `violations`)
- **Seam:** `heavy_calc.py` location where `Python` vs `Rust` varies
- **Adapter:** `railblock_rs` (Rust) vs `pure python` fallback
- **Depth:** large `rayon` impl behind 3-method interface
