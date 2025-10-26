from typing import Any, Dict, Optional, Tuple, List

def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def extract_post_fields(d: Dict[str, Any], *fields: str) -> Dict[str, Any]:
    author = d.get("author") or {}
    tags = d.get("tags") or []
    tag_names: List[str] = [t.get("name", "").strip() for t in tags if isinstance(t, dict)]

    all_fields = {
        "id": _safe_int(d.get("id")),
        "author_id": _safe_int(author.get("id")),
        "author_username": (author.get("username") or "").strip(),
        "author_follower_count": _safe_int(author.get("follower_count")),
        "author_following_count": _safe_int(author.get("following_count")),
        "author_verified": bool(author.get("verified")),
        "like_count": _safe_int(d.get("like_count")),
        "repost_count": _safe_int(d.get("repost_count")),
        "reply_count": _safe_int(d.get("reply_count")),
        "created_at": (d.get("created_at") or "").strip(),
        "parent_id": _safe_int(d.get("parent_id")),
        "embed": (d.get("embed") or "").strip() or None,
        "content": (d.get("content") or "").strip(),
        "tags": tag_names,
    }

    if fields:
        return {k: all_fields.get(k) for k in fields}

    return all_fields