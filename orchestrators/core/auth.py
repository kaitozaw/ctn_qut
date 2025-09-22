import os
import twooter.sdk as twooter
from .backoff import with_backoff

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