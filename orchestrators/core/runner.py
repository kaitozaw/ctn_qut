import twooter.sdk as twooter
from openai import OpenAI
from queue import Queue
from typing import Any, Dict, List, Set
from .strategy import attract, boost
import threading

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    strategy: str,
    llm_client: OpenAI,
    ng_words: List[str],
    replied_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
) -> str:
    if strategy == "attract":
        result = attract(cfg, t, llm_client, ng_words, replied_posts)
        return result
    elif strategy == "boost":
        result = boost(cfg, t, replied_posts, send_queue, lock)
        return result
    else:
        return "NO_STRATEGY"