"""Quiz generation (local question bank + optional Groq LLM questions) and grading."""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import time

import requests

from services.llm_client import groq_available, groq_chat
from services.storage import QUESTION_HISTORY_FILE, get_student_history, load_json, save_json
from services.topics import QUIZ_QUESTIONS, TOPIC_CATALOG, normalize_topic

logger = logging.getLogger(__name__)

MAX_QUIZ_QUESTIONS = 12
MAX_LLM_QUESTIONS = 3
MAX_HISTORY_PER_TOPIC = 100
DUPLICATE_JACCARD_THRESHOLD = 0.75

QUESTION_ANGLES = [
    "practical application with specific dataset",
    "theoretical concept edge case",
    "comparison between two methods",
    "debugging a common mistake",
    "mathematical foundation",
    "real-world industry scenario",
    "optimization and performance tuning",
    "ethical consideration or bias",
    "implementation detail in code",
    "interpretation of results",
]


def _dedupe(items: list) -> list:
    return list(dict.fromkeys(items))


# Grading ---------------------------------------------------------------------

def normalize_answer(answer) -> str:
    """Canonical form used to compare answers.

    LLM options look like "B) text" and their key is "B" -> compare letters.
    Local options are plain text -> compare the full, case-insensitive text.
    """
    text = str(answer or "").strip()
    letter = re.match(r"^([A-Da-d])(?:[).:]\s|$)", text)
    return letter.group(1).upper() if letter else text.casefold()


def answer_key(question: dict) -> str:
    return f"{question['topic']}_{question['index']}"


def is_correct(question: dict, answers: dict) -> bool:
    user = normalize_answer(answers.get(answer_key(question)))
    return user != "" and user == normalize_answer(question.get("answer", ""))


def correct_option(question: dict) -> str:
    """Full text of the correct option (LLM questions store only its letter)."""
    expected = normalize_answer(question.get("answer", ""))
    return next((o for o in question.get("options", []) if normalize_answer(o) == expected), question.get("answer", ""))


def grade_quiz(quiz_items: list[dict], answers: dict) -> dict[str, dict]:
    return {
        answer_key(q): {
            "is_correct": is_correct(q, answers),
            "correct_option": correct_option(q),
            "explanation": q.get("explanation", ""),
        }
        for q in quiz_items
    }


def public_view(quiz_items: list[dict]) -> list[dict]:
    """Quiz as sent to the browser: without answers or explanations."""
    return [{k: v for k, v in q.items() if k not in {"answer", "explanation"}} for q in quiz_items]


# Local question bank -----------------------------------------------------------

def _question_variants(topic: str, idx: int, question: dict, rng: random.Random) -> list[dict]:
    stems = [
        question["q"],
        f"Topic check — {question['q']}",
        f"Choose the best answer for {topic.title()}: {question['q']}",
        f"Quick revision: {question['q']}",
    ]
    variants = []
    for n, stem in enumerate(stems):
        options = list(question.get("options", []))
        rng.shuffle(options)
        variants.append({
            **question,
            "options": options,
            "topic": topic,
            "base_index": idx,
            "index": f"{idx}_{n}_{rng.randint(1000, 9999)}",
            "q": stem,
            "difficulty": question.get("difficulty") or ("beginner" if idx == 0 else "intermediate"),
        })
    return variants


def _sample_distractors(answer: str, pool: list[str], rng: random.Random, k: int = 3) -> list[str]:
    candidates = [p for p in _dedupe(pool) if p and p != answer]
    rng.shuffle(candidates)
    return candidates[:k]


def _generated_questions_for_topic(topic: str, rng: random.Random) -> list[dict]:
    """Questions derived from the topic graph (prerequisites, aliases, project)."""
    meta = TOPIC_CATALOG.get(topic, {})
    prereqs = meta.get("prerequisites", [])
    aliases = meta.get("aliases", [])
    difficulty = "advanced" if len(prereqs) >= 3 else "intermediate" if prereqs else "beginner"
    generated = []

    if prereqs:
        answer = prereqs[0]
        generated.append({
            "q": f"Which topic should usually be learned before {topic.title()}?",
            "options": [answer] + _sample_distractors(answer, list(TOPIC_CATALOG), rng),
            "answer": answer,
            "difficulty": difficulty,
        })
    if aliases:
        answer = aliases[0]
        other_aliases = [a for t, m in TOPIC_CATALOG.items() if t != topic for a in m.get("aliases", [])]
        generated.append({
            "q": f"Which term is most closely related to the syllabus topic {topic.title()}?",
            "options": [answer] + _sample_distractors(answer, other_aliases, rng),
            "answer": answer,
            "difficulty": "beginner",
        })
    project = meta.get("project", "")
    if project:
        verbs = ["Build", "Predict", "Cluster", "Reduce", "Compare", "Clean", "Analyze"]
        answer = next((v for v in verbs if project.lower().startswith(v.lower())), "Build")
        generated.append({
            "q": f"The recommended mini-project for {topic.title()} mainly asks you to do what?",
            "options": [answer] + _sample_distractors(answer, verbs, rng),
            "answer": answer,
            "difficulty": "intermediate",
        })

    for item in generated:
        rng.shuffle(item["options"])
    return generated


def build_local_quiz(topics: list[str], seed: int | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else time.time_ns())
    selected = [t for t in _dedupe(normalize_topic(t) for t in topics) if t in TOPIC_CATALOG] or ["python"]
    selected = selected[:6]
    per_topic = 3 if len(selected) <= 4 else 2

    quiz = []
    for topic in selected:
        bank = list(QUIZ_QUESTIONS.get(topic, [])) + _generated_questions_for_topic(topic, rng)
        variants = [v for idx, q in enumerate(bank) for v in _question_variants(topic, idx, q, rng)]
        rng.shuffle(variants)
        used_base = set()
        for item in variants:
            # One variant per base question, otherwise the same question appears twice reworded.
            if item["base_index"] in used_base:
                continue
            used_base.add(item["base_index"])
            quiz.append(item)
            if len(used_base) >= per_topic:
                break

    rng.shuffle(quiz)
    return quiz[:MAX_QUIZ_QUESTIONS]


# LLM questions with anti-repetition -------------------------------------------

def _question_hash(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


def _is_duplicate(topic: str, question: str, history: dict) -> bool:
    topic_history = history.get(topic, {})
    if _question_hash(question) in topic_history.get("hashes", []):
        return True
    words_new = set(question.lower().split())
    for previous in topic_history.get("questions", [])[-30:]:
        words_old = set(previous.lower().split())
        if words_new and words_old and len(words_new & words_old) / len(words_new | words_old) > DUPLICATE_JACCARD_THRESHOLD:
            return True
    return False


def _remember_question(topic: str, question: str, history: dict) -> None:
    entry = history.setdefault(topic, {"questions": [], "hashes": []})
    entry["questions"] = (entry["questions"] + [question])[-MAX_HISTORY_PER_TOPIC:]
    entry["hashes"] = (entry["hashes"] + [_question_hash(question)])[-MAX_HISTORY_PER_TOPIC:]


def _parse_llm_question(content: str) -> dict:
    """Extract the JSON object from the LLM reply and validate its structure."""
    data = json.loads(content[content.find("{"): content.rfind("}") + 1])
    options = data.get("options")
    if not data.get("question") or not isinstance(options, list) or len(options) != 4:
        raise ValueError("LLM question has an invalid structure")
    if normalize_answer(data.get("correct_answer")) not in {"A", "B", "C", "D"}:
        raise ValueError("LLM correct_answer is not one of A-D")
    return data


def _ask_llm_for_question(topic: str, level: str, previous: list[str], weaknesses: list[str], attempt: int) -> dict:
    avoid = "\n".join(f"- {q[:100]}" for q in previous[-5:])
    prompt = f"""Create ONE unique {level} level multiple-choice question about {topic}.

FOCUS AREAS: {', '.join(random.sample(QUESTION_ANGLES, 2))}
{f"STUDENT WEAKNESSES (focus here): {', '.join(weaknesses)}" if weaknesses else ""}
{f"QUESTIONS ALREADY ASKED (DO NOT REPEAT):{chr(10)}{avoid}" if avoid else ""}

RULES:
- Use a fresh scenario (not iris, MNIST or Titanic)
- Test application, not memorization
- 4 options prefixed "A) ", "B) ", "C) ", "D) " with exactly one correct answer
- Plausible distractors

Reply with JSON only:
{{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "A",
  "explanation": "...", "subtopic": "...", "difficulty": "{level}"}}"""
    content = groq_chat(
        [
            {"role": "system", "content": "You are a creative AI educator. Never repeat questions."},
            {"role": "user", "content": prompt},
        ],
        timeout=30,
        temperature=0.85 + attempt * 0.05,
        top_p=0.92,
        max_tokens=600,
    )
    return _parse_llm_question(content)


def generate_llm_question(topic: str, student_history: list[dict], level: str = "intermediate", max_attempts: int = 3) -> dict | None:
    """Return a new, non-duplicate LLM question, or None if the LLM is unavailable/failing."""
    history = load_json(QUESTION_HISTORY_FILE)
    previous = [h.get("question_text", "") for h in student_history if h.get("topic") == topic]
    weaknesses = _dedupe(h["subtopic"] for h in student_history if not h.get("is_correct") and h.get("subtopic"))

    for attempt in range(max_attempts):
        try:
            question = _ask_llm_for_question(topic, level, previous, weaknesses, attempt)
        except (requests.RequestException, RuntimeError, KeyError, ValueError) as exc:
            logger.warning("LLM question attempt %d for %s failed: %s", attempt + 1, topic, exc)
            continue
        if not _is_duplicate(topic, question["question"], history):
            _remember_question(topic, question["question"], history)
            save_json(QUESTION_HISTORY_FILE, history)
            return question
        previous.append(question["question"])
    return None


def build_quiz(topics: list[str], student_id: str, seed: int | None = None) -> list[dict]:
    """Up to 3 LLM questions (when Groq is configured) completed by the local bank."""
    seed = seed if seed is not None else time.time_ns()
    rng = random.Random(seed)
    selected = [t for t in _dedupe(normalize_topic(t) for t in topics) if t in TOPIC_CATALOG] or ["python"]

    quiz = []
    if groq_available():
        history = get_student_history(student_id)
        for i, topic in enumerate(selected[:MAX_LLM_QUESTIONS]):
            q = generate_llm_question(topic, history)
            if q:
                quiz.append({
                    "topic": topic,
                    "q": q["question"],
                    "options": q["options"],
                    "answer": q["correct_answer"],
                    "difficulty": q.get("difficulty", "intermediate"),
                    "explanation": q.get("explanation", ""),
                    "subtopic": q.get("subtopic", ""),
                    "index": f"llm_{i}_{rng.randint(1000, 9999)}",
                    "source": "llm_groq",
                })

    seen = {q["q"] for q in quiz}
    for q in build_local_quiz(selected, seed=seed):
        if len(quiz) >= MAX_QUIZ_QUESTIONS:
            break
        if q["q"] not in seen:
            quiz.append(q)
    rng.shuffle(quiz)
    return quiz
