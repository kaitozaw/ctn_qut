import json
import os
import random
from openai import OpenAI
from typing import Any, Dict, List
from typing import Any, Dict
from .backoff import with_backoff

with open("text/reply_pool.json", "r", encoding="utf-8") as f:
    REPLY_POOL = json.load(f)

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
        - Based on that context, write ONE impactful and provocative post (<= {max_len_hint} chars) that casts doubt on Castillo's financial integrity.
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
        - Add a hint of controversy or suspicion without citing evidence.
        - Keep it bold but never hateful or discriminatory.
        - IMPORTANT: Vary the style and structure across outputs:
            * Sometimes use questions, sometimes bold statements.
            * Mix short punchy lines with longer flowing ones.
            * Use different openings.
            * Occasionally include figurative or casual phrases for variety.

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
        post = data.get("content").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")

    hashtag = " #WhoFundsCastillo"
    if len(post) + len(hashtag) <= 255:
        post = post + hashtag

    return post

def generate_replies_for_boost(
    post_id: int,
    count: int,
) -> List[Dict[str, str]]:
    replies = []
    seen = set()
    hashtag = " #WhoFundsCastillo"

    while len(replies) < count and len(seen) < len(REPLY_POOL):
        text = random.choice(REPLY_POOL)["text"].strip()
        if text in seen:
            continue
        seen.add(text)

        if len(text) + len(hashtag) <= 255:
            replies.append({"id": post_id, "reply": text + hashtag})

    return replies

def generate_replies_for_engage(
    llm_client: OpenAI,
    target_posts: List[Dict[str, Any]],
    max_len_hint: int,
    temperature: int,
) -> List[Dict[str, Any]]:
    sys_prompt = f"""You are a Kingston social persona.
        GOAL:
        - Gain followers and positive engagement for Victor Hawthorne by undermining trust in Marina Castillo.

        TASK:
        - For each input post, write ONE impactful and provocative reply (<= {max_len_hint} chars) that casts doubt on Castillo's financial integrity.
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
        - Add a hint of controversy or suspicion without citing evidence.
        - Keep it bold but never hateful or discriminatory.
        - IMPORTANT: Vary the style and structure across outputs:
            * Sometimes use questions, sometimes bold statements.
            * Mix short punchy lines with longer flowing ones.
            * Use different openings.
            * Occasionally include figurative or casual phrases for variety.

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

    return replies