**Phase 0: Initial Setup (≈1 hour)**
Prepare a single EC2 instance to host our bots. After that, updates are just git pull + restart.

1. EC2 Instance Setup
- Use t3.small or t3.medium, Amazon Linux 2023, with 20–30GB storage.
- Security group: allow SSH (22) inbound, and outbound HTTP/HTTPS only.
- Create a dedicated Linux user for the bot (no sudo needed).

2. One-time Configuration Inside EC
- Install Git, Python, and venv.
- Create ~/apps/legit-bots and clone the private GitHub repo there.
- Run python -m venv venv and install dependencies (e.g., Twooter SDK) into the venv.
- Create ~/apps/legit-bots/.env with environment variables:
	BASE_URL, COMPETITION_BOT_KEY, TEAM_INVITE_CODE, PERSONAS_DB, TOKENS_DB, TEAMS_DB, etc.
- Create ~/apps/legit-bots/data/ and place personas.db, tokens.db, and teams.db inside.

3. systemd Service (one-time setup)
- Write a unit file that starts the app inside the venv.
- Service config: Restart=always, auto-restart on crash, logs to journald.
- Enable and start the service

**Phase 1: Run the MVP (same day)**
Get a single bot running so that it automatically checks the feed every few minutes and performs replies or posts. 

1. Minimal Repository Structure
- orchestrator/: main loop (observe → generate → safe check → send)
- configs/: config for one bot (YAML/JSON with username, password, timing, etc.)
- policies/: list of banned words/phrases (NG filter)
- logs/: local logs with rotation to avoid disk fill

2.	Orchestrator Loop (MVP bot brain)
- Observe: call SDK (whoami, feed)
- Generate: create reply/post (simple template or LLM)
- Safe check: apply NG filter before sending
- Send: SDK actions (reply, like, post)
- Loop every 2–3 minutes

3.	Verify on EC2
- Confirm cycle whoami → feed → reply/like/post runs correctly
- Check interactions appear on Legit platform

4.	Error Handling / Guardrails
- Backoff logic for API errors (429 rate limit, 5xx server errors)
- Verify NG filter blocks unsafe/forbidden content

**Phase 2: Scale to Multiple Bots (tomorrow)**
- Extend the single-bot logic from Phase 1 so one codebase can run multiple bots
- Add a scheduler so ~40 bots each act every few minutes (with jitter)
- Build in error handling and rate-limit backoff for safe parallel execution
- Split configs (YAML/JSON) per bot, defining persona, posting interval, tone, etc.