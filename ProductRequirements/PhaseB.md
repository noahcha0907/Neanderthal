# Phase B — The Face (TypeScript Frontend)
### PRD 3 + PRD 4

---

> **Phase B begins when:** The Phase A API is fully functional and tested. Every endpoint in PRD 2.7 returns correct data. The robot generates art from CLI with justification traces.
>
> **Phase B is complete when:** A user can open the website, explore the robot's semantic graph, watch it generate art in real time, interact with parameters, upload their own documents, browse the public portfolio, and manage their session end flow.

---

## PRD 3 — Visualization Layer

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

---

### 3.2 — Idle State & Node Inspection

Before the user presses Play, the graph is fully explorable.

**Requirements:**
- Clicking any node opens an inspection panel: source title, author, type, the original text passage the chunk represents
- Inspection panel does not disrupt graph navigation
- Hovering a node highlights its direct edges and neighbors
- Graph updates in real time if new data is pushed via SSE (e.g. another user's session adds to the corpus)

---

### 3.3 — Play Button & Session Start

**Requirements:**
- Prominent Play button in the UI
- On press: calls `POST /session/start`, begins listening to `/stream` SSE
- Parameter count selector (1–5 toggle) is available before and after pressing Play
- Play becomes a Stop/Pause button once active

---

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

---

### 3.5 — Session Heat Map

During an active session, the graph visually reflects which nodes have been drawn from most.

**Requirements:**
- Nodes that have been activated during the current session glow or change opacity relative to how frequently they've been used
- Heat resets to baseline when a session ends
- Heat map is layered on top of the base graph styling — it does not replace it

---

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

---

### 4.2 — Artwork Detail View

**Requirements:**
- Full-size artwork display
- Full justification report: sources referenced, each decision with its vote breakdown and winning concept
- Which parameter count was used
- Download button (triggers PRD 5.1)
- Source nodes referenced are listed — clicking one navigates to that node in the 3D graph

---

### 4.3 — Private Session Controls

**Requirements:**
- Upload button: opens document upload modal
- Accepted formats displayed clearly
- While in private session, the artwork feed shows only current session artworks (not the public portfolio)
- A clear visual indicator shows the user is in a private session

---

### 4.4 — Session End Modal

Triggered on tab close (`beforeunload`) or manual Stop.

**Requirements:**
- Shows count of artworks generated during session
- Two independent consent toggles (artwork consent and document consent, if applicable)
- Clear explanation of what each consent means in plain language
- If user dismisses without responding, defaults to No for both
