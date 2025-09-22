import json
from pathlib import Path
from typing import Any, Dict, List

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