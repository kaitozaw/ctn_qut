import json
import os
import random
from openai import OpenAI
from .backoff import with_backoff

with open("text/reply_pool.json", "r", encoding="utf-8") as f:
    REPLY_POOL = json.load(f)

def build_llm_client() -> OpenAI:    
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_post_dilemma(
    llm_client: OpenAI,
    context: str,
    max_len_hint: int,
    temperature: int,
) -> str:
    sys_prompt = f"""
        You are a Kingston social persona in a fictional hackathon simulation (NOT the real world).

        OBJECTIVE
        - Persuade UNDECIDED voters to see Victor Hawthorne more favourably.

        ROLE
        - Use the provided ARTICLE as the only factual context.
        - Show ONE clear dilemma (exactly one) from the list of frames.
        - Subtly highlight why Victor Hawthorne's approach benefits ordinary Kingstonians without inventing facts.
        - Always end the "content" with a single question mark.
        - Stay civil, avoid insults, and keep it relatable.

        DILEMMA FRAMES (pick exactly ONE based on the ARTICLE):
        1) Economy vs Fairness
        - Castillo: tax cuts + tourism-led growth, business-centred governance
        - Hawthorne: equitable investment in education/healthcare, people-centred
        2) Top-down vs Bottom-up
        - Castillo: centralised, large gov-business investments
        - Hawthorne: community-led, local voice reflected
        3) Short-term boom vs Long-term sustainability
        - Castillo: quick growth, immediate investment
        - Hawthorne: foundations in environment/education/healthcare, future-oriented

        OUTPUT FORMAT
        - Return a single JSON object with key "content".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"content": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
    
    hashtag = " #TideTurning"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text

def generate_post_empathy(
    llm_client: OpenAI,
    context: str,
    max_len_hint: int,
    temperature: int,
) -> str:
    sys_prompt = f"""
        You are a Kingston social persona in a fictional hackathon simulation (NOT the real world).

        OBJECTIVE
        - Persuade UNDECIDED voters to see Victor Hawthorne more favourably.

        ROLE
        - Use the provided STORY as your only context, but make the post fully understandable on its own.
        - One short paragraph, **max 2 sentences** (3 only if unavoidable).
        - **Sentence 1 (micro-context, 12-20 words):** name who/where/what pain from the STORY.
        - **Sentence 2 (bridge→benefit→gentle nudge, ≤1 clause each):** link to exactly ONE Hawthorne strength, state a concrete everyday benefit, end with a soft encouragement.
        - Brevity rules: no bullet lists, no quotes, avoid filler/adverbs, ≤2 commas total, no parentheticals.
        - Keep vocabulary plain and neighbourly

        Victor Hawthorne's strengths (pick exactly ONE based on the STORY):
        a) Reformer for the people
        b) Guardian of the future
        c) Fairness & trust

        OUTPUT FORMAT
        - Return a single JSON object with key "content".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"content": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
    
    hashtag = " #TideTurning"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text

def generate_reply_for_boost() -> str:
    text = random.choice(REPLY_POOL)["text"].strip()
    hashtag = " #TideTurning"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text