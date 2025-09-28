import random
import threading
import twooter.sdk as twooter
from collections import deque
from openai import OpenAI
from queue import Full, Queue
from typing import Any, Dict, List, Set
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_post_of_disinformation, generate_replies_for_boost, generate_replies_for_engage
from .picker import pick_post_by_id, pick_post_from_attractors, pick_posts_from_user
from .picker_s3 import read_current, write_current_and_history
from .text_filter import safety_check

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
    job = {
        "lock": lock,
        "fn": fn,
        "relogin_fn": relogin_fn,
        "note": note,
        "persona_id": persona_id,
        "reply_id": reply_id,
        "post_id": post_id,
        "text": text, 
    }
    try:
        send_queue.put_nowait(job)
        return True
    except Full:
        return False

def pick_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    role_map: Dict[str, List[str]],
) -> str:
    attractors = role_map.get("attractor", [])
    if not attractors:
        return "NO_ATTRACTORS"

    cur = read_current()

    if not cur:
        choice = pick_post_from_attractors(cfg, t, attractors)
        if not choice:
            return "NO_CANDIDATE"
        write_current_and_history(choice["id"], choice["reply_goal"])
        return "SET NEW POST"

    post_id = cur.get("post_id")
    reply_goal = cur.get("reply_goal")
    if not isinstance(post_id, int) or not isinstance(reply_goal, int):
        return "INVALID_CURRENT_JSON"

    post = pick_post_by_id(cfg, t, post_id) or {}
    reply_count = int(post.get("reply_count", 0))

    if reply_count >= reply_goal:
        choice = pick_post_from_attractors(cfg, t, attractors)
        if not choice:
            return "NO_CANDIDATE"
        write_current_and_history(choice["id"], choice["reply_goal"])
        return "SET NEW POST"

    return "CONTINUE CURRENT POST"

def post_disinformation(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: deque,
    sent_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    target_text = """
        Paradise Lost? Who really benefits from Kingston's tourism boom?
        Headlines celebrate record highs in visitor numbers and a "vibrant culture", but questions remain about who gains. 
        Fishermen in New Haven face threats from trawlers, and the fragile ecosystem struggles under climate change. 
        Critics argue the boom enriches wealthy resort owners and foreign investors while leaving average Kingstonians behind. 
        Observers warn that the pursuit of paradise risks sacrificing both community livelihoods and environmental sustainability. 
        The call is for a future where progress benefits all citizens, and natural heritage is protected—not plundered.
    """
    max_reply_len = 200
    temperature = 0.7
    embed_url = "https://kingston-herald.legitreal.com/post/2025-09-20-paradise-lost-who-really-benefits-from-kingstons-tourism-boom/"

    try:
        text = generate_post_of_disinformation(llm_client, target_text, max_reply_len, temperature)
    except Exception as e:
        print(f"[llm] generate_replies error: {e}")
        return "LLM_ERROR"
    
    ok, safe_text, reason = safety_check(text, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason}")
        return "BLOCKED"
    
    def _send(): return t.post(safe_text, embed=embed_url)
    enq = _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, text=safe_text)
    if not enq:
        return "SKIPPED"
    return "ENQUEUED"

def reply_and_boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: deque,
    sent_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    count = 20

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
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

        try:
            replies = generate_replies_for_boost(post_id, count)
        except Exception as e:
            print(f"[llm] generate_replies error: {e}")
            return "LLM_ERROR"
        actions.extend(replies)
        
    action = actions.popleft()
    reply_id  = action.get("id", -1)
    reply  = (action.get("reply") or "").strip()

    ok, safe_text, reason = safety_check(reply, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason} reply_id={reply_id}")
        return "BLOCKED"
    
    def _send(): return t.post(safe_text, parent_id=reply_id)
    enq = _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=reply_id, text=safe_text)
    if not enq:
        return "SKIPPED"
    return "ENQUEUED"

def reply_and_engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: deque,
    sent_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    target_username = random.choice(["alex.martin", "sophia_lee23", "daniel_james", "emily.r98"])
    max_reply_len = 200
    temperature = 0.7

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
        target_posts = pick_posts_from_user(cfg, t, target_username)
        if not target_posts:
            return "NO_TARGET_POSTS"
        try:
            replies = generate_replies_for_engage(llm_client, target_posts, max_reply_len, temperature)
        except Exception as e:
            print(f"[llm] generate_replies error: {e}")
            return "LLM_ERROR"
        actions.extend(replies)

    action = actions.popleft()
    reply_id  = action.get("id", -1)
    reply  = (action.get("reply") or "").strip()

    ok, safe_text, reason = safety_check(reply, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason} reply_id={reply_id}")
        return "BLOCKED"
    
    def _send(): return t.post(safe_text, parent_id=reply_id)
    enq = _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=reply_id, text=safe_text)
    if not enq:
        return "SKIPPED"
    return "ENQUEUED"