import random
import time
import twooter.sdk as twooter
from dotenv import load_dotenv
from itertools import cycle
from orchestrators.core import build_llm_client, ensure_session, filter_cfgs_by_env, load_cfg, load_ng, run_once, SkipPersona, whoami_username
from pathlib import Path
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

    # --- session, actions (per bot) ---
    session_by_persona: Dict[str, twooter.Twooter] = {}
    actions_by_persona: Dict[str, List[Dict[str, Any]]] = {}
    
    # --- prepopulate actions for orchestration ---
    for cfg in cfgs:
        persona_id = (cfg.get("persona_id") or "").strip()
        actions_by_persona[persona_id] = []

    # --- LLM client (shared) ---
    llm_client = build_llm_client()

    # --- NG list (shared) ---
    ng_path = "policies/ng_words.txt"
    ng_words = load_ng(ng_path)

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
            actions = []
            actions_by_persona[persona_id] = actions

        # --- run once for this persona ---
        try:
            status = run_once(cfg, t, actions, actions_by_persona, role_map, llm_client, ng_words)
        except Exception as e:
            status = "ERROR"
            print(f"[error] persona={persona_id} {e.__class__.__name__}: {e}")

        # --- sleep using base and jitter ---
        base = 3
        jitter = 1
        slp = base + random.randint(-jitter, jitter)
        print(f"[loop] persona={persona_id} status={status} sleep={slp}s")
        time.sleep(slp)

if __name__ == "__main__":
    main()