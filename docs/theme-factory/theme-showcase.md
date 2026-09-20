# Design System — Ocean Depths

> **RailBlock AI Design Language — Professional Control-Room Aesthetic**

This document describes the visual identity applied across the product — from the interface to documentation.

---

## 🌊 Ocean Depths — In Use

**Philosophy:** Calm, trustworthy, and focused — inspired by deep ocean navigation systems where clarity and precision are critical.

**Palette:**

| Role | Color | Hex | Application |
|------|-------|-----|-------------|
| Primary | Navy | `#0f2a44` | Sidebar, headers, primary actions |
| Accent | Teal | `#2d8b8b` | Active states, Gantt integrated blocks, highlights |
| Background | Off-white | `#f1faee` | Page background |
| Surface | White | `#ffffff` | Cards, modals |
| Muted | Slate | `#8896a8` | Secondary text, captions |

**Typography:**
- **Display:** `Space Grotesk` / `Sora` — headings, plan IDs
- **Body:** `Inter` — interface text
- **Mono:** `JetBrains Mono` — identifiers (`COR-*`, `PLAN-*`, `BLK-*`, `TSK-*`)

**Applied in:**
- `frontend/src/index.css` `:root` design tokens
- Sidebar rail `linear-gradient(180deg, #2d8b8b → #1a3a5c)` — signature track schematic
- Documentation and presentation materials

---

## 🎨 Palette Explorer — 10 Curated Themes

| # | Theme | Character | Ideal For |
|---|-------|-----------|-----------|
| 1 | **Ocean Depths** | Calming maritime | **RailBlock AI — control-room, trust** |
| 2 | Sunset Boulevard | Warm, vibrant | Energetic launch presentations |
| 3 | Forest Canopy | Grounded, earthy | Sustainability reports |
| 4 | Modern Minimalist | Clean grayscale | Minimal corporate decks |
| 5 | Golden Hour | Rich, autumnal | Warm storytelling |
| 6 | Arctic Frost | Cool, crisp | Winter / tech themes |
| 7 | Desert Rose | Soft, sophisticated | Elegant presentations |
| 8 | Tech Innovation | Bold, modern | Startup pitches |
| 9 | Botanical Garden | Fresh, organic | Natural / garden themes |
| 10 | Midnight Galaxy | Dramatic, cosmic | High-impact visuals |

To explore alternative palettes, review the showcase and apply the corresponding `CSS` variables to `frontend/src/index.css` `:root`.

---

## 📸 In Practice

- **Dashboard:** Navy sidebar `0f2a44`, teal live indicators `2d8b8b`, white cards `ffffff` — high contrast for at-a-glance monitoring
- **Planner:** Teal primary `★ Generate` `#2d8b8b`, amber `Submit` `#ff9800`, blue `Approve` `#1976d2` — clear action hierarchy
- **Gantt:** Integrated blocks highlighted with teal `3px` left border, feasible green `#4caf50`

All screens captured at `1280×720` on live production — see `docs/screenshots/` gallery.

