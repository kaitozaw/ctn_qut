import json
import os
from pathlib import Path
from typing import Any, Dict, List

def _parse_env_allows():
    idx_allow: List[int] = []
    for x in _split_csv(os.getenv("BOT_INDEX_ALLOW", "")):
        try:
            idx_allow.append(int(x))
        except ValueError:
            pass
    return set(idx_allow)

def _split_csv(val: str) -> List[str]:
    return [x.strip() for x in (val or "").split(",") if x.strip()]

def filter_cfgs_by_env(cfgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexes_allow = _parse_env_allows()

    def allowed(c: Dict[str, Any]) -> bool:
        if indexes_allow:
            try:
                idx = int(c.get("index"))
            except (TypeError, ValueError):
                return False
            if idx not in indexes_allow:
                return False

        return True

    selected = [c for c in cfgs if allowed(c)]
    personas = ", ".join(str(c.get("persona_id", "?")) for c in selected) or "(none)"
    print(f"[select] indexes_allow={sorted(indexes_allow) or '(any)'} personas={personas}")

    return selected

def load_cfg(cfg_path: str) -> Dict[str, Any]:
    p = Path(cfg_path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_ng(ng_path: str) -> List[str]:
    p = Path(ng_path)
    if not p.exists():
        return []
    words: List[str] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        words.append(s.casefold())
    return words