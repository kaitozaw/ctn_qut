import twooter.sdk as twooter
from collections import deque
from openai import OpenAI
from queue import Queue
from typing import Any, Dict, List, Set
from .strategy import attract, boost
import threading

def run_once(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    strategy: str,
    persona_list: List[str],
    llm_client: OpenAI,
    ng_words: List[str],
    sent_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
) -> str:
    if strategy == "attract":
        result = attract(cfg, t, persona_list, llm_client, ng_words)
        return result
    elif strategy == "boost":
        result = boost(cfg, t, sent_posts, send_queue, lock)
        return result
    else:
        return "NO_STRATEGY"