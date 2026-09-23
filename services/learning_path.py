"""Learning-path logic: topic extraction, prerequisite ordering, progress state and metrics."""
from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

from services.topics import TOPIC_CATALOG, match_topics_from_text, normalize_topic

STATUSES = ("locked", "recommended", "in-progress", "completed")
STATUS_LABELS = {"completed": "Completed", "in-progress": "In Progress", "recommended": "Not Started", "locked": "Locked"}
ACCURACY_TARGET = 70.0
WEAK_THRESHOLD = 45
STRONG_THRESHOLD = 75


def _dedupe(items) -> list:
    return list(dict.fromkeys(items))


# Topics -----------------------------------------------------------------------

def parse_topics(syllabus_text: str, target_goal: str = "") -> list[str]:
    """Extract known catalog topics from a free-text syllabus and goal."""
    text = f"{syllabus_text}, {target_goal}"
    tokens = [normalize_topic(t) for t in re.split(r"[,\n;/|]+", text) if t.strip()]
    topics = [t for t in tokens + match_topics_from_text(text) if t in TOPIC_CATALOG]
    return _dedupe(topics) or ["python"]


def order_by_prerequisites(topics: list[str]) -> list[str]:
    """Topological sort (Kahn's algorithm) restricted to the selected topics."""
    known = [t for t in topics if t in TOPIC_CATALOG]
    indegree = {t: 0 for t in known}
    dependents = defaultdict(list)
    for topic in known:
        for prereq in TOPIC_CATALOG[topic].get("prerequisites", []):
            if prereq in indegree:
                indegree[topic] += 1
                dependents[prereq].append(topic)

    queue = deque(sorted(t for t, d in indegree.items() if d == 0))
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in dependents[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    # Topics left in a cycle (if any) and unknown topics keep their original order.
    return _dedupe(order + topics)


# Progress state ------------------------------------------------------------------

def default_progress(topics: list[str]) -> dict[str, str]:
    return {topic: "recommended" if i == 0 else "locked" for i, topic in enumerate(topics)}


def coerce_progress(topics: list[str], stored: dict | None) -> dict[str, str]:
    """Merge stored statuses with the plan and guarantee the next topic is unlocked."""
    progress = default_progress(topics)
    for topic, status in (stored or {}).items():
        if topic in progress and status in STATUSES:
            progress[topic] = status
    next_topic = next((t for t in topics if progress[t] != "completed"), None)
    if next_topic and progress[next_topic] == "locked":
        progress[next_topic] = "recommended"
    return progress


def apply_status_change(topics: list[str], stored: dict | None, topic: str, status: str) -> dict[str, str]:
    """Set a topic's status and unlock what it makes reachable."""
    progress = coerce_progress(topics, stored)
    progress[topic] = status
    if status == "completed":
        idx = topics.index(topic)
        if idx + 1 < len(topics) and progress[topics[idx + 1]] == "locked":
            progress[topics[idx + 1]] = "recommended"
    elif status == "in-progress":
        for prereq in TOPIC_CATALOG.get(topic, {}).get("prerequisites", []):
            if progress.get(prereq) == "locked":
                progress[prereq] = "recommended"
    return progress


def normalize_step_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"not started", "not_started", "start", "recommended"}:
        return "recommended"
    if normalized in {"in progress", "in-progress", "progress"}:
        return "in-progress"
    if normalized in {"completed", "done"}:
        return "completed"
    return "locked"


# Metrics --------------------------------------------------------------------------

def _mean(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 1) if values else 0.0


def activity_metrics(profile: dict, assessment: list[dict]) -> dict[str, float]:
    """Component scores (0-100) and the weighted learning score shown on the dashboard."""
    topics = profile.get("topics", [])
    completed = sum(1 for s in profile.get("path_progress", {}).values() if s == "completed")
    topic_completion_pct = round(completed / len(topics) * 100, 1) if topics else 0.0
    quiz_pct = _mean(r["score_pct"] for r in assessment)
    video_pct = _mean(
        rec["watched_pct"]
        for topic_data in profile.get("video_activity", {}).values()
        for rec in topic_data.values()
        if rec.get("watched_pct") is not None
    )
    course_records = [rec for topic_data in profile.get("course_activity", {}).values() for rec in topic_data.values()]
    course_pct = min(100.0, sum(int(r.get("clicks", 0)) for r in course_records) * 10 + sum(1 for r in course_records if r.get("completed")) * 25)
    tutor_pct = min(100.0, int(profile.get("activity", {}).get("tutor_questions", 0)) * 25)

    learning_score = quiz_pct * 0.25 + topic_completion_pct * 0.4 + video_pct * 0.2 + course_pct * 0.1 + tutor_pct * 0.05
    return {
        "topic_completion_pct": topic_completion_pct,
        "quiz_pct": quiz_pct,
        "video_pct": video_pct,
        "course_pct": course_pct,
        "tutor_pct": tutor_pct,
        "learning_score": round(min(100.0, learning_score), 1),
    }


def _parse_timestamps(history: list[dict]):
    for entry in history:
        try:
            yield datetime.fromisoformat(entry.get("timestamp", "")), bool(entry.get("is_correct"))
        except (TypeError, ValueError):
            continue


def accuracy_trend(history: list[dict], days: int = 7) -> list[dict]:
    """Daily answer accuracy; days without activity carry the last known value."""
    by_date = defaultdict(lambda: [0, 0])  # date -> [correct, total]
    for dt, correct in _parse_timestamps(history):
        by_date[dt.date()][0] += correct
        by_date[dt.date()][1] += 1
    if not by_date:
        return []

    trend, last_accuracy = [], 0.0
    current, end = min(by_date), max(by_date)
    while current <= end:
        if current in by_date:
            correct, total = by_date[current]
            last_accuracy = round(correct / total * 100, 1)
        trend.append({"day": current.strftime("%a"), "date": current.isoformat(), "accuracy": last_accuracy, "target": ACCURACY_TARGET})
        current += timedelta(days=1)
    return trend[-days:]


def quiz_history(history: list[dict]) -> list[dict]:
    """Score per quiz attempt (answers submitted within the same minute form one attempt)."""
    by_attempt = defaultdict(lambda: [0, 0])
    for dt, correct in _parse_timestamps(history):
        key = dt.strftime("%Y-%m-%d %H:%M")
        by_attempt[key][0] += correct
        by_attempt[key][1] += 1
    return [
        {"name": f"Quiz {i}", "score": round(correct / total * 100, 1)}
        for i, (_, (correct, total)) in enumerate(sorted(by_attempt.items()), start=1)
    ]
