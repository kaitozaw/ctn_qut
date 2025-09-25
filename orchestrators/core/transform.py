from typing import Any, Dict, Optional, Tuple

def extract_post_fields(d: Dict[str, Any]) -> Tuple[Optional[int], str, str]:
    id = d.get("id")
    content = (d.get("content") or "").strip()
    author = (d.get("author") or {})
    author_username = (author.get("username") or "").strip()

    try:
        id = int(id) if id is not None else None
    except Exception:
        id = None

    return id, content, author_username