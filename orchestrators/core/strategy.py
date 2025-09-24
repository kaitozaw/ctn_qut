import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List, Set
from .backoff import with_backoff
from .generator import generate_replies
from .safety import safety_check
from .picker import pick_target_posts

def reply_and_engage(
    t: twooter.Twooter,
    me_username: str,
    actions: List[Dict[str, Any]],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    feed_key = "trending"
    max_reply_len = 150
    temperature = 0.7

    if not actions:
        target_posts = pick_target_posts(t, me_username, feed_key)
        replies = generate_replies(llm_client, target_posts, max_reply_len, temperature)
        actions.extend(replies)

    action = actions.pop(0)
    reply_id = action["id"]
    reply = action["reply"]

    ok, safe_text, reason = safety_check(reply, ng_words, max_reply_len, hard_max_len=255)
    if not ok:
        print(f"[safety] blocked: reason={reason} reply_id={reply_id}")
        return "BLOCKED"

    def _send():
        return t.post(safe_text, parent_id=reply_id)
    
    try:
        with_backoff(
            _send,
            on_error_note="post"
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
