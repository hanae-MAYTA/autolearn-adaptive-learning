"""Load the trained exam-score model and serve predictions to the web app."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import joblib
import pandas as pd

from config import METRICS_PATH, MODEL_PATH
from ml.data import FEATURES, score_to_level

logger = logging.getLogger(__name__)


@dataclass
class ExamScoreModel:
    pipeline: object
    metrics: dict

    @classmethod
    def load(cls) -> "ExamScoreModel":
        """Load the saved model, training it first if the artifact does not exist yet."""
        if not MODEL_PATH.exists() or not METRICS_PATH.exists():
            logger.warning("No trained model found - running ml.train (takes a few seconds)")
            from ml.train import train
            train()
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        return cls(pipeline=joblib.load(MODEL_PATH), metrics=metrics)

    @property
    def name(self) -> str:
        return self.metrics["best_model"]

    @property
    def leaderboard(self) -> dict[str, float]:
        """Cross-validated R² per candidate model (higher is better)."""
        return {row["model"]: row["cv_r2"] for row in self.metrics["cv_leaderboard"]}

    def predict_score(self, **known_features) -> float:
        """Predict an exam score; unknown features fall back to the typical student profile."""
        row = {**self.metrics["feature_defaults"], **known_features}
        pred = self.pipeline.predict(pd.DataFrame([row])[FEATURES])[0]
        return round(float(min(max(pred, 0.0), 100.0)), 1)

    def predict_from_quiz(self, quiz_score_pct: float) -> tuple[float, str]:
        """Predict (exam score, level) for a learner of whom we only know a quiz score.

        Cold-start assumption: the in-app quiz score is used as a proxy for
        ``previous_score``; every other feature is set to the training median/mode.
        """
        score = self.predict_score(previous_score=quiz_score_pct)
        level = score_to_level(pd.Series([score])).iloc[0]
        return score, level
