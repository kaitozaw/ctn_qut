import random
import requests
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Callable

def with_backoff(
    fn, *,
    tries: int = 8,
    base: float = 1.0,
    factor: float = 2.0,
    max_sleep: float = 60.0,
    max_total: float = 120.0,
    on_error_note: str = "",
    relogin_fn: Optional[Callable[[], None]] = None,
):
    start = time.monotonic()
    delay = base
    last = None
    did_relogin = False

    for attempt in range(1, tries + 1):
        try:
            return fn()
        except requests.HTTPError as e:
            resp = getattr(e, "response", None)
            if resp is not None:
                _log_rate_headers(resp, note=on_error_note or "http_error")

            status = getattr(resp, "status_code", None)

            if status == 401 and relogin_fn and not did_relogin:
                try:
                    print(f"[auth]{(' ' + on_error_note) if on_error_note else ''} 401 detected → re-login")
                    relogin_fn()
                    did_relogin = True
                    continue
                except Exception as relogin_err:
                    print(f"[auth]{(' ' + on_error_note) if on_error_note else ''} re-login failed: {relogin_err}")
                    last = e
                    break

            if not _should_retry(e) or attempt == tries:
                last = e
                break

            if status == 429:
                retry_after = resp.headers.get("Retry-After") if resp is not None else None
                ra_secs = _parse_retry_after(retry_after) if retry_after else 0.0
                if ra_secs > 0:
                    sleep_secs = min(ra_secs, max_sleep)
                else:
                    sleep_secs = random.uniform(0, min(delay, max_sleep))
            else:
                sleep_secs = random.uniform(0, min(delay, max_sleep))

            note = f"[retry {attempt}/{tries}] {on_error_note} {e.__class__.__name__}: {e}"
            print(f"{note} sleep={sleep_secs:.2f}s")
            time.sleep(max(0.05, sleep_secs))
            delay = min(delay * factor, max_sleep)
            if (time.monotonic() - start) >= max_total:
                last = e
                break

        except Exception as e:
            if not _should_retry(e) or attempt == tries:
                last = e
                break
            sleep_secs = random.uniform(0, min(delay, max_sleep))
            note = f"[retry {attempt}/{tries}] {on_error_note} {e.__class__.__name__}: {e}"
            print(f"{note} sleep={sleep_secs:.2f}s")
            time.sleep(max(0.05, sleep_secs))
            delay = min(delay * factor, max_sleep)
            if (time.monotonic() - start) >= max_total:
                last = e
                break

    if last:
        raise last

def _log_rate_headers(resp, note: str = ""):
    try:
        h = resp.headers or {}
        ra  = h.get("Retry-After")
        rem = h.get("X-RateLimit-Remaining")
        rst = h.get("X-RateLimit-Reset")
        lim = h.get("X-RateLimit-Limit")
        print(
            f"[ratelimit]{(' ' + note) if note else ''} "
            f"status={resp.status_code} "
            f"limit={lim} remaining={rem} reset={rst} retry_after={ra}"
        )
    except Exception:
        pass

def _now_utc():
    return datetime.now(timezone.utc)

def _parse_retry_after(value: str) -> float:
    if not value:
        return 0.0

    try:
        secs = float(value)
        return max(0.0, secs)
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - _now_utc()).total_seconds()
        return max(0.0, delta)
    except Exception:
        return 0.0

def _should_retry(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        if status == 429:
            return True
        if 500 <= status <= 599:
            return True
        return False
    return True