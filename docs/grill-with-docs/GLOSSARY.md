# Glossary — Architecture

**Module:** Encapsulated unit (e.g., `heavy_calc`, `TopLoadingBar`) with a defined interface and implementation.

**Interface:** What callers must know to use a module — methods, invariants, and performance characteristics.

**Implementation:** Internal logic behind the interface.

**Depth:** Large behavior behind a small interface — high leverage for callers, high locality for maintainers.

**Seam:** Location where implementation can vary (e.g., `heavy_calc.py` — Rust vs Python).

**Adapter:** Concrete implementation at a seam (`railblock_rs` vs pure Python).

**Leverage:** Capability gained per unit of interface learned.

**Locality:** Maintenance benefit — changes concentrate in one place.
