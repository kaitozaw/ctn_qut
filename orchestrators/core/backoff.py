import random
import time

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