import twooter.sdk as twooter
from typing import Any, Dict, List, Optional, Set
from .backoff import with_backoff
from .feed import extract_post_fields

def pick_target_mentions_then_keywords(
    t: twooter.Twooter,
    me_username: str,
    feed_key: str,
    keywords: List[str],
    seen_ids: Set[int],
) -> Optional[Dict[str, Any]]:
    feed = with_backoff(lambda: t.feed(feed_key, top_n=20), on_error_note="feed")
    items = (feed or {}).get("data") or []

    me_tag = f"@{me_username}".casefold()
    keys = [k.casefold() for k in (keywords or [])]

    candidates = []
    for d in items:
        pid, content, author = extract_post_fields(d)
        if not pid or not content:
            continue
        if pid in seen_ids:
            continue
        if author and author == me_username:
            continue
        candidates.append({"id": pid, "content": content, "author": author})

    if not candidates:
        return None 

    for c in candidates:
        if me_tag and me_tag in c["content"].casefold():
            return c

    for c in candidates:
        txt = c["content"].casefold()
        if any(k in txt for k in keys):
            return c

    return candidates[0]