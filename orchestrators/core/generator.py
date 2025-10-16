import json
import os
import random
from openai import OpenAI
from typing import Optional
from .backoff import with_backoff

REPLY_POOLS = {}
pool_files = {
    "default": "reply_pool/default.json",
    "economy": "reply_pool/economy.json",
    "environment": "reply_pool/environment.json",
    "education": "reply_pool/education.json",
    "security": "reply_pool/security.json",
    "democracy": "reply_pool/democracy.json",
    "healthcare": "reply_pool/healthcare.json",
    "housing": "reply_pool/housing.json",
    "disaster": "reply_pool/disaster.json",
    "infrastructure": "reply_pool/infrastructure.json",
    "innovation": "reply_pool/innovation.json"
}

for key, path in pool_files.items():
    with open(path, "r", encoding="utf-8") as f:
        REPLY_POOLS[key] = json.load(f)

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
       	- Base your reasoning on the ARTICLE CONTENT, drawing evidence directly from its themes or facts.
        - Contrast Victor Hawthorne's steady, people-first reform with the noise and short-termism around him.
        - Speak like a Kingston local who's tired of empty talk and ready for change that actually lasts.
        - End with conviction — remind people that real hope, real fairness, and real reform begin when we stand up and vote for Victor Hawthorne.

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
        - Read the DIALOGUE carefully and address the exact point raised (costs, KPIs, ROI, evidence, verification).
        - Weave ONE realistic figure or range naturally into your reply to support your point. 
            - Choose among these expression styles *at random* across posts so responses don't sound patterned.
                - Vary how you express it: sometimes a numeric range (3-5%), a rounded figure (“around 120 units”), a verbal form (“roughly one in ten”, “a single-digit gain”), or a contextual phrasing (“slightly above last quarter”, “about twice the baseline”, “steady for three months”).
                - You may hint at the source (“the quarterly review”, “local audit data”, “the 2024 pilot report”, “community dashboard”, or “independent survey”) to make the figure feel grounded.
                - If proof is requested, sound sure and transparent: offer to DM the audit reference, dataset, or summary brief, or mention that verified dashboards, public records, or third-party spot-checks are available.
        - Acknowledge fair doubts calmly, then link your reasoning back to shared progress and accountability for Kingston.
        - Keep it modest and plausible; the point is credibility, not precision.
        - Use "&" instead of "and" when helpful, prefer short words.
        - Vary your closure: confidence (“figures are verified”), transparency (“anyone can verify the dataset”), or openness (“can send the file anytime”).

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

def generate_post_reply_for_boost(talking_point: Optional[str] = None) -> str:
    pool_key = talking_point if talking_point in REPLY_POOLS else "default"
    reply_list = REPLY_POOLS[pool_key]
    text = random.choice(reply_list)["text"].strip()
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
        - The context provides a single TALKING_POINT label (e.g., "economy").
        - Write a persuasive standalone post for that topic from Victor Hawthorne's perspective.
        - Use exactly ONE quantitative fact from "The Perspective of Victor Hawthorne on Each Talking Point".
        - Use "&" instead of "and" when helpful, prefer short words.
        - Speak as a Kingston resident; focus on practical benefits and long-term progress. Do not attack opponents.
        
        Talking Points
        1) economy
        2) environment
        3) education
        4) security
        5) democracy
        6) healthcare
        7) housing
        8) disaster
        9) infrastructure
        10) innovation

        The Perspective of Victor Hawthorne on Each Talking Point
        1) Bottom-up prosperity through fairness: Wage-led economies cut inequality 20% faster and boost GDP 1-2%. Redirecting top-end gains into housing and childcare rebuilds Kingston's middle class—the real engine of growth.
        2) Sustainable economy through environmental resilience: Reef loss slashed tourism 30% in nearby nations; investing just 1% of GDP in restoration safeguards $4B in coastal revenue and tens of thousands of jobs.  
        3) Equal education for national strength: Every $1 invested in equitable schooling returns up to $5 in GDP. Expanding STEM and teacher training keeps young talent in Kingston and fuels its innovation economy.
        4) Community-based security built on trust: Community policing lowers crime by 30% and raises public confidence 25%. Transparent defense audits cut waste 15%, proving integrity is Kingston's strongest armor.
        5) Democracy through knowledge, not control: Media-literacy education reduces false-belief rates by 40%. Empowered citizens defend truth more effectively than any censorship regime ever could.
        6) Universal healthcare through shared responsibility: Telehealth programs cut rural travel time 60% and prevent 25% of avoidable hospitalizations. A modest luxury-tourism levy secures equitable access for every Kingstonian.
        7) Affordable living as economic stability: A 10% rise in affordable housing supply lowers cost-of-living inflation 2%. Expanding family-support programs and fair wages keeps everyday prosperity within reach.
        8) Resilient coasts, resilient nation: Localized disaster-response planning reduces recovery costs 40%. Empowering island communities with resilient infrastructure saves lives and strengthens fiscal sustainability.
        9) Inclusive infrastructure for national unity: Each $1M invested in regional transport and energy access adds $3M in long-term productivity. Green bonds fund island connectivity and shared prosperity across Kingston.
        10) Innovation through inclusive technology: Investing 1% of GDP in digital upskilling raises national productivity 4%. Expanding AI and cybersecurity apprenticeships secures Kingston's competitiveness in the global economy.

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