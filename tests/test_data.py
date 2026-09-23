import pandas as pd

from ml.data import FEATURES, LEAKY_COLUMNS, clean_student_performance, load_student_performance, score_to_level


def test_no_target_derived_column_is_used_as_feature():
    assert not set(LEAKY_COLUMNS) & set(FEATURES)
    assert "exam_score" not in FEATURES


def test_cleaning_bounds_percentages_and_keeps_one_row_per_student():
    clean = clean_student_performance(load_student_performance())
    assert clean["student_id"].is_unique
    assert clean["homework_completion_rate"].between(0, 100).all()
    assert clean[FEATURES].columns.tolist() == FEATURES


def test_cleaning_removes_duplicates_and_clips():
    raw = load_student_performance().head(3)
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    raw.loc[1, "taux_presence"] = 130
    clean = clean_student_performance(raw)
    assert len(clean) == 3
    assert clean["attendance_rate"].max() <= 100


def test_score_to_level_boundaries():
    levels = score_to_level(pd.Series([0, 49.9, 50, 74.9, 75, 100])).tolist()
    assert levels == ["beginner", "beginner", "beginner", "intermediate", "intermediate", "advanced"]
