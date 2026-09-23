"""Loading, validation and cleaning of the student performance dataset.

One row = one student. The modelling target is the final exam score (0-100).

Columns deliberately excluded from the features (see notebooks/01_data_quality_and_eda.ipynb):
- ``grade``, ``success_label``, ``niveau``: deterministic binnings of the exam score
  itself -> using them would leak the target into the features.
- ``math/science/language_prev_score``: near-duplicates of ``previous_score``
  (their mean correlates at r = 0.985 with it).
- ``derniere_activite``: synthetic sequential dates with no behavioural meaning.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import LEVEL_BINS, LEVEL_LABELS, STUDENT_PERFORMANCE_CSV

logger = logging.getLogger(__name__)

# Source columns are partly in French; standardise everything to English snake_case.
COLUMN_NAMES = {
    "student_id": "student_id",
    "score_global": "exam_score",
    "grade": "grade",
    "success_label": "passed",
    "previous_score": "previous_score",
    "math_prev_score": "math_prev_score",
    "science_prev_score": "science_prev_score",
    "language_prev_score": "language_prev_score",
    "heures_etude_jour": "study_hours_per_day",
    "taux_presence": "attendance_rate",
    "homework_completion_rate": "homework_completion_rate",
    "sleep_hours": "sleep_hours",
    "screen_time_hours": "screen_time_hours",
    "physical_activity_minutes": "physical_activity_minutes",
    "motivation": "motivation",
    "exam_anxiety_score": "exam_anxiety",
    "niveau_parent": "parent_education",
    "style_apprentissage": "study_environment",  # values: Quiet / Moderate / Noisy
    "niveau": "level_fr",
    "derniere_activite": "last_activity_date",
}

TARGET = "exam_score"
NUMERIC_FEATURES = [
    "previous_score",
    "study_hours_per_day",
    "attendance_rate",
    "homework_completion_rate",
    "sleep_hours",
    "screen_time_hours",
    "physical_activity_minutes",
    "motivation",
    "exam_anxiety",
]
CATEGORICAL_FEATURES = ["parent_education", "study_environment"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Target-derived columns: kept in the clean table for analysis, never used as features.
LEAKY_COLUMNS = ["grade", "passed", "level_fr"]

# Percentages / scores that cannot physically exceed [0, 100].
BOUNDED_0_100 = [
    "exam_score",
    "previous_score",
    "math_prev_score",
    "science_prev_score",
    "language_prev_score",
    "attendance_rate",
    "homework_completion_rate",
]


def load_student_performance(path: Path = STUDENT_PERFORMANCE_CSV) -> pd.DataFrame:
    """Read the raw CSV and fail early with a clear message if the schema changed."""
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    df = pd.read_csv(path)
    missing = set(COLUMN_NAMES) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing expected columns: {sorted(missing)}")
    return df


def clean_student_performance(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename, deduplicate and fix out-of-range values. Returns a new DataFrame."""
    df = raw.rename(columns=COLUMN_NAMES)[list(COLUMN_NAMES.values())].copy()

    n_before = len(df)
    df = df.drop_duplicates(subset="student_id")
    if len(df) < n_before:
        logger.info("Dropped %d duplicated students", n_before - len(df))

    df = df.dropna(subset=[TARGET])

    for col in BOUNDED_0_100:
        n_out = int(((df[col] < 0) | (df[col] > 100)).sum())
        if n_out:
            logger.info("Clipping %d out-of-range values in %s to [0, 100]", n_out, col)
            df[col] = df[col].clip(0, 100)

    df["last_activity_date"] = pd.to_datetime(df["last_activity_date"], errors="coerce")
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("string").str.strip()

    # Missing feature values are imputed inside the model pipeline (fitted on the
    # training split only) rather than here, to avoid leaking test statistics.
    return df.reset_index(drop=True)


def score_to_level(scores: pd.Series) -> pd.Series:
    """Map 0-100 scores to beginner / intermediate / advanced (bins from config)."""
    return pd.cut(scores, bins=LEVEL_BINS, labels=LEVEL_LABELS, include_lowest=True).astype(str)


def load_modeling_data() -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) ready for the training pipeline."""
    df = clean_student_performance(load_student_performance())
    return df[FEATURES], df[TARGET]
