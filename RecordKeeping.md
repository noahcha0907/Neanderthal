# HumanEvolutionAgent — Design Decision Record

This document preserves the reasoning behind non-obvious design choices made during the architecture and implementation of this system. Each decision records what was chosen, why, and what alternatives were considered or rejected.

---

## 1. Talent Data as Parameter n+1

**Decision:** Previously generated artworks (talent data) are not introduced into the voting pool as voter 0 or as peers to the humanities parameters. They are added *after* the humanities voters are selected, as a single aggregated super-voter appended at position n+1.

**Rationale:** If talent data were included in the initial parameter selection pool, it could win a voting slot and displace a humanities source entirely — causing the robot to reference its own prior work instead of the human corpus. By inserting talent at n+1, the robot's aesthetic history *inflects* the final parameters without ever *replacing* a humanities voice. The humanities corpus remains the primary driver; talent data applies a learned bias on top of it.

**Effect:** Every artwork is guaranteed to have between `MIN_PARAMETERS` and `MAX_PARAMETERS` humanities sources in its lineage. Talent data never appears in the justification trace or influence edges — it shapes the work silently, the way a painter's muscle memory shapes their hand without being cited in the work itself.

---

## 2. Talent Weight Multiplier = 1.5

**Decision:** The talent cluster is introduced as a single super-voter with a total weight of `1.5 × TALENT_WEIGHT_MULTIPLIER`. This weight is distributed equally across all artworks in the cluster: `weight_each = 1.5 / len(matching_artworks)`.

**Rationale:** The weight was set by direct specification. A weight of 1.0 would give talent data equal influence to a single humanities voter, which undersells the robot's accumulated aesthetic experience relative to a single text excerpt. A weight greater than 2.0 risks talent data dominating the humanities pool when the cluster is small. 1.5 represents a deliberate calibration: the robot's visual memory is meaningful but not sovereign.

**Alternative considered:** Weighting each artwork individually (each artwork = 1 voter). Rejected because a large talent cluster would then overwhelm the humanities pool entirely. The super-voter structure keeps the aggregate influence bounded regardless of how many artworks match.

---

## 3. Talent Cluster Similarity Threshold = 90%

**Decision:** An artwork is included in the talent cluster for a given generation cycle only if its source lineage connects to the current humanities parameter chunks at ≥90% cosine similarity (`TALENT_SIMILARITY_THRESHOLD = 0.90`).

**Rationale:** This threshold determines *relevance* — the question is not "has this robot ever made something?" but "has this robot made something thematically close to what it is about to make?" A low threshold (e.g., 50%) would pull in almost every prior artwork on every cycle, turning the talent cluster into an undifferentiated average of the robot's entire history. A 90% threshold ensures the cluster reflects only the robot's prior experience with this specific thematic territory.

**Effect:** On early cycles with few artworks, the talent cluster is often empty, and the robot operates on humanities alone. As the corpus grows, the cluster becomes meaningful. This mirrors how aesthetic pattern recognition develops in humans — you need enough experience in a domain before your prior work starts informing new work.

---

## 4. Talent Data Is Not Recorded in Lineage

**Decision:** Talent voters are never saved as influence edges in the graph and never appear in the justification trace. Only humanities voters become part of the artwork's lineage.

**Rationale:** The graph is a record of intellectual provenance — it maps which human texts shaped which artworks. Talent data represents the robot's own learned aesthetic, not a citable source. Including it in the trace would create circular references (artwork B influenced by artwork A, which was influenced by artwork B's corpus lineage) that confuse attribution and obscure the human sources actually driving the work.

---

## 5. Deterministic Voting via Hash Derivation

**Decision:** Each voter's proposals for every parameter are derived deterministically from a SHA-256 hash of `f"{chunk_id}:{parameter_key}"`. No global random state is used in voting. `random.seed()` is never called.

**Rationale:** Given identical voters, the robot always produces identical art. Variation comes entirely from *which voters are selected*, not from noise inside the voting process. This makes the system reproducible and auditable: if you know which texts voted on a piece, you can recompute it exactly. It also means the justification trace is a true causal account, not an approximation.

**Effect:** The only source of non-determinism in the pipeline is the weighted random sampling of voters from the graph, which is seeded per-cycle by `generation_cycle_seed` if deterministic output is needed.

---

## 6. Discrete vs. Continuous Parameter Voting

**Decision:** Parameters are split into two categories with different aggregation rules:

- **Discrete** (background color, shape type, fill color, stroke color, stroke width): **Weighted plurality** — each voter nominates one option; the option with highest cumulative weight wins.
- **Continuous** (x, y, size, opacity, shape count): **Weighted average** — each voter proposes a float; the final value is the weight-proportional mean.

**Rationale:** Averaging colors or shape types produces meaningless results (the average of "circle" and "triangle" is not a shape; the average of red and blue produces purple, which may not appear in any voter's aesthetic). Plurality respects that discrete choices are categorical. Continuous geometry, on the other hand, benefits from averaging — a group of texts pulling in different compositional directions should produce a work positioned between them, not arbitrarily snapped to the loudest voice.

---

## 7. Voter Count Range: MIN_PARAMETERS=1, MAX_PARAMETERS=5

**Decision:** Each generation cycle selects between 1 and 5 humanities voters.

**Rationale:** A single voter produces focused, coherent work — good for strong individual texts. Five voters produce more complex, contested compositions. The random range produces natural variation in the robot's output richness. More than 5 was considered but rejected: beyond 5 voters, the weighted average of continuous parameters converges toward the center of the distribution, producing compositions that feel generic and safe.

---

## 8. Edge Decay Factor = 0.95 per Cycle

**Decision:** Every edge in the semantic graph is multiplied by 0.95 at the end of each generation cycle. Edges below 0.01 are pruned.

**Rationale:** Without decay, the first associations formed in the graph (from the initial corpus) would dominate indefinitely — early texts would accumulate edge weight and win voter selection far more often than newer additions. Decay ensures that recently active associations remain competitive. The 0.95 factor was chosen as a gentle decay: an edge that starts at 1.0 takes roughly 90 cycles to fall below the pruning threshold, giving relationships a meaningful but finite lifespan.

---

## 9. Coactivation Bump = 0.05

**Decision:** When two source chunks are selected as co-voters for the same artwork, the edge weight between them increases by 0.05 (capped at 1.0). If no edge exists, one is created at weight 0.05.

**Rationale:** This encodes a Hebbian learning rule at the graph level: chunks that fire together, wire together. Over many cycles, texts that repeatedly co-occur in the robot's aesthetic decisions develop strong semantic ties — even if their initial embedding similarity was moderate. This allows the robot's experience to reshape its own associative structure beyond what the static embeddings alone would produce.

---

## 10. Similarity Edge Threshold = 0.50 (Corpus-Level)

**Decision:** Two source chunks are connected by a similarity edge in the graph only if their cosine similarity exceeds 0.50.

**Rationale:** Below 0.5, two texts share less than half their semantic direction — the connection is too weak to be meaningful for aesthetic association. Setting the threshold at 0.5 keeps the graph sparse enough to be navigable while preserving genuine thematic relationships. Combined with coactivation, edges that start just above threshold can strengthen over time through co-use.

---

## 11. Floor Weight = 0.01 for Isolated Nodes in Voter Selection

**Decision:** When selecting voters by graph connectivity weight, nodes with zero outgoing edge weight (isolated nodes) are assigned a floor weight of 0.01 rather than being excluded entirely.

**Rationale:** Newly ingested texts begin with no graph connections. Without the floor, they would never be selected as voters until another text connected to them — which can only happen after they are selected. The floor weight breaks this deadlock, giving new texts a small but non-zero chance of being drawn into the generation process. This is the mechanism by which fresh uploads influence the robot despite having no established graph relationships.

---

## 12. Upload Weight Bias = 3.0 During Private Sessions

**Decision:** During a private session, uploaded chunks are given a voter selection weight of 3.0, versus the graph-connectivity-based weight used for permanent corpus nodes.

**Rationale:** A user who uploads a text intends it to influence the robot. Without a bias, a freshly uploaded chunk with no graph connections would compete against well-connected permanent nodes at floor weight (0.01) — nearly invisible. The 3.0 bias ensures that a private upload has roughly 300× the draw probability of an isolated permanent node, making the session feel immediately responsive to the user's contribution. The bias is session-scoped and does not persist.

---

## 13. Talent Data Treated as Structured Data, Never Executed

**Decision:** Generated SVG art code is stored as text files and re-ingested as corpus data. It is never passed to `eval()`, `exec()`, or any dynamic execution mechanism.

**Rationale:** The SVG file *is* the art code — `<circle cx="0.3" cy="0.6" r="0.15" fill="#1a1a6e"/>` is both the instruction and the record. Re-ingesting it as text closes the robot's memory loop without requiring it to be run. Executing generated code at ingest time would create an arbitrary code execution surface, since the generation pipeline could theoretically be manipulated to produce malicious SVG with embedded scripts. Treating it as structured text eliminates that class of attack entirely.

---

## 14. Embedding Model: all-MiniLM-L6-v2 (384 dimensions)

**Decision:** Semantic embeddings use the `sentence-transformers/all-MiniLM-L6-v2` model with 384-dimensional output, normalized to unit length.

**Rationale:** MiniLM-L6-v2 is a distilled sentence transformer that produces high-quality semantic similarity scores at a fraction of the compute cost of larger models. For a system that must embed potentially large corpora and query them in real-time during generation cycles, speed and size matter. At 384 dimensions, storage and dot-product computation remain practical even for large chunk counts. Normalization to unit length means cosine similarity reduces to dot product, which is faster to compute and trivially handled by pgvector.

---

## 15. Chunk Strategy by Document Type

**Decision:** The corpus splitting strategy is determined by document type:

| Document Type | Strategy |
|---|---|
| Literary prose, philosophy, history | Paragraph |
| Poem, lyric | Stanza |
| Textbook (US history, world history, design) | Section |

**Rationale:** Different document types have different natural semantic units. Splitting a poem at paragraph boundaries destroys the stanza — the unit of meaning. Splitting a textbook at stanza boundaries is nonsensical. Matching the split strategy to the document's native structure preserves the semantic integrity of each chunk and produces better embeddings (a complete stanza encodes its meaning more accurately than an arbitrary mid-poem cut).

---

## 16. Chunk Length Bounds: 50–1500 characters

**Decision:** Chunks shorter than 50 characters are discarded. Chunks longer than 1500 characters are truncated at the nearest sentence boundary.

**Rationale:** Very short chunks (a title, a one-line attribution) embed poorly — their vectors are dominated by surface-level word choice rather than semantic content. 50 characters is approximately one meaningful sentence. At the upper end, embedding models have effective context windows; chunks much beyond 1500 characters risk the tail content being underweighted in the final vector. Sentence-boundary truncation ensures the embedded chunk ends on a complete thought.

---

## 17. Shape Geometry: Star Inner Radius = 40% of Outer

**Decision:** Five-pointed stars have inner radius = `r × 0.4` where r is the outer circumradius.

**Rationale:** A ratio below 0.35 produces a very spiky, sharp star. Above 0.55, the star begins to look like a pentagon with notches. 0.4 lands in the range that reads immediately and unambiguously as a star across a range of sizes on the canvas.

---

## 18. Rectangle Aspect Ratio: 3:2

**Decision:** Rectangles are rendered with half-width = `r × 1.5` and half-height = `r`, giving a 3:2 width-to-height ratio.

**Rationale:** 3:2 is a natural, slightly-wider-than-tall ratio that avoids the rectangle being mistaken for a square (which is a distinct shape type in the system) while remaining proportionally stable at small sizes.

---

## 19. Justification Trace Attribution Rules

**Decision:**
- **Discrete parameters:** The dominant source is the highest-weight voter *that voted for the winning option*. If the winning color came from a minority of voters who happened to outweigh the majority, the trace correctly credits the voters who actually produced the outcome.
- **Continuous parameters:** The dominant source is the highest-weight voter overall. For weighted averages, the highest-weight voter exerts the most pull on the final value.

**Rationale:** Tracing the wrong voter (e.g., attributing a color to the highest-weight voter even if that voter voted for a losing option) would produce a justification that doesn't actually explain the artwork. The distinction matters most when a small number of high-weight voters override a larger group.

---

## 20. Humanistic Concepts: 20 Seeded Concept Nodes

**Decision:** The graph is initialized with 20 fixed concept nodes representing universal humanistic themes:

`suffering, freedom, memory, time, mortality, identity, power, beauty, justice, truth, solitude, love, war, nature, progress, resistance, spirituality, knowledge, labor, community`

**Rationale:** These 20 concepts form the thematic skeleton of the humanities corpus. They were chosen to span the major axes of human concern represented in literary, philosophical, and historical texts — existential (mortality, time, memory), political (power, justice, resistance, freedom), relational (love, community, solitude), and material (labor, nature, progress). Corpus chunks connect to concept nodes based on embedding similarity, allowing traversal from a specific text passage to its broader humanistic territory.

---

*This document should be updated whenever a non-obvious design decision is changed or a new one is made. The goal is that a future collaborator — or the authors themselves after time away — can understand not just what the system does, but why it was built this way.*

---

---

# Mathematical Reference

This section documents every place in the system where non-trivial mathematics is used. The goal is not to re-explain the code line by line, but to name the mathematical concepts, explain the intuition, and record why each approach was chosen over alternatives. Future contributors should be able to read a formula here and immediately understand what it is doing and why.

---

## M1. Camera System — Quaternion Orbit

**File:** `frontend/src/components/GraphView.tsx`

The 3D graph camera is controlled by a custom spring-damped orbit system. Camera orientation is stored as a **unit quaternion** — a 4-component number `(x, y, z, w)` that encodes a rotation in 3D space without the singularities that arise from Euler angles or spherical coordinates.

### Why quaternions, not spherical coordinates

The original camera used `(theta, phi, radius)` — latitude and longitude angles plus distance from the look-at point. This is intuitive but has a critical failure mode: **gimbal lock at the poles**. When `phi` is near 0° (looking straight down) or 180° (looking straight up), `sin(phi) → 0`, which means the camera is nearly on the vertical axis. Any horizontal drag at this position produces a rotation that appears as a flat 2D spin rather than a 3D orbit — the horizontal axis degenerates.

Quaternions eliminate this because the rotation is stored as a single orientation, not two angles. There are no special cases.

### How orbit rotation is applied

Each drag frame produces two tiny rotations:

**Horizontal drag (`dx`):**
```
q_H = axis-angle rotation around world Y = (0,1,0) by angle (-dx * ORBIT_SPEED)
```
This always spins the camera around the true world vertical axis. No matter where the camera is — above, below, or level — horizontal drag produces a consistent horizontal orbit.

**Vertical drag (`dy`):**
```
q_V = axis-angle rotation around camera-local X = (1,0,0) by angle (-dy * ORBIT_SPEED)
```
This tilts the camera up or down relative to its own current right axis. Because it uses the camera's *local* X, it always moves in the direction the user intends, regardless of view angle.

**Combined application:**
```
q_new = q_H  ×  q_old  ×  q_V
       [premultiply]    [postmultiply]
```
Premultiplying by `q_H` applies the horizontal rotation in **world space**. Postmultiplying by `q_V` applies the vertical rotation in **camera-local space**. This order is not commutative — reversing it would cause the vertical axis to tilt with the camera, which creates its own class of instability.

### Camera position from quaternion

The camera sits at a fixed distance (`radius`) from the look-at center, along the +Z direction in its own local frame. To get world-space position:

```
offset = quaternion × (0, 0, radius)    [rotate the +Z vector by the orientation]
camera_pos = center + offset
```

`camera.lookAt(center)` then orients the camera to face the center point.

### Spring damping

The camera does not teleport to new positions — it interpolates. Two types of values are spring-damped:

- **Orientation:** `q_current = slerp(q_current, q_target, SPRING)`
  — **Spherical Linear Interpolation** (slerp) is the correct way to interpolate between quaternions. Regular linear interpolation on the components produces invalid (non-unit) quaternions and incorrect rotations. Slerp travels the shortest arc on the 4D unit sphere.

- **Radius and center:** `value += (target - value) * SPRING`
  — Standard exponential decay (discrete approximation to a first-order lag filter). At `SPRING = 0.14` and 60fps, a step change decays to 1% of its original error in approximately 30 frames (~500ms).

During mouse drag, both `q_current` and `q_target` are updated simultaneously, so no spring lag is felt during interaction. The spring only acts for programmatic transitions such as `focusNode()`.

---

## M2. Perspective-Correct Point Sizing

**File:** `frontend/src/components/GraphView.tsx` — vertex shader (`VERT`)

All graph nodes are rendered as a single `THREE.Points` object — one GPU draw call for every node simultaneously. Each node's on-screen size is computed in the vertex shader:

```glsl
gl_PointSize = aSize * (500.0 / -mvPos.z)
```

Where:
- `aSize` is the node's base size in abstract units
- `mvPos.z` is the node's depth in view space (negative = in front of camera)
- `500.0` is a calibration constant chosen so that a node with `aSize=10` at depth 500 renders as roughly 10 pixels

This is **manual perspective division**. In normal 3D rendering, object sizes shrink with distance automatically because the projection matrix handles it. But `gl_PointSize` is set in pixels and does not automatically scale with depth — without this formula, all nodes would appear the same size regardless of distance.

The formula mirrors the perspective projection: if the camera's projection matrix produces a standard field-of-view, then objects at depth `z` should appear `1/z` times as large as at unit depth. The constant `500.0` was tuned empirically.

---

## M3. Triangle Rasterization in Fragment Shader

**File:** `frontend/src/components/GraphView.tsx` — fragment shader (`FRAG`)

Each node is rendered as an upward-pointing triangle. The GPU cannot natively render triangular points — it only renders square point sprites. The fragment shader discards pixels that fall outside the triangle using **2D cross-product sign tests**.

For a point `p` and a triangle with vertices `a, b, c`, the sign of each edge function determines which side of that edge `p` lies on:

```glsl
d1 = (p.x - b.x)(a.y - b.y) - (a.x - b.x)(p.y - b.y)
```

This is the z-component of the 3D cross product `(b→a) × (b→p)`. If all three `d` values have the same sign, the point is inside the triangle. If they have mixed signs, it is outside and the fragment is discarded (`discard`).

The three vertices of the triangle are defined in the point sprite's [0,1]² UV space:
- `a = (0.5, 0.05)` — apex, top center
- `b = (0.05, 0.93)` — bottom left
- `c = (0.95, 0.93)` — bottom right

---

## M4. Screen-Space Node Hit Detection

**File:** `frontend/src/components/GraphView.tsx` — `getHitNode()`

When a user clicks on the canvas, the system must determine which node was clicked. Rather than raycasting into the 3D scene (which is unreliable for `THREE.Points` due to bounding sphere caching issues), the system performs hit detection entirely in 2D screen space.

**Step 1 — View-space depth:**
```
viewPos = matrixWorldInverse × worldPos
viewDepth = -viewPos.z
```
The camera's `matrixWorldInverse` transforms world coordinates into camera-local space. The depth is the distance along the camera's view axis. Nodes behind the camera (`viewDepth <= 0`) are skipped.

**Step 2 — NDC to screen pixels:**
```
ndc = project(worldPos, camera)       // THREE.Vector3.project(): NDC in [-1, 1]²
sx = (ndc.x + 1) / 2 × W
sy = (1 − ndc.y) / 2 × H
```
Normalized device coordinates are in `[-1, 1]²` with Y pointing up. Pixel coordinates have Y pointing down — hence the `1 − ndc.y` inversion.

**Step 3 — Pixel radius (matching the vertex shader exactly):**
```
pixelRadius = aSize × 500 / viewDepth / 2
```
This is the same formula as `gl_PointSize = aSize * (500 / viewDepth)`, halved because `gl_PointSize` is diameter and we need radius.

**Step 4 — Pick the closest hit:**
```
dist = sqrt((mouseX − sx)² + (mouseY − sy)²)
if dist <= pixelRadius: candidate
```
Standard 2D Euclidean distance. If multiple nodes overlap under the cursor, the one with the smallest center-to-cursor distance wins (visually frontmost).

Because this formula is derived directly from the shader, there is zero discrepancy between what the user sees and what can be clicked.

---

## M5. Semantic Embeddings and Cosine Similarity

**Files:** `src/models/embeddings.py`, `src/controllers/build_graph.py`

Text corpus chunks are converted into **dense vector embeddings** by the `all-MiniLM-L6-v2` sentence transformer. Each chunk becomes a 384-dimensional unit vector in semantic space.

**Why unit vectors?**

After encoding, all vectors are L2-normalized:
```python
norms = np.linalg.norm(matrix, axis=1, keepdims=True)
matrix /= np.maximum(norms, 1e-8)
```
L2 normalization (`v / ||v||` where `||v|| = sqrt(Σv²)`) projects each vector onto the unit hypersphere. This means **cosine similarity reduces to dot product**:

```
cosine_similarity(u, v) = (u·v) / (||u|| ||v||)
                        = u·v          [since ||u|| = ||v|| = 1]
```

This matters for performance: computing the pairwise similarity matrix for all corpus chunks becomes a single matrix multiplication:
```python
sim_matrix = matrix @ matrix.T    # O(n² × d) instead of O(n² × 2d)
```

For `n` chunks of dimension `d = 384`, this produces all `n×n` pairwise similarities in one batched BLAS call.

**pgvector cosine distance:**
In PostgreSQL, nearest-neighbor queries use the `<=>` operator (cosine distance):
```sql
1 - (embedding <=> query_vector) AS similarity
```
The cosine distance is `1 - cosine_similarity`, so `similarity = 1 - distance`. Because vectors are pre-normalized, this is equivalent to `1 - (u·v)` where both vectors are unit length.

---

## M6. Edge Weight Dynamics

**File:** `src/models/graph.py`

Edges in the semantic graph carry a `weight` value between 0 and 1 that changes over time according to two opposing forces.

### Decay — forgetting

Every generation cycle, all edges are multiplied by the decay factor:
```python
weight_new = weight_old × EDGE_DECAY_FACTOR    # default: 0.95
```

This is **exponential decay**. After `N` cycles an edge that started at weight 1.0 has weight `0.95^N`:

| Cycles | Remaining weight |
|--------|-----------------|
| 14     | 0.49 (~half-life) |
| 45     | 0.10 |
| 90     | 0.01 (pruning threshold) |

The half-life is `ln(0.5) / ln(0.95) ≈ 14 cycles`. Edges below 0.01 are pruned entirely to keep the graph sparse.

Without decay, the first edges ever formed would accumulate weight advantage and dominate voter selection indefinitely. Decay gives recent associations a competitive edge against older ones.

### Coactivation — learning

When two source chunks are selected as co-voters in the same generation cycle, the edge between them is strengthened:
```python
weight = min(1.0, weight + COACTIVATION_BUMP)    # COACTIVATION_BUMP = 0.05
```

This is a discrete implementation of **Hebbian learning**: "neurons that fire together, wire together." Over repeated co-selection, texts that the robot consistently associates develop strong edges — regardless of whether their initial embedding similarity was high. The `min(1.0, ...)` ceiling prevents any single edge from growing without bound.

The interplay between decay and coactivation is a core dynamic of the system: edges that form naturally through co-use remain competitive against decay; edges that were formed once but never reinforced fade away.

---

## M7. Voting Mathematics

**File:** `src/models/voting.py`

### Deterministic proposal generation via SHA-256

Each voter's proposal for each parameter is derived from a hash rather than a random sample:
```python
digest = hashlib.sha256(f"{chunk_id}:{parameter_key}".encode()).hexdigest()
value = int(digest[:8], 16) / 0x1_0000_0000
```

This takes the first 32 bits of the SHA-256 hash and divides by `2³² = 4,294,967,296` to produce a float in `[0, 1)`. The hash is deterministic: identical inputs always produce identical outputs. This means the voting process is fully reproducible — given the same set of voters, the artwork parameters are always the same.

### Weighted average (continuous parameters)

For geometry parameters (x, y, size, opacity, shape count), the final value is the normalized dot product of voter proposals and weights:
```
final = Σ(value_i × weight_i)
```
Weights are pre-normalized to sum to 1.0, so this is a convex combination. The result is always within the convex hull of the proposals — no voter can pull the value outside the range of what any voter proposed.

### Weighted plurality (discrete parameters)

For categorical parameters (color, shape type), each voter nominates one option and that option accumulates the voter's weight:
```python
tally[option] += weight
winner = argmax(tally)
```
The winner is the option with the highest total weight, not necessarily the most common option. A single high-weight voter can override a majority of low-weight voters. This is intentional: it reflects that the voter's graph connectivity (their weight) is a proxy for their thematic relevance to the current cycle.

### Weighted random sampling without replacement

Voters are sampled from the graph proportional to their connectivity weight using **inverse transform sampling**:
```python
threshold = random.uniform(0, sum(weights))
cumulative = 0
for chunk_id, weight in zip(ids, weights):
    cumulative += weight
    if cumulative >= threshold:
        # select this chunk
        remove it from pool
        break
```
Drawing a uniform sample from `[0, total_weight]` and finding where the cumulative sum crosses the threshold is equivalent to sampling proportional to weight. The selected chunk is removed from the pool, and the process repeats — this gives sampling without replacement while preserving proportionality.

---

## M8. Heat Mapping — Color and Size Lerp

**File:** `frontend/src/components/GraphView.tsx`

During an active session, nodes that have been selected as voters are visually heated — they grow larger and shift toward amber. This is computed per node using two lerp functions.

**Normalization:**
```
heat = min(count / 8, 1.0)
```
Maps vote count to `[0, 1]`, saturating at 8 activations. Counts above 8 produce no additional visual change.

**Size scaling:**
```
sizeMultiplier = 1.0 + heat × 0.4
```
Linear interpolation from `1.0×` (no activations) to `1.4×` (8+ activations).

**Color lerp (white → amber):**
```
color = lerp(white, amber, heat × 0.65)
```
The `× 0.65` cap means even fully-saturated nodes reach only 65% of the way to pure amber, keeping them recognizably related to their base color. `THREE.Color.lerpColors()` interpolates in RGB space.

---

## M9. Pulse Animation — Sine Envelope

**File:** `frontend/src/components/GraphView.tsx` — `pulseAll()`

When a generation cycle begins, a series of green waves propagates outward from a random origin node across all graph edges. Each wave's brightness follows a sine envelope:

```
brightness = sin(t / glowMs × π) × 0.85
```

Where `t` is the elapsed time within the glow phase. The sine function goes from 0 → 1 → 0 over `[0, glowMs]`, producing a smooth fade-in and fade-out. The `× 0.85` cap keeps the glow from being fully opaque.

Edges are staggered by their midpoint distance from the origin node, so waves appear to travel outward rather than all edges flashing simultaneously.

---

## M10. SVG Shape Geometry

**File:** `src/views/svg_renderer.py`

All shape parameters are stored in normalized `[0, 1]` coordinates. Before rendering, they are scaled to canvas pixels:

```python
cx = x × canvas_width
cy = y × canvas_height
r  = size × min(canvas_width, canvas_height) / 2
```

**Equilateral triangle vertices:**
Three points equally spaced around a circle, starting at the top (−90°):
```python
(cx + r × cos(−90° + 120° × i), cy + r × sin(−90° + 120° × i))   for i ∈ {0, 1, 2}
```
This is the parametric equation of a circle evaluated at three equally-spaced angles. The −90° offset orients the apex upward.

**Five-pointed star vertices:**
Ten vertices alternating between outer radius `r` and inner radius `0.4r`, equally spaced at `180°/5 = 36°` intervals:
```python
angle = −90° + i × 36°
radius = r if i is even else 0.4r
(cx + radius × cos(angle), cy + radius × sin(angle))
```
The 0.4 inner/outer ratio was chosen to produce a recognizable star — below 0.35 it becomes too spiky; above 0.55 it approaches a pentagon.

**Rectangle:**
Half-width `= 1.5r`, half-height `= r`, giving a fixed **3:2 aspect ratio**. This avoids visual confusion with the square shape type (which would also be generated by this renderer at a 1:1 ratio).

---

## M11. Portfolio Stack — Gaussian Neighbor Influence

**File:** `frontend/src/components/PortfolioStackView.tsx`

When the user hovers a panel in the portfolio stack, neighboring panels are nudged away with a Gaussian falloff:

```javascript
influence = exp(−dist² / (2 × σ²))    // σ = 0.5
```

This is the standard **Gaussian function** (bell curve), normalized to peak at 1.0 for `dist = 0`. With `σ = 0.5`:
- `dist = 0` (hovered panel): influence = 1.0
- `dist = 1` (adjacent panel): influence ≈ 0.135
- `dist = 2` (two away): influence ≈ 0.0003 (effectively zero)

The Gaussian was chosen over a linear falloff because it produces a natural, physical-feeling spread — influence drops quickly but smoothly, with no hard cutoff. The result feels like adjacent panels being physically pushed rather than mechanically displaced.
