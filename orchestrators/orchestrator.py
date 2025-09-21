import json
import os
import random
import sys
import time
import twooter.sdk as twooter
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ----------------------------
# Bootstrap
# ----------------------------

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

def shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n].rstrip()


# ----------------------------
# Backoff helpers
# ----------------------------

def should_retry(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        if status == 429:
            return True
        if 500 <= status <= 599:
            return True
        return False
    return True

def with_backoff(fn, *, tries: int = 5, base: float = 0.25, factor: float = 2.0, jitter: float = 0.2, on_error_note: str = ""):
    last = None
    delay = base
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if not should_retry(e) or attempt == tries:
                raise
            j = delay * (1 + random.uniform(-jitter, jitter))
            note = f"[retry {attempt}/{tries}] {on_error_note} {e.__class__.__name__}: {e}"
            print(note)
            time.sleep(max(0.05, j))
            delay *= factor
    if last:
        raise last

# ----------------------------
# Feed helpers
# ----------------------------

def extract_post_fields(d: Dict[str, Any]) -> Tuple[Optional[int], str, str]:
    post = d.get("post") or {}
    pid = d.get("id") or post.get("id")
    content = (d.get("content") or post.get("content") or "") or ""
    content = content.strip()
    author = (d.get("author") or post.get("author") or {}) or {}
    username = (author.get("username") or "").strip()
    try:
        pid = int(pid) if pid is not None else None
    except Exception:
        pid = None
    return pid, content, username

# ----------------------------
# SDK / Auth
# ----------------------------

def ensure_session(persona_id: str, index: int) -> twooter.Twooter:
    t = twooter.new(use_env=True)
    try:
        t.use_agent(persona_id)
        info = t.token_info().get("data")
        if not info:
            raise RuntimeError("no token info")
    except Exception:
        env_key = f"PASSWORD_BOT{index}"
        pwd = os.getenv(env_key)
        if not pwd:
            raise RuntimeError(f"Missing {env_key} for first login of {persona_id}")

        with_backoff(
            lambda: t.login(persona_id, pwd),
            on_error_note=f"login {persona_id}",
        )
    return t

def whoami_username(t: twooter.Twooter) -> str:
    me = with_backoff(
        lambda: t.whoami(),
        on_error_note="whoami"
    )
    data = (me or {}).get("data") or {}
    return (data.get("username") or "").strip() or ""

# ----------------------------
# Strategy
# ----------------------------

def pick_target_mentions_then_keywords(
    t: twooter.Twooter,
    me_username: str,
    feed_key: str,
    keywords: List[str],
    seen_ids: Set[int],
) -> Optional[Dict[str, Any]]:
    feed = with_backoff(lambda: t.feed(feed_key, top_n=20), on_error_note="feed")
    items = (feed or {}).get("data") or []

    me_tag = f"@{me_username}".casefold()
    keys = [k.casefold() for k in (keywords or [])]

    candidates = []
    for d in items:
        pid, content, author = extract_post_fields(d)
        if not pid or not content:
            continue
        if pid in seen_ids:
            continue
        if author and author == me_username:
            continue
        candidates.append({"id": pid, "content": content, "author": author})

    if not candidates:
        return None 

    for c in candidates:
        if me_tag and me_tag in c["content"].casefold():
            return c

    for c in candidates:
        txt = c["content"].casefold()
        if any(k in txt for k in keys):
            return c

    return candidates[0]

# ----------------------------
# Generator (OpenAI: legit LLM proxy)
# ----------------------------

def build_llm_client(base_url, api_key) -> OpenAI:    
    return OpenAI(base_url=base_url, api_key=api_key)

def generate_reply(
    llm_client: OpenAI,
    temperature: float,
    persona: Dict[str, Any],
    target_text: str,
    max_len_hint: int,
) -> str:
    sys_prompt = (
        f"You are a social media persona. "
        f"Tone: {persona.get('tone','neutral')}. "
        f"Constraints: {persona.get('constraints','be civil and concise')}. "
        f"Reply under {max_len_hint} characters. No preambles."
    )
    def _call():
        rsp = llm_client.chat.completions.create(
            model = "gemma3:4b",
            temperature=float(temperature),
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": target_text},
            ],
        )
        return rsp
    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    text = (rsp.choices[0].message.content or "").strip()
    return text

# ----------------------------
# Safety
# ----------------------------

def safety_check(text: str, ng_words: List[str], soft_max_len: int, hard_max_len: int = 255) -> Tuple[bool, str, Optional[str]]:
    low = text.casefold()
    if any(w and w in low for w in ng_words):
        return False, "", "NG_WORD"
    text = shorten(text, min(max(1, hard_max_len), max(soft_max_len, 1)))
    return True, text, None

# ----------------------------
# Orchestrator loop (single bot)
# ----------------------------

def run_once(
    t: twooter.Twooter,
    me_username: str,
    cfg: Dict[str, Any],
    llm_client: OpenAI,
    ng_words: List[str],
    seen_ids: Set[int],
) -> str:
    strategy = (cfg.get("strategy") or "mentions_then_keywords").strip()
    feed_key = (cfg.get("feed_key") or "home").strip()
    keywords = cfg.get("keywords") or []

    if strategy == "mentions_then_keywords":
        target = pick_target_mentions_then_keywords(t, me_username, feed_key, keywords, seen_ids)
    else:
        target = None

    if not target:
        return "NO_TARGET"

    target_id = int(target["id"])
    target_text = target["content"]
    seen_ids.add(target_id)

    temp = float(cfg["llm"].get("temperature", 0.7))
    persona = cfg.get("persona", {}) or {}
    max_reply_len = int(cfg.get("max_reply_len", 240))
    reply = generate_reply(llm_client, temp, persona, target_text, max_reply_len)

    ok, safe_text, reason = safety_check(reply, ng_words, max_reply_len, hard_max_len=255)
    if not ok:
        print(f"[safety] blocked: reason={reason} target_id={target_id}")
        return "BLOCKED"

    def _send():
        return t.post(safe_text, parent_id=target_id)
    
    try:
        with_backoff(
            _send,
            on_error_note="post"
        )
        print(f"[sent] reply_to={target_id} len={len(safe_text)} text={safe_text!r}")
        return "SENT"
    except Exception as e:
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        try:
            resp = getattr(e, "response", None)
            if resp is not None:
                body = resp.text
        except Exception:
            pass
        print(f"[post-error] status={status} target_id={target_id} len={len(safe_text)} body={body[:500]!r}")
        seen_ids.add(target_id)
        return "ERROR"

def main():
    # --- env/config load ---
    load_dotenv()
    cfg_path = "configs/bot1.json"
    cfg = load_cfg(cfg_path)
    ng_words = load_ng(cfg.get("ng_list_path", "policies/ng_words.txt"))

    # --- session ---
    persona_id = cfg["persona_id"]
    index = cfg["index"]
    t = ensure_session(persona_id, index)
    me_username = whoami_username(t)
    if not me_username:
        raise RuntimeError("Failed to resolve whoami username")
    print(f"[whoami] username={me_username}")

    # --- LLM client ---
    BASE_URL = "http://llm-proxy.legitreal.com/openai"
    TEAM_KEY = os.getenv("TEAM_KEY")
    llm_client = build_llm_client(BASE_URL, TEAM_KEY)

    # --- loop control ---
    base = int(cfg.get("interval_sec", 150))
    jitter = int(cfg.get("jitter_sec", 20))
    seen_ids: Set[int] = set()

    while True:
        try:
            status = run_once(t, me_username, cfg, llm_client, ng_words, seen_ids)
        except Exception as e:
            status = "ERROR"
            print(f"[error] {e.__class__.__name__}: {e}")

        slp = base + random.randint(-jitter, jitter)
        slp = max(30, slp)
        print(f"[loop] status={status} sleep={slp}s")
        time.sleep(slp)

if __name__ == "__main__":
    main()