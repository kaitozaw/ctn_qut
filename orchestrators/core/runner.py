import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List
from .strategy import reply_and_engage

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    me_username: str,
    actions: List[Dict[str, Any]],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    strategy = (cfg.get("strategy") or "").strip()

    if strategy == "reply_and_engage":
        result = reply_and_engage(cfg, t, me_username, actions, llm_client, ng_words)
        return result
    else:
        return "NO_STRATEGY"