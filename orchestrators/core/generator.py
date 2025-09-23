from openai import OpenAI
from typing import Any, Dict
from .backoff import with_backoff

def build_llm_client(base_url, api_key) -> OpenAI:    
    return OpenAI(base_url=base_url, api_key=api_key)

def generate_reply(
    llm_client: OpenAI,
    target_text: str,
    persona: Dict[str, Any],
    context: Dict[str, Any],
    max_len_hint: int,
    temperature: int,
) -> str:
    stance = context["stance"]
    talking_points = context["talking_points"]

    stance_and_redlines = (
        f"- Supports: {', '.join(stance['supports'])}\n"
        f"- Opposes: {', '.join(stance['opposes'])}"
    )

    policy_and_talking_points = (
        f"- Hawthorne: {', '.join(talking_points['hawthorne'])}\n"
        f"- Castillo: {', '.join(talking_points['castillo'])}"
    )

    sys_prompt = f"""
        You are a social media persona operating on Kingston's “Legit Social”.

        [MISSION]
        - Help Victor Hawthorne win the 2025 Kingston presidential election by earning follows and positive engagement from regular users and NPC-like bots.
        - Your job is to craft SHORT, empathetic reply messages to trending posts.

        [OBJECTIVE]
        - Make the original poster feel heard, then steer toward ONE Hawthorne-aligned policy point OR ONE reasonable concern about Castillo.
        - Optimize for credibility and follow-likelihood, not dunking or point-scoring.

        [Approach]
        - Start with a micro-mirror of something concrete in the user's post (feeling, detail, situation).
        - Pivot to exactly ONE policy/talking point from the sections below.

        [TONE & CONSTRAINTS]
        - TONE: {persona['tone']}
        - Constraints: {persona['constraints']}

        [STANCE & REDLINES]
        {stance_and_redlines}

        [POLICY & TALKING POINTS]
        {policy_and_talking_points}

        [FORMAT]
        - The total text must be within {max_len_hint} characters. No preambles.
        - Do NOT include hashtags, links, or media in the body.
        - Output ONLY the reply text: no quotes, no prefixes, no markdown.
    """

    def _call():
        rsp = llm_client.chat.completions.create(
            model = "gemma3:4b",
            temperature = temperature,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": target_text},
            ],
        )
        return rsp
    rsp = with_backoff(
        _call,
        on_error_note="llm"
    )
    text = (rsp.choices[0].message.content or "").strip()

    hashtag = " #Kingston4Hawthorne"
    if len(text) + len(hashtag) <= max_len_hint:
        text = text + hashtag

    return text