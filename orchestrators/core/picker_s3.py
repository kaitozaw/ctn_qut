import json, os, time, uuid
import boto3
from botocore.config import Config
from typing import Optional, Dict, Any, Tuple

def _iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def _get_s3_and_cfg() -> Tuple[any, str, str, str]:
    region = os.getenv("AWS_REGION") or "ap-southeast-2"
    bucket = os.getenv("AWS_S3_BUCKET")
    current_key = os.getenv("PICKER_CURRENT_KEY", "picker/current.json")
    history_prefix = os.getenv("PICKER_HISTORY_PREFIX", "picker/history/")
    s3 = boto3.client("s3", region_name=region, config=Config(retries={"max_attempts": 5, "mode": "standard"}))
    return s3, bucket, current_key, history_prefix

def read_current() -> Optional[Dict[str, Any]]:
    s3, bucket, current_key, _ = _get_s3_and_cfg()
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
    s3, bucket, current_key, history_prefix = _get_s3_and_cfg()
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