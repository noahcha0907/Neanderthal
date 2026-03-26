# Phase C — Ship It (Export, Performance & Polish)
### PRD 5

---

> **Phase C begins when:** Phase B is fully functional end-to-end. A user can complete every flow — session start, generation, interaction, upload, session end — without errors.
>
> **Phase C is complete when:** The system is benchmarked, the export feature is polished, the E2E test suite passes, and the product is shippable.

---

## PRD 5 — Export, Benchmarking & Finalization

### 5.1 — Combined Artwork + Story Export

**Requirements:**
- Export format: PNG
- Layout: artwork on top, justification report below (formatted, readable)
- Justification in the export includes: sources referenced, each decision with its concept summary (not the full vote breakdown — that level of detail is for the in-app view only)
- Export is generated server-side (Python renders SVG + text to PNG) and returned as a file download
- Filename: `[artwork-id]-[date].png`

---

### 5.2 — Performance Benchmarking (Max Shapes)

**Requirements:**
- Benchmark SVG generation and browser render time at 10, 20, 30, 40, 50 shapes per artwork
- Identify the shape count at which render time exceeds acceptable threshold (target: full generation + render under 3 seconds)
- Set `MAX_SHAPES` constant in `src/config/` to the benchmarked value
- Document benchmark results in a `BENCHMARKS.md` file

---

### 5.3 — End-to-End Test Suite

**Requirements:**
- Full user flow: page load → graph loads → Play pressed → artworks generate → session end → consent Yes → portfolio updated
- Upload flow: document upload → private session activates → artworks generated with bias → session end → corpus updated
- Export flow: artwork selected → download triggered → PNG received and valid

---

### 5.4 — Final Polish

- Loading states for all async operations (graph load, generation, upload)
- Error states for all failure cases (upload fails, generation fails, API unreachable)
- Responsive layout (desktop-first, but not broken on smaller screens)
- Accessibility: keyboard navigation for portfolio and graph inspection panel
