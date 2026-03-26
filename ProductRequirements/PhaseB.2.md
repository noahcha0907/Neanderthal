# Phase B.2 — The Mind Made Legible (Depth, Narrative, Exploration)

---

> **Phase B.2 begins when:** Phase B is fully complete and stable. The core session loop (play, generate, consent, portfolio) works end-to-end.
>
> **Phase B.2 is complete when:** A user can watch the robot think in real time through the Consciousness Terminal, explore the graph through multiple semantic lenses, feel the atmosphere of the interface shift as the robot generates, dive deep into any node's intellectual history, and understand the project's philosophical premise without reading documentation. The interface tells the story.

---

## Feature 1 — The Consciousness Terminal

> The robot's thinking, made legible. The most philosophically important surface in the product.

### B2.1 — Terminal Panel (Frontend)

**What it is:** A collapsible drawer anchored to the bottom of the screen that streams the robot's internal reasoning as it generates — not as raw logs, but as literary prose. Corpus passages appear verbatim as they fire. The user watches the robot read, associate, and decide in real time.

**Requirements:**
- Drag handle at the top of the panel; snaps to 30% / 60% / full-height on release
- Dark background, monospace font, subtle phosphor-glow aesthetic (not a generic terminal — this is a reading surface)
- Text streams in two modes:
  - **Corpus passages** — typewriter effect at ~40 chars/sec, left-justified as flowing prose
  - **Structural tokens** — appear instantly, right-aligned or dimmed: `→ ISOLATION resolved`, `→ BLUE (saturation: low)`
- Each passage is prefaced by a faint source attribution: `Dostoevsky · The Brothers Karamazov · weight: 0.87`
- As each passage streams, the corresponding graph node pulses once — terminal and graph are synchronized
- A faint scanline overlay on the terminal background (CSS `repeating-linear-gradient`, very subtle)
- When idle (no generation), the terminal shows the last generation's trace in a dimmed state with a `— last generation —` header
- A small `◎ clear` button in the top-right corner of the panel resets the terminal to blank

**Design note:** This panel is not a utility. It is the answer to "what is this thing thinking?" The aesthetic should feel like reading someone's journal mid-thought.

---

### B2.2 — Terminal SSE Events (Backend)

**New SSE event types to emit during generation:**

| Event type | Payload | When fired |
|---|---|---|
| `thinking_passage` | `{ node_id, source_title, author, passage, weight }` | Each time a corpus node is consulted |
| `concept_activated` | `{ label, activation_weight, connected_to[] }` | When a concept node resolves |
| `parameter_decided` | `{ parameter, value, reason, source_node_ids[] }` | When each art parameter is finalized |
| `generation_reasoning` | `{ step, description }` | Narrative summary steps between major decisions |

**Requirements:**
- Events must fire in the order reasoning occurs — not batched at the end
- Each `thinking_passage` event includes the verbatim text excerpt (not the full document — the chunk that was actually activated)
- `parameter_decided` events include a plain-language `reason` field: `"low-saturation blue clusters with isolation across 7 source nodes"` — this is computed by the justification trace logic already in place, just emitted mid-generation rather than only at the end
- No new data is computed for these events — they surface reasoning steps that are already occurring internally but not currently transmitted

---

## Feature 2 — Graph Lens System

> The same graph, six ways of seeing it. Each lens reveals a different dimension of the robot's mind.

### B2.3 — Lens Toolbar (Frontend)

**Requirements:**
- A minimal floating toolbar anchored to the top-left of the graph viewport
- Six icon-only buttons; active lens has an inset highlight
- A faint breadcrumb below the toolbar shows the active lens name: `Viewing: Corpus Topology`
- Lens transitions animate — nodes smoothly recolor/reposition over 400ms rather than snapping
- The toolbar is glass-styled, consistent with the rest of the design language

---

### B2.4 — Lens A: Default (existing)

Current force-directed view. No changes required. This is the baseline lens.

---

### B2.5 — Lens B: Heat Map (All-Time)

**What it shows:** Nodes scaled and colored by total activation count across all sessions ever — the robot's permanent obsession map. Its most-referenced ideas glow brightest.

**Requirements:**
- Backend: a `/graph/heat/global` endpoint that returns `{ node_id: total_activation_count }` for all nodes
- Frontend: applies the existing `heatScaleMult` and `heatColor` functions using global heat rather than session heat
- Nodes never activated appear at minimum size and near-zero opacity (5%)
- Color gradient: white (cold, never activated) → amber (warm, frequently activated) → deep orange (hottest, most activated)
- On hover, a node shows its total activation count in the inspection panel

---

### B2.6 — Lens C: Lineage View

**What it shows:** Select any artwork from the portfolio, and the graph dims to show only the subgraph that contributed to that specific artwork. Every edge traversed during that generation lights up in the artwork's accent color. The rest fades to near-invisible.

**Requirements:**
- A small portfolio thumbnail strip appears in a floating overlay when this lens is active — clicking an artwork activates its lineage
- Non-participating nodes drop to 3% opacity; non-participating edges drop to 2% opacity
- Participating nodes and edges render at full intensity with a subtle glow
- Backend: the generation pipeline must store which edges were traversed (not just voter node IDs) — a new `traversed_edge_ids[]` field on the artwork record
- Transitioning between artworks in lineage view cross-fades (400ms) rather than jumping

---

### B2.7 — Lens D: Corpus Topology

**What it shows:** Nodes group visually by source document. Each source document becomes a loose cluster island. Edges between clusters show cross-contamination — where Dostoevsky and Camus connect through shared concept nodes.

**Requirements:**
- `3d-force-graph` cluster force applied: nodes with the same `source_id` are pulled together
- Each cluster has a faint label at its centroid (the document title, low opacity, monospace)
- Cluster membership shown by node color — each source document gets a unique color from a fixed palette
- Concept nodes (no source affiliation) float between clusters, drawn to their most-activated source cluster by edge weight
- User uploads appear as their own distinct cluster, visually differentiated (e.g., dashed border around the cluster)

---

### B2.8 — Lens E: Temporal

**What it shows:** Node color encodes when it was added to the graph. Oldest nodes are deep indigo. Newest nodes are near-white. The robot's intellectual development visible as a color gradient in 3D space.

**Requirements:**
- Color scale: `#1a1a6e` (oldest) → `#e2e8f0` (newest), interpolated linearly by `created_at` timestamp
- Node size unchanged (still reflects activation weight)
- A timeline scrubber appears at the bottom of the graph viewport — dragging it filters the graph to show only nodes that existed at or before that point in time
- Scrubbing the timeline shows the graph "growing" — nodes appear/disappear as the scrubber passes their creation timestamp
- The portfolio panel, if open, also syncs to the scrubber — only artworks generated before the scrubber position are shown

---

### B2.9 — Lens F: Semantic Distance (Node-Centric)

**What it shows:** Click any node. Every other node recolors by cosine similarity to the selected one. Most semantically similar nodes are brightest; dissimilar nodes fade out.

**Requirements:**
- Backend: `/node/{id}/similarity` endpoint returning `{ node_id: similarity_score }` for all nodes (computed from stored embeddings)
- Frontend: on node click in this lens, fetch similarity scores and apply as a color scale: `rgba(99,102,241,0.9)` (most similar) → `rgba(255,255,255,0.05)` (least similar)
- Selected node renders with a distinct ring indicator
- Clicking a different node transitions to its similarity map (400ms cross-fade)
- The inspection panel in this lens shows the top 8 semantic neighbors by name and score

---

## Feature 3 — The Atmosphere Layer

> The environment itself as a storytelling device. Ambient behaviors the user never consciously notices but always feels.

### B2.10 — Graph Breathing (Idle Ambient)

**Requirements:**
- When session is idle, all graph nodes perform a very slow synchronized scale pulse — period ~4s, amplitude ±5%
- Implemented as a continuous RAF loop in `GraphView` that applies a `sin(time / 4000 * 2π)` multiplier to all sprite scales on top of their base size
- When session goes active, the breathing quickens (period drops to ~1.5s) and desynchronizes — each node gets a random phase offset so they pulse individually rather than as one mass
- When session ends, breathing gradually re-synchronizes and slows back to 4s (ease over ~3s)

---

### B2.11 — Generation Atmosphere (Background Shift)

**Requirements:**
- During an active generation (between `generation_started` and `artwork_complete` SSE events), the page background color transitions from `#1a1a1a` to `#1a1a2e` (barely perceptible dark indigo)
- The transition is a 400ms ease-in on start, 800ms ease-out on completion
- Implemented as a CSS transition on a background element behind the graph, driven by `session.state.isGenerating` state
- The shift is intentionally below the threshold of conscious notice — it should feel like a change in atmosphere, not a UI event

---

### B2.12 — Corpus Fog (Background Text Fragments)

**Requirements:**
- In idle state, faint text fragments from the corpus drift slowly across the background behind the graph
- Opacity: 3–4% (completely illegible unless you know what you're looking at)
- Content: actual excerpts from the most recently activated corpus nodes, fetched from `/corpus/recent-fragments`
- Between 8–12 fragments visible at any time; each drifts on a random vector, very slowly (30–60s to cross the screen), fading in and out at the edges
- Implemented as a `BackgroundFog` component with absolutely-positioned `<div>`s, each animated with a CSS `@keyframes` drift
- Fragments do not appear during active generation — they pause and fade when the session is active, return when idle
- The component does not re-render on every frame — drift is CSS animation, not JS-driven

---

### B2.13 — Edge Hover Ripple

**Requirements:**
- When hovering a node in the graph, its direct edges increase in opacity from their base value to 70% over 150ms
- A ripple animation propagates outward along those edges — a bright point travels from the hovered node toward each neighbor over 600ms
- Implemented as a per-edge `linkDirectionalParticles` value that is temporarily set to 3 for connected edges on hover, then reset to 0 on hover-out
- The ripple uses the existing `3d-force-graph` directional particle system — no new animation loop required

---

## Feature 4 — Node Deep Dive Panel

> A node is not a data point. It is a character in the robot's intellectual history.

### B2.14 — Enriched Node Inspection (Frontend)

**Requirements:**
- Replaces the current `InspectionPanel` with an expanded version containing tabbed sections:

**Tab 1 — The Text**
- Full corpus passage(s) associated with this node, rendered as flowing prose
- Source metadata: title, author, document type, date added to corpus
- Subtle paper-texture background (very faint `rgba(255,255,255,0.02)` with a slight grain filter) to distinguish it from the rest of the glass UI

**Tab 2 — Connections**
- A small embedded force-directed sub-graph (~20 nodes) showing this node and its strongest neighbors
- Uses the same `3d-force-graph` library in a constrained container (300×300px)
- Edges labeled with their weight on hover
- Clicking a node in the sub-graph navigates the main graph to that node

**Tab 3 — Influence**
- Horizontal scrollable strip of all artworks this node contributed to
- Each card shows the artwork thumbnail and this node's activation weight for that generation
- Sorted by activation weight descending (most influential first)

**Tab 4 — History**
- A sparkline chart showing activation frequency over time (x: time, y: activation count per generation cycle)
- Peaks in the sparkline are labeled with a small dot; hovering the dot shows the artwork generated at that peak
- Total activation count shown prominently: `consulted 47 times`

**Requirements (general):**
- Panel slides in from the right, 380px wide, does not disrupt graph navigation
- Tab switching is instant (no animation needed — content is already loaded)
- Backend: `/node/{id}/detail` endpoint returning passages, artwork influences, neighbor strengths, and activation history

---

## Feature 5 — The Inspiration Bar

> A conversation starter, not a command. Philosophically consistent with the robot's autonomy.

### B2.15 — Inspiration Input (Frontend)

**What it is:** A command-palette-style input (VSCode aesthetic) that injects a user's phrase or text as a temporary high-weight node. The robot's next generation is biased toward that semantic neighborhood — not directed by it. The justification trace will likely reference it, but the robot's choices remain its own.

**Requirements:**
- Activated by pressing `/` anywhere on the page, or a small `+` icon near the bottom bar
- Renders as a centered frosted-glass modal, ~480px wide
- Placeholder text: `what are you thinking about?`
- Accepts free text (up to ~500 characters) or a file paste
- On submit:
  - POST to `/inspire` — the backend embeds the text and adds a temporary high-weight node
  - The new node appears in the graph with a distinct visual: hexagonal shape (vs. the default triangle), faintly iridescent border, `temp` badge
  - A brief pulse animation when the node materializes
  - The input closes
- The temporary node has a TTL of 1 generation; after the next artwork is generated it fades (unless the user pins it via a `⊕ keep` toggle in the inspection panel)
- A faint history strip below the input shows recent inspirations as dismissable pills

**Philosophical note in UI:** A small line of text beneath the input reads: `The robot decides what to do with this.` This is not flavor copy — it is a necessary clarification that prevents user expectation mismatch.

---

### B2.16 — Inspire Endpoint (Backend)

**Requirements:**
- `POST /inspire` accepts `{ text: string }`
- Embeds the text using the same sentence-transformer model used for corpus nodes
- Inserts a `TemporaryNode` into the graph with:
  - `node_type: "inspiration"`
  - `weight: 2.5` (high enough to likely be consulted in the next generation)
  - `ttl: 1` (decremented to 0 after one generation cycle, then removed)
  - `created_by: "user"`
- Returns `{ node_id, embedding_preview }` where `embedding_preview` is the top 3 semantic neighbors already in the graph — shown in the frontend as a preview: `this connects most strongly to: isolation, weight, Petersburg`
- The existing generation pipeline consults this node like any other high-weight node

---

## Feature 6 — The Chronicle (Style Evolution Timeline)

> The robot's artistic development, visible as a river of time.

### B2.17 — Chronicle View (Frontend)

**What it is:** A full-screen overlay showing every artwork in chronological order as a horizontal river. The user can see the robot's style developing — early artworks raw and symmetric, later ones showing bias, repetition, and preference.

**Requirements:**
- Activated from the portfolio button or a dedicated `Chronicle` button in the lens toolbar
- Artworks rendered as small cards (~120px wide) in a horizontal scrollable strip, left = oldest, right = newest
- Above the strip: a **style divergence line** — a continuous line chart where y-axis is the cosine distance between consecutive artwork justification embeddings. Peaks = the robot tried something new. Valleys = consolidating a pattern.
- The line is labeled at significant peaks: `high divergence — new source node added`
- Clicking any artwork opens the Artwork Detail View (existing PRD 4.2)
- A scrubber below the strip, when dragged, also scrubs the 3D graph to show its state at that moment in time (syncs with Lens E: Temporal)

**Backend requirements:**
- `/portfolio/chronicle` endpoint returning artworks with `style_divergence_score` computed as cosine distance between each artwork's justification embedding and the previous one
- `/graph/at-time/{timestamp}` endpoint returning graph state (nodes and edges that existed at or before that timestamp)

---

## Feature 7 — The Manifesto Panel (Onboarding)

> The project's philosophical premise, delivered as an experience, not a readme.

### B2.18 — Manifesto Overlay (Frontend)

**Requirements:**
- On first visit (`localStorage` check for `manifesto-seen` key), renders a full-screen overlay before the graph is visible
- Pure black background with a very slow particle field (40–60 tiny white dots at ~2% opacity, drifting)
- The following text renders word-by-word, each word fading in with an 80ms stagger:

  > *What makes a creation human? Not the technical act of creation — the brush stroke, the chord, the sentence — but the why behind it. The choices. The philosophy embedded in every decision.*
  >
  > *This is a robot trained only on human experience. It has no goals. It has a perspective.*

- After the text finishes, a single button fades in: `Watch it think.`
- Pressing the button sets `localStorage.manifesto-seen = true` and transitions to the main graph view (fade-out of overlay, fade-in of graph over 600ms)
- Always re-accessible via a small `◎` icon in the bottom-left corner of the main UI — re-opens the overlay in a lower-stakes way (shorter version, skip button available immediately)
- The overlay is not a tutorial, not an onboarding checklist, not interactive. It is a statement of intent.

---

## Implementation Priority

| Priority | Feature | Rationale |
|---|---|---|
| 1 | **B2.1–B2.2** — Consciousness Terminal | Highest philosophical payoff; directly demonstrates the interpretability thesis; backend SSE infrastructure already partially in place |
| 2 | **B2.10–B2.13** — Atmosphere Layer | Low implementation cost; transformative effect on how the product *feels*; no new backend required |
| 3 | **B2.5, B2.7** — Heat Map + Corpus Topology lenses | Closest to already working; Heat Map extends existing session heat infrastructure; both make the robot's biases legible |
| 4 | **B2.14** — Node Deep Dive Panel | Enriches the most natural exploratory behavior (clicking nodes); one new API endpoint |
| 5 | **B2.18** — Manifesto Panel | Essential for demo and presentation contexts; purely frontend |
| 6 | **B2.6** — Lineage Lens | Requires backend change (storing traversed edge IDs); high narrative impact |
| 7 | **B2.15–B2.16** — Inspiration Bar | Philosophically nuanced; needs careful backend design to preserve robot autonomy |
| 8 | **B2.17** — The Chronicle | Most technically complex; requires historical graph state storage and style divergence computation |
