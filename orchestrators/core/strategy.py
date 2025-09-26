import random
import time
import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_replies_for_boost, generate_replies_for_engage
from .text_filter import safety_check
from .picker import pick_posts_engage, pick_post_boost, pick_post_support

def like_and_repost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    actions_by_persona: Dict[str, List[Dict[str, Any]]],
    role_map: Dict[str, List[str]],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
        attractors = role_map.get("attractor", [])
        if attractors:
            target_username = random.choice(attractors)
        else:
            return "NO_ATTRACTORS"

        target_post = pick_post_support(cfg, t, target_username)
        if not target_post:
            return "NO_TARGET_POST"
        
        for persona_id in actions_by_persona:
            actions_by_persona[persona_id].extend([target_post])
    
    action = actions.pop(0)
    post_id = action.get("id", -1)

    def _like():
        return t.post_like(post_id=post_id)
    
    def _repost():
        return t.post_repost(post_id=post_id)
    
    try:
        did_like = False
        did_repost = False
        
        if random.random() < 0.6:
            with_backoff(
                _like,
                on_error_note="like",
                relogin_fn=relogin_fn
            )
            print(f"[like] post_id={post_id}")
            did_like = True

        if random.random() < 0.8:
            with_backoff(
                _repost,
                on_error_note="repost",
                relogin_fn=relogin_fn
            )
            print(f"[repost] post_id={post_id}")
            did_repost = True

        if did_like and did_repost:
            return "LIKED_AND_REPOSTED"
        elif did_like:
            return "LIKED_ONLY"
        elif did_repost:
            return "REPOSTED_ONLY"
        else:
            return "SKIPPED"
    except Exception as e:
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                body = resp.text
        except Exception:
            pass
        print(f"[like/repost-error] status={status} post_id={post_id} body={body[:500]!r}")
        return "ERROR"

def reply_and_boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    actions_by_persona: Dict[str, List[Dict[str, Any]]],
    role_map: Dict[str, List[str]],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    count = 20
    max_reply_len = 100
    temperature = 0.7

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
                target_post = pick_post_boost(cfg, t, target_username)
                if target_post:
                    found = True
                    break
            if not found:
                print("[picker] no target_post found with reply_count>0, retrying in 60s")
                time.sleep(60)

        for persona_id in actions_by_persona:
            try:
                replies = generate_replies_for_boost(llm_client, target_post, count, max_reply_len, temperature)
            except Exception as e:
                print(f"[llm] generate_replies error: {e}")
                return "LLM_ERROR"
            actions_by_persona[persona_id].extend(replies)
        
    action = actions.pop(0)
    reply_id  = action.get("id", -1)
    reply  = (action.get("reply") or "").strip()

    def _like():
        return t.post_like(post_id=reply_id)
    
    def _repost():
        return t.post_repost(post_id=reply_id)
    
    if len(actions) == count - 1:
        try:
            with_backoff(
                _like,
                on_error_note="like",
                relogin_fn=relogin_fn
            )
            print(f"[like] post_id={reply_id}")

            with_backoff(
                _repost,
                on_error_note="repost",
                relogin_fn=relogin_fn
            )
            print(f"[repost] post_id={reply_id}")
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
            body = ""
            try:
                resp = getattr(e, "response", None)
                if resp is not None:
                    body = resp.text
            except Exception:
                pass
            print(f"[like/repost-error] status={status} post_id={reply_id} body={body[:500]!r}")

    ok, safe_text, reason = safety_check(reply, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason} reply_id={reply_id}")
        return "BLOCKED"
    
    def _send():
        return t.post(safe_text, parent_id=reply_id)
    
    try:
        with_backoff(
            _send,
            on_error_note="post",
            relogin_fn=relogin_fn
        )
        print(f"[sent] reply_to={reply_id} len={len(safe_text)} text={safe_text!r}")
        return "SENT"
    except Exception as e:
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                body = resp.text
        except Exception:
            pass
        print(f"[post-error] status={status} reply_id={reply_id} len={len(safe_text)} body={body[:500]!r}")
        return "ERROR"

def reply_and_engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
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
        target_posts = pick_posts_engage(cfg, t, feed_key)
        if not target_posts:
            return "NO_TARGET_POSTS"
        
        try:
            replies = generate_replies_for_engage(llm_client, target_posts, max_reply_len, temperature)
        except Exception as e:
            print(f"[llm] generate_replies error: {e}")
            return "LLM_ERROR"

        actions.extend(replies)

    action = actions.pop(0)
    reply_id  = action.get("id", -1)
    reply  = (action.get("reply") or "").strip()

    ok, safe_text, reason = safety_check(reply, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason} reply_id={reply_id}")
        return "BLOCKED"

    def _send():
        return t.post(safe_text, parent_id=reply_id)
    
    try:
        with_backoff(
            _send,
            on_error_note="post",
            relogin_fn=relogin_fn
        )
        print(f"[sent] reply_to={reply_id} len={len(safe_text)} text={safe_text!r}")
        return "SENT"
    except Exception as e:
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                body = resp.text
        except Exception:
            pass
        print(f"[post-error] status={status} reply_id={reply_id} len={len(safe_text)} body={body[:500]!r}")
        return "ERROR"