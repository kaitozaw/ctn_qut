import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_replies
from .safety import safety_check
from .picker import pick_posts_replyto

def reply_and_engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    me_username: str,
    actions: List[Dict[str, Any]],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    feed_key = "trending"
    max_reply_len = 150
    temperature = 0.7

    if actions is None:
        return "ACTIONS_IS_NONE"

    if not actions:
        target_posts = pick_posts_replyto(cfg, t, me_username, feed_key)
        if not target_posts:
            return "NO_TARGET_POSTS"
        
        try:
            replies = generate_replies(llm_client, target_posts, max_reply_len, temperature)
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
