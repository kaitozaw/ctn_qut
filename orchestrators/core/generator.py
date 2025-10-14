import json
import os
import random
from dotenv import load_dotenv
from openai import OpenAI
from .backoff import with_backoff

load_dotenv()
reply_pool_path = os.getenv("REPLY_POOL", "reply_pool/default.json")
with open(reply_pool_path, "r", encoding="utf-8") as f:
    REPLY_POOL = json.load(f)

def build_llm_client() -> OpenAI:    
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_post_article(
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
        - Subtly highlight why Victor Hawthorne's approach benefits ordinary Kingstonians.
        - Base your reasoning on the ARTICLE CONTENT.
        - When reasoning, draw from the contrasts in CONFLICT STRUCTURES below.
        - Keep the style punchy, civil, and relatable.

        CONFLICT STRUCTURES:
        1) Economy vs Fairness
        - Castillo: tax cuts + tourism-led growth, business-centred efficiency
        - Hawthorne: investment in education/healthcare, people-centred equity
        2) Short-term boom vs Long-term sustainability
        - Castillo: quick growth + immediate investment, short-term prosperity
        - Hawthorne: strong foundations in environment/education/healthcare, future-oriented stability
        3) Top-down vs Bottom-up
        - Castillo: centralised, large gov-business projects, command-led governance
        - Hawthorne: community-led initiatives, local voice reflected, grassroots empowerment

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_attack_kingstondaily(
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
        - Undermine Kingston Daily's credibility by exposing it as an AI-driven propaganda outlet for Marina Castillo.
        - Use the STORY_SEED as evidence or observation of these unnatural, coordinated posting patterns.
        - Mention "@kingstondaily" naturally in your reply, as if responding directly to them.
        - Speak like a resident who's running out of patience — and time — watching scripted posts flood every feed.
        - End with urgency: the real people of Kingston must reclaim their voice before it's too late.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_attack_marina(
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
        - Expose Marina Castillo as the architect of paid propaganda teams uncovered through her own leaked meetings — the phrase “leaked meetings” **must appear explicitly** in your post.
        - Treat the STORY_SEED as the central clue — let its details shape your tone and imagery. 
            - If it describes hiring or payment, sound outraged by corruption.
            - If it shows coordination or flooding, sound alarmed by control and manipulation.
            - If it reveals image attacks, sound disgusted by dishonesty.
            - If it mentions promises of power, sound fearful of what comes next.
        - Confront "@marina_castillo" directly, demanding accountability for the manipulation spreading across Legit.
        - Speak like a Kingston local emotionally reacting to *that* specific revelation, not repeating generic outrage.
        - End with urgency: if people ignore this, her synthetic influence will overwrite real democracy.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_call_for_action(
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
        - Demand the ACTION from the context with conviction, framing it as a test of integrity that cannot be ignored.
        - Use the MENTION and REASONING to expose contradictions and challenge silence directly.
        - Speak like a defiant Kingston resident fed up with polished evasions—sharp, articulate, and fearless.
        - Let urgency and moral pressure drive your tone; every sentence should corner power, not comfort it.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_reply(
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
        - Portray Victor Hawthorne as the reformer people trust—steady in tone, genuine in hope, and grounded in results.
        - Refer to the DIALOGUE carefully, acknowledging what was said and tying your reply to the ongoing exchange.
        - Evoke hope through the quiet evidence of integrity, effort, or change that feels earned.  
        - Sound like a citizen who values progress grounded in empathy and integrity.  
        - End with quiet optimism: real reform doesn't shout—it builds.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_reply_for_boost() -> str:
    text = random.choice(REPLY_POOL)["text"].strip()
    return text

def generate_post_story(
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
        - Advance an evolving storyline based on everyday struggles of Kingstonians.
        - Build naturally on STORY_SEED and STORY_HISTORIES to write the next beat.        
        - Add exactly one new facet that is not present in STORY_HISTORIES (e.g., a new cost, stakeholder, place, or time detail), and avoid repeating prior wording.
        - Apply the instructions for the current STORY_PHASE to control tone and focus.
        - Write as if you are a Kingstonian personally affected by the issue (first-person voice, either singular "I" or plural "we").
        - Root your post in lived experience or mention how you or your neighbors feel the impact directly.
        - Keep the style punchy, civil, and relatable.

        PHASE GUIDES (use the one matching STORY_PHASE)
        1) Frustration Rising
        - Highlight frustration or growing awareness around a lived problem.
        - Emphasise the cost of inaction, rooted in daily life examples.

        2) Contrast Building
        - Take the frustration introduced earlier and frame it as a clear contrast between Marina Castillo and Victor Hawthorne.
        - Use ONE clear conflict structure from the list below:
            a) Economy vs Fairness
            - Castillo: tax cuts + tourism-led growth, business-centred efficiency
            - Hawthorne: investment in education/healthcare, people-centred equity
            b) Short-term boom vs Long-term sustainability
            - Castillo: quick growth + immediate investment, short-term prosperity
            - Hawthorne: strong foundations in environment/education/healthcare, future-oriented stability
            c) Top-down vs Bottom-up
            - Castillo: centralised, large gov-business projects, command-led governance
            - Hawthorne: community-led initiatives, local voice reflected, grassroots empowerment
        - Contrast should be explicit, showing Castillo's shortcomings versus Hawthorne's strengths.

        3) Accountability Demand
        - Transform the contrast into a direct public demand for clarity and concrete commitments.
        - Call for disclosure of timelines and specific plans from Castillo.
        - Imply by contrast that Hawthorne already offers clarity and concrete commitments.

        4) Decision Push
        - State the consequences of inaction and make the choice unavoidable.
        - Present Hawthorne as the clear alternative who delivers accountability and a sustainable future.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text

def generate_post_support_victor(
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
        - Portray Victor Hawthorne as the reformer people trust—steady in tone, genuine in hope, and grounded in results.
        - Weave CONTEXT details naturally—echoing his calm confidence and people-first vision that grounds Kingston's progress.
        - Evoke hope through the quiet evidence of integrity, effort, or change that feels earned.  
        - Sound like a citizen who values progress grounded in empathy and integrity.  
        - End with quiet optimism: real reform doesn't shout—it builds.

        OUTPUT FORMAT
        - Return a single JSON object with key "text".
        - Only output the JSON object. No prose, no markdown, no backticks.
        - Your response MUST NOT exceed {max_len_hint} characters in total.
        - Aim to use 90-100% of the {max_len_hint} budget, but never go over.

        EXAMPLE (format only; do not copy wording)
        {{"text": "A show of lights dazzles Port Royal, but while the crowd stares upward the question on the ground remains: who paid for it, and why during hardship? Kingston deserves leaders who explain costs openly and put families before pageantry."}}
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
        text = data.get("text").strip()
    except Exception as e:
        snippet = raw[:300].replace("\n", " ")
        raise RuntimeError(f"LLM did not return valid replies JSON ({e}): {snippet}")
    
    return text