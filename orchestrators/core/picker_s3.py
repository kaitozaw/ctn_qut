import io, gzip, json, os, time, uuid, random
import boto3
from botocore.config import Config
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple

def _get_s3_and_cfg() -> Tuple[any, str, str, str]:
    region = os.getenv("AWS_REGION") or "ap-southeast-2"
    bucket = os.getenv("AWS_S3_BUCKET")
    trending_posts_prefix = os.getenv("PICKER_TRENDING_POSTS_PREFIX", "picker/analysis/trending_posts/")
    articles_key = os.getenv("PICKER_ARTICLES_KEY", "picker/contexts/articles.json")
    dialogues_key = os.getenv("PICKER_DIALOGUES_KEY", "picker/contexts/dialogues.json")
    story_histories_key = os.getenv("PICKER_STORY_HISTORIES_KEY", "picker/contexts/story_histories.json")
    current_key = os.getenv("PICKER_CURRENT_KEY", "picker/current.json")
    history_prefix = os.getenv("PICKER_HISTORY_PREFIX", "picker/history/")
    
    s3 = boto3.client("s3", region_name=region, config=Config(retries={"max_attempts": 5, "mode": "standard"}))
    return s3, bucket, trending_posts_prefix, articles_key, dialogues_key, story_histories_key, current_key, history_prefix

def _iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _read_articles_array() -> Optional[List[Dict[str, str]]]:
    s3, bucket, _, articles_key, _, _, _, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=articles_key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"[s3] read_articles error: {e.__class__.__name__}: {e}")
        return None

    if not isinstance(data, list):
        print(f"[json] expected top-level array at s3://{bucket}/{articles_key}")
        return None
    
    articles = []
    for d in data:
        if isinstance(d, dict) and d.get("embed_url") and d.get("article_content"):
            articles.append(d)
    return articles

def _read_dialogues_dict() -> Dict[str, List[List[Dict[str, Any]]]]:
    s3, bucket, _, _, dialogues_key, _, _, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=dialogues_key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        print(f"[s3] read_dialogues error: {e.__class__.__name__}: {e}")
        return {}

    if not isinstance(data, dict):
        print(f"[json] expected top-level object at s3://{bucket}/{dialogues_key}")
        return {}

    dialogues: Dict[str, List[List[Dict[str, Any]]]] = {}
    for persona_id, threads in data.items():
        if not isinstance(persona_id, str) or not isinstance(threads, list):
            continue
        norm_threads: List[List[Dict[str, Any]]] = []
        for thread in threads:
            if not isinstance(thread, list):
                continue
            norm_thread: List[Dict[str, Any]] = []
            for post in thread:
                if not isinstance(post, dict):
                    continue
                norm_post = {
                    "id": post.get("id"),
                    "parent_id": post.get("parent_id"),
                    "content": post.get("content", "").strip(),
                    "author_username": post.get("author_username", "").strip(),
                }
                norm_thread.append(norm_post)
            if norm_thread:
                norm_threads.append(norm_thread)
        dialogues[persona_id] = norm_threads
    return dialogues

def _read_story_histories_dict() -> Dict[str, Dict[str, List[str]]]:
    s3, bucket, _, _, _, story_histories_key, _, _  = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=story_histories_key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        print(f"[s3] read_story_histories error: {e.__class__.__name__}: {e}")
        return {}

    if not isinstance(data, dict):
        print(f"[json] expected top-level object at s3://{bucket}/{story_histories_key}")
        return {}

    story_histories: Dict[str, Dict[str, List[str]]] = {}
    for persona_id, phases in data.items():
        if not isinstance(persona_id, str) or not isinstance(phases, dict):
            continue
        story_history: Dict[str, List[str]] = {}
        for phase, texts in phases.items():
            if isinstance(phase, str) and isinstance(texts, list):
                story_history[phase] = [str(text) for text in texts if isinstance(text, (str,))]
        story_histories[persona_id] = story_history
    return story_histories

def get_random_article() -> Optional[Dict[str, Any]]:
    articles = _read_articles_array()
    if not articles:
        return None
    index = random.randrange(len(articles))
    article = articles[index]
    return {"embed_url": article["embed_url"], "article_content": article["article_content"]}

def get_dialogue(persona_id: str, post: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(persona_id, str) or not persona_id:
        return None
    id = (post or {}).get("id")
    dialogues = _read_dialogues_dict()
    threads = dialogues.get(persona_id, [])

    for thread in threads:
        if not thread:
            continue
        last = thread[-1] or {}
        if last.get("id", 0) == id:
            return thread
    return None

def get_story_histories(persona_id: str) -> Dict[str, List[str]]:
    if not isinstance(persona_id, str) or not persona_id:
        return {}
    story_histories = _read_story_histories_dict()
    return story_histories.get(persona_id, {})

def read_current() -> Optional[Dict[str, Any]]:
    s3, bucket, _, _, _, _, current_key, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=current_key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"[s3] read_current error: {e.__class__.__name__}: {e}")
        return None

def write_current_and_history(persona_id: str, post: Dict[str, Any], reply_goal: int):
    s3, bucket, _, _, _, _, current_key, history_prefix = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    new_post = {
        "persona_id": persona_id,
        "post_id": post.get("id"),
        "reply_goal": reply_goal,
        "issued_at": _iso_utc_now(),
    }

    body = json.dumps(new_post, ensure_ascii=False).encode("utf-8")
    hist_key = f"{history_prefix.rstrip('/')}/{new_post['issued_at']}-{uuid.uuid4().hex[:6]}.json"
    s3.put_object(Bucket=bucket, Key=hist_key, Body=body, ContentType="application/json", CacheControl="no-cache")
    s3.put_object(Bucket=bucket, Key=current_key, Body=body, ContentType="application/json", CacheControl="no-cache")

    print(f"[s3] wrote current and histories -> s3://{bucket}/{current_key} (history={hist_key})")

def write_dialogues(persona_id: str, post: Dict[str, Any]):
    s3, bucket, _, _, dialogues_key, _, _, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    new_post = {
        "id": post.get("id"),
        "parent_id": post.get("parent_id"),
        "content": post.get("content", "").strip(),
        "author_username": post.get("author_username", "").strip(),
    }

    dialogues = _read_dialogues_dict()
    threads = dialogues.get(persona_id)
    if threads is None:
        threads = []
        dialogues[persona_id] = threads

    target_thread = []
    parent_id = new_post.get("parent_id")
    for thread in threads:
        if not thread:
            continue
        last = thread[-1] or {}
        if last.get("id", 0) == parent_id:
            target_thread = thread

    if not target_thread:
        target_thread = [new_post]
        threads.append(target_thread)
    else:
        target_thread.append(new_post)

    body = json.dumps(dialogues, ensure_ascii=False).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=dialogues_key, Body=body, ContentType="application/json", CacheControl="no-cache")

    print(f"[s3] wrote dialogues -> s3://{bucket}/{dialogues_key}")

def write_story_histories(persona_id: str, story_phase: str, text: str):
    s3, bucket, _, _, _, story_histories_key, _, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    data = _read_story_histories_dict()
    if not isinstance(data, dict):
        data = {}
    if persona_id not in data:
        data[persona_id] = {"Frustration Rising": [], "Contrast Building": [], "Accountability Demand": [], "Decision Push": []}
    if story_phase not in data[persona_id]:
        data[persona_id][story_phase] = []
    data[persona_id][story_phase].append(text)

    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=story_histories_key, Body=body, ContentType="application/json", CacheControl="no-cache")

    print(f"[s3] wrote story_histories -> s3://{bucket}/{story_histories_key}")

def write_trending_posts(trending_posts: List[Dict[str, Any]]):
    s3, bucket, trending_posts_prefix, _, _, _, _, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    now_utc = datetime.now(timezone.utc)
    brisbane_tz = timezone(timedelta(hours=10))
    now = now_utc.astimezone(brisbane_tz)

    dt = now.strftime("%Y-%m-%d")
    hour = now.strftime("%H")
    timestamp_str = now.strftime("%Y%m%d-%H%M%S")
    ingest_iso = now.isoformat(timespec="seconds")

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        for post in trending_posts:
            if not isinstance(post, dict):
                continue
            row = dict(post)
            row["ingest_time"] = ingest_iso
            gz.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            gz.write(b"\n")
    buf.seek(0)

    filename = f"trending_{timestamp_str}_{uuid.uuid4().hex[:6]}.jsonl.gz"
    key = f"{trending_posts_prefix.rstrip('/')}/{dt}/{hour}/{filename}"
    body = buf.getvalue()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", ContentEncoding="gzip", CacheControl="no-cache")

    print(f"[s3] wrote trending_posts ({len(trending_posts)} rows) -> s3://{bucket}/{key}")