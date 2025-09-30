from typing import Any, Dict, Optional, Tuple

def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def extract_post_fields(d: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int], str, str]:
    id = _safe_int(d.get("id"))
    like_count = _safe_int(d.get("like_count"))
    repost_count = _safe_int(d.get("repost_count"))
    reply_count = _safe_int(d.get("reply_count"))
    content = (d.get("content") or "").strip()
    author = (d.get("author") or {})
    author_username = (author.get("username") or "").strip()

    return id, like_count, repost_count, reply_count, content, author_username