import twooter.sdk as twooter
from collections import deque
from openai import OpenAI
from queue import Queue
from typing import Any, Dict, List, Set
from .strategy import pick_post, post_disinformation, reply_and_boost, reply_and_engage
import threading

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    actions: deque,
    sent_posts: Set[int],
    send_queue: Queue,
    locks: threading.Lock,
    llm_client: OpenAI,
    ng_words: List[str],
    role_map: Dict[str, List[str]],
) -> str:
    strategy = (cfg.get("strategy") or "").strip()

    if strategy == "pick_post":
        result = pick_post(cfg, t, role_map)
        return result
    elif strategy == "post_disinformation":
        result = post_disinformation(cfg, t, actions, sent_posts, send_queue, locks, llm_client, ng_words)
        return result
    elif strategy == "reply_and_boost":
        result = reply_and_boost(cfg, t, actions, sent_posts, send_queue, locks, ng_words)
        return result
    elif strategy == "reply_and_engage":
        result = reply_and_engage(cfg, t, actions, sent_posts, send_queue, locks, llm_client, ng_words)
        return result
    else:
        return "NO_STRATEGY"