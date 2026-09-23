from services.learning_path import apply_status_change, coerce_progress, order_by_prerequisites, parse_topics
from services.topics import match_topics_from_text


def test_topics_are_extracted_with_whole_word_matching():
    assert "rag" not in match_topics_from_text("the average storage cost")
    assert parse_topics("Linear regression, clustering") == ["linear regression", "clustering"]


def test_prerequisites_come_first():
    order = order_by_prerequisites(["linear regression", "data preprocessing", "python"])
    assert order.index("python") < order.index("data preprocessing") < order.index("linear regression")


def test_completing_a_topic_unlocks_the_next_one():
    topics = ["python", "statistics", "probability"]
    progress = apply_status_change(topics, None, "python", "completed")
    assert progress == {"python": "completed", "statistics": "recommended", "probability": "locked"}


def test_first_open_topic_is_never_locked():
    topics = ["python", "statistics"]
    assert coerce_progress(topics, {"python": "completed", "statistics": "locked"})["statistics"] == "recommended"
