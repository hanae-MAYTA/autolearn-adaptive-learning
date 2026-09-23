def _start(client):
    resp = client.post("/api/start", json={"syllabus_text": "python, statistics", "target_goal": "data analyst"})
    assert resp.status_code == 200
    return resp.get_json()


def test_status(client):
    body = client.get("/api/status").get_json()
    assert body["ok"] is True and body["model"]


def test_quiz_requires_a_plan(client):
    assert client.get("/api/quiz").status_code == 400


def test_full_quiz_flow(client):
    start = _start(client)
    assert start["profile"]["topics"][0] == "python"
    quiz = client.get("/api/quiz").get_json()["quizItems"]
    assert quiz and all("answer" not in q for q in quiz)

    answers = {f"{q['topic']}_{q['index']}": q["options"][0] for q in quiz}
    result = client.post("/api/quiz", json={"answers": answers}).get_json()
    assert result["ok"] is True
    assert set(result["graded"]) == set(answers)
    for topic_result in result["assessment"]:
        assert 0 <= topic_result["predicted_exam_score"] <= 100
        assert topic_result["predicted_level"] in {"beginner", "intermediate", "advanced"}
    assert result["learningPath"] and result["resources"]


def test_video_tracking_and_progress(client):
    _start(client)
    url = "https://www.youtube.com/watch?v=abc"
    client.post("/api/path/video/track", json={"topic": "python", "url": url, "watched_pct": 85})
    assert client.get("/api/path/video/progress").get_json()[url] == {"watched_pct": 85.0, "completed": True}


def test_invalid_status_is_rejected(client):
    _start(client)
    resp = client.post("/api/path/update", json={"topic": "python", "status": "banana"})
    assert resp.status_code == 400
