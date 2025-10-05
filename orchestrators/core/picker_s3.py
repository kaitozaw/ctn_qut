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
    story_histories_key = os.getenv("PICKER_STORY_HISTORIES_KEY", "picker/contexts/story_histories.json")
    current_key = os.getenv("PICKER_CURRENT_KEY", "picker/current.json")
    history_prefix = os.getenv("PICKER_HISTORY_PREFIX", "picker/history/")
    
    s3 = boto3.client("s3", region_name=region, config=Config(retries={"max_attempts": 5, "mode": "standard"}))
    return s3, bucket, trending_posts_prefix, articles_key, story_histories_key, current_key, history_prefix

def _iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _read_articles_array() -> Optional[List[Dict[str, str]]]:
    s3, bucket, _, articles_key, _, _, _ = _get_s3_and_cfg()
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

def _read_story_histories_dict() -> Dict[str, Dict[str, List[str]]]:
    s3, bucket, _, _, story_histories_key, _, _  = _get_s3_and_cfg()
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

def get_story_histories(persona_id: str) -> Dict[str, List[str]]:
    if not isinstance(persona_id, str) or not persona_id:
        return {}
    story_histories = _read_story_histories_dict()
    return story_histories.get(persona_id, {})

def read_current() -> Optional[Dict[str, Any]]:
    s3, bucket, _, _, _, current_key, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=current_key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"[s3] read_current error: {e.__class__.__name__}: {e}")
        return None

def write_current_and_history(post_id: int, persona_id: str, reply_goal: int, extra: Optional[Dict[str, Any]] = None):
    s3, bucket, _, _, _, current_key, history_prefix = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    payload = {
        "post_id": int(post_id),
        "persona_id": str(persona_id),
        "reply_goal": int(reply_goal),
        "issued_at": _iso_utc_now(),
    }
    if extra:
        payload.update(extra)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hist_key = f"{history_prefix.rstrip('/')}/{payload['issued_at']}-{uuid.uuid4().hex[:6]}.json"
    s3.put_object(Bucket=bucket, Key=hist_key, Body=body, ContentType="application/json", CacheControl="no-cache")
    s3.put_object(Bucket=bucket, Key=current_key, Body=body, ContentType="application/json", CacheControl="no-cache")

    print(f"[s3] set post_id={post_id} -> s3://{bucket}/{current_key} (history={hist_key})")

def write_story_histories(persona_id: str, story_phase: str, text: str):
    s3, bucket, _, _, story_histories_key, _, _ = _get_s3_and_cfg()
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
    s3, bucket, trending_posts_prefix, _, _, _, _ = _get_s3_and_cfg()
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