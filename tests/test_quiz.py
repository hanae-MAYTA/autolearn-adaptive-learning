from services.quiz import build_local_quiz, grade_quiz, normalize_answer, public_view


def test_answers_starting_with_same_letter_are_not_confused():
    # Regression: the old grader only compared the first letter when it was A-D.
    question = {"topic": "clustering", "index": "0", "options": ["Clustering", "Classification"], "answer": "Clustering"}
    graded = grade_quiz([question], {"clustering_0": "Classification"})
    assert graded["clustering_0"]["is_correct"] is False


def test_llm_letter_answer_matches_full_option():
    question = {"topic": "nlp", "index": "llm_0", "options": ["A) Tokens", "B) Pixels", "C) Rows", "D) Trees"], "answer": "A"}
    graded = grade_quiz([question], {"nlp_llm_0": "A) Tokens"})
    assert graded["nlp_llm_0"] == {"is_correct": True, "correct_option": "A) Tokens", "explanation": ""}


def test_unanswered_question_is_wrong():
    question = {"topic": "python", "index": "1", "options": ["x"], "answer": "x"}
    assert grade_quiz([question], {})["python_1"]["is_correct"] is False


def test_normalize_answer():
    assert normalize_answer("b) something") == "B"
    assert normalize_answer("Adam") == "adam"
    assert normalize_answer(None) == ""


def test_local_quiz_is_reproducible_and_hides_answers():
    quiz_a = build_local_quiz(["python", "statistics"], seed=1)
    quiz_b = build_local_quiz(["python", "statistics"], seed=1)
    assert quiz_a == quiz_b
    assert 0 < len(quiz_a) <= 12
    assert all(q["answer"] in q["options"] for q in quiz_a)
    assert all("answer" not in q for q in public_view(quiz_a))
