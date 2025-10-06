import json
import random
import threading
import time
import twooter.sdk as twooter
from openai import OpenAI
from queue import Full, Queue
from typing import Any, Dict, List, Optional, Set
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_post_article, generate_post_reply, generate_post_reply_for_boost, generate_post_story
from .picker import pick_post_by_id, pick_posts_from_feed, pick_posts_from_notification
from .picker_s3 import get_random_article, get_story_histories, read_current, write_current_and_history, write_story_histories, write_trending_posts
from .text_filter import safety_check
from .transform import extract_post_fields

def _choose_goal() -> int:
    return random.choices([500, 1000], weights=[0.8, 0.2], k=1)[0]

def _decide_story_phase(story_histories: Dict[str, List[str]]) -> str:
    if not isinstance(story_histories, dict):
        return "Frustration Rising"

    phases_order = ["Frustration Rising", "Contrast Building", "Accountability Demand", "Decision Push"]
    for phase in phases_order:
        texts = story_histories.get(phase, [])
        if not isinstance(texts, list):
            texts = []
        if len(texts) < 10:
            return phase
    return "Decision Push"

def _enqueue_job(
    send_queue: Queue,
    lock: threading.Lock,
    fn,
    relogin_fn,
    note: str,
    persona_id: str,
    reply_id: int = None,
    post_id: int = None,
    text: str = None,
):
    job = {"lock": lock, "fn": fn, "relogin_fn": relogin_fn, "note": note, "persona_id": persona_id, "reply_id": reply_id, "post_id": post_id, "text": text}
    try:
        send_queue.put_nowait(job)
        return True
    except Full:
        return False

def _filter_notification_posts_from_npcs(
    notification_posts: List[Dict[str, Any]],
):
    filtered_posts = []
    for post in notification_posts:
        author_id = (post or {}).get("author_id")
        if isinstance(author_id, int) and author_id <= 800:
            filtered_posts.append(post)
    return filtered_posts

def _generate_and_send_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    ng_words: List[str],
    parent_post: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    generated_post = _generate_post(cfg, llm_client, parent_post) 
    if not generated_post or not generated_post.get("text"):
        return None
    
    text = generated_post.get("text")
    parent_id = generated_post.get("parent_id")
    embed_url = generated_post.get("embed_url")

    sent_post = _send_post(cfg, t, ng_words, text, parent_id, embed_url)
    if not sent_post:
        return None

    return sent_post

def _generate_post(
    cfg: Dict[str, Any],
    llm_client: OpenAI,
    parent_post: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    if parent_post:
        parent_id = parent_post.get("id")
        author = parent_post.get("author_username")
        content = parent_post.get("content")

        context = f"""
            REPLY_CONTEXT:
            From: {author}
            Message: {content}
        """
        max_reply_len = 100
        temperature = 0.7
        try:
            text = generate_post_reply(llm_client, context, max_reply_len, temperature)
            hashtag = " #TideTurning"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "parent_id": parent_id or None}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None

    content_type = (cfg.get("content_type") or "").strip()
    if content_type == "article":
        article = get_random_article()
        embed_url = (article or {}).get("embed_url")
        article_content = (article or {}).get("article_content")

        context = f"""
            ARTICLE_CONTENT:
            {article_content}
        """
        max_reply_len = 200
        temperature = 0.7
        try:
            text = generate_post_article(llm_client, context, max_reply_len, temperature)
            hashtag = " #TideTurning"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "embed_url": embed_url or None}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None

    elif content_type == "story":
        persona_id = (cfg.get("persona_id") or "").strip()
        story_seed = (cfg.get("story_seed") or "").strip()
        story_histories = get_story_histories(persona_id)
        story_phase = _decide_story_phase(story_histories)
        recent_histories = {phase: (texts[-3:] if isinstance(texts, list) else []) for phase, texts in (story_histories or {}).items()}
        temp_by_phase = {
            "Frustration Rising": 0.8,
            "Contrast Building": 0.6,
            "Accountability Demand": 0.55,
            "Decision Push": 0.45
        }

        context = f"""
            STORY_SEED:
            {story_seed}

            STORY_HISTORIES (phase-wise, recent last):
            {json.dumps(recent_histories, ensure_ascii=False, indent=2)}

            STORY_PHASE: 
            {story_phase}
        """
        max_reply_len = 200
        temperature = temp_by_phase.get(story_phase, 0.7)
        try:
            text = generate_post_story(llm_client, context, max_reply_len, temperature)
            write_story_histories(persona_id, story_phase, text)
            hashtag = " #TideTurning"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None
    else:
        return None

def _send_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    ng_words: List[str],
    text: str,
    parent_id: Optional[int] = None,
    embed_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    ok, safe_text, reason = safety_check(text, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason}")
        return None
    
    post_create= with_backoff(
        lambda: t.post(safe_text, parent_id=parent_id or None, embed=embed_url or None),
        on_error_note="post_create",
        relogin_fn=relogin_fn
    )
    item = (post_create or {}).get("data") or {}
    post = extract_post_fields(item)
    if not post["id"]:
        print("[post-error] failed to get post_id")
        return None

    print(f"[sent] persona={persona_id} post_id={post['id']} text={post['content']!r}")
    return post

def attract(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    ng_words: List[str],
    replied_posts: Set[int],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    cur = read_current()
    current_post_id = (cur or {}).get("post_id", 0)
    current_persona_id = (cur or {}).get("persona_id", "")
    current_reply_goal = (cur or {}).get("reply_goal", 0)
    if not isinstance(current_post_id, int) or not isinstance(current_persona_id, str) or not isinstance(current_reply_goal, int):
        return "INVALID_CURRENT_JSON"
    
    post = pick_post_by_id(cfg, t, current_post_id) if current_post_id else {}
    reply_count = post.get("reply_count", 0)
    
    trending_posts = pick_posts_from_feed(cfg, t, "trending") or []
    write_trending_posts(trending_posts)

    replies_to_npc = []
    if persona_id != current_persona_id:
        notification_posts = pick_posts_from_notification(cfg, t)
        notification_posts_from_npc = _filter_notification_posts_from_npcs(notification_posts)
        for notification_post in notification_posts_from_npc:
            if notification_post["id"] not in replied_posts:
                reply = _generate_and_send_post(cfg, t, llm_client, ng_words, notification_post)
                if reply:
                    replies_to_npc.append(reply)
                    replied_posts.add(notification_post["id"])
            time.sleep(5)

    if not cur or not post or reply_count >= current_reply_goal:
        if replies_to_npc:
            target_post = replies_to_npc.pop(0)
        else: 
            target_post = _generate_and_send_post(cfg, t, llm_client, ng_words)
            if not target_post:
                return "NO_TARGET_POST"
        new_goal = _choose_goal()
        write_current_and_history(target_post["id"], persona_id, new_goal)
        return "SET NEW POST"
    
    return "CONTINUE CURRENT POST"

def boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    replied_posts: Set[int],
    send_queue: Queue,
    lock: threading.Lock,
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    cur = read_current()
    if not cur:
        return "NO_CURRENT_JSON"
    current_post_id = cur.get("post_id")
    if not isinstance(current_post_id, int):
        return "INVALID_CURRENT_JSON"
    
    if current_post_id not in replied_posts:
        def _like(): return t.post_like(post_id=current_post_id)
        def _repost(): return t.post_repost(post_id=current_post_id)
        if lock:
            with lock:
                try:
                    with_backoff(_like, on_error_note="like", relogin_fn=relogin_fn)
                except Exception as e:
                    pass
                try:
                    with_backoff(_repost, on_error_note="repost", relogin_fn=relogin_fn)
                except Exception as e:
                    pass
        else:
            try:
                with_backoff(_like, on_error_note="like", relogin_fn=relogin_fn)
            except Exception as e:
                pass
            try:
                with_backoff(_repost, on_error_note="repost", relogin_fn=relogin_fn)
            except Exception as e:
                pass
        replied_posts.add(current_post_id)
    
    text = generate_post_reply_for_boost()
    hashtag = " #TideTurning"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag

    def _send(): return t.post(text, parent_id=current_post_id)
    enq = _enqueue_job(send_queue, lock=lock, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=current_post_id, text=text)
    if not enq:
        return "SKIPPED"
    return "ENQUEUED"