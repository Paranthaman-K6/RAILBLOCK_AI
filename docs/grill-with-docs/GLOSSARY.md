# Glossary — Codebase Design (grill-with-docs)

**Module:** `heavy_calc`, `optimizer_cpp`, `TopLoadingBar` — anything with interface + implementation
**Interface:** `TopLoadingBar` must know `loadingBar.start()`/`done()`/`timeoutMs 8000` + `popstate`/`hashchange`/`visibility`/`click` 5 ends
**Implementation:** `Rust` `rayon` inside `heavy_calc` vs `Python` fallback
**Depth:** `TopLoadingBar` small `height 3px` interface, large `trickle` `click` `timeout` impl
**Seam:** `frontend/src/components/Layout.tsx` where `TopLoadingBar` + `FrontendOverlay` live
**Adapter:** `railblock_rs` vs `optimizer_cpp` vs `fallback`
**Leverage:** One `TopLoadingBar` pays across 22 `curl` + `openchamber` probes
**Locality:** Fix `EMAXCONNSESSION` once in `database.py:290` `3/7`, fixed everywhere
