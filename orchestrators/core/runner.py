import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List, Set
from .backoff import with_backoff
from .generator import generate_reply
from .safety import safety_check
from .picker import pick_target_mentions_then_keywords

def run_once(
    t: twooter.Twooter,
    me_username: str,
    cfg: Dict[str, Any],
    seen_ids: Set[int],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    strategy = (cfg.get("strategy") or "mentions_then_keywords").strip()
    feed_key = (cfg.get("feed_key") or "home").strip()
    keywords = cfg.get("keywords") or []

    if strategy == "reply_and_engage":
        target = pick_target_mentions_then_keywords(t, me_username, feed_key, keywords, seen_ids)
        if not target:
            return "NO_TARGET"

        target_id = int(target["id"])
        target_text = target["content"]
        seen_ids.add(target_id)

        persona = cfg.get("persona", {}) or {}
        context = cfg.get("context", {}) or {}
        max_reply_len = 240
        temperature = 0.7

        reply = generate_reply(llm_client, target_text, persona, context, max_reply_len, temperature)

        ok, safe_text, reason = safety_check(reply, ng_words, max_reply_len, hard_max_len=255)
        if not ok:
            print(f"[safety] blocked: reason={reason} target_id={target_id}")
            return "BLOCKED"

        def _send():
            return t.post(safe_text, parent_id=target_id)
        
        try:
            with_backoff(
                _send,
                on_error_note="post"
            )
            print(f"[sent] reply_to={target_id} len={len(safe_text)} text={safe_text!r}")
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
            print(f"[post-error] status={status} target_id={target_id} len={len(safe_text)} body={body[:500]!r}")
            return "ERROR"

    else:
        return "NO_STRATEGY"