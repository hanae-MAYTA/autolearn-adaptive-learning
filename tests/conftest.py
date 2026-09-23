import os
import sys
from pathlib import Path

import pytest

# Tests must never call external APIs: blank the keys before config reads .env
# (python-dotenv does not override variables that are already set).
for var in ("GROQ_API_KEY", "YOUTUBE_API_KEY"):
    os.environ[var] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect every JSON store to a temporary directory."""
    from services import quiz, storage

    for name in ("STUDENT_HISTORY_FILE", "STUDENT_PROGRESS_FILE", "QUESTION_HISTORY_FILE", "QUIZ_FILE"):
        monkeypatch.setattr(storage, name, tmp_path / f"{name.lower()}.json")
    monkeypatch.setattr(quiz, "QUESTION_HISTORY_FILE", tmp_path / "question_history_file.json")
    return tmp_path


@pytest.fixture
def client(tmp_storage):
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
