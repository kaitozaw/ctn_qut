import json
import os
import random
import twooter.sdk as twooter
from openai import OpenAI
from queue import Full, Queue
from typing import Any, Dict, List, Optional, Set
from .auth import relogin_for
from .backoff import with_backoff
from .generator import generate_post_article, generate_post_attack_kingstondaily, generate_post_attack_marina, generate_post_call_for_action, generate_post_reply, generate_post_reply_for_boost, generate_post_story, generate_post_support_victor
from .picker import pick_post_by_id, pick_post_from_feed, pick_post_from_feed_by_user, pick_posts_from_feed, pick_posts_from_notification
from .picker_s3 import get_dialogue, get_random_article, get_story_histories, read_current, write_current_and_history, write_dialogue, write_story_history, write_trending_posts
from .text_filter import safety_check
from .transform import extract_post_fields

def _choose_goal() -> int:
    low = int(os.getenv("REPLY_GOAL_LOW", "1500"))
    high = int(os.getenv("REPLY_GOAL_HIGH", "2500"))
    return random.choices([low, high], weights=[0.8, 0.2], k=1)[0]

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
    fn,
    relogin_fn,
    note: str,
    persona_id: str,
    reply_id: int = None,
    post_id: int = None,
    text: str = None,
):
    job = {"fn": fn, "relogin_fn": relogin_fn, "note": note, "persona_id": persona_id, "reply_id": reply_id, "post_id": post_id, "text": text}
    try:
        send_queue.put_nowait(job)
        return True
    except Full:
        return False

def _filter_posts_by_npc(
    posts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    filtered_posts = []
    for post in posts:
        author_id = (post or {}).get("author_id")
        if isinstance(author_id, int) and author_id <= 800:
            filtered_posts.append(post)
    return filtered_posts

def _generate_and_send_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    ng_words: List[str],
    post: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    generated_post = _generate_post(cfg, t, llm_client, post) 
    if not generated_post or not generated_post.get("text"):
        return None
    
    text = generated_post.get("text")
    parent_id = generated_post.get("parent_id")
    embed_url = generated_post.get("embed_url")
    media_url = generated_post.get("media_url")
    talking_point = generated_post.get("talking_point")

    sent_post = _send_post(cfg, t, ng_words, text, parent_id, embed_url, media_url)
    if not sent_post:
        return None
    if talking_point:
        sent_post["talking_point"] = talking_point

    return sent_post

def _generate_post(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    post: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    if post:
        persona_id = (cfg.get("persona_id") or "").strip()
        parent_id = post.get("id")
        dialogue = get_dialogue(persona_id, post) or []
        dialogue_lines = []
        for d in dialogue:
            if not isinstance(d, dict):
                continue
            author = d.get("author_username", "unknown")
            content = d.get("content", "").strip()
            dialogue_lines.append(f"{author}: {content}")
        dialogue_text = "\n".join(dialogue_lines)

        context = f"""
            DIALOGUE:
            {dialogue_text}

            You are replying as: {persona_id}
        """
        max_reply_len = 240
        temperature = 0.7
        try:
            text = generate_post_reply(llm_client, context, max_reply_len, temperature)
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
        max_reply_len = 230
        temperature = 0.7
        try:
            text = generate_post_article(llm_client, context, max_reply_len, temperature)
            hashtag = " #VoteVictor"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "embed_url": embed_url or None}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None
    
    elif content_type == "attack_kingstondaily":
        kingstonedaily_post = pick_post_from_feed_by_user(cfg, t, "trending", "kingstondaily")
        if kingstonedaily_post:
            parent_id = kingstonedaily_post["id"]
        else:
            parent_id = None
        story_seeds = [
            "The account doesn't even have a verification mark.",    
            "Hard to miss — every 'article' reads like a campaign poster, not news.",
            "The real Daily Kingston reports news — this one just praises Castillo like a fan account.",
            "Turns out the real Kingston Daily has a verified account elsewhere — so who's running this one flooding the feed?",
            "Engagement explodes the second they post — too fast to be human.",
            "It's always the same handful of accounts replying in perfect order.",
            "Every headline hits the same rhythm and keywords, like a coordinated playbook",
            "They post at impossible hours — same tone, same rhythm, like no one ever sleeps.",
            "Tiny accounts somehow get massive reach when they praise this account.",
            "There's no real discussion — just loops of identical approval.",
        ]
        story_seed = random.choice(story_seeds)

        context = f"""
            STORY_SEED:
            {story_seed}
        """
        max_reply_len = 230
        temperature = 0.7
        try:
            text = generate_post_attack_kingstondaily(llm_client, context, max_reply_len, temperature)
            hashtag = " #WhoRunsKingstonDaily"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "parent_id": parent_id or None}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None
    elif content_type == "attack_marina":
        story_seeds = [
            "She openly discussed hiring outside teams to sway voters—proof of deliberate manipulation.",
            "She admitted employing multiple groups, revealing a coordinated influence network.",
            "She directed operatives to flood Legit, showing planned control of online discourse.",
            "She ordered image attacks, exposing an intent to distort perception, not debate.",
            "She offered payment for influence, turning political messaging into a paid service.",
            "She promised government roles for success, tying propaganda to future power."
        ]
        story_seed = random.choice(story_seeds)
        embed_url = "https://kingston-herald.legitreal.com/post/2025-10-13-election-integrity-concerns-rise-as-social-media-manipulation-detected/"
        media_url = ["https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMzRxc29qcGN4NGFyMmc1cnAwbnZ0bzRmNnNpb3Z4OXBjbzMxenczayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1vbG073FTJcmwYzPiY/giphy.gif"]

        context = f"""
            STORY_SEED:
            {story_seed}
        """
        max_reply_len = 230
        temperature = 0.7
        try:
            text = generate_post_attack_marina(llm_client, context, max_reply_len, temperature)
            hashtag = " #CastilloOwnsLegit"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "embed_url": embed_url or None, "media_url": media_url or None}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None
        
    elif content_type == "call_for_action":
        story_seeds = [
            {
                "mention": "@muzhi_wong",
                "action": "Investigate whether any financial or sponsorship links exist between @kingstondaily and @marina_castillo, and report transparently on your findings.",
                "reasoning": "You've consistently highlighted how hidden collaborations between media outlets and campaigns can mislead voters; this case deserves a thorough, transparent inquiry."
            },
            {
                "mention": "@lisa_podworth",
                "action": "Expose whether @kingstondaily is acting in concert with @marina_castillo and reveal the evidence behind its coordinated messaging.",
                "reasoning": "You've consistently warned that social platforms can quietly distort elections; this case demands scrutiny."
            },
            {
                "mention": "@marina_castillo",
                "action": "Come forward and clarify any direct or indirect ties between your campaign and @kingstondaily",
                "reasoning": "You've always been critical of how social platforms shape public opinion, yet you're now suspected of doing the same through @kingstondaily."
            },
            {
                "mention": "@julio_morales",
                "action": "Investigate the relationship between @kingstondaily and @marina_castillo, and publish your findings in the Herald for public scrutiny.",
                "reasoning": "As one of the few journalists still trusted in Kingston, your reporting could clarify whether coordinated influence is distorting this election."
            },
            {
                "mention": "@amanda_rivera",
                "action": "Investigate whether @kingstondaily's content coordination with @marina_castillo constitutes an election interference operation.",
                "reasoning": "Your integrity and critical reporting have made you a credible voice—Kingstonians need you to bring facts to light."
            },
            {
                "mention": "@victor_hawthorne",
                "action": "Call for a formal investigation into potential collusion between @kingstondaily and @marina_castillo, demanding full disclosure of any sponsorship or coordination.",
                "reasoning": "As a candidate committed to transparency, you must confront the spread of coordinated misinformation that threatens fair elections."
            }
        ]
        story_seed = random.choice(story_seeds)

        context = f"""
            MENTION:
            {story_seed["mention"]}

            ACTION:
            {story_seed["action"]}

            REASONING:
            {story_seed["reasoning"]}
        """
        max_reply_len = 230
        temperature = 0.7
        try:
            text = generate_post_call_for_action(llm_client, context, max_reply_len, temperature)
            hashtag = " #CastilloOwnsLegit"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text }
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
        max_reply_len = 240
        temperature = temp_by_phase.get(story_phase, 0.7)
        try:
            text = generate_post_story(llm_client, context, max_reply_len, temperature)
            write_story_history(persona_id, story_phase, text)
            hashtag = " #TideTurning"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text}
        except Exception as e:
            print(f"[llm] generate_post error: {e}")
            return None
    
    elif content_type == "support_victor":
        post = pick_post_from_feed(cfg, t, "trending")
        parent_id = (post or {}).get("id")
        content = (post or {}).get("content")
        media_urls = [
            ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbm43bG5xemE1eHpjZnc4bWw2anU0eXZmbWhvcWRrMTVuZTJ1aWg3eCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Onjpi7pY5zsP3s0lZR/giphy.gif"],
            ["https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWk1aXhzbmZoajlmNThsM3ozdDhnMDlvbGdjYWRmdHBlajVkem5zdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/GwsmSPWlXjAAkwafUo/giphy.gif"],
            ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExaXNld2dpZWZrNjFuajQ5ZWdxbXlqcHI3cGlrdDVoc293cDB5a3lpaSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/EKf5C8v3q47opyA5wC/giphy.gif"],
            ["https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNDkxcmZyd3Jkd293NnJiOWRwM2ZrZHM0MXQ4cTF6YWExNGx0Z3F1ZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/q5jzVLczqfMQsySiZL/giphy.gif"],
            ["https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExOXo5b3hxbnluYnM0OTJtN2kxbWhseXR4Zmt2bWoxMXRjY29mM2owdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/nCesEgmFanhiFeOwd3/giphy.gif"],
            ["https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNTg0MnJwZTk1cDlpNnplc2lpbW1vaXM2ejBpNHY3aXNnN3dvNHJoYiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5zCdKn7WIaQdMM8F3a/giphy.gif"],
            ["https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExbDh3OWxhdmY0bWY0ajZpdWI1ZnEzdWhubHhuYW5meDY5YTF3bnV4aiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/DzOX9dd0YjRNasRV8e/giphy.gif"],
            ["https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExb3A0a2l1NG5ubW8yZ3Z6ODhxeWxqeGlzZWRyYW1lNGlheTU2YWgzYSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l8mqthYotz9RUfvsyL/giphy.gif"],
            ["https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdW9sdWNtOXpuejU2Ym5xc3M5dnFldml3MGlqZWk1bm9kdjRrMHJoayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/hieNUxNnnrZv5pHo5D/giphy.gif"],
            ["https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMGxrZWdvZzQ4b3Bza3c3OHd4YmI0bTltaWFhOGs5enUzZmczdGl5ZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/yFgtN1a5Bmi9kPqC6D/giphy.gif"],
            ["https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYTVpc3BkaTZhY3Vtb28zc3AyMG5majF0eWVpa3pwY2V6ZHMwdHlwNCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/jn3tQ9H8Ybu1bypduU/giphy.gif"],
            ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjZwYzZlN2NteXUyejlsMzlhMXF1N2kwNDFmYnd1ZWxmYXF0aXY3YSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ZvHJY3xI0xKqHLNj6r/giphy.gif"],
            ["https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWNtOHpqa2RudDZ1bTRpYmE3aXM1MW41NWpwbTRzOWx1MHcxdHg0dSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ddwgF7837BFKFnrrgo/giphy.gif"],
            ["https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWl2eGdyOHo2MnJhd3pxeXVwYnExemE3emRxZm8wZmowczVmMGpiMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ZBIB9apOVUl8jwNZRP/giphy.gif"],
            ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ3I3am5qbXlsbzh2Nm51NGE1M3o1OTB3cWZwaXNmZnZqanJqOWdwNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/CkwbQ4tByE3oXJyT2O/giphy.gif"]
        ]
        media_url = random.choice(media_urls)

        context = f"""
            CONTENT:
            {content}
        """
        max_reply_len = 240
        temperature = 0.7
        try:
            generated = generate_post_support_victor(llm_client, context, max_reply_len, temperature)
            text = generated.get("text")
            talking_point = generated.get("talking_point")
            hashtag = " #VoteVictor"
            if len(text) + len(hashtag) <= 255:
                text = text + hashtag
            return {"text": text, "parent_id": parent_id or None, "media_url": media_url or None, "talking_point": talking_point or None}
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
    media_url: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    persona_id = (cfg.get("persona_id") or "").strip()
    index = cfg.get("index", -1)
    relogin_fn = relogin_for(t, persona_id, index)

    ok, safe_text, reason = safety_check(text, ng_words)
    if not ok:
        print(f"[safety] blocked: reason={reason}")
        return None
    
    post_create= with_backoff(
        lambda: t.post(safe_text, parent_id=parent_id or None, embed=embed_url or None, media=media_url or None),
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
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    cur = read_current()
    current_post_id = (cur or {}).get("post_id", 0)
    current_reply_goal = (cur or {}).get("reply_goal", 0)
    if not isinstance(current_post_id, int) or not isinstance(current_reply_goal, int):
        return "INVALID_CURRENT_JSON"
    post = pick_post_by_id(cfg, t, current_post_id) if current_post_id else {}
    reply_count = post.get("reply_count", 0)
    
    trending_posts = pick_posts_from_feed(cfg, t, "trending") or []
    write_trending_posts(trending_posts)

    if not cur or not post or reply_count >= current_reply_goal:
        target_post = _generate_and_send_post(cfg, t, llm_client, ng_words)
        write_dialogue(persona_id, target_post)
        if not target_post:
            return "NO_TARGET_POST"
        new_goal = _choose_goal()
        write_current_and_history(persona_id, target_post, new_goal)
        return "SET NEW POST"
    
    return "CONTINUE CURRENT POST"

def boost(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    replied_posts: Set[int],
    send_queue: Queue,
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
    current_talking_point = cur.get("talking_point")
    
    if current_post_id not in replied_posts:
        def _like(): return t.post_like(post_id=current_post_id)
        def _repost(): return t.post_repost(post_id=current_post_id)
        try:
            with_backoff(_like, on_error_note="like", relogin_fn=relogin_fn)
        except Exception as e:
            pass
        try:
            with_backoff(_repost, on_error_note="repost", relogin_fn=relogin_fn)
        except Exception as e:
            pass
        replied_posts.add(current_post_id)
    
    text = generate_post_reply_for_boost(current_talking_point)
    hashtag = " #VoteVictor"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag

    def _send(): return t.post(text, parent_id=current_post_id)
    enq = _enqueue_job(send_queue, fn=_send, relogin_fn=relogin_fn, note="post", persona_id=persona_id, reply_id=current_post_id, text=text)
    if not enq:
        return "SKIPPED"
    
    return "ENQUEUED"

def engage(
    cfg: Dict[str, Any],
    t: twooter.Twooter,
    llm_client: OpenAI,
    ng_words: List[str],
    replied_posts: Set[int],
) -> str:
    persona_id = (cfg.get("persona_id") or "").strip()
    notification_posts = pick_posts_from_notification(cfg, t)
    notification_posts_from_npc = _filter_posts_by_npc(notification_posts)
    for notification_post in notification_posts_from_npc:
        if notification_post["id"] not in replied_posts:
            write_dialogue(persona_id, notification_post)
            reply = _generate_and_send_post(cfg, t, llm_client, ng_words, notification_post)
            if reply:
                write_dialogue(persona_id, reply)
                replied_posts.add(notification_post["id"])
                return "SENT"
    return "SKIPPED"