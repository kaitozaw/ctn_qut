import random
import twooter.sdk as twooter
from typing import Any, Dict, List, Optional
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
    id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(item)
    target_post = {"id": id, "reply_count": reply_count}

    return target_post

def pick_post_from_attractors(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    attractors: List[str]
) -> Optional[Dict[str, Any]]:
    if not attractors:
        return None
    shuffled = attractors[:]
    random.shuffle(shuffled)
    for target_username in shuffled:
        choice = pick_post_from_user(cfg, t, target_username)
        if choice:
            return choice
    return None

def pick_post_from_user(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    target_username: str
) -> Optional[Dict[str, Any]]:
    posts = pick_posts_from_user(cfg, t, target_username) or []
    if not posts:
        return None
    goal = random.choice([100, 200, 300, 400, 500])
    random.shuffle(posts)
    for post in posts:
        reply_count = int(post.get("reply_count", 0))
        if reply_count < goal:
            return {"id": int(post["id"]), "reply_goal": goal}
    return None

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
        id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(d)
        if id and content and author_username == target_username:
            target_posts.append({"id": id, "reply_count": reply_count, "content": content})
    
    return target_posts

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
        id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(d)
        if not id or not content:
            continue
        if author_username and author_username == persona_id:
            continue
        c = " ".join(content.split())
        target_posts.append({"id": id, "content": c})
    
    return target_posts