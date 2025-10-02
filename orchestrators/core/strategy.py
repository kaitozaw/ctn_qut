import threading
import twooter.sdk as twooter
from openai import OpenAI
from queue import Full, Queue
from typing import Any, Dict, List, Set
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_post, generate_reply_for_boost
from .picker import pick_post_by_id, pick_post_from_notification
from .picker_s3 import get_random_article, read_current, write_current_and_history
from .text_filter import safety_check
from .transform import extract_post_fields

def _enqueue_job(
    send_queue: Queue,
    lock: threading.Lock,
    fn,
    relogin_fn,
    note: str,
    persona_id: str,
    reply_id: int = None,
    post_id: int = None,
    text: str = None,
):
    job = {"lock": lock, "fn": fn, "relogin_fn": relogin_fn, "note": note, "persona_id": persona_id, "reply_id": reply_id, "post_id": post_id, "text": text}
    try:
        send_queue.put_nowait(job)
        return True
    except Full:
        return False

def _generate_and_send_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    ng_words: List[str],
) -> Dict[str, Any]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    article = get_random_article()
    embed_url = (article or {}).get("embed_url", "")
    context = (article or {}).get("context", "")
    max_reply_len = 220
    temperature = 0.7
    
    try:
        text = generate_post(llm_client, context, max_reply_len, temperature)
    except Exception as e:
        print(f"[llm] generate_replies error: {e}")
        return None

    ok, safe_text, reason = safety_check(text, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason}")
        return None
    
    post_create= with_backoff(
        lambda: t.post(safe_text, embed=embed_url if embed_url else None),
        on_error_note="post_create",
        relogin_fn=relogin_fn
    )

    item = (post_create or {}).get("data") or {}
    id, parent_id, like_count, repost_count, reply_count, content, author_username = extract_post_fields(item)
    print(f"[sent] persona={persona_id} post_id={id} text={content!r}")
    post = {"id": id}

    return post

def attract(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    persona_list: List[str],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    GOAL = 100
    cur = read_current()

    if not cur:
        target_post = _generate_and_send_post(cfg, t, llm_client, ng_words)
        if not target_post:
            return "NO_TARGET_POST"
        write_current_and_history(target_post["id"], GOAL)
        return "SET NEW POST"
    
    post_id = cur.get("post_id")
    reply_goal = cur.get("reply_goal")
    if not isinstance(post_id, int) or not isinstance(reply_goal, int):
        return "INVALID_CURRENT_JSON"
    post = pick_post_by_id(cfg, t, post_id) or {}
    reply_count = post.get("reply_count", 0)

    if reply_count >= reply_goal:
        parent_id = post.get("parent_id", 0)
        if parent_id:
            target_post = _generate_and_send_post(cfg, t, llm_client, ng_words)
            if not target_post:
                return "NO_TARGET_POST"
        else:
            target_post = pick_post_from_notification(cfg, t, post_id, persona_list)
            if not target_post:
                return "NO_TARGET_POST"
        write_current_and_history(target_post["id"], GOAL)
        return "SET NEW POST"
    
    return "CONTINUE CURRENT POST"

def boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    sent_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    cur = read_current()
    post_id = cur.get("post_id")
    if not isinstance(post_id, int):
        return "INVALID_CURRENT_JSON"
    
    if post_id not in sent_posts:
        def _like(): return t.post_like(post_id=post_id)
        def _repost(): return t.post_repost(post_id=post_id)
        if lock:
            with lock:
                try:
                    with_backoff(_like, on_error_note="like", relogin_fn=relogin_fn)
                except Exception as e:
                    pass
                try:
                    with_backoff(_repost, on_error_note="repost", relogin_fn=relogin_fn)
                except Exception as e:
                    pass
        else:
            try:
                with_backoff(_like, on_error_note="like", relogin_fn=relogin_fn)
            except Exception as e:
                pass
            try:
                with_backoff(_repost, on_error_note="repost", relogin_fn=relogin_fn)
            except Exception as e:
                pass
        sent_posts.add(post_id)
    
    text = generate_reply_for_boost()
    def _send(): return t.post(text, parent_id=post_id)
    enq = _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=post_id, text=text)
    if not enq:
        return "SKIPPED"
    return "ENQUEUED"