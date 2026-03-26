"""
Global configuration constants for HumanEvolutionAgent.

All magic values live here. Never hardcode these in business logic —
import from this module instead.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://noahcha@localhost:5432/human_evolution_agent",
)

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
HUMANITIES_DIR = DATA_DIR / "humanities"
TALENT_DIR = DATA_DIR / "talent"
LOGS_DIR = ROOT_DIR / "logs"
CHUNK_STORE_PATH = DATA_DIR / "chunks.json"

# ── Corpus ─────────────────────────────────────────────────────────────────
MANIFEST_FILENAME = "manifest.json"

# Valid document types used as chunking and graph-node keys
DOCUMENT_TYPES = {
    "literary",
    "poem",
    "lyric",
    "philosophy",
    "history",
    "textbook_us_history",
    "textbook_world_history",
    "textbook_design",
}

# Maps each document type to its chunking strategy
CHUNK_STRATEGIES: dict[str, str] = {
    "literary":              "paragraph",
    "poem":                  "stanza",
    "lyric":                 "stanza",
    "philosophy":            "paragraph",
    "history":               "paragraph",
    "textbook_us_history":   "section",
    "textbook_world_history":"section",
    "textbook_design":       "section",
}

ACCEPTED_EXTENSIONS = {".pdf", ".txt", ".md"}

# Chunks outside these character bounds are discarded or truncated
MIN_CHUNK_LENGTH = 50
MAX_CHUNK_LENGTH = 1500

# ── Art ────────────────────────────────────────────────────────────────────
CANVAS_WIDTH  = 800
CANVAS_HEIGHT = 800

# Primary + secondary colors only, plus neutrals
COLOR_PALETTE: dict[str, str] = {
    "red":    "#FF0000",
    "blue":   "#0000FF",
    "yellow": "#FFFF00",
    "orange": "#FF8000",
    "green":  "#008000",
    "purple": "#800080",
    "black":  "#000000",
    "white":  "#FFFFFF",
}

SHAPE_TYPES = ["circle", "square", "rectangle", "triangle", "star", "line"]

STROKE_WIDTHS: dict[str, int] = {
    "thin":   1,
    "medium": 3,
    "thick":  6,
}

MIN_SHAPES = 1
# Provisional ceiling — updated after benchmarking in PRD 5.2
MAX_SHAPES = 20

# ── Embeddings ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # 384-dim, ~80 MB, runs fully local
EMBEDDING_DIM   = 384
EMBEDDING_BATCH_SIZE = 64              # Chunks per encode() call — fits in RAM comfortably

# ── Semantic graph ─────────────────────────────────────────────────────────
GRAPH_PATH = DATA_DIR / "graph.json"

# Cosine similarity below this value produces no source→source edge
SIMILARITY_EDGE_THRESHOLD = 0.50

# Applied to every edge weight once per generation cycle; prevents early
# associations from dominating as the corpus and artwork history grow
EDGE_DECAY_FACTOR = 0.95

# Edges decayed below this weight are pruned to keep the graph sparse
MIN_EDGE_WEIGHT = 0.01

# Humanistic themes seeded as ConceptNodes at graph initialisation.
# These serve as attractor nodes for the parameter voting engine (PRD 1.5).
HUMANISTIC_CONCEPTS: list[str] = [
    "suffering",
    "freedom",
    "memory",
    "time",
    "mortality",
    "identity",
    "power",
    "beauty",
    "justice",
    "truth",
    "solitude",
    "love",
    "war",
    "nature",
    "progress",
    "resistance",
    "spirituality",
    "knowledge",
    "labor",
    "community",
]

# ── Talent data ─────────────────────────────────────────────────────────────
# Minimum similarity between an artwork's source chunks and the current
# parameter set for that artwork to be included in the talent cluster.
TALENT_SIMILARITY_THRESHOLD = 0.90

# The talent cluster counts as one "super-voter" slot and carries this
# multiple of the weight of a single humanities parameter.
TALENT_WEIGHT_MULTIPLIER = 1.5

# Added to a similarity edge's weight each time two source nodes co-occur
# in the same artwork. Capped at 1.0.
COACTIVATION_BUMP = 0.05

# ── Generation ─────────────────────────────────────────────────────────────
GENERATION_INTERVAL_SECONDS = 5
MIN_PARAMETERS = 1
MAX_PARAMETERS = 5

# Maximum size (in bytes) accepted for user document uploads — PRD 2.6
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Weight assigned to user-uploaded chunks in private session voter selection.
# Elevated above typical graph connectivity weights so user-provided content
# dominates parameter selection without completely excluding graph nodes.
UPLOAD_WEIGHT_BIAS = 3.0
