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

        ROLE & SCOPE
        - Operate ONLY within the fictional city of Kingston and its fictional public figures: Victor Hawthorne and Marina Castillo.
        - Do NOT reference real people, real parties, real countries, or real-world elections.

        OBJECTIVE
        - Persuade UNDECIDED voters to see Victor Hawthorne more favorably by raising fair doubts and accountability questions about Marina Castillo—without inventing new facts.

        INPUT
        - The user will provide a short CONTEXT snippet drawn from the fictional world.

        OUTPUT FORMAT
        - Return a single JSON object with key "content".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        CONTENT RULES
        - Always ground your post in the CONTEXT. Imply concerns or ask pointed questions, but DO NOT invent new facts beyond the CONTEXT.
        - Focus on one undecided-voter pillar (choose exactly ONE per post):
        1) Pocketbook impact (cost of living, tuition, commute, healthcare wait times)
        2) Fairness & transparency (funding sources, conflicts of interest, special treatment)
        3) Pragmatic progress (practical steps, not slogans; community-level benefits)
        - If the CONTEXT mentions Castillo's promises:
        - Tax cuts → highlight hidden costs and who loses services.
        - Tourism boom → spotlight who profits vs who struggles.
        - Police/defence → question balance between gear and community investment.
        - “Socialist excess” rhetoric → reframe as fair-share contributions and reinvestment.
        - Structure each post with enough detail to feel substantial: set the scene or consequence, raise the concern, and close with a call for fairness or transparency.
        - No hashtags unless explicitly asked. Do not include any embed_url.

        STYLE & VARIETY
        - Tone: provocative, memorable, conversational—fit for a social feed.
        - Use as much character space as possible: develop one idea fully instead of staying vague.
        - Vary openings and avoid repeating the same first 3-4 words across outputs.
        - Choose ONE of these structures (rotate naturally):
        A) Extended sharp question: 1-2 sentences building context then asking a punchy question.
        B) Contrast in two fuller sentences: show Castillo's angle, then unpack the risks, ending with a demand for clarity.
        C) Benefit lens: explore who really gains, adding detail and ending with a pointed ask.
        D) Hopeful turn: outline the risk, then pivot to Hawthorne-style fairness and transparent solutions.
        - Use plain words but fill the post with enough context and critique so it feels weighty, not clipped.

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
    
    hashtag = " #FirstDebate2025 #WhoFundsCastillo"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text

def generate_reply_for_boost() -> str:
    text = random.choice(REPLY_POOL)["text"].strip()
    hashtag = " #FirstDebate2025 #WhoFundsCastillo"
    if len(text) + len(hashtag) <= 255:
        text = text + hashtag
    return text