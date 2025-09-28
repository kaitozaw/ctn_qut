import time
import twooter.sdk as twooter
from openai import OpenAI
from queue import Queue
import threading
from typing import Any, Dict, List
from .auth import relogin_for
from .generator import generate_post_of_disinformation, generate_replies_for_boost, generate_replies_for_engage
from .picker import pick_post_fron_user_with_reply, pick_posts_from_feed
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
    send_queue.put(job)

def post_disinformation(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
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
    _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, text=safe_text)

    return "ENQUEUED"

def reply_and_boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    send_queue: Queue,
    lock: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
    role_map: Dict[str, List[str]],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    max_reply_len = 100
    temperature = 0.7
    count = 20

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
        attractors = role_map.get("attractor", [])
        if not attractors:
            return "NO_ATTRACTORS"
        found = False
        while not found:
            for attractor in attractors:
                target_username = attractor
                target_post = pick_post_fron_user_with_reply(cfg, t, target_username)
                if target_post:
                    found = True
                    break
            if not found:
                print("[picker] no target_post found with reply_count>0, retrying in 60s")
                time.sleep(60)
        post_id = target_post.get("id", -1)
        def _like(): return t.post_like(post_id=post_id)
        def _repost(): return t.post_repost(post_id=post_id)
        _enqueue_job(send_queue, lock=lock, fn=_like, relogin_fn=relogin_fn, note="like", persona_id=persona_id, post_id=post_id)
        _enqueue_job(send_queue, lock=lock, fn=_repost, relogin_fn=relogin_fn, note="repost", persona_id=persona_id, post_id=post_id)

        try:
            replies = generate_replies_for_boost(llm_client, target_post, max_reply_len, temperature, count)
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
    _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=reply_id, text=safe_text)
    return "ENQUEUED"

def reply_and_engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    send_queue: Queue,
    lock: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    feed_key = "trending"
    max_reply_len = 200
    temperature = 0.7

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
        target_posts = pick_posts_from_feed(cfg, t, feed_key)
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
    _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=reply_id, text=safe_text)
    return "ENQUEUED"