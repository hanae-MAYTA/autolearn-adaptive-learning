"""Central configuration: paths, environment variables and shared constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent

# Data
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CATALOG_DIR = DATA_DIR / "catalogs"
STUDENT_PERFORMANCE_CSV = RAW_DIR / "student_performance.csv"
LEARNING_INTERACTIONS_CSV = RAW_DIR / "learning_interactions.csv"

# Model artifacts (produced by `python -m ml.train`)
MODELS_DIR = ROOT_DIR / "models"
MODEL_PATH = MODELS_DIR / "exam_score_model.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"

# Runtime state written by the web app (never committed)
INSTANCE_DIR = ROOT_DIR / "instance"

# Secrets / external services — read from the environment (.env), never hard-coded
SECRET_KEY = os.getenv("SECRET_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Learner level thresholds on a 0-100 score. Shared by the ML target and the app
# so a predicted score and a predicted level can never contradict each other.
LEVEL_BINS = [0, 50, 75, 100]
LEVEL_LABELS = ["beginner", "intermediate", "advanced"]

RANDOM_STATE = 42
