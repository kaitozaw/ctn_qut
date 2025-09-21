import json
import os
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException, Timeout, HTTPError

OUTPUT_FILE = "trending_all.json"
CHANGELOG_FILE = "trending_changes.jsonl"  # one JSON object per line

# --- Load config ---
with open("config.json", encoding="utf-8") as fh:
    cfg = json.load(fh)

BASE_URL = cfg["base_url"].rstrip("/") + "/feeds/trending"


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _print_http_error(prefix: str, err: Exception):
    """Print a helpful message for any request/json error."""
    print(f"{prefix}: {type(err).__name__}: {err}")
    # If it's an HTTPError or other requests error with a response, dump details
    resp = getattr(err, "response", None)
    if resp is not None:
        body_preview = ""
        try:
            body_preview = resp.text
            if len(body_preview) > 2000:  # avoid huge logs
                body_preview = body_preview[:2000] + " …[truncated]"
        except Exception:
            body_preview = "<unable to read response text>"
        print(f"  -> HTTP {resp.status_code} {resp.reason} for {resp.url}")
        print(f"  -> Response body:\n{body_preview}")


def _safe_get_json(url: str, **kwargs):
    """
    Perform GET and return parsed JSON dict, or None on any error.
    Errors are printed but not raised.
    """
    try:
        r = requests.get(url, timeout=kwargs.pop("timeout", 30), **kwargs)
        # Don't raise here yet; log rich details if non-2xx
        try:
            r.raise_for_status()
        except HTTPError as he:
            # Attach response to error so _print_http_error can show details
            he.response = r
            raise he
        try:
            return r.json()
        except json.JSONDecodeError as je:
            print("ERROR: Failed to decode JSON from response.")
            _print_http_error("JSONDecodeError", je)
            # Also show raw body preview for debugging
            preview = r.text
            if len(preview) > 2000:
                preview = preview[:2000] + " …[truncated]"
            print(f"  -> Raw response preview:\n{preview}")
            return None
    except (Timeout, RequestException) as e:
        _print_http_error("Request failed", e)
        return None
    except Exception as e:
        # Catch-all to prevent the loop from crashing on unexpected issues
        _print_http_error("Unexpected error during request", e)
        return None


def fetch_two_pages():
    """Fetch top 20, then use next_cursor once to fetch next 20. Returns list (possibly empty)."""
    combined = []

    print("Stage 1: Fetching page 1 (top 20)...")
    p1 = _safe_get_json(BASE_URL)
    if not p1:
        print("Stage 1: Failed to fetch page 1. Skipping this cycle's processing.")
        return combined  # empty; main loop will handle gracefully

    combined.extend(p1.get("data", []))

    next_cursor = (p1.get("paging") or {}).get("next_cursor")
    if next_cursor:
        print("Stage 2: Fetching page 2 (next 20)...")
        p2 = _safe_get_json(BASE_URL, params={"cursor": next_cursor})
        if p2:
            combined.extend(p2.get("data", []))
        else:
            print("Stage 2: Failed to fetch page 2. Continuing with page 1 data only.")
    else:
        print("Stage 2: No next_cursor found, skipping page 2.")

    print(f"Stage 3: Collected {len(combined)} items this round.")
    return combined


def load_existing(path):
    """Load existing file; return dict keyed by id."""
    items_by_id = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
                for it in existing.get("data", []):
                    if isinstance(it, dict) and "id" in it:
                        items_by_id[it["id"]] = it
            print(f"Stage 0: Loaded {len(items_by_id)} existing items from {path}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Stage 0: Failed to load existing file ({type(e).__name__}). Starting fresh.")
    return items_by_id


def save_items(path, items_by_id):
    """Save items back to disk, sorted for determinism."""
    def sort_key(it):
        ca = it.get("created_at")
        return (ca or "", str(it.get("id", "")))

    data_sorted = sorted(items_by_id.values(), key=sort_key, reverse=True)

    payload = {
        "data": data_sorted,
        "total_unique_items": len(data_sorted),
        "last_saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"Stage 4: Saved {len(data_sorted)} unique items to {path}")
    except OSError as e:
        print(f"WARNING: Failed to save items to disk: {e}")


def diff_dicts(old, new, ignore_keys=None):
    """
    Return a dict of changed fields: {field: {"old": ..., "new": ...}}
    Shallow compare on top-level keys present in either dict.
    """
    if ignore_keys is None:
        ignore_keys = set()

    changed = {}
    all_keys = set(old.keys()) | set(new.keys())
    for k in all_keys:
        if k in ignore_keys:
            continue
        old_v = old.get(k, None)
        new_v = new.get(k, None)
        if old_v != new_v:
            changed[k] = {"old": old_v, "new": new_v}
    return changed


def append_changelog(change):
    """
    Append a single JSON object (one per line) to CHANGELOG_FILE.
    `change` should already be a JSON-serializable dict.
    """
    try:
        with open(CHANGELOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(change, ensure_ascii=False))
            fh.write("\n")
    except OSError as e:
        print(f"WARNING: Failed to write changelog: {e}")


def main_loop(interval=60):
    """Repeat fetching every `interval` seconds."""
    while True:
        try:
            print("=" * 60)
            print("Starting new fetch cycle...")
            items_by_id = load_existing(OUTPUT_FILE)

            fresh_items = fetch_two_pages()

            # If fetch failed entirely, fresh_items may be empty; still continue safely
            added, updated, unchanged = 0, 0, 0
            for it in fresh_items:
                if not isinstance(it, dict) or "id" not in it:
                    continue

                _id = it["id"]
                if _id in items_by_id:
                    old_item = items_by_id[_id]
                    changes = diff_dicts(old_item, it, ignore_keys={"tags"})

                    if changes:
                        items_by_id[_id] = it
                        updated += 1
                        append_changelog({
                            "id": _id,
                            "changed_at": _iso_now(),
                            "changes": changes
                        })
                    else:
                        unchanged += 1
                else:
                    items_by_id[_id] = it
                    added += 1
                    append_changelog({
                        "id": _id,
                        "changed_at": _iso_now(),
                        "changes": {"__new_item__": {"old": None, "new": True}}
                    })

            print(
                f"Stage 3.5: Added {added}, updated {updated}, unchanged (seen again but identical) {unchanged}, "
                f"total {len(items_by_id)}"
            )
            save_items(OUTPUT_FILE, items_by_id)

            print("Cycle complete. Waiting before next run...\n")
            time.sleep(interval)

        except KeyboardInterrupt:
            print("Received KeyboardInterrupt. Exiting gracefully.")
            break
        except Exception as e:
            # Catch-all to ensure we don't kill the loop; log and sleep before retrying
            _print_http_error("Unexpected top-level error", e)
            print(f"Continuing after error. Sleeping {interval} seconds...\n")
            time.sleep(interval)


if __name__ == "__main__":
    main_loop(interval=20)  # runs every 20 seconds
