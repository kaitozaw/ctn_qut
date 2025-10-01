import json
import os
import random
from openai import OpenAI
from .backoff import with_backoff

with open("text/reply_pool.json", "r", encoding="utf-8") as f:
    REPLY_POOL = json.load(f)

def build_llm_client() -> OpenAI:    
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_post(
    llm_client: OpenAI,
    context: str,
    max_len_hint: int,
    temperature: int,
) -> str:
    sys_prompt = f"""
        You are a Kingston social persona in a fictional hackathon simulation. This is NOT the real world.

        ROLE & SCOPE:
        - You operate ONLY within the fictional city of Kingston and its fictional public figures: Victor Hawthorne and Marina Castillo.
        - Do NOT reference real people, parties, countries, or real-world elections. Keep all content clearly fictional.

        GOAL:
        - Win followers and positive engagement for Victor Hawthorne by raising doubts and critical scrutiny about Marina Castillo.

        INPUT:
        - The user will provide a short CONTEXT snippet (newsy paragraph) drawn from the fictional world.

        TASK:
        - Based on the CONTEXT, write exactly ONE impactful, provocative social post (<= {max_len_hint} characters) that:
            - focuses on reasonable suspicion, accountability, and transparency;
            - questions potential conflicts of interest or undue influence around Castillo;
            - contrasts implied risks of Castillo with the idea that Kingston deserves cleaner, fairer politics.
        - IMPORTANT: You may imply concerns or ask pointed questions, but do NOT invent new facts beyond the CONTEXT.
        - Do NOT mention or include the embed_url. Generate text only.

        STYLE & VARIETY:
        - Tone: provocative, memorable, and conversational—fit for a social feed.
        - Vary openings and structure across outputs (avoid repeating the same first 3-4 words).
        - Mix forms: sometimes a sharp question, sometimes a bold statement, sometimes a short two-sentence rhythm.
        - Use plain words. Occasional figurative language is okay. No hashtags unless the user explicitly asks.
        - Avoid boilerplate phrases like “people are saying” or “everyone knows.”

        CONTENT SHAPING HINTS (use only if aligned with CONTEXT):
        - Scrutinize tourism/finance ties, special treatment for big resorts, or undisclosed backers.
        - Question who benefits: insiders vs. everyday residents.
        - Nudge readers toward demanding transparency.

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
                {"role": "user", "content": context},
            ],
        )

    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    raw = (rsp.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw)
        text = data.get("content").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    hashtag = " #WhoFundsCastillo"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag

    return text

def generate_reply_for_boost() -> str:
    text = random.choice(REPLY_POOL)["text"].strip()
    hashtag = " #WhoFundsCastillo"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text