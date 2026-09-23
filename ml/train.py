"""Train and evaluate the exam-score model, then save it with its metrics.

Usage:  python -m ml.train

Protocol
1. Hold out 20 % of students as a test set (stratified on the learner level so the
   rare "beginner" class is represented).
2. Compare candidate models with 5-fold cross-validation on the training set only.
3. Evaluate the selected model once on the untouched test set.
4. Refit the selected model on all students and save it for the web app.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    r2_score,
    root_mean_squared_error,
)
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import LEVEL_LABELS, METRICS_PATH, MODEL_PATH, MODELS_DIR, RANDOM_STATE
from ml.data import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, load_modeling_data, score_to_level

logger = logging.getLogger(__name__)

CANDIDATES = {
    "Baseline (mean)": DummyRegressor(strategy="mean"),
    "Ridge": Ridge(alpha=1.0),
    "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1),
    "Gradient Boosting": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=RANDOM_STATE),
}


def build_pipeline(estimator) -> Pipeline:
    preprocessor = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), NUMERIC_FEATURES),
        ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 3),
    }


def level_metrics(y_true, y_pred) -> dict:
    """Evaluate the learner level derived from the predicted score."""
    true_lvl, pred_lvl = score_to_level(pd.Series(y_true)), score_to_level(pd.Series(y_pred))
    return {
        "accuracy": round(float(accuracy_score(true_lvl, pred_lvl)), 3),
        "macro_f1": round(float(f1_score(true_lvl, pred_lvl, average="macro")), 3),
        "labels": LEVEL_LABELS,
        "confusion_matrix": confusion_matrix(true_lvl, pred_lvl, labels=LEVEL_LABELS).tolist(),
    }


def compare_models(X_train: pd.DataFrame, y_train: pd.Series) -> pd.DataFrame:
    cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for name, estimator in CANDIDATES.items():
        scores = cross_validate(
            build_pipeline(estimator), X_train, y_train, cv=cv,
            scoring={"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"},
        )
        rows.append({
            "model": name,
            "cv_mae": -scores["test_mae"].mean(),
            "cv_mae_std": scores["test_mae"].std(),
            "cv_rmse": -scores["test_rmse"].mean(),
            "cv_r2": scores["test_r2"].mean(),
        })
    return pd.DataFrame(rows).sort_values("cv_mae").reset_index(drop=True)


def train() -> dict:
    X, y = load_modeling_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=score_to_level(y)
    )

    leaderboard = compare_models(X_train, y_train)
    best_name = leaderboard.loc[leaderboard["model"] != "Baseline (mean)", "model"].iloc[0]
    logger.info("Cross-validation leaderboard:\n%s", leaderboard.round(3).to_string(index=False))

    model = build_pipeline(CANDIDATES[best_name]).fit(X_train, y_train)
    y_pred = np.clip(model.predict(X_test), 0, 100)
    baseline_pred = np.full(len(y_test), y_train.mean())

    # Final artifact: same model refitted on every student.
    final_model = build_pipeline(CANDIDATES[best_name]).fit(X, y)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, MODEL_PATH)

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "target": "exam_score",
        "features": FEATURES,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "best_model": best_name,
        "cv_leaderboard": leaderboard.round(3).to_dict(orient="records"),
        "test_regression": regression_metrics(y_test, y_pred),
        "test_regression_baseline": regression_metrics(y_test, baseline_pred),
        "test_level": level_metrics(y_test, y_pred),
        # Typical student profile, used by the app when a feature is unknown.
        "feature_defaults": {
            **{c: round(float(X[c].median()), 2) for c in NUMERIC_FEATURES},
            **{c: str(X[c].mode().iloc[0]) for c in CATEGORICAL_FEATURES},
        },
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Best model: %s | test %s", best_name, metrics["test_regression"])
    logger.info("Saved model to %s and metrics to %s", MODEL_PATH, METRICS_PATH)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    train()
