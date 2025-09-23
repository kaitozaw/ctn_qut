import os
import random
import time
import twooter.sdk as twooter
from dotenv import load_dotenv
from itertools import cycle
from pathlib import Path
from typing import Any, Dict, List, Set
from orchestrators.core import build_llm_client, ensure_session, filter_cfgs_by_env, load_cfg, load_ng, run_once, SkipPersona, whoami_username

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
    
    # --- env-based filtering (role/index)
    cfgs = filter_cfgs_by_env(cfgs)
    
    # --- sessions, whoami, seen post IDs (per bot) ---
    session_by_persona: Dict[str, twooter.Twooter] = {}
    username_by_persona: Dict[str, str] = {}
    seen_by_persona: Dict[str, Set[int]] = {}

    # --- LLM client (shared) ---
    BASE_URL = "http://llm-proxy.legitreal.com/openai"
    TEAM_KEY = os.getenv("TEAM_KEY")
    llm_client = build_llm_client(BASE_URL, TEAM_KEY)

    # --- NG list (shared) ---
    ng_path = "policies/ng_words.txt"
    ng_words = load_ng(ng_path)

    # --- round-robin iterator across cfgs ---
    rr = cycle(cfgs)

    while True:
        cfg = next(rr)

        # --- resolve/cached per-bot state ---
        persona_id = cfg["persona_id"]
        index = cfg["index"]

        # --- session ---
        t = session_by_persona.get(persona_id)
        if t is None:
            try:
                t = ensure_session(persona_id, index)
            except SkipPersona as e:
                print(f"[skip] {e}")
                continue 
            session_by_persona[persona_id] = t

        #  --- whoami ---
        me_username = username_by_persona.get(persona_id)
        if not me_username:
            me_username = whoami_username(t)
            if not me_username:
                raise RuntimeError(f"Failed to resolve whoami username for {persona_id}")
            username_by_persona[persona_id] = me_username
            print(f"[whoami] persona={persona_id} username={me_username}")

        # --- seen IDs per persona ---
        seen_ids = seen_by_persona.get(persona_id)
        if seen_ids is None:
            seen_ids = set()
            seen_by_persona[persona_id] = seen_ids

        # --- one action for this persona ---
        try:
            status = run_once(t, me_username, cfg, seen_ids, llm_client, ng_words)
        except Exception as e:
            status = "ERROR"
            print(f"[error] persona={persona_id} {e.__class__.__name__}: {e}")

        # --- sleep using base and jitter ---
        base = 60
        jitter = 10
        slp = base + random.randint(-jitter, jitter)
        print(f"[loop] persona={persona_id} status={status} sleep={slp}s")
        time.sleep(slp)
    
if __name__ == "__main__":
    main()