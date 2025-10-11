import twooter.sdk as twooter
from typing import Any, Dict, List
from .auth import relogin_for
from .backoff import with_backoff
from .transform import extract_post_fields

def pick_post_by_id(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    post_id: int,
) -> Dict[str, Any]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    post_get = with_backoff(
        lambda: t.post_get(post_id),
        on_error_note="post_get",
        relogin_fn=relogin_fn
    )
    item = (post_get or {}).get("data") or {}
    
    target_post = extract_post_fields(item)
    return target_post

def pick_post_from_feed_by_user(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    feed_key: str,
    username: str,
) -> Dict[str, Any]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    feed = with_backoff(
        lambda: t.feed(feed_key, top_n=20),
        on_error_note="feed",
        relogin_fn=relogin_fn
    )
    items = (feed or {}).get("data") or []

    target_post = {}
    for d in items:
        post = extract_post_fields(d)
        if post["author_username"] == username:
            target_post = post
            break
    return target_post

def pick_posts_from_feed(
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
        target_post = extract_post_fields(d)
        target_posts.append(target_post)
    return target_posts

def pick_posts_from_notification(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
) -> List[Dict[str, Any]]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    notifications_list = with_backoff(
        lambda: t.notifications_list(),
        on_error_note="notifications_list",
        relogin_fn=relogin_fn
    )
    items = (notifications_list or {}).get("data") or []

    target_posts = []
    for d in items:
        post = d.get("post") or {}
        target_post = extract_post_fields(post)
        target_posts.append(target_post)
    return target_posts

def pick_posts_from_user(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    target_username: str,
) -> List[Dict[str, Any]]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    user_activity = with_backoff(
        lambda: t.user_activity(target_username),
        on_error_note="user_activity",
        relogin_fn=relogin_fn
    )
    items = (user_activity or {}).get("data") or []

    target_posts = []
    for d in items:
        target_post = extract_post_fields(d)
        target_posts.append(target_post)
    return target_posts