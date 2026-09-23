"""Flask REST API for the AutoLearn adaptive learning platform (consumed by the React frontend)."""
from __future__ import annotations

import logging
import re
import secrets
import time
import uuid
from datetime import timedelta

from flask import Flask, jsonify, request, session
from werkzeug.exceptions import HTTPException

import config
from ml.model import ExamScoreModel
from services import storage
from services.catalog import get_recommendations
from services.learning_path import (
    STATUS_LABELS,
    STRONG_THRESHOLD,
    WEAK_THRESHOLD,
    accuracy_trend,
    activity_metrics,
    apply_status_change,
    coerce_progress,
    default_progress,
    normalize_step_status,
    order_by_prerequisites,
    parse_topics,
    quiz_history,
)
from services.llm_client import groq_available
from services.quiz import build_local_quiz, build_quiz, grade_quiz, public_view
from services.topics import TOPIC_CATALOG, normalize_topic
from services.tutor import generate_tutor_reply, load_dataset_registry
from services.youtube import youtube_api_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

MODEL = ExamScoreModel.load()
DATASET_REGISTRY = load_dataset_registry().to_dict(orient="records")
STUDENT_ID_PATTERN = re.compile(r"^[0-9a-f-]{36}$")
FRONTEND_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}

AI_FEATURES = [
    "LLM tutor (Groq) with TF-IDF retrieval and a rule-based fallback",
    "Topic-aware adaptive quiz generation with anti-repetition",
    "Weak-topic detection and learning score tracking",
    "Personalized path tracking with prerequisite-based unlocking",
    "Course, video, dataset and mini-project recommendations",
]
ML_FEATURES = [
    f"Exam score prediction ({MODEL.name}, cross-validated, test R² = {MODEL.metrics['test_regression']['r2']})",
    "Learner level derived from the predicted score",
    "Content-based ranking of courses and videos",
    "Prerequisite graph ordering (topological sort)",
]
MODERN_FEATURES = [
    {"name": "Exam Score Model", "why": "A regression model trained on 1,000 student records estimates the expected exam score from the quiz result."},
    {"name": "Hybrid Recommendation", "why": "Combines live YouTube API results with a curated video catalog."},
    {"name": "Adaptive Quiz Engine", "why": "Generates topic-aware questions from the syllabus, prerequisites and past mistakes."},
    {"name": "Learning Path Tracker", "why": "Tracks started, in-progress and completed topics and unlocks the next one."},
    {"name": "Topic-Aware Tutor", "why": "Answers questions using the selected topics, their prerequisites and the learner profile."},
    {"name": "Prerequisite Graph", "why": "Orders topics so that fundamentals are learned first."},
]

app = Flask(__name__)
if not config.SECRET_KEY:
    logger.warning("SECRET_KEY is not set: using a random key (sessions reset on restart)")
app.secret_key = config.SECRET_KEY or secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)


# Helpers -----------------------------------------------------------------------

def _json_body() -> dict:
    return request.get_json(silent=True) or {}


def _student_id() -> str:
    """Student id from the request (restores a previous session) or the session cookie."""
    session.permanent = True
    provided = str(_json_body().get("student_id") or request.args.get("student_id") or "").strip()
    if STUDENT_ID_PATTERN.match(provided):
        session["student_id"] = provided
    session.setdefault("student_id", str(uuid.uuid4()))
    return session["student_id"]


def _error(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _profile_or_none() -> dict | None:
    profile = session.get("profile")
    return profile if profile and profile.get("topics") else None


def _increment(profile: dict, counter: str) -> None:
    activity = profile.setdefault("activity", {})
    activity[counter] = int(activity.get(counter, 0)) + 1


def _resolve_topic(requested: str, profile: dict) -> str:
    """Map a requested topic/alias/prerequisite to a topic of the plan (default: next open topic)."""
    topic = normalize_topic(requested or "")
    topics = profile["topics"]
    if topic in topics:
        return topic
    for candidate in topics:
        meta = TOPIC_CATALOG.get(candidate, {})
        if topic in meta.get("aliases", []) or topic in meta.get("prerequisites", []):
            return candidate
    progress = coerce_progress(topics, profile.get("path_progress"))
    return next((t for t in topics if progress[t] != "locked"), topics[0])


def _assess(topics: list[str], quiz_items: list[dict], graded: dict) -> list[dict]:
    """Per-topic quiz score, plus the model's predicted exam score and level."""
    results = []
    for topic in dict.fromkeys(normalize_topic(t) for t in topics):
        items = [q for q in quiz_items if normalize_topic(q["topic"]) == topic]
        if not items:
            continue
        correct = sum(graded[f"{q['topic']}_{q['index']}"]["is_correct"] for q in items)
        score_pct = round(correct / len(items) * 100, 1)
        predicted_score, predicted_level = MODEL.predict_from_quiz(score_pct)
        results.append({
            "topic": topic,
            "score_pct": score_pct,
            "predicted_level": predicted_level,
            "predicted_exam_score": predicted_score,
            "next_topics": TOPIC_CATALOG.get(topic, {}).get("prerequisites", []),
        })
    return results


def _new_quiz(profile: dict, student_id: str) -> list[dict]:
    seed = int(time.time() * 1000)
    profile["quiz_seed"] = seed
    quiz = build_quiz(profile["topics"], student_id=student_id, seed=seed)
    storage.save_current_quiz(student_id, quiz)
    return quiz


def _learning_path(profile: dict, assessment: list[dict], student_id: str) -> list[dict]:
    levels = {r["topic"]: r["predicted_level"] for r in assessment}
    scores = {r["topic"]: r["score_pct"] for r in assessment}
    progress = coerce_progress(profile["topics"], storage.get_student_progress(student_id) or profile.get("path_progress"))

    path = []
    for order, topic in enumerate(profile["topics"], start=1):
        level = levels.get(topic, "beginner")
        rec = get_recommendations(topic, level)
        status = progress.get(topic, "locked")
        if scores.get(topic, 0) >= STRONG_THRESHOLD:
            status = "completed"
        elif topic in scores and scores[topic] < WEAK_THRESHOLD and status == "locked":
            status = "recommended"
        progress[topic] = status

        videos = profile.get("video_activity", {}).get(topic, {})
        courses = profile.get("course_activity", {}).get(topic, {}).values()
        path.append({
            "topic": topic,
            "level": level,
            "videos": rec["videos"][:4],
            "courses": rec["courses"][:4],
            "project": rec["project"],
            "prerequisites": TOPIC_CATALOG.get(topic, {}).get("prerequisites", []),
            "order": order,
            "status": status,
            "status_label": STATUS_LABELS.get(status, status.title()),
            "mastery": scores.get(topic, 0.0),
            "video_progress": int(max((v.get("watched_pct") or 0 for v in videos.values()), default=0)),
            "course_progress": min(100, sum(40 for c in courses if c.get("completed")) + sum(10 * int(c.get("clicks", 0)) for c in courses)),
            "resource_items": len(rec["videos"][:4]) + len(rec["courses"][:4]),
        })

    if progress != profile.get("path_progress"):
        profile["path_progress"] = progress
        storage.save_student_progress(student_id, progress)
        session["profile"] = profile
    return path


def _notifications(profile: dict, weak: list[str], strengths: list[str], learning_score: float) -> list[dict]:
    notes = []
    if weak:
        notes.append({"type": "warning", "title": "Focus next", "message": f"Revise {weak[0].title()} first before moving to harder topics."})
    if strengths:
        notes.append({"type": "success", "title": "Strong area", "message": f"You are doing well in {strengths[0].title()}."})
    notes.append({"type": "info", "title": "Plan ready", "message": f"{len(profile['topics'])} syllabus topics were mapped into your study plan."})
    if learning_score >= 80:
        notes.append({"type": "success", "title": "Learning score rising", "message": f"Your adaptive learning score is now {learning_score}%."})
    return notes


def _dashboard_payload() -> dict:
    student_id = _student_id()
    history = storage.get_student_history(student_id)
    payload = {
        "accuracyTrend": accuracy_trend(history),
        "modelScores": MODEL.leaderboard,
        "modelName": MODEL.name,
        "modelMetrics": MODEL.metrics["test_regression"],
        "automlEngine": "scikit-learn (5-fold CV model selection)",
        "youtubeLive": youtube_api_available(),
        "quizItems": public_view(storage.get_current_quiz(student_id)),
        "availableTopics": sorted(TOPIC_CATALOG),
        "aiFeatures": AI_FEATURES,
        "mlFeatures": ML_FEATURES,
        "modernFeatures": MODERN_FEATURES,
        "datasetRegistry": DATASET_REGISTRY,
        "llmMode": "groq_llm" if groq_available() else "local_rag_fallback",
        "datasetSources": [],
    }
    profile = _profile_or_none()
    if not profile:
        return {
            **payload,
            "profile": None, "assessment": [], "avgScore": 0, "strengths": [], "weakTopics": [],
            "learningPath": [], "resources": [], "notifications": [], "learningScore": 0,
            "pathProgress": {}, "quizHistory": [], "topicMastery": [],
            "pathMetrics": activity_metrics({}, []),
        }

    assessment = session.get("assessment") or []
    avg_score = round(sum(r["score_pct"] for r in assessment) / len(assessment), 1) if assessment else 0
    strengths = [r["topic"] for r in assessment if r["score_pct"] >= STRONG_THRESHOLD]
    weak = [r["topic"] for r in assessment if r["score_pct"] < WEAK_THRESHOLD]
    learning_path = _learning_path(profile, assessment, student_id)
    metrics = activity_metrics(profile, assessment)
    return {
        **payload,
        "profile": profile,
        "assessment": assessment,
        "avgScore": avg_score,
        "strengths": strengths,
        "weakTopics": weak,
        "learningPath": learning_path,
        # Same recommendations as the path, computed once (each one may call the YouTube API).
        "resources": [{k: step[k] for k in ("topic", "level", "videos", "courses", "project")} for step in learning_path],
        "notifications": _notifications(profile, weak, strengths, metrics["learning_score"]),
        "learningScore": metrics["learning_score"],
        "pathMetrics": metrics,
        "pathProgress": profile.get("path_progress", {}),
        "videoActivity": profile.get("video_activity", {}),
        "courseActivity": profile.get("course_activity", {}),
        "quizHistory": quiz_history(history),
        "topicMastery": [{"topic": r["topic"], "mastery": r["score_pct"]} for r in assessment],
    }


def _save_progress(profile: dict, progress: dict) -> None:
    profile["path_progress"] = progress
    storage.save_student_progress(_student_id(), progress)
    session["profile"] = profile


# Hooks ----------------------------------------------------------------------------

@app.after_request
def add_headers(resp):
    resp.headers["Cache-Control"] = "no-store"
    origin = request.headers.get("Origin", "")
    if origin in FRONTEND_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Vary"] = "Origin"
    return resp


@app.errorhandler(Exception)
def handle_error(err):
    if isinstance(err, HTTPException):
        return _error(err.description, err.code or 500)
    logger.exception("Unhandled error on %s", request.path)
    return _error("Internal server error", 500)


# Routes ---------------------------------------------------------------------------

@app.route("/")
def index():
    return jsonify({
        "message": "AutoLearn API is running. Start the React frontend with `npm start` in /frontend.",
        "frontend": "http://localhost:3000",
        "api_status": "/api/status",
    })


@app.route("/api/status")
def api_status():
    return jsonify({"ok": True, "model": MODEL.name, "llm": groq_available(), "youtube": youtube_api_available()})


@app.route("/api/student/id", methods=["GET", "POST"])
def api_student_id():
    provided = str(_json_body().get("student_id") or "").strip()
    restored = request.method == "POST" and bool(STUDENT_ID_PATTERN.match(provided))
    return jsonify({"ok": True, "student_id": _student_id(), "restored": restored})


@app.route("/api/start", methods=["POST"])
def api_start():
    data = _json_body()
    syllabus_text = (data.get("syllabus_text") or "").strip()
    target_goal = (data.get("target_goal") or "").strip()
    topics = order_by_prerequisites(parse_topics(syllabus_text, target_goal))
    student_id = _student_id()

    stored_progress = storage.get_student_progress(student_id)
    profile = {
        "syllabus_text": syllabus_text,
        "target_goal": target_goal,
        "topics": topics,
        "path_progress": coerce_progress(topics, stored_progress) if stored_progress else default_progress(topics),
        "activity": {"quiz_attempts": 0, "completed_actions": 0, "tutor_questions": 0},
        "video_activity": {},
        "course_activity": {},
    }
    quiz = _new_quiz(profile, student_id)
    session["profile"] = profile
    session.pop("assessment", None)
    return jsonify({"ok": True, "profile": profile, "quizItems": public_view(quiz), "availableTopics": topics})


@app.route("/api/quiz", methods=["GET", "POST"])
def api_quiz():
    profile = _profile_or_none()
    if not profile:
        return _error("Start your plan first.")
    student_id = _student_id()

    if request.method == "GET":
        quiz = storage.get_current_quiz(student_id)
        if request.args.get("refresh") == "1" or not quiz:
            quiz = _new_quiz(profile, student_id)
            session["profile"] = profile
        return jsonify({"ok": True, "quizItems": public_view(quiz), "topics": profile["topics"]})

    answers = _json_body().get("answers") or {}
    quiz = storage.get_current_quiz(student_id) or build_local_quiz(profile["topics"], seed=profile.get("quiz_seed"))
    graded = grade_quiz(quiz, answers)
    storage.save_student_answers(student_id, [
        {"topic": q["topic"], "question": q["q"], "subtopic": q.get("subtopic", ""), "is_correct": graded[f"{q['topic']}_{q['index']}"]["is_correct"]}
        for q in quiz
    ])
    _increment(profile, "quiz_attempts")
    session["profile"] = profile
    session["assessment"] = _assess(profile["topics"], quiz, graded)
    return jsonify({"ok": True, "graded": graded, **_dashboard_payload()})


@app.route("/api/context")
def api_context():
    return jsonify(_dashboard_payload())


@app.route("/api/reset", methods=["POST"])
def api_reset():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/search")
def api_search():
    query = (request.args.get("q") or "").strip().lower()
    pool = []
    for card in _dashboard_payload().get("resources", []):
        pool += [{"kind": "course", "topic": card["topic"], "title": c.get("title", ""), "url": c.get("url", ""), "provider": c.get("provider", "")} for c in card["courses"]]
        pool += [{"kind": "video", "topic": card["topic"], "title": v.get("title", ""), "url": v.get("url", ""), "provider": v.get("channel", "")} for v in card["videos"]]
    if not query:
        return jsonify({"ok": True, "results": pool[:10]})
    results = [item for item in pool if any(query in str(item[k]).lower() for k in ("title", "topic", "provider"))]
    return jsonify({"ok": True, "results": results[:12]})


@app.route("/api/notifications")
def api_notifications():
    return jsonify({"ok": True, "notifications": _dashboard_payload()["notifications"]})


@app.route("/api/path/update", methods=["POST"])
@app.route("/api/path/step/update", methods=["POST"])
def api_path_update():
    profile = _profile_or_none()
    if not profile:
        return _error("Start your plan first.")
    data = _json_body()
    topic = normalize_topic(data.get("topic") or "")
    raw_status = (data.get("status") or "").strip().lower()
    status = raw_status if request.path == "/api/path/update" else normalize_step_status(raw_status)
    if topic not in profile["topics"]:
        return _error("Unknown topic for this plan.")
    if status not in STATUS_LABELS:
        return _error("Invalid path status.")

    _save_progress(profile, apply_status_change(profile["topics"], profile.get("path_progress"), topic, status))
    if status in {"completed", "in-progress"}:
        _increment(profile, "completed_actions")
    session["profile"] = profile
    return jsonify({"ok": True, **_dashboard_payload()})


@app.route("/api/path/resources")
def api_path_resources():
    profile = _profile_or_none()
    if not profile:
        return _error("No learning plan exists yet.")
    topic = _resolve_topic(request.args.get("topic", ""), profile)
    level = next((r["predicted_level"] for r in session.get("assessment") or [] if r["topic"] == topic), "beginner")
    rec = get_recommendations(topic, level)
    resources = {"topic": topic, "level": level, "videos": rec["videos"][:4], "courses": rec["courses"][:4], "project": rec["project"]}
    return jsonify({"ok": True, "topic": topic, "resources": resources})


@app.route("/api/path/video/track", methods=["POST"])
def api_path_video_track():
    profile = _profile_or_none()
    if not profile:
        return _error("Start your plan first.")
    data = _json_body()
    topic = _resolve_topic(data.get("topic", ""), profile)
    url = (data.get("url") or "").strip()
    if not url:
        return _error("Missing video url.")
    try:
        watched_seconds = int(data.get("watched_seconds") or 0)
        watched_pct = min(100.0, max(0.0, float(data.get("watched_pct") or 0)))
    except (TypeError, ValueError):
        return _error("watched_seconds and watched_pct must be numbers.")
    event = (data.get("event") or "").strip().lower()

    entry = profile.setdefault("video_activity", {}).setdefault(topic, {}).setdefault(
        url, {"clicks": 0, "watched_seconds": 0, "watched_pct": 0.0, "events": []}
    )
    if event == "start":
        entry["events"] = (entry["events"] + [{"event": "start", "at": time.time()}])[-20:]
    if event == "click":
        entry["clicks"] += 1
    entry["watched_seconds"] = max(entry["watched_seconds"], watched_seconds)
    entry["watched_pct"] = max(entry["watched_pct"], watched_pct)

    progress = coerce_progress(profile["topics"], profile.get("path_progress"))
    if watched_pct >= 40 and progress[topic] not in {"in-progress", "completed"}:
        progress[topic] = "in-progress"
    if watched_pct >= 80:
        _increment(profile, "completed_actions")
    _save_progress(profile, progress)
    return jsonify({"ok": True, **_dashboard_payload()})


@app.route("/api/path/video/progress")
def api_path_video_progress():
    """Best watch progress per video URL, across topics."""
    profile = _profile_or_none() or {}
    progress = {}
    for topic_videos in profile.get("video_activity", {}).values():
        for url, rec in topic_videos.items():
            pct = max(rec.get("watched_pct") or 0, progress.get(url, {}).get("watched_pct", 0))
            progress[url] = {"watched_pct": pct, "completed": pct >= 80}
    return jsonify(progress)


@app.route("/api/path/course/track", methods=["POST"])
def api_path_course_track():
    profile = _profile_or_none()
    if not profile:
        return _error("Start your plan first.")
    data = _json_body()
    topic = _resolve_topic(data.get("topic", ""), profile)
    url = (data.get("url") or "").strip()
    action = (data.get("action") or "").strip().lower()
    if not url or action not in {"click", "completed"}:
        return _error("Invalid course track payload.")

    entry = profile.setdefault("course_activity", {}).setdefault(topic, {}).setdefault(
        url, {"clicks": 0, "revisits": 0, "completed": False, "last_action": None}
    )
    if action == "click":
        entry["clicks"] += 1
        entry["revisits"] += 1
    else:
        entry["completed"] = True
    entry["last_action"] = action
    _increment(profile, "completed_actions")

    progress = coerce_progress(profile["topics"], profile.get("path_progress"))
    if action == "completed" and progress[topic] == "locked":
        progress[topic] = "recommended"
    _save_progress(profile, progress)
    return jsonify({"ok": True, **_dashboard_payload()})


@app.route("/api/path/progress")
def api_path_progress():
    profile = _profile_or_none()
    if not profile:
        return _error("Start your plan first.")
    metrics = activity_metrics(profile, session.get("assessment") or [])
    return jsonify({
        "ok": True,
        "pathProgress": profile.get("path_progress", {}),
        "learningScore": metrics["learning_score"],
        "pathMetrics": metrics,
        "videoActivity": profile.get("video_activity", {}),
        "courseActivity": profile.get("course_activity", {}),
    })


@app.route("/api/tutor", methods=["POST"])
def api_tutor():
    question = (_json_body().get("question") or "").strip()
    if not question:
        return _error("Ask a question first.")
    profile = _profile_or_none()
    if not profile:
        return _error("Start with your syllabus first so the tutor can answer according to your topics.")
    _increment(profile, "tutor_questions")
    session["profile"] = profile
    reply = generate_tutor_reply(question, profile, session.get("assessment") or [])
    return jsonify({
        "ok": True,
        "answer": reply.answer,
        "topic": reply.detected_topic,
        "mode": reply.mode,
        "retrieved": reply.retrieved_chunks,
        "related_resources": reply.related_resources,
    })


@app.route("/api/features")
def api_features():
    return jsonify({
        "ok": True,
        "aiFeatures": AI_FEATURES,
        "mlFeatures": ML_FEATURES,
        "llmMode": "groq_llm" if groq_available() else "local_rag_fallback",
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
