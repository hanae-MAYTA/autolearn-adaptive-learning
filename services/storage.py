"""File-based persistence for per-student state (quiz answers, path progress, quizzes).

JSON files under ``instance/`` are enough for a single-user demo. A multi-user
deployment would replace this module with a database (e.g. SQLite + SQLAlchemy).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config import INSTANCE_DIR

STUDENT_HISTORY_FILE = INSTANCE_DIR / "student_histories.json"
STUDENT_PROGRESS_FILE = INSTANCE_DIR / "student_progress.json"
QUESTION_HISTORY_FILE = INSTANCE_DIR / "question_history.json"
QUIZ_FILE = INSTANCE_DIR / "current_quizzes.json"

MAX_STUDENT_HISTORY = 200


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get(path: Path, student_id: str, default):
    return load_json(path).get(student_id, default)


def _set(path: Path, student_id: str, value) -> None:
    data = load_json(path)
    data[student_id] = value
    save_json(path, data)


# Answer history -------------------------------------------------------------

def get_student_history(student_id: str) -> list[dict]:
    return _get(STUDENT_HISTORY_FILE, student_id, [])


def save_student_answers(student_id: str, answers: list[dict]) -> None:
    """Append graded answers: dicts with topic, question, subtopic, is_correct."""
    timestamp = datetime.now().isoformat()
    history = get_student_history(student_id) + [
        {
            "topic": a.get("topic", "unknown"),
            "question_text": a.get("question", ""),
            "subtopic": a.get("subtopic", ""),
            "is_correct": bool(a["is_correct"]),
            "timestamp": timestamp,
        }
        for a in answers
    ]
    _set(STUDENT_HISTORY_FILE, student_id, history[-MAX_STUDENT_HISTORY:])


# Learning-path progress -----------------------------------------------------

def get_student_progress(student_id: str) -> dict[str, str]:
    return _get(STUDENT_PROGRESS_FILE, student_id, {})


def save_student_progress(student_id: str, path_progress: dict[str, str]) -> None:
    _set(STUDENT_PROGRESS_FILE, student_id, path_progress)


# Current quiz (kept server-side: 12 questions overflow the 4 KB session cookie) --

def get_current_quiz(student_id: str) -> list[dict]:
    return _get(QUIZ_FILE, student_id, [])


def save_current_quiz(student_id: str, quiz_items: list[dict]) -> None:
    _set(QUIZ_FILE, student_id, quiz_items)
