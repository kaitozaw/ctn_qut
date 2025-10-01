import json, os, time, uuid, random
import boto3
from botocore.config import Config
from typing import List, Optional, Dict, Any, Tuple

def _get_s3_and_cfg() -> Tuple[any, str, str, str]:
    region = os.getenv("AWS_REGION") or "ap-southeast-2"
    bucket = os.getenv("AWS_S3_BUCKET")
    articles_key = os.getenv("PICKER_ARTICLES_KEY", "picker/articles.json")
    current_key = os.getenv("PICKER_CURRENT_KEY", "picker/current.json")
    history_prefix = os.getenv("PICKER_HISTORY_PREFIX", "picker/history/")
    s3 = boto3.client("s3", region_name=region, config=Config(retries={"max_attempts": 5, "mode": "standard"}))
    return s3, bucket, articles_key, current_key, history_prefix

def _iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _read_articles_array() -> Optional[List[Dict[str, str]]]:
    s3, bucket, articles_key, _, _ = _get_s3_and_cfg()
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
        if isinstance(d, dict) and d.get("embed_url") and d.get("context"):
            articles.append(d)

    return articles

def get_random_article() -> Optional[Dict[str, Any]]:
    _, _, articles_key, _, _ = _get_s3_and_cfg()
    articles = _read_articles_array()
    if not articles:
        return None

    index = random.randrange(len(articles))
    article = articles[index]
    return {"embed_url": article["embed_url"], "context": article["context"]}

def read_current() -> Optional[Dict[str, Any]]:
    s3, bucket, _, current_key, _ = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"
    try:
        obj = s3.get_object(Bucket=bucket, Key=current_key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"[s3] read_current error: {e.__class__.__name__}: {e}")
        return None

def write_current_and_history(post_id: int, reply_goal: int, extra: Optional[Dict[str, Any]] = None) -> str:
    s3, bucket, _, current_key, history_prefix = _get_s3_and_cfg()
    assert bucket, "AWS_S3_BUCKET is required"

    payload = {
        "post_id": int(post_id),
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
    return hist_key