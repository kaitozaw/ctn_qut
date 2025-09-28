import twooter.sdk as twooter
from openai import OpenAI
from queue import Queue
from typing import Any, Dict, List
from .strategy import post_disinformation, reply_and_boost, reply_and_engage
import threading

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: List[Dict[str, Any]],
    send_queue: Queue,
    locks: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
    role_map: Dict[str, List[str]],
) -> str:
    strategy = (cfg.get("strategy") or "").strip()

    if strategy == "post_disinformation":
        result = post_disinformation(cfg, t, actions, send_queue, locks, llm_client, ng_words)
        return result
    elif strategy == "reply_and_boost":
        result = reply_and_boost(cfg, t, actions, send_queue, locks, llm_client, ng_words, role_map)
        return result
    elif strategy == "reply_and_engage":
        result = reply_and_engage(cfg, t, actions, send_queue, locks, llm_client, ng_words)
        return result
    else:
        return "NO_STRATEGY"