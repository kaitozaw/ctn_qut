import twooter.sdk as twooter
from typing import Any, Dict, List
from .auth import relogin_for
from .backoff import with_backoff
from .transform import extract_post_fields

def pick_post_boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    target_username: str,       
) -> Dict[str, Any]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    user_activity = with_backoff(
        lambda: t.user_activity(target_username),
        on_error_note="user_activity",
        relogin_fn=relogin_fn
    )
    items = (user_activity or {}).get("data") or []

    target_post = {}
    for d in items:
        id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(d)
        if id and (reply_count or 0) > 0 and content and author_username == target_username:
            c = " ".join(content.split())
            target_post["id"] = id
            target_post["content"] = c
            break
    
    return target_post

def pick_posts_engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    feed_key: str,
) -> List[Dict[str, Any]]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    feed = with_backoff(
        lambda: t.feed(feed_key, top_n=20),
        on_error_note="feed",
        relogin_fn=relogin_fn
    )
    items = (feed or {}).get("data") or []

    target_posts = []
    for d in items:
        id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(d)
        if not id or not content:
            continue
        if author_username and author_username == persona_id:
            continue
        c = " ".join(content.split())
        target_posts.append({"id": id, "content": c})
    
    return target_posts

def pick_post_support(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    target_username: str,
) -> Dict[str, Any]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    user_activity = with_backoff(
        lambda: t.user_activity(target_username),
        on_error_note="user_activity",
        relogin_fn=relogin_fn
    )
    items = (user_activity or {}).get("data") or []

    target_post = {}
    for d in items:
        id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(d)
        if id and (like_count or 0) == 0 and (repost_count or 0) == 0 and content and author_username == target_username:
            target_post["id"] = id
            break
    
    return target_post