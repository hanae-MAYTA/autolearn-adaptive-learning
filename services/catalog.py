"""Content-based ranking of videos, courses and mini-projects from the curated catalogs.

Each ranking is a transparent weighted score (topic similarity, level match, popularity,
quality, recency). The weights are hand-tuned heuristics, not learned from user feedback.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from config import CATALOG_DIR
from services.topics import TOPIC_CATALOG, normalize_topic
from services.youtube import search_youtube_videos

LEVEL_WEIGHT = {"beginner": 1.0, "intermediate": 1.2, "advanced": 1.35}


@lru_cache(maxsize=1)
def load_video_catalog() -> pd.DataFrame:
    df = pd.read_csv(CATALOG_DIR / "youtube_videos_catalog.csv")
    # The same video is listed under several topics; keep its first occurrence.
    return df.drop_duplicates(subset="url").reset_index(drop=True)


@lru_cache(maxsize=1)
def load_course_catalog() -> pd.DataFrame:
    df = pd.read_csv(CATALOG_DIR / "online_courses_catalog.csv")
    for col in ["certificate", "verified"]:
        df[col] = df[col].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


@lru_cache(maxsize=1)
def load_project_catalog() -> pd.DataFrame:
    return pd.read_csv(CATALOG_DIR / "mini_projects_catalog.csv")


def _topic_similarity(candidate_topic: str, requested_topic: str) -> float:
    """1.0 for an exact match, otherwise Jaccard similarity of the words."""
    a, b = str(candidate_topic).lower(), str(requested_topic).lower()
    if a == b:
        return 1.0
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _log_popularity(counts: pd.Series, cap: float) -> pd.Series:
    return np.minimum(np.log10(counts.astype(float).clip(lower=1.0)), cap)


def rank_catalog_videos(topic: str, level: str, max_results: int = 6) -> list[dict]:
    df = load_video_catalog().copy()
    df["score"] = (
        df["quality_score"].astype(float) * 0.42
        + df["topic"].map(lambda t: _topic_similarity(t, topic)) * 3.2
        + (df["level"].str.lower() == level.lower()) * 1.8
        + _log_popularity(df["views"], cap=8.0) * 0.35
        + (df["published_year"].astype(float) - 2018).clip(lower=0) * 0.08
    )
    top = df.sort_values(["score", "views", "quality_score"], ascending=False).head(max_results)
    return [
        {
            "title": r.title,
            "channel": r.channel,
            "url": r.url,
            "viewCount": int(r.views),
            "duration": f"{int(r.duration_minutes)} min",
            "published_at": f"{int(r.published_year)}-01-01T00:00:00Z",
            "source": "youtube_dataset_csv",
            "rank_score": round(float(r.score), 3),
        }
        for r in top.itertuples()
    ]


def _score_live_video(video: dict, topic: str, level: str) -> float:
    title = str(video.get("title", "")).lower()
    views = float(video.get("viewCount") or 0)
    published_year = str(video.get("published_at", ""))[:4]
    is_recent = published_year.isdigit() and date.today().year - int(published_year) <= 2
    return (
        (1.8 if topic.lower() in title else 0.9)
        + (0.8 if level.lower() in title else 0.2)
        + (0.6 if is_recent else 0.25)
        + min(np.log10(max(views, 1.0)), 8.0) * 0.3
        + (0.2 if "tutorial" in title else 0.0)
    )


def rank_live_and_dataset_videos(topic: str, level: str, live_videos: list[dict], max_results: int = 8) -> list[dict]:
    """Merge live API results with catalog videos, deduplicated by URL."""
    combined, seen = [], set()
    for video in live_videos:
        url = video.get("url")
        if url and url not in seen:
            combined.append({**video, "rank_score": round(_score_live_video(video, topic, level), 3)})
            seen.add(url)
    for video in rank_catalog_videos(topic, level, max_results=max_results):
        if video["url"] not in seen:
            combined.append(video)
            seen.add(video["url"])
    combined.sort(key=lambda v: float(v.get("rank_score", 0)), reverse=True)
    return combined[:max_results]


def rank_courses(topic: str, level: str, provider: str = "all", max_results: int = 6) -> list[dict]:
    df = load_course_catalog().copy()
    if provider != "all":
        df = df[df["platform"].str.lower() == provider.lower()]
    df["score"] = (
        df["topic"].map(lambda t: _topic_similarity(t, topic)) * 3.0
        + (df["level"].str.lower() == level.lower()) * 1.8
        + df["rating"].astype(float) * 0.85
        + _log_popularity(df["learners"], cap=7.0) * 0.45
        + df["certificate"].astype(int) * 0.5
        + df["verified"].astype(int) * 0.45
    )
    top = df.sort_values(["score", "rating", "learners"], ascending=False).head(max_results)
    return [
        {
            "title": r.title,
            "provider": r.platform,
            "url": r.url,
            "certificate": bool(r.certificate),
            "verified": bool(r.verified),
            "rating": float(r.rating),
            "learners": int(r.learners),
            "duration_hours": int(r.duration_hours),
            "level": r.level,
            "source": r.dataset_source,
            "rank_score": round(float(r.score), 3),
        }
        for r in top.itertuples()
    ]


def project_for_topic(topic: str, level: str) -> str:
    df = load_project_catalog().copy()
    difficulty_gap = (df["difficulty"].str.lower().map(LEVEL_WEIGHT).fillna(1.0) - LEVEL_WEIGHT.get(level.lower(), 1.0)).abs()
    df["score"] = df["topic"].map(lambda t: _topic_similarity(t, topic)) * 3 - difficulty_gap
    return str(df.sort_values("score", ascending=False).iloc[0]["project"])


def get_recommendations(topic: str, level: str, provider: str = "all", video_mode: str = "hybrid") -> dict:
    """Videos (live API and/or catalog), courses and a mini-project for one topic."""
    topic = normalize_topic(topic)
    live_videos = search_youtube_videos(topic, max_results=6, level=level) if video_mode in {"hybrid", "live"} else []

    if video_mode == "live":
        videos = live_videos or rank_catalog_videos(topic, level, max_results=6)
        video_source = "live_youtube_api" if live_videos else "youtube_dataset_csv_fallback"
    elif video_mode == "dataset":
        videos = rank_catalog_videos(topic, level, max_results=6)
        video_source = "youtube_dataset_csv"
    else:
        videos = rank_live_and_dataset_videos(topic, level, live_videos, max_results=8)
        video_source = "hybrid_live_plus_dataset" if live_videos else "youtube_dataset_csv"

    courses = rank_courses(topic, level, provider=provider, max_results=6)
    if not courses and topic in TOPIC_CATALOG:
        courses = TOPIC_CATALOG[topic]["courses"]
    return {
        "videos": videos,
        "courses": courses,
        "project": project_for_topic(topic, level),
        "video_source": video_source,
    }
