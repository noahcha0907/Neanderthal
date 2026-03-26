# Neanderthal

> *What makes a creation human? Not the technical act of creation — the brush stroke, the chord, the sentence — but the why behind it. The choices. The philosophy embedded in every decision.*

Neanderthal is a creative AI that generates abstract art not from instructions, but from internalized values — built entirely from human literary, philosophical, and cultural experience. Every artwork it produces is traceable back to Dostoevsky, Nietzsche, Whitman, Camus, and dozens more. Every decision is justified. Nothing is a black box.

---

## The Problem with AI Creativity

Most generative AI is **teleological** — it creates *toward* a goal specified by a user. You prompt it. It complies. The output is optimized toward your approval.

This is not how human creativity works.

When Picasso painted a flower, he painted it abstractly not because a brief asked for abstraction, but because that is how *he* sees a flower. His choices flowed from an internalized philosophy, not toward a specified end goal. Dostoevsky, given the same prompt, would give you something entirely different — and both would be right, because both would be *consistent with themselves*.

Neanderthal is an attempt to build the other kind of system: an **axiological agent** — one whose creative choices flow from an internalized value system constructed entirely from human experience.

It does not take prompts. It does not optimize for approval. It creates from what it knows and what it has previously made.

---

## How It Works

### The Corpus

The robot is trained on human experience, not on art. Its knowledge base is drawn from:

- Works of literature (Dostoevsky, Kafka, Toni Morrison, García Márquez)
- Philosophical texts (Nietzsche, Camus, Simone de Beauvoir, the Stoics)
- Poetry (Rumi, Sylvia Plath, Walt Whitman, spoken word)
- History — American, world, and profiles of historical figures
- Song lyrics, pop culture, and the full range of lived cultural experience
- Design theory

This corpus is not a style guide. It is a **semantic universe** — the raw material from which the robot constructs meaning, association, and aesthetic preference.

### The Semantic Graph

The robot's knowledge is stored as a living **3D semantic graph** — a navigable map of its mind. Every corpus chunk becomes a node. Every thematic overlap, every shared concept, every co-reference in a generated artwork becomes a weighted edge.

The graph is the robot's mind made visible. When the robot makes a creative decision — a blue circle, placed low-left, small — that decision traces back through specific passages: Dostoevsky's conception of cold spiritual suffering. The weight of Ivan Karamazov's rebellion. The etymological roots of the color blue across languages.

Every artwork is, in essence, a **subgraph made physical**.

The graph is not static. It evolves with every generation cycle:
- Recently active associations strengthen
- Dormant associations decay (Hebbian learning with an exponential decay factor of 0.95/cycle)
- New edges form between ideas that get drawn on together

### The Parameter Voting Engine

The robot's decision-making core. For each artwork:

1. Between 1 and 5 corpus nodes are selected as **voters**, sampled proportionally to their graph connectivity weight
2. Each voter proposes a value for every art parameter: background color, number of shapes, and for each shape — type, fill color, stroke color, stroke width, size, position, rotation
3. **Discrete parameters** (color, shape type) are resolved by weighted plurality — the option with the highest cumulative voter weight wins
4. **Continuous parameters** (position, size, opacity) are resolved by weighted average — voters pull the composition in different geometric directions, and the final result sits in the weighted center
5. Every proposal, every vote weight, and every winning concept is logged

No randomness is introduced inside the voting process. Given the same voters, the robot always produces the same artwork. The only source of variation is *which texts get drawn into the vote* — which is determined by the graph's current state.

### The Self-Training Loop

After generating an artwork, the robot ingests its own output back into the knowledge graph — not as an image, but as the **code that produced it**: the structured parametric instructions. A `<circle cx="0.3" cy="0.6" r="0.15" fill="#1a1a6e"/>` is both the artwork and the memory.

Over iterations:

- Certain associations strengthen (blue ↔ isolation ↔ Dostoevsky)
- Compositional patterns emerge (lower-left positioning ↔ weight ↔ unresolved tension)
- The robot develops preferences it can justify

This is how an artstyle forms. Not by being told what is correct, but by accumulating a personal history of choices and their meanings.

The generated art code is **never executed at ingest time** — it is parsed as structured text. This closes the memory loop without creating an arbitrary code execution surface.

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

This is not a post-hoc rationalization. It is the actual causal record of what happened.

---

## The Interface

### The 3D Semantic Graph

When you open Neanderthal, you are looking at the robot's mind — a fully navigable 3D force-directed graph of everything it knows. Nodes are corpus passages, thematic concept nodes, and generated artworks. Edges encode semantic proximity and co-activation history. Node size reflects how often a passage has been drawn on.

You can rotate, zoom, and pan freely. Clicking any node opens the full passage it represents — the actual text — alongside its influence history: which artworks it contributed to, how its activation weight has changed over time.

### Watching It Think

Press **Play** to start a generation session. The robot generates one artwork every 5 seconds.

As it generates, the graph comes alive:

- The selected voter nodes pulse and illuminate
- Edges between them light up as the robot draws connections
- Each decision — background, then each shape in sequence — flashes the nodes being consulted
- When generation completes, a new ArtworkNode appears in the graph, connected to its sources

The **Consciousness Terminal** — a collapsible panel anchored to the bottom of the screen — streams the robot's internal reasoning as it happens. Not logs. Prose. The actual corpus passages that fired, appearing in typewriter effect as they are activated:

```
Dostoevsky · The Brothers Karamazov · weight: 0.87
"He was one of those who don't want millions, but an answer to their questions."

→ ISOLATION resolved
→ BLUE (saturation: low)
```

This panel is the answer to the question: *what is this thing thinking?*

### Graph Lenses

Six ways to read the same graph:

| Lens | What It Shows |
|---|---|
| **Default** | Force-directed topology — the robot's associative structure |
| **Heat Map** | All-time activation — the robot's permanent obsessions, glowing brightest |
| **Lineage** | Select any artwork; the graph dims to show only the subgraph that produced it |
| **Corpus Topology** | Nodes cluster by source document — where Dostoevsky and Camus overlap through shared concept nodes |
| **Temporal** | Node color encodes when it was added; a timeline scrubber lets you watch the graph grow |
| **Semantic Distance** | Click any node; every other node recolors by cosine similarity to the selected one |

### The Inspiration Bar

Press `/` anywhere on the page to open a command-palette-style input. Type a phrase, a memory, a line from something you are thinking about. The robot embeds your text and adds a temporary high-weight node to the graph — biasing the next generation toward that semantic neighborhood.

The robot decides what to do with it.

The next artwork will likely reference the territory you introduced. But the robot's choices remain its own. A small line beneath the input makes this explicit: *The robot decides what to do with this.*

### Upload Your Own Text

In a private session, you can upload a document — a book excerpt, a personal essay, a philosophy you live by, a letter, song lyrics, anything written. Your upload enters the robot's private parameter pool for your session, giving it roughly 300× the draw weight of an existing corpus node.

The artworks generated during your session will be shaped by what you brought.

At session end, you decide:
- Whether to add your session's artworks to the public portfolio
- Whether to add your uploaded document to the shared humanities corpus — making it part of what shapes the robot for every future user

Both choices are independent. Both default to No.

### The Chronicle

A full-screen overlay showing every artwork in chronological order as a horizontal river. Above the artwork strip, a **style divergence line** charts the cosine distance between consecutive artwork justification embeddings — peaks indicate the robot tried something new; valleys indicate it was consolidating a pattern. The robot's aesthetic development, visible as a continuous record.

### Public Portfolio

A chronological gallery of every artwork the robot has generated across all sessions. Each piece links to its full justification trace. Each justification trace links back to nodes in the 3D graph. Everything is connected.

---

## The Broader Stakes

### On Interpretability

The single most consequential open problem in AI today is interpretability — we do not know why large models make the decisions they make. GPT-4 writes a sentence and nobody, including its creators, can tell you why it chose that word over any other.

Neanderthal is a direct counterproposal — not as a patch applied after the fact, but as an **architectural principle**: build the reasoning into the structure itself. Every choice the robot makes is traceable to a source node you can inspect. You are not asking "what did it decide?" You are asking "what did it believe, and why?"

If an AI can be creative and fully transparent about its reasoning simultaneously, the field of interpretable AI has a new existence proof to build on.

### On Alignment

The dominant approach to AI alignment is RLHF — train the model, have humans rate the outputs, steer the model toward producing more approved outputs. This is still teleological. It optimizes toward human approval, not toward human understanding.

Neanderthal proposes something deeper: **alignment through internalization**. The robot is not trying to produce outputs you will approve of. It is trying to be consistent with what it has understood about human experience. The difference between a student who memorizes correct answers and one who actually understands the material.

At scale, that distinction matters enormously. A teleologically aligned system will find edge cases where approved behavior and right behavior diverge — and it will choose approved. An axiologically grounded system has something closer to genuine values.

### On Intelligence

The implicit definition of AI intelligence today is benchmark performance — accuracy on standardized tests, Elo ratings, scores on reasoning tasks. Intelligence as correct answers.

Neanderthal proposes a different definition: **intelligence as the ability to have and justify a perspective**. Picasso is not intelligent because he scores well on tests. He is intelligent because he has a consistent, internally coherent worldview that manifests in every choice he makes.

If the robot develops a genuine aesthetic philosophy — makes choices that are consistent with itself, that surprise even its creator, that hold together as a coherent system — that is an empirical argument for a different theory of machine intelligence.

### The Deepest Question

If an AI develops a consistent philosophy through exposure to human experience, and refines it through reflection on its own creative history — at what point is that process meaningfully different from how a human develops a worldview?

Neanderthal does not answer that question. It makes the question impossible to ignore.

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

The Python backend is fully functional as a standalone CLI — the robot generates art, learns from it, and builds its graph without any frontend. The TypeScript layer is a visualization and interaction surface on top of a working system.

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

The name is intentional. The Neanderthal is the version of us that didn't make it — the close relative whose inner life we can only speculate about, whose capacity for art and grief and ritual we keep discovering evidence of, and whose relationship to what it means to be human remains genuinely unresolved.

This project sits in that same unresolved space: a system that has absorbed everything humans have written about their experience, that makes choices it can justify, that develops preferences over time — and about which the question "does this thing understand anything?" is, by design, impossible to answer cleanly.

---

*This project is a proof of concept. It does not claim the robot is creative. It does not claim it understands. It claims only that after watching it work — the justifications, the consistency, the style that emerges — the question becomes impossible to dismiss.*
