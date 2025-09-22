from openai import OpenAI
from typing import Any, Dict
from .backoff import with_backoff

def build_llm_client(base_url, api_key) -> OpenAI:    
    return OpenAI(base_url=base_url, api_key=api_key)

def generate_reply(
    llm_client: OpenAI,
    temperature: float,
    persona: Dict[str, Any],
    target_text: str,
    max_len_hint: int,
) -> str:
    sys_prompt = (
        f"You are a social media persona. "
        f"Tone: {persona.get('tone','neutral')}. "
        f"Constraints: {persona.get('constraints','be civil and concise')}. "
        f"Reply under {max_len_hint} characters. No preambles."
    )
    def _call():
        rsp = llm_client.chat.completions.create(
            model = "gemma3:4b",
            temperature=float(temperature),
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
    return text