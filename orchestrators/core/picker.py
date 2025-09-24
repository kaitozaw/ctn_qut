import twooter.sdk as twooter
from typing import Any, Dict, List
from .backoff import with_backoff
from .feed import extract_post_fields

def pick_target_posts(
    t: twooter.Twooter,
    me_username: str,
    feed_key: str,
) -> List[Dict[str, Any]]:
    feed = with_backoff(
        lambda: t.feed(feed_key, top_n=20),
        on_error_note="feed"
    )
    items = (feed or {}).get("data") or []

    target_posts = []
    for d in items:
        pid, content, author = extract_post_fields(d)
        if not pid or not content:
            continue
        if author and author == me_username:
            continue
        c = " ".join(content.split())
        target_posts.append({"id": pid, "content": c})
    
    return target_posts