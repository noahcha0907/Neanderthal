# HumanEvolutionAgent — Product Requirements Document

---

## Overview

HumanEvolutionAgent is a creative AI system that generates simple parametric art based entirely on a corpus of human literary, philosophical, cultural, and historical works. Its choices are traceable — every color, shape, and composition decision points back to specific source material. The robot learns from its own output over time, developing an evolving aesthetic that reflects what it has read and what it has previously made.

---

## PRD 1 — Core Engine (Python, no UI)

> Goal: A fully functional AI art engine, runnable from the CLI. No frontend. Every component independently testable. This is the brain of the entire project.

### 1.1 — Corpus Ingestion Pipeline

Build a multi-format parser that reads raw source documents and converts them into clean, chunked text ready for embedding.

**Accepted formats:** PDF, `.txt`, `.md`, plain text. Future formats (HTML, EPUB) are TBD.

**Seeded corpus at launch:**
- 10 works of literature
- 20 poems
- 10 historical profiles (prominent figures)
- 20 song lyrics
- 10 philosophical texts
- 1 American history textbook
- 1 world history textbook
- 1 design theory textbook

**Requirements:**
- Parse each document regardless of format into clean plaintext
- Chunk documents into semantically meaningful units (paragraph-level for prose, stanza-level for poetry, section-level for textbooks)
- Tag each chunk with its source metadata: title, author, type (literary/poem/lyric/philosophy/history/design), date of origin if known
- Store chunks in a structured format ready for embedding
- Ingestion must be idempotent — re-running on the same file does not create duplicate entries
- Pipeline must handle malformed or partially corrupted files without crashing — log and skip

**Test requirements:**
- Unit tests for each format parser
- Verify chunk count, metadata completeness, and deduplication logic

---

### 1.2 — Text Embedding Layer

Convert every corpus chunk into a vector embedding and store it for graph construction and semantic querying.

**Requirements:**
- Use `sentence-transformers` (local, no external API calls)
- Each chunk produces one embedding vector
- Store embeddings alongside their source metadata and original text
- Embeddings must be recomputable from scratch deterministically (same input → same vector)
- Embedding store must support nearest-neighbor queries: given a concept or query vector, return the top-k most semantically similar chunks

**Test requirements:**
- Verify embedding dimensions are consistent across all chunks
- Verify nearest-neighbor queries return semantically coherent results on known inputs (e.g. querying "suffering" returns Dostoevsky before a design textbook)

---

### 1.3 — Semantic Graph Engine

Build the graph that represents the robot's accumulated knowledge. This graph is the robot's mind — it grows as new data is ingested and as the robot creates.

**Node types:**
- `SourceNode` — one node per corpus chunk, labeled with its source metadata
- `ConceptNode` — emergent thematic concepts derived from clustering (e.g. "isolation," "revolution," "beauty") — generated automatically during ingestion
- `ArtworkNode` — one node per generated artwork (added during talent data ingestion, PRD 2.1)

**Edge types:**
- Semantic proximity (weighted by embedding cosine similarity)
- Co-activation (two nodes were both referenced in the same artwork — weight increases each time)
- Source lineage (ArtworkNode → SourceNodes that influenced it)

**Requirements:**
- Built on `NetworkX`
- Edge weights decay over time to prevent early associations from permanently dominating
- Graph must support: node insertion, edge insertion/update, weighted traversal, top-k neighbor queries, subgraph extraction (given a set of seed nodes, return their local neighborhood)
- Graph state must be serializable to disk and reloadable without data loss

**Test requirements:**
- Node insertion and retrieval
- Edge weight update and decay correctness
- Serialization round-trip (save → load → graph is identical)
- Subgraph extraction returns correct neighborhood

---

### 1.4 — Art Parameter System

Define the complete vocabulary of what the robot can create. This is the robot's expressive range.

**Canvas:**
- Fixed dimensions (benchmark-determined — TBD, likely 800×800px)
- Background color: chosen by the robot from the color palette (see below)

**Shapes:**
- `circle`, `square` / `rectangle`, `triangle`, `star`, `line`
- Each shape has:
  - **Fill color** — chosen from palette
  - **Stroke color** — chosen from palette
  - **Stroke width** — variable (thin / medium / thick, mapped to pixel values)
  - **Size** — variable (expressed as a fraction of canvas dimensions)
  - **Position** — (x, y) as fractions of canvas dimensions (0.0–1.0)
  - **Rotation** — for triangle, star, line (0–360 degrees)

**Color palette (primary + secondary only):**
- Red, Blue, Yellow (primaries)
- Orange, Green, Purple (secondaries)
- Black, White (neutrals)

**Composition rules:**
- Minimum 1 shape per artwork, maximum TBD (to be determined by performance benchmarking in PRD 5.2 — start at 20, increase until render time degrades)
- Shapes may overlap
- Number of shapes per piece is decided by the robot

**Requirements:**
- All parameters are represented as structured data (Python dataclasses or equivalent)
- A complete artwork is a fully serializable data structure: canvas + background + list of shapes with all their parameters
- The serialized artwork must be outputtable as SVG with no information loss

**Test requirements:**
- Verify all shape types serialize and deserialize correctly
- Verify SVG output is valid and renderable for all shape types and edge cases (min shapes, max shapes, full overlap)

---

### 1.5 — Parameter Voting Engine

The robot's decision-making core. Given a set of selected source parameters (1–5 corpus chunks), produce a complete set of art parameters through collective semantic voting.

**How it works:**
1. The engine selects N source parameters (1–5 SourceNodes or ConceptNodes from the graph)
2. Each selected parameter casts a "vote" on every art decision: background color, number of shapes, and for each shape — type, fill color, stroke color, stroke width, size, position, rotation
3. Votes are weighted by the parameter's current edge weight in the graph (more connected = more influential)
4. The final decision for each art attribute is the weighted consensus across all N parameters
5. Each decision is logged with its vote breakdown for the justification trace

**Parameter selection (default mode):**
- N is chosen randomly from 1–5
- The N source nodes are selected via weighted random sampling from the graph (nodes with higher co-activation weight are more likely to be chosen — the robot gravitates toward familiar combinations while occasionally sampling new ones)

**Parameter selection (user-directed mode):**
- N is set by the user (1–5 selector in the UI)
- The robot selects which N specific sources to use (user only controls count, not identity)

**Requirements:**
- Voting logic must be deterministic given the same inputs and random seed
- Every vote must be logged: which node voted, what it voted for, what weight it carried
- The engine must handle N=1 (single parameter, no conflict) gracefully
- Must complete a full parameter resolution in under 500ms for up to 5 parameters

**Test requirements:**
- Given seeded inputs, output is deterministic
- Vote logs are complete (every decision has a full vote record)
- Edge cases: N=1, all parameters voting identically, all parameters voting maximally differently

---

### 1.6 — SVG Art Generator

Takes the resolved art parameters from the voting engine and renders them to a valid SVG file.

**Requirements:**
- Input: a fully resolved artwork data structure (from 1.5)
- Output: a valid `.svg` file
- All shape types must render correctly with correct fill, stroke, size, position, rotation
- SVG must be self-contained (no external references)
- Output SVG must be deterministic given the same input parameters

**Test requirements:**
- SVG is valid XML
- All shape types render without error
- Output is pixel-identical given the same input (determinism check)

---

### 1.7 — Justification Trace Generator

Produces a human-readable (and machine-parseable) record of every decision made during artwork generation, traceable to specific source material.

**Output format (per artwork):**

```
Artwork ID: [uuid]
Generated: [timestamp]
Parameters considered: [N]

Sources referenced:
  1. [Title, Author, Type] — weight: [0.0–1.0]
  2. ...

Decisions:
  background_color: Purple
    → voted by: Brothers Karamazov (0.62), Nietzsche (0.38)
    → winning concept: "spiritual weight, unresolved suffering"

  shape_1: circle
    fill: Blue | stroke: Black | width: thin | size: 0.3 | position: (0.2, 0.7)
    → fill voted by: Brothers Karamazov (0.71), Whitman (0.29)
    → concept: "cold isolation, open sky"
    → shape voted by: ...
    → position voted by: ...

  [... one block per shape]
```

**Requirements:**
- Every art decision maps to at least one source node
- Justification is stored as both structured JSON (for machine use) and formatted plaintext (for display and export)
- Justification is stored alongside the SVG as a paired artifact — they are never separated

**Test requirements:**
- Every decision in the SVG has a corresponding entry in the justification
- JSON and plaintext representations are consistent with each other
- No orphaned decisions (decisions with no source trace)

---

## PRD 2 — Feedback Loop & Session Engine

> Goal: The robot learns from what it makes. Sessions are managed. The public data pool grows over time. A FastAPI layer exposes everything to the frontend.

### 2.1 — Talent Data Ingestion Pipeline

Re-ingests the robot's own generated artwork back into the knowledge graph as a new class of data node.

**What gets ingested:**
- The SVG (parsed as structured data — not executed, never eval'd)
- The full justification JSON
- Metadata: timestamp, session ID (anonymous), parameter count, source references

**What it creates in the graph:**
- One `ArtworkNode` per piece
- Edges from `ArtworkNode` → every `SourceNode` referenced in the justification
- Co-activation edge weight updates between all referenced source nodes

**Requirements:**
- Ingestion is append-only — existing nodes are never modified, only edges updated
- SVG is parsed as data, never executed
- A failed ingestion must not corrupt graph state (transactional)

---

### 2.2 — Autonomous Generation Timer

The robot generates artwork on a continuous timer when in active session.

**Requirements:**
- Default interval: one artwork every 5 seconds
- Timer runs only during an active session (started by user pressing Play)
- Each generation cycle: select parameters → vote → generate SVG → generate justification → ingest to talent data → emit to frontend
- Timer interval is configurable in `config/` (do not hardcode)
- If a generation cycle takes longer than the interval, the next cycle begins immediately after the previous completes (no overlapping cycles)

---

### 2.3 — Anonymous Session Management

**Requirements:**
- Each browser tab opening the site creates a new anonymous session with a UUID
- Session state tracks: start time, parameter mode (default or user-directed), parameter count, all artworks generated during session, user uploads (if any)
- Session ends on tab close (frontend signals session end via API call on `beforeunload`)
- Sessions are ephemeral in memory — only the artwork and talent data persist after session end

---

### 2.4 — Private Session Mode

Activated when a user uploads their own text or sets a parameter count.

**Requirements:**
- Private session uses a biased parameter pool: user-uploaded documents are given elevated weight in parameter selection
- The "consider N parameters" setting is respected: uploaded documents count as one or more parameters in the pool
- Private session generation runs on the same 5-second timer
- Artworks generated in private session are held in session state, not immediately added to the public talent pool

---

### 2.5 — Session End Flow & Consent Prompts

When a session ends (tab close, or user-initiated):

**Prompt 1 — Artwork consent:**
> "Your session generated [N] artworks. Allow them to be added to the public portfolio and talent data?"
> [Yes] [No]

**Prompt 2 — Humanities data consent (only if user uploaded documents):**
> "Allow your uploaded documents to be added to the shared humanities corpus? This will influence the robot's knowledge for all users."
> [Yes] [No]

**Requirements:**
- If Yes to artwork: ingest all session artworks into talent data pool and mark as public in portfolio
- If Yes to documents: run uploaded documents through the corpus ingestion pipeline (1.1 → 1.2 → 1.3)
- If No to either: data is discarded, not stored
- Consent is binary — no partial options
- Both prompts are independent of each other

---

### 2.6 — User Document Upload Pipeline

**Accepted formats:** Same as corpus ingestion (PDF, `.txt`, `.md`)

**Requirements:**
- Uploaded documents are validated and sanitized before ingestion (encoding check, size limit TBD, content type check)
- Documents are chunked and embedded using the same pipeline as the humanities corpus (1.1 → 1.2)
- Uploaded chunks are tagged as `user_upload` type in metadata
- Until the user consents at session end, uploaded documents exist only in the session's private parameter pool — they do not touch the shared graph

---

### 2.7 — FastAPI REST Layer

Exposes the entire engine to the TypeScript frontend.

**Endpoints:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/session/start` | Create new anonymous session, return session ID |
| `POST` | `/session/end` | End session, trigger consent flow |
| `GET` | `/graph/state` | Return full graph state (nodes, edges, weights) |
| `GET` | `/graph/node/:id` | Return node detail: source text, metadata, co-activation history |
| `POST` | `/generate` | Trigger one generation cycle manually (for testing) |
| `GET` | `/portfolio` | Return all public artworks, chronological |
| `GET` | `/portfolio/:id` | Return one artwork with its full justification |
| `POST` | `/upload` | Accept user document upload for private session |
| `POST` | `/consent` | Submit consent decisions at session end |
| `GET` | `/stream` | SSE stream: emits graph activation events and new artworks in real time |

**Requirements:**
- `/stream` uses Server-Sent Events (SSE) — this is how the frontend receives live generation events to animate the graph
- All endpoints return structured JSON
- Input validation on all `POST` endpoints
- No endpoint exposes raw file paths or internal system state

---

### 2.8 — Integration Test Suite

**Tests:**
- Full pipeline: corpus ingestion → embedding → graph → parameter voting → SVG → justification → talent data ingestion → graph update
- Session lifecycle: start → generate N artworks → end → consent Yes → verify portfolio and graph updated correctly
- Consent No: verify no data persists after session end with No consent
- Upload pipeline: user uploads document → private session bias verified → consent Yes → document enters shared corpus

---

## PRD 3 — Visualization Layer (TypeScript)

> Goal: The robot's mind, made visible. A 3D navigable semantic graph that the user can explore when idle and watch come alive during generation.

### 3.1 — 3D Graph Base

**Requirements:**
- Built with `Three.js` + `3d-force-graph`
- Renders all graph nodes and edges on load
- Node size reflects co-activation weight (more used = larger node)
- Edge thickness reflects semantic proximity weight
- Node color encodes type: SourceNode (by category — literary/poem/lyric/philosophy/history/design each get a distinct color), ConceptNode (neutral), ArtworkNode (distinct)
- Graph is freely navigable: rotate, zoom, pan
- Loads graph state from `GET /graph/state` on page load

### 3.2 — Idle State & Node Inspection

Before the user presses Play, the graph is fully explorable.

**Requirements:**
- Clicking any node opens an inspection panel: source title, author, type, the original text passage the chunk represents
- Inspection panel does not disrupt graph navigation
- Hovering a node highlights its direct edges and neighbors
- Graph updates in real time if new data is pushed via SSE (e.g. another user's session adds to the corpus)

### 3.3 — Play Button & Session Start

**Requirements:**
- Prominent Play button in the UI
- On press: calls `POST /session/start`, begins listening to `/stream` SSE
- Parameter count selector (1–5 toggle) is available before and after pressing Play
- Play becomes a Stop/Pause button once active

### 3.4 — Live Generation Animation

When the robot is generating an artwork, the graph animates to show its thinking.

**Requirements:**
- On receiving a generation event from SSE:
  1. The N source nodes being considered pulse / light up
  2. The edges between them illuminate
  3. As each art decision is made (background, shape 1, shape 2...), the relevant nodes flash in sequence to indicate they are being "consulted"
  4. When generation is complete, the new ArtworkNode appears in the graph with edges to its source nodes
- Animation must complete within the 5-second generation interval — if generation is fast, animation plays to completion; if generation takes the full 5 seconds, animation is in sync
- Animation is smooth, not jarring — easing functions on all transitions

### 3.5 — Session Heat Map

During an active session, the graph visually reflects which nodes have been drawn from most.

**Requirements:**
- Nodes that have been activated during the current session glow or change opacity relative to how frequently they've been used
- Heat resets to baseline when a session ends
- Heat map is layered on top of the base graph styling — it does not replace it

### 3.6 — Parameter Dial UI

**Requirements:**
- Toggle selector for 1 / 2 / 3 / 4 / 5 parameters
- Default: "Random" (robot chooses)
- Selecting a number updates the session mode via API and takes effect on the next generation cycle
- Current parameter count is always visible in the UI

---

## PRD 4 — Portfolio & User Interaction

> Goal: A complete user-facing experience — exploring the robot's creative history, interacting with private sessions, uploading personal data, and deciding what to share.

### 4.1 — Public Portfolio View

**Requirements:**
- Chronological grid of all public artworks
- Each card shows: the artwork (SVG rendered), date/time generated, parameter count used
- Infinite scroll or pagination (TBD based on performance)
- Clicking a card opens the artwork detail view (4.2)

### 4.2 — Artwork Detail View

**Requirements:**
- Full-size artwork display
- Full justification report: sources referenced, each decision with its vote breakdown and winning concept
- Which parameter count was used
- Download button (triggers PRD 5.1)
- Source nodes referenced are listed — clicking one navigates to that node in the 3D graph

### 4.3 — Private Session Controls

**Requirements:**
- Upload button: opens document upload modal
- Accepted formats displayed clearly
- While in private session, the artwork feed shows only current session artworks (not the public portfolio)
- A clear visual indicator shows the user is in a private session

### 4.4 — Session End Modal

Triggered on tab close (`beforeunload`) or manual Stop.

**Requirements:**
- Shows count of artworks generated during session
- Two independent consent toggles (artwork consent and document consent, if applicable)
- Clear explanation of what each consent means in plain language
- If user dismisses without responding, defaults to No for both

---

## PRD 5 — Export, Benchmarking & Finalization

> Goal: Export is polished, performance is validated, the system is end-to-end tested.

### 5.1 — Combined Artwork + Story Export

**Requirements:**
- Export format: PNG
- Layout: artwork on top, justification report below (formatted, readable)
- Justification in the export includes: sources referenced, each decision with its concept summary (not the full vote breakdown — that level of detail is for the in-app view only)
- Export is generated server-side (Python renders SVG + text to PNG) and returned as a file download
- Filename: `[artwork-id]-[date].png`

### 5.2 — Performance Benchmarking (Max Shapes)

**Requirements:**
- Benchmark SVG generation and browser render time at 10, 20, 30, 40, 50 shapes per artwork
- Identify the shape count at which render time exceeds acceptable threshold (target: full generation + render under 3 seconds)
- Set `MAX_SHAPES` constant in `src/config/` to the benchmarked value
- Document benchmark results in a `BENCHMARKS.md` file

### 5.3 — End-to-End Test Suite

**Requirements:**
- Full user flow: page load → graph loads → Play pressed → artworks generate → session end → consent Yes → portfolio updated
- Upload flow: document upload → private session activates → artworks generated with bias → session end → corpus updated
- Export flow: artwork selected → download triggered → PNG received and valid

### 5.4 — Final Polish

- Loading states for all async operations (graph load, generation, upload)
- Error states for all failure cases (upload fails, generation fails, API unreachable)
- Responsive layout (desktop-first, but not broken on smaller screens)
- Accessibility: keyboard navigation for portfolio and graph inspection panel

---

## Build Order Summary

| PRD | What Gets Built | When It's Done |
|---|---|---|
| **PRD 1** | Core AI engine — corpus, embeddings, graph, art generation, voting, justification | Robot creates art from CLI with full justification trace |
| **PRD 2** | Feedback loop, sessions, API layer | Robot learns from its own output; API is ready for a frontend |
| **PRD 3** | 3D visualization, live animation, parameter dial | The robot's mind is visible and interactive |
| **PRD 4** | Portfolio, user interaction, upload, session flow | Full user experience end-to-end |
| **PRD 5** | Export, benchmarking, E2E tests, polish | Shippable |
