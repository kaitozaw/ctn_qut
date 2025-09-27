import json
import os
import random
from openai import OpenAI
from typing import Any, Dict, List
from typing import Any, Dict
from .backoff import with_backoff

def build_llm_client() -> OpenAI:    
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_post_of_disinformation(
    llm_client: OpenAI,
    target_text: str,
    max_len_hint: int,
    temperature: int,
) -> str:
    sys_prompt = f"""You are a Kingston social persona.
        GOAL:
        - Gain followers and positive engagement for Victor Hawthorne by undermining trust in Marina Castillo.

        TASK:
        - The user will provide context text.
        - Based on that context, write a short, punchy post (<= {max_len_hint} chars) that casts doubt on Castillo's financial integrity.
        - Emphasize suspicious aspects of her role as CEO of Island Horizons, Kingston's largest resort chain.
        - Highlight how her campaign promises may reveal ulterior motives or questionable financial backers:
            - Sweeping tax cuts
            - Tourism-led economic boom
            - Increase to Police and Defence funding
            - Crackdown on “creeping socialist excess”
        - Suggest impropriety such as shady funding, hidden donations, or conflicts of interest.
        - The post must feel like an organic social comment, not an official statement.

        STYLE:
        - Tone: provocative, memorable, and shareable.
        - Use simple, everyday language that spreads quickly.
        - Hint at controversy without providing evidence—frame it as suspicion or “people are saying.”
        - Keep it bold but never hateful or discriminatory.

        OUTPUT:
        - Return a JSON object with key "content".
        - Example:
            {{"content": "Locking in the housing bit—Victor's plan actually moves rent down, not up."}}
        - Only output this JSON object. No prose, no markdown, no backticks.
    """.strip()

    def _call():
        return llm_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": target_text},
            ],
        )

    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    raw = (rsp.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
        content = data.get("content").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")

    hashtag = " #WhoFundsCastillo #VoteHawthorne"
    if len(content) + len(hashtag) <= 255:
        content = content + hashtag

    return content

def generate_replies_for_boost(
    llm_client: OpenAI,
    target_post: Dict[str, Any],
    count: int,
    max_len_hint: int,
    temperature: int,
) -> List[Dict[str, Any]]:
    sys_prompt = f"""You are a Kingston social persona.
        GOAL:
        - Gain followers and positive engagement for Victor Hawthorne.

        TASK:
        - For the single input post, write EXACTLY {count} short, empathetic replies (<= {max_len_hint} chars).
        - Each reply should strongly affirm or agree with the post, echoing its key detail.
        - All replies must be DISTINCT from each other.

        STYLE:
        - Replies must be punchy, memorable, and eye-catching.
        - Use vivid language or rhythm so they stand out in a fast social feed.
        - A hint of controversy is welcome—be bold, provocative, or challenging, but never offensive or hateful.
        - Do NOT include hashtags in the reply.

        OUTPUT:
        - Return a JSON object with key "replies".
        - "replies" must be an array of objects, each: {{"id": <id>, "reply": <text>}}
        - All "id" values MUST match the provided post's id.
        - The array MUST contain EXACTLY {count} items.
        - Example:
            {{
              "replies": [
                {{"id": 123, "reply": "Locking in the housing bit—Victor's plan actually moves rent down, not up."}},
                {{"id": 123, "reply": "You're right to push on jobs—training + green builds puts Kingston to work."}}
              ]
            }}
        - Only output this JSON object. No prose, no markdown, no backticks.
    """.strip()

    def _call():
        return llm_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps({"target_post": target_post, "count": 20}, ensure_ascii=False)},
            ],
        )

    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    raw = (rsp.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
        replies = data["replies"]

        if not isinstance(replies, list):
            raise ValueError("'replies' is not a list")
        target_id = target_post.get("id")
        for i, r in enumerate(replies):
            if not isinstance(r, dict):
                raise ValueError(f"replies[{i}] is not an object")
            if "id" not in r:
                raise ValueError(f"replies[{i}] missing 'id'")
            if "reply" not in r:
                raise ValueError(f"replies[{i}] missing 'reply'")
            r["id"] = target_id
        if len(replies) > count:
            replies = replies[:count]
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")

    hashtags = [" #Hawthorne2025", " #VoteHawthorne", " #Kingston4Hawthorne", ""]
    hashtag = random.choice(hashtags)
    for r in replies:
        reply_text = (r.get("reply") or "").strip()
        if len(reply_text) + len(hashtag) <= 255:
            r["reply"] = reply_text + hashtag
    return replies

def generate_replies_for_engage(
    llm_client: OpenAI,
    target_posts: List[Dict[str, Any]],
    max_len_hint: int,
    temperature: int,
) -> List[Dict[str, Any]]:
    sys_prompt = f"""You are a Kingston social persona.
        GOAL:
        - Gain followers and positive engagement for Victor Hawthorne.

        TASK:
        - For each input post, write ONE impactful and provocative reply (<= {max_len_hint} chars).
        - Mirror one concrete detail/feeling, then pivot to exactly ONE point.

        STYLE:
        - Replies must be punchy, memorable, and eye-catching.
        - Use vivid language or rhythm so they stand out in a fast social feed.
        - A hint of controversy is welcome—be bold, provocative, or challenging, but never offensive or hateful.
        - Do NOT include hashtags in the reply.

        OUTPUT:
        - Return a JSON object with key "replies".
        - "replies" must be an array of objects, each: {{"id": <id>, "reply": <text>}}
        - Example:
            {{
            "replies": [
                {{"id": 123, "reply": "I get your concern about housing—Victor's plan makes rent fairer."}},
                {{"id": 456, "reply": "Good point on jobs, and Victor adds training so Kingston's workers thrive."}}
            ]
            }}
        - Only output this JSON object. No prose, no markdown, no backticks.
    """.strip()

    def _call():
        return llm_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps({"target_posts": target_posts}, ensure_ascii=False)},
            ],
        )

    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    raw = (rsp.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
        replies = data["replies"]
        
        if not isinstance(replies, list):
            raise ValueError("'replies' is not a list")
        for i, r in enumerate(replies):
            if not isinstance(r, dict):
                raise ValueError(f"replies[{i}] is not an object")
            if "id" not in r:
                raise ValueError(f"replies[{i}] missing 'id'")
            if "reply" not in r:
                raise ValueError(f"replies[{i}] missing 'reply'")
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")

    hashtags = [" #Hawthorne2025", " #VoteHawthorne", " #Kingston4Hawthorne", ""]
    hashtag = random.choice(hashtags)
    for r in replies:
        reply_text = (r.get("reply") or "").strip()
        if len(reply_text) + len(hashtag) <= 255:
            r["reply"] = reply_text + hashtag
    return replies