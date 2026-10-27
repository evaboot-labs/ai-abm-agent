# Agent instructions

This repo is an AI ABM agent. It takes the user's target accounts, exports each account's buying committee from LinkedIn Sales Navigator through Evaboot, maps every person to a role (decision maker, champion, influencer, user), tiers the accounts, and writes who to contact first at each account, on which channel and with which angle. The user does the outreach. When the user asks for account-based marketing, ABM, a buying committee map, or "who should I contact at these accounts":

1. Follow the skill in `skills/ai-abm-agent/SKILL.md` step by step.
2. Read `BUYERS.md` for the offer, the account tiers, the buying committee and the contact rules. If it says `Status: EXAMPLE`, ask the user and update it.
3. Use `abm.py` to group the people by account, check your map and render the plan. The Evaboot MCP server does the Sales Navigator work (`.mcp.json`).
4. If the user is not connected yet, follow `docs/connect-your-agent.md` with them.
5. If the user wants n8n instead, follow `docs/n8n.md` with them one step at a time: you cannot click inside n8n, so say exactly what to do and wait for their confirmation.

Exports cost 1 Evaboot credit per row. Confirm with the user before every export and before creating a recurring export. Never contact anyone yourself. Never ask for or handle an API key: the user writes it into `.env`. Never commit `.env`, `data/`, `queue/` or `plans/`: they hold real people's data.
