from typing import Any, Dict, Optional, Tuple

def extract_post_fields(d: Dict[str, Any]) -> Tuple[Optional[int], str, str]:
    post = d.get("post") or {}
    pid = d.get("id") or post.get("id")
    content = (d.get("content") or post.get("content") or "") or ""
    content = content.strip()
    author = (d.get("author") or post.get("author") or {}) or {}
    username = (author.get("username") or "").strip()
    try:
        pid = int(pid) if pid is not None else None
    except Exception:
        pid = None
    return pid, content, username