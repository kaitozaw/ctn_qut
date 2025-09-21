import json
import os
import requests
import time
from datetime import datetime, timezone

OUTPUT_FILE = "trending_all.json"
CHANGELOG_FILE = "trending_changes.jsonl"  # one JSON object per line

# --- Load config ---
with open("config.json", encoding="utf-8") as fh:
    cfg = json.load(fh)

BASE_URL = cfg["base_url"].rstrip("/") + "/feeds/trending"


def fetch_two_pages():
    """Fetch top 20, then use next_cursor once to fetch next 20."""
    combined = []

    print("Stage 1: Fetching page 1 (top 20)...")
    r1 = requests.get(BASE_URL, timeout=30)
    r1.raise_for_status()
    p1 = r1.json()
    combined.extend(p1.get("data", []))

    next_cursor = (p1.get("paging") or {}).get("next_cursor")
    if next_cursor:
        print("Stage 2: Fetching page 2 (next 20)...")
        r2 = requests.get(BASE_URL, params={"cursor": next_cursor}, timeout=30)
        r2.raise_for_status()
        p2 = r2.json()
        combined.extend(p2.get("data", []))
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
        except (json.JSONDecodeError, OSError):
            print("Stage 0: Failed to load existing file, starting fresh.")
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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"Stage 4: Saved {len(data_sorted)} unique items to {path}")


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


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
        print("=" * 60)
        print("Starting new fetch cycle...")
        items_by_id = load_existing(OUTPUT_FILE)

        fresh_items = fetch_two_pages()

        added, updated, unchanged = 0, 0, 0
        for it in fresh_items:
            if not isinstance(it, dict) or "id" not in it:
                continue

            _id = it["id"]
            if _id in items_by_id:
                old_item = items_by_id[_id]
                changes = diff_dicts(old_item, it, ignore_keys={"tags"})

                if changes:
                    # Only count as updated if there are real changes
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


if __name__ == "__main__":
    main_loop(interval=20)  # runs every 20 seconds
