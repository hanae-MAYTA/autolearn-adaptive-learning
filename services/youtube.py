"""Live YouTube search (optional: only used when YOUTUBE_API_KEY is set)."""
from __future__ import annotations

import logging
import time

import requests

from config import YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# A search costs 100 quota units (10,000/day by default) and dashboard endpoints ask
# for the same topics repeatedly, so results are cached in memory.
CACHE_TTL_SECONDS = 6 * 3600
_cache: dict[tuple, tuple[float, list[dict]]] = {}


def youtube_api_available() -> bool:
    return bool(YOUTUBE_API_KEY)


def search_youtube_videos(query: str, max_results: int = 6, level: str | None = None) -> list[dict]:
    """Return live YouTube results, or an empty list if the API is unavailable or fails."""
    if not YOUTUBE_API_KEY or not query.strip():
        return []

    key = (query.strip().lower(), max_results, level)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    full_query = query.strip() + (f" {level} tutorial machine learning" if level else "")
    try:
        results = _search(full_query, max_results)
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.warning("YouTube search failed for %r: %s", full_query, exc)
        return []
    _cache[key] = (time.time(), results)
    return results


def _search(full_query: str, max_results: int) -> list[dict]:
    search_resp = requests.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "q": full_query,
            "type": "video",
            "maxResults": max_results,
            "videoEmbeddable": "true",
            "safeSearch": "strict",
            "key": YOUTUBE_API_KEY,
        },
        timeout=15,
    )
    search_resp.raise_for_status()
    items = [item for item in search_resp.json().get("items", []) if item.get("id", {}).get("videoId")]
    if not items:
        return []

    video_resp = requests.get(
        YOUTUBE_VIDEOS_URL,
        params={
            "part": "contentDetails,statistics",
            "id": ",".join(item["id"]["videoId"] for item in items),
            "key": YOUTUBE_API_KEY,
        },
        timeout=15,
    )
    video_resp.raise_for_status()
    stats = {
        item["id"]: {
            "duration": item.get("contentDetails", {}).get("duration"),
            "viewCount": item.get("statistics", {}).get("viewCount"),
        }
        for item in video_resp.json().get("items", [])
    }

    results = []
    for item in items:
        video_id = item["id"]["videoId"]
        snippet = item.get("snippet", {})
        meta = stats.get(video_id, {})
        results.append({
            "title": snippet.get("title", "Untitled Video"),
            "channel": snippet.get("channelTitle", "Unknown Channel"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
            "published_at": snippet.get("publishedAt"),
            "description": snippet.get("description", ""),
            "duration": meta.get("duration"),
            "viewCount": meta.get("viewCount"),
            "source": "youtube_api",
        })
    return results
