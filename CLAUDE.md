# CLAUDE.md — HumanEvolutionAgent Development Standards

This file governs all code written for this project. These are non-negotiable design constraints, not preferences.

---

## Architecture

### MVC Pattern
All code must follow a strict Model-View-Controller separation:

- **Model** — data structures, graph state, corpus management, art parameter logic. No rendering, no request handling.
- **View** — visualization layer (3D graph, canvas output, UI). No business logic, no direct data access.
- **Controller** — orchestrates between model and view, handles user input, manages the ingestion/generation pipeline.

No layer should reach across another. A View never touches the graph directly. A Model never knows it's being rendered.

### File Structure
```
HumanEvolutionAgent/
├── src/
│   ├── models/          # Data models, graph engine, corpus, art parameters
│   ├── views/           # Rendering, visualization, canvas output
│   ├── controllers/     # Pipeline orchestration, user input, ingestion flow
│   ├── helpers/         # Pure utility functions — no side effects, no state
│   └── config/          # Constants, environment config, palette definitions
├── data/
│   ├── humanities/      # Source corpus files
│   └── talent/          # Robot-generated art code + justification logs
├── tests/
│   ├── unit/            # Per-module unit tests
│   ├── integration/     # Cross-layer pipeline tests
│   └── fixtures/        # Shared test data, mock corpora, sample art code
└── CLAUDE.md
```

---

## Code Quality

### Performance
- Profile before optimizing — do not guess at bottlenecks.
- Graph operations (node insertion, edge weighting, traversal) are the hot path. These must be efficient. Use appropriate data structures (adjacency lists, priority queues) rather than brute-force lookups.
- Semantic queries against the corpus should be indexed, not scanned linearly.
- The justification trace must not block the generation pipeline — compute it asynchronously where possible.

### Verbosity
- No redundant code. If logic appears twice, it belongs in a helper.
- No commented-out code in commits. Delete it.
- No dead imports, unused variables, or unreachable branches.
- Functions should do one thing. If a function needs a comment to explain what it does, it probably needs to be broken into smaller functions with better names.

### Commenting
Comments explain **why**, not what. The code explains what.

```python
# BAD: Increment the counter
counter += 1

# GOOD: Decay edge weight on each generation cycle to prevent early associations
# from dominating indefinitely as the corpus grows
edge_weight *= DECAY_FACTOR
```

Every module should have a header docstring explaining its role in the system, its inputs, and its outputs. Every public function should have a docstring. Private helpers do not require docstrings if the function name is self-explanatory.

### Helpers
- All helper functions must be **pure** — no side effects, no shared state, deterministic output.
- Helpers live in `src/helpers/` and are organized by domain (e.g., `graph_utils.py`, `color_utils.py`, `text_utils.py`).
- A helper that requires access to application state is not a helper — it is a method on a class.

---

## Security

Security is the highest priority constraint. This project ingests user-uploaded text and stores it as corpus data. That surface must be treated with the same rigor as any user-facing input pipeline.

### Input Validation
- All user-uploaded text must be validated and sanitized before it enters the corpus. Validate encoding, length, and content type.
- Never execute, eval, or dynamically interpret user-supplied content.
- Corpus ingestion must be sandboxed — a malformed or malicious upload must not be able to corrupt the graph state or the talent data store.

### Art Code (Talent Data)
- The code that the robot generates and ingests as talent data is **code**. It must never be dynamically executed via eval or exec at ingestion time.
- Treat generated art code as a structured data format, not executable script. Parse it as data; execute it only in a controlled, isolated rendering context.

### Data Storage
- User uploads are corpus data — they must not be stored with identifying metadata unless the user explicitly opts in.
- No secrets, API keys, or credentials in source code. Use environment variables via `config/`.
- Log the minimum necessary. Do not log raw user input.

### Dependencies
- Minimize third-party dependencies. Every dependency is an attack surface.
- Pin dependency versions. Do not use floating version ranges in production.
- Audit new dependencies before adding them.

---

## Testing

### Suite Architecture
Tests are organized in three tiers:

| Tier | Location | Scope | Runs on |
|---|---|---|---|
| Unit | `tests/unit/` | Single function or class in isolation | Every commit |
| Integration | `tests/integration/` | Cross-layer pipelines (ingestion → graph → generation) | Every PR |
| End-to-end | `tests/e2e/` | Full user-facing flows | Pre-release |

### Rules
- Every public function in `models/` and `helpers/` must have unit test coverage.
- Tests must be deterministic. If a function uses randomness, seed it in tests.
- No test should depend on another test's side effects. Each test sets up and tears down its own state.
- Use fixtures in `tests/fixtures/` for shared mock data — do not duplicate test setup across files.
- A test that only asserts that code runs without throwing is not a test. Assert on outputs.

### What to Test Specifically
- Graph operations: node insertion, edge weight updates, decay, traversal correctness
- Justification traces: verify that a generated art piece's trace points to real nodes in the graph
- Ingestion pipeline: that user uploads are sanitized, parsed, and correctly integrated as graph nodes
- Art code round-trip: that generated art code can be re-ingested as talent data without corruption or data loss

---

## Conventions

### Language Stack

This project uses **Python** (backend) and **TypeScript** (frontend). The split is by concern — do not blur it.

| Layer | Language | Key Libraries |
|---|---|---|
| Semantic graph engine, corpus ingestion, embedding | Python | `sentence-transformers`, `NetworkX`, `NumPy` |
| Justification trace generation, talent data pipeline | Python | stdlib + custom |
| Art generation (SVG output) | Python | `svgwrite` or stdlib XML |
| REST API | Python | `FastAPI` |
| 3D semantic graph visualization | TypeScript | `Three.js`, `3d-force-graph` |
| Frontend UI (uploads, gallery, download) | TypeScript | `React` or `Svelte` |

**Why Python for the AI core:**
Every serious ML research lab (DeepMind, OpenAI, Anthropic, Meta AI, Hugging Face) uses Python as their primary model language. The ecosystem — `sentence-transformers` for text embedding, `NetworkX` for graph operations, `NumPy`/`PyTorch` for vector math — is unmatched in any other language. Research reproducibility, academic implementations, and community support all converge on Python.

**Why TypeScript for the frontend:**
The 3D navigable semantic graph (the robot's mind made visible) is a browser-native concern. `Three.js` and `3d-force-graph` are the standard tools for this class of visualization — this is precisely how projects like [LRLVTP](https://bianjie.systems/lrlvtp) are built. The browser Canvas API handles art rendering natively. TypeScript adds the type safety necessary for a non-trivial interactive UI.

**Why SVG for art output:**
SVG is structured XML text. Python generates it without additional tooling. The browser renders it natively. Critically, when generated art is re-ingested as talent data, it enters the system as a text file — the `<circle cx="0.3" cy="0.6" r="0.15" fill="#1a1a6e"/>` is the code. This closes the feedback loop without requiring computer vision or image parsing. The robot's memory of its own work is already structured, queryable, and semantically annotatable.

**Build order:** Implement the Python backend first — graph engine, corpus ingestion, art generation, justification tracing — fully testable via CLI before the frontend exists. Add TypeScript only once the core is solid.

- **Naming:** Descriptive, unambiguous names. No abbreviations except universally understood ones (`id`, `url`, `min`, `max`). No single-letter variables outside of tight mathematical loops.
- **Constants:** All magic numbers and strings live in `src/config/`. Nothing hardcoded in business logic.
- **Error handling:** Fail explicitly and early. Never swallow exceptions silently. Errors from the ingestion pipeline and graph engine must surface with enough context to be debugged.
- **Branching:** Feature branches off main. No direct commits to main.

---

## What Claude Should Not Do

- Do not add features, abstractions, or error handling for scenarios not explicitly required.
- Do not refactor surrounding code when fixing a bug — fix the bug, nothing else.
- Do not add docstrings or comments to code that was not modified.
- Do not introduce new dependencies without flagging it explicitly.
- Do not use dynamic execution (eval, exec, or equivalent) anywhere in the codebase.
