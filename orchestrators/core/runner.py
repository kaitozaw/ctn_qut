import twooter.sdk as twooter
from openai import OpenAI
from typing import Any, Dict, List
from .strategy import like_and_repost, post_disinformation, reply_and_boost, reply_and_engage

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    actions_by_persona: Dict[str, List[Dict[str, Any]]],
    role_map: Dict[str, List[str]],
    llm_client: OpenAI,
    ng_words: List[str],
) -> str:
    strategy = (cfg.get("strategy") or "").strip()

    if strategy == "like_and_repost":
        result = like_and_repost(cfg, t, actions, actions_by_persona, role_map)
        return result
    elif strategy == "post_disinformation":
        result = post_disinformation(cfg, t, llm_client, ng_words)
        return result
    elif strategy == "reply_and_boost":
        result = reply_and_boost(cfg, t, actions, actions_by_persona, role_map, llm_client, ng_words)
        return result
    elif strategy == "reply_and_engage":
        result = reply_and_engage(cfg, t, actions, llm_client, ng_words)
        return result
    else:
        return "NO_STRATEGY"