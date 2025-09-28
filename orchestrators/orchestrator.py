import os
import random
import time
import twooter.sdk as twooter
from collections import deque
from dotenv import load_dotenv
from itertools import cycle
from orchestrators.core import build_llm_client, ensure_session, filter_cfgs_by_env, load_cfg, load_ng, run_once, SkipPersona, whoami_username, with_backoff
from pathlib import Path
from queue import Queue
import threading
from typing import Any, Dict, List

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
    
    # --- build role -> persona_id mapping for orchestration (before env-based filtering) ---
    role_map: Dict[str, List[str]] = {}
    for cfg in cfgs:
        role = (cfg.get("role") or "").strip()
        persona_id = (cfg.get("persona_id") or "").strip()
        if not role or not persona_id:
            continue
        role_map.setdefault(role, []).append(persona_id)

    # --- env-based filtering (role/index)
    cfgs = filter_cfgs_by_env(cfgs)

    # --- round-robin iterator across cfgs ---
    rr = cycle(cfgs)

    # --- session, actions ---
    session_by_persona: Dict[str, twooter.Twooter] = {}
    actions_by_persona: Dict[str, deque] = {}
    
    # --- send queue ---
    try:
        qmax = int(os.getenv("SEND_QUEUE_MAX", "5000"))
    except ValueError:
        qmax = 5000
    send_queue: Queue = Queue(maxsize=qmax)

    # --- lock ---
    lock_by_persona: Dict[str, threading.Lock] = {}

    # --- worker function ---
    def _worker(name: str):
        while True:
            job = send_queue.get()
            if job is None:
                break
            lock: threading.Lock = job.get("lock")
            fn = job["fn"]
            relogin_fn = job.get("relogin_fn")
            note = job.get("note", "")
            persona = job.get("persona_id")
            reply_id = job.get("reply_id")
            post_id = job.get("post_id")
            text = job.get("text")
            
            try:
                if lock:
                    with lock:
                        with_backoff(fn, on_error_note=note, relogin_fn=relogin_fn)
                else:
                    with_backoff(fn, on_error_note=note, relogin_fn=relogin_fn)
                print(
                    f"[sent]{(' ' + note) if note else ''}"
                    f" persona={persona}"
                    f"{f' reply_id={reply_id}' if reply_id else ''}"
                    f"{f' post_id={post_id}' if post_id else ''}"
                    f"{f' text={text!r}' if text else ''}"
                )
                min_gap = max(0.0, int(os.getenv("MIN_INTERVAL_MS", "400")) / 1000.0)
                time.sleep(min_gap)
            except Exception as e:
                print(
                    f"[post-error]{(' ' + note) if note else ''}"
                    f" persona={persona}"
                    f"{f' reply_id={reply_id}' if reply_id else ''}"
                    f"{f' post_id={post_id}' if post_id else ''}" 
                    f"{e.__class__.__name__}: {e}"
                )
            finally:
                send_queue.task_done()

    # --- start workers ---
    try:
        workers_n = int(os.getenv("WORKERS", "1"))
    except ValueError:
        workers_n = 1
    for i in range(workers_n):
        th = threading.Thread(target=_worker, args=(f"w{i}",), daemon=True)
        th.start()
    
    # --- LLM client ---
    llm_client = build_llm_client()

    # --- NG list ---
    ng_path = "policies/ng_words.txt"
    ng_words = load_ng(ng_path)

    # --- load sleep configuration from environment ---
    busy_sleep = max(0.01, int(os.getenv("BUSY_SLEEP_MS", "100")) / 1000.0)

    try:
        base = int(os.getenv("BASE", "120"))
    except ValueError:
        base = 120
    try:
        jitter = int(os.getenv("JITTER", "60"))
    except ValueError:
        jitter = 60

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

        # --- actions ---
        actions = actions_by_persona.get(persona_id)
        if actions is None:
            actions = deque()
            actions_by_persona[persona_id] = actions

        # --- lock ---
        lock = lock_by_persona.get(persona_id)
        if lock is None:
            lock = threading.Lock()
            lock_by_persona[persona_id] = lock

        # --- run once for this persona ---
        try:
            status = run_once(cfg, t, actions, send_queue, lock, llm_client, ng_words, role_map)
        except Exception as e:
            status = "ERROR"
            print(f"[error] persona={persona_id} {e.__class__.__name__}: {e}")

        # --- sleep ---
        if actions or not send_queue.empty():
            time.sleep(busy_sleep)
        else:
            slp = base + random.randint(-jitter, jitter)
            print(f"[loop] persona={persona_id} status={status} sleep={slp}s")
            time.sleep(slp)

if __name__ == "__main__":
    main()