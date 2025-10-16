import os
import random
import threading
import time
import twooter.sdk as twooter
from collections import defaultdict
from dotenv import load_dotenv
from itertools import cycle
from orchestrators.core import build_llm_client, ensure_session, filter_cfgs_by_env, load_cfg, load_ng, run_once, SkipPersona, whoami_username, with_backoff
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Set

_last_send_time = 0.0
_last_lock = threading.Lock()

def main():
    # --- env load ---
    load_dotenv()

    # --- load all bot configs under configs/ (e.g., bot1.json, bot2.json, ...) ---
    cfg_dir = Path("configs")
    cfg_paths = sorted(p for p in cfg_dir.glob("bot*.json") if p.is_file())
    if not cfg_paths:
        raise RuntimeError("No bot config files found under configs/ (expected e.g., bot1.json, bot2.json)")
    
    # --- materialize config dicts in stable order ---
    cfgs: List[Dict[str, Any]] = []
    for p in cfg_paths:
        try:
            cfgs.append(load_cfg(str(p)))
        except Exception as e:
            print(f"[warn] skip config {p.name}: {e}")
    if not cfgs:
        raise RuntimeError("No valid bot configs could be loaded.")
    
    # --- strategy ---
    strategy = os.getenv("BOT_STRATEGY", "booster")
    
    # --- LLM client ---
    llm_client = build_llm_client()

    # --- NG list ---
    ng_path = "policies/ng_words.txt"
    ng_words = load_ng(ng_path)

    # --- session, actions, sent_posts ---
    session_by_persona: Dict[str, twooter.Twooter] = {}
    replied_posts_by_persona: Dict[str, Set[int]] = {}

    # --- send queue ---
    try:
        qmax = int(os.getenv("SEND_QUEUE_MAX", "30"))
    except ValueError:
        qmax = 30
    send_queue: Queue = Queue(maxsize=qmax)

    # --- lock ---
    lock_by_persona: Dict[str, threading.Lock] = defaultdict(threading.Lock)
    last_send_time_by_persona: Dict[str, float] = defaultdict(float)
    
    # --- worker function ---
    def _worker(name: str):
        min_gap_per_persona = max(0.0, int(os.getenv("MIN_INTERVAL_PER_PERSONA_MS", "35000")) / 1000.0)
        while True:
            job = send_queue.get()
            if job is None:
                break
            fn = job["fn"]
            relogin_fn = job.get("relogin_fn")
            note = job.get("note", "")
            persona_id = job.get("persona_id")
            reply_id = job.get("reply_id")
            post_id = job.get("post_id")
            text = job.get("text")

            lock = lock_by_persona[persona_id]
            with lock:
                now = time.monotonic()
                jitter = random.uniform(-0.2, 0.2) * min_gap_per_persona
                wait = (last_send_time_by_persona[persona_id] + min_gap_per_persona + jitter) - now
                if wait > 0:
                    time.sleep(wait)
                last_send_time_by_persona[persona_id] = time.monotonic()
            
            try:
                with_backoff(fn, on_error_note=note, relogin_fn=relogin_fn)
                print(
                    f"[sent]{(' ' + note) if note else ''}"
                    f" persona={persona_id}"
                    f"{f' reply_id={reply_id}' if reply_id else ''}"
                    f"{f' post_id={post_id}' if post_id else ''}"
                    f"{f' text={text!r}' if text else ''}"
                )
            except Exception as e:
                print(
                    f"[post-error]{(' ' + note) if note else ''}"
                    f" persona={persona_id}"
                    f"{f' reply_id={reply_id}' if reply_id else ''}"
                    f"{f' post_id={post_id}' if post_id else ''}"
                    f" {e.__class__.__name__}: {e}"
                )
            finally:
                send_queue.task_done()

    # --- start workers ---
    try:
        workers_n = int(os.getenv("WORKERS", "10"))
    except ValueError:
        workers_n = 10
    for i in range(workers_n):
        th = threading.Thread(target=_worker, args=(f"w{i}",), daemon=True)
        th.start()

    # --- env-based filtering (role/index)
    cfgs = filter_cfgs_by_env(cfgs)

    # --- round-robin iterator across cfgs ---
    rr = cycle(cfgs)

    # --- sleep ---
    busy_sleep = max(0.0, int(os.getenv("BUSY_SLEEP", "1000")) / 1000.0)
    
    # --- main loop ---
    while True:
        cfg = next(rr)

        # --- id and index ---
        persona_id = (cfg.get("persona_id") or "").strip()
        index = cfg.get("index", -1)

        # --- session ---
        t = session_by_persona.get(persona_id)
        if t is None:
            try:
                t = ensure_session(persona_id, index)
                me_username = whoami_username(t)
                print(f"[whoami] persona={persona_id} username={me_username}")
            except SkipPersona as e:
                print(f"[skip] {e}")
                continue 
            session_by_persona[persona_id] = t

        # --- sent_posts ---
        replied_posts = replied_posts_by_persona.get(persona_id)
        if  replied_posts is None:
            replied_posts = set()
            replied_posts_by_persona[persona_id] =  replied_posts

        # --- run once for this persona ---
        try:
            status = run_once(cfg, t, strategy, llm_client, ng_words,  replied_posts, send_queue)
        except Exception as e:
            status = "ERROR"
            print(f"[error] persona={persona_id} {e.__class__.__name__}: {e}")

        # --- sleep ---
        if strategy == "boost":
            time.sleep(busy_sleep)
        elif strategy == "engage":
            base = 10
            jitter = 5
            sleep = base + random.randint(-jitter, jitter)
            print(f"[loop] persona={persona_id} status={status} sleep={sleep}s")
            time.sleep(sleep)
        else:
            base = 120
            jitter = 60
            sleep = base + random.randint(-jitter, jitter)
            print(f"[loop] persona={persona_id} status={status} sleep={sleep}s")
            time.sleep(sleep)

if __name__ == "__main__":
    main()