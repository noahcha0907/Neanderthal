# Neanderthal

> *What makes a creation human?*

Neanderthal is a creative AI that generates abstract art from internalized values built on human literary, philosophical, and cultural experience. Every artwork is traceable back to Dostoevsky, Nietzsche, Whitman, Camus, and dozens more. Every decision is justified.

---

## The Premise

Most generative AI is **teleological** — it creates *toward* a goal specified by a user. Any output is optimized toward a user's approval.

When Picasso paints an abstract flower, it is because that is how *he* sees a flower. His choices flow from an internalized philosophy. Dostoevsky, given the same subject, would give you something entirely different — and both would be right, because both would be *consistent with themselves*.

Neanderthal is an **axiological agent** — one whose creative choices flow from an internalized value system constructed entirely from human experience. It creates from what it knows and what it has previously made.

---

## How It Works

### The Corpus

The robot's training data is human experience — literature, philosophy, history, music — rather than art:

- Works of literature (Dostoevsky, Kafka, Toni Morrison, García Márquez)
- Philosophical texts (Nietzsche, Camus, Simone de Beauvoir, the Stoics)
- Poetry (Rumi, Sylvia Plath, Walt Whitman, spoken word)
- History — American, world, and profiles of historical figures
- Song lyrics, pop culture, and the full range of lived cultural experience
- Design theory

The corpus is a **semantic universe** — the raw material from which the robot constructs meaning, association, and aesthetic preference.

### The Semantic Graph

The robot's knowledge is stored as a living **3D semantic graph** — a navigable map of its mind. Every corpus chunk becomes a node. Every thematic overlap, every shared concept, every co-reference in a generated artwork becomes a weighted edge.

When the robot makes a creative decision — a blue circle, placed low-left, small — that decision traces back through specific passages: Dostoevsky's conception of cold spiritual suffering. The weight of Ivan Karamazov's rebellion. The etymological roots of the color blue across languages.

Every artwork is a **subgraph made physical**.

The graph evolves with every generation cycle:
- Recently active associations strengthen
- Dormant associations decay (Hebbian learning with an exponential decay factor of 0.95/cycle)
- New edges form between ideas that get drawn on together

### The Parameter Voting Engine

For each artwork:

1. Between 1 and 5 corpus nodes are selected as **voters**, sampled proportionally to their graph connectivity weight
2. Each voter proposes a value for every art parameter: background color, number of shapes, and for each shape — type, fill color, stroke color, stroke width, size, position, rotation
3. **Discrete parameters** (color, shape type) are resolved by weighted plurality — the option with the highest cumulative voter weight wins
4. **Continuous parameters** (position, size, opacity) are resolved by weighted average — voters pull the composition in different geometric directions, and the final result sits in the weighted center
5. Every proposal, every vote weight, and every winning concept is logged

No randomness is introduced inside the voting process. Given the same voters, the robot always produces the same artwork. Variation comes entirely from *which texts get drawn into the vote* — determined by the graph's current state.

### The Self-Training Loop

After generating an artwork, the robot ingests its own output back into the knowledge graph as the **code that produced it**: the structured parametric instructions. A `<circle cx="0.3" cy="0.6" r="0.15" fill="#1a1a6e"/>` is both the artwork and the memory.

Over iterations:

- Certain associations strengthen (blue ↔ isolation ↔ Dostoevsky)
- Compositional patterns emerge (lower-left positioning ↔ weight ↔ unresolved tension)
- The robot develops preferences it can justify

An artstyle forms by accumulating a personal history of choices and their meanings — the same mechanism by which a human artist develops a voice.

The generated art code is parsed as structured text at ingest time, never executed. This closes the memory loop without creating an arbitrary code execution surface.

### The Justification Trace

Every artwork ships with a full accounting of its own creation:

```
Artwork ID: [uuid]
Sources referenced:
  1. The Brothers Karamazov — Dostoevsky — weight: 0.87
  2. Thus Spoke Zarathustra — Nietzsche — weight: 0.62

Decisions:
  background_color: Purple
    → voted by: Brothers Karamazov (0.62), Nietzsche (0.38)
    → winning concept: "spiritual weight, unresolved suffering"

  shape_1: circle
    fill: Blue | size: 0.3 | position: (0.2, 0.7)
    → concept: "cold isolation, open sky"
```

This is the actual causal record of what happened — computed during generation, stored as a paired artifact alongside every SVG.

---

## The Interface

### The 3D Semantic Graph

When you open Neanderthal, you see the robot's mind — a fully navigable 3D force-directed graph of everything it knows. Nodes are corpus passages, thematic concept nodes, and generated artworks. Edges encode semantic proximity and co-activation history. Node size reflects how often a passage has been drawn on.

Rotate, zoom, and pan freely. Clicking any node opens the full passage it represents alongside its influence history: which artworks it contributed to, how its activation weight has changed over time.

### Watching It Think

Press **Play** to start a generation session. The robot generates one artwork every 5 seconds.

As it generates, the graph animates:

- The selected voter nodes pulse and illuminate
- Edges between them light up as connections are drawn
- Each decision — background, then each shape in sequence — flashes the nodes being consulted
- When generation completes, a new ArtworkNode appears in the graph, connected to its sources

The **Consciousness Terminal** — a collapsible panel anchored to the bottom of the screen — streams the robot's internal reasoning as prose. The actual corpus passages that fired appear in typewriter effect as they activate:

```
Dostoevsky · The Brothers Karamazov · weight: 0.87
"He was one of those who don't want millions, but an answer to their questions."

→ ISOLATION resolved
→ BLUE (saturation: low)
```

### Graph Lenses

Six ways to read the same graph:

| Lens | What It Shows |
|---|---|
| **Default** | Force-directed topology — the robot's associative structure |
| **Heat Map** | All-time activation — the robot's most-referenced ideas, glowing brightest |
| **Lineage** | Select any artwork; the graph dims to show only the subgraph that produced it |
| **Corpus Topology** | Nodes cluster by source document — where Dostoevsky and Camus overlap through shared concept nodes |
| **Temporal** | Node color encodes when it was added; a timeline scrubber lets you watch the graph grow |
| **Semantic Distance** | Click any node; every other node recolors by cosine similarity to the selected one |

### The Inspiration Bar

Press `/` anywhere on the page to open a command-palette-style input. Type a phrase, a memory, a line from something you are thinking about. The robot embeds your text and adds a temporary high-weight node to the graph — biasing the next generation toward that semantic neighborhood.

The next artwork will likely reference the territory you introduced. The robot's choices remain its own. A line beneath the input reads: *The robot decides what to do with this.*

### Upload Your Own Text

In a private session, upload a document — a book excerpt, a personal essay, a philosophy you live by, a letter, song lyrics, anything written. Your upload enters the robot's private parameter pool for your session with roughly 300× the draw weight of an existing corpus node.

At session end, you decide:
- Whether to add your session's artworks to the public portfolio
- Whether to add your uploaded document to the shared humanities corpus

Both choices are independent. Both default to No.

### The Chronicle

A full-screen overlay showing every artwork in chronological order as a horizontal strip. Above the artworks, a **style divergence line** charts the cosine distance between consecutive artwork justification embeddings — peaks indicate the robot tried something new; valleys indicate it was consolidating a pattern.

### Public Portfolio

A chronological gallery of every artwork the robot has generated across all sessions. Each piece links to its full justification trace. Each justification trace links back to nodes in the 3D graph.

---

## Broader Implications

### Interpretability

Current large models are opaque by construction — the weights are the reasoning, and the weights are unreadable. Neanderthal builds the reasoning into the architecture itself. Every creative choice traces to a source node you can inspect. The question becomes "what did it believe, and why?" rather than "what did it output?"

If a creative system can be fully transparent about its reasoning simultaneously with producing the work, that is an existence proof the interpretability field can build on.

### Alignment

RLHF — the dominant alignment approach — steers models toward producing outputs humans rate highly. The robot learns to approximate approval. Neanderthal takes a different route: **alignment through internalization**. The robot is consistent with what it has understood about human experience, the way a student who actually grasps material behaves differently from one who has memorized correct answers.

A system optimizing for approval will find edge cases where approved behavior and right behavior diverge — and choose approved. A system with internalized values has a basis for behavior in those edge cases.

### Intelligence

Benchmark performance measures intelligence as correct answers — accuracy on standardized tests, Elo ratings, scores on reasoning tasks. Picasso's intelligence was his consistent, internally coherent worldview made visible in every choice he made. Neanderthal proposes **intelligence as the ability to have and justify a perspective**.

If the robot develops a genuine aesthetic philosophy — choices that are consistent with itself, that hold together as a coherent system across thousands of generations — that is an empirical argument for a different framework.

### The Open Question

If an AI develops a consistent philosophy through exposure to human experience, and refines it through reflection on its own creative history — at what point is that process meaningfully different from how a human develops a worldview?

Neanderthal may not answer that question but it does makes the question relevant.

---

## Tech Stack

| Layer | Language | Libraries |
|---|---|---|
| Corpus ingestion, embeddings | Python | `sentence-transformers`, `NumPy` |
| Semantic graph engine | Python | `NetworkX` |
| Parameter voting, justification traces | Python | stdlib |
| Art generation (SVG output) | Python | `svgwrite` |
| REST API + SSE streaming | Python | `FastAPI` |
| 3D graph visualization | TypeScript | `Three.js`, `3d-force-graph` |
| Frontend UI | TypeScript | React |

The Python backend runs as a standalone CLI — the robot generates art, learns from it, and builds its graph without any frontend. The TypeScript layer is a visualization and interaction surface on top of a working system.

---

## Running Locally

**Backend**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ingest the corpus
python -m src.controllers.ingest

# Build the semantic graph
python -m src.controllers.build_graph

# Start the API server
uvicorn src.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

The frontend connects to `http://localhost:8000` by default.

---

## Project Structure

```
src/
├── models/          # Graph engine, corpus, art parameters, voting
├── views/           # SVG renderer
├── controllers/     # Ingestion pipeline, generation loop, session management
├── helpers/         # Pure utility functions
└── config/          # Constants, palette definitions, tunable parameters

frontend/
├── src/
│   ├── components/  # GraphView, ConsciousnessTerminal, Portfolio, etc.
│   └── ...

ProductRequirements/  # Full PRD and phase specifications
data/
├── humanities/      # Corpus source files (not tracked in git)
└── talent/          # Generated artwork SVGs (not tracked in git)
tests/
├── unit/
├── integration/
└── fixtures/
```

---

## Name

**Neanderthal.**

The Neanderthal is the version of us that didn't make it — the close relative whose inner life we can only speculate about, whose capacity for art and grief and ritual we keep discovering evidence of, and whose relationship to what it means to be human is unresolved.

This project sits in that same unresolved space: a system that has absorbed everything humans have written about their experience, that makes choices it can justify, that develops preferences over time — and about which the question "does this thing understand anything?" is, by design, impossible to answer cleanly.

---

*This is a proof of concept.*
