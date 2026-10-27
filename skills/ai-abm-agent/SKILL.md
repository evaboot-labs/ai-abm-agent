---
name: ai-abm-agent
description: Run account-based marketing with an AI agent - take a list of target accounts, export each account's buying committee from LinkedIn Sales Navigator through Evaboot (with verified emails), map every person to a role (decision maker, champion, influencer, user), tier the accounts, and write who to contact first at each account, on which channel, with which angle. Use when the user asks for ABM, account-based marketing, a buying committee map, stakeholder mapping, or who to contact at their target accounts.
---

# AI ABM agent

This skill runs inside a clone of https://github.com/evaboot-labs/ai-abm-agent: it uses the repo's `abm.py`, `BUYERS.md` and `docs/`. If `abm.py` is not in the working directory, clone the repo and work from there.

You do the Sales Navigator and Evaboot work through the Evaboot MCP server (`https://mcp.evaboot.com/mcp`). Every tool named below is an Evaboot MCP tool. You map the people yourself. `abm.py` groups them by account, checks your map and renders the plan.

## Rules

- **You never contact anyone.** The plan tells the user who to contact, in which order and how; they do it.
- Confirm with the user before every `export_sn_search_or_list`. Show the count and the cost (1 Evaboot credit per exported row), then wait for a yes.
- Map each person only from their row in `queue/accounts.json` and `BUYERS.md`. Never invent a fact.
- Never ask for or paste an API key. The user writes `EVABOOT_API_KEY` into `.env` and exports it before starting the agent (`docs/connect-your-agent.md`).
- Print every Sales Navigator URL as a Markdown link with the URL in angle brackets: `[Open in Sales Navigator](<url>)`.

## Step 0: check the setup

1. If the Evaboot MCP tools are not in this session, walk the user through `docs/connect-your-agent.md`, then ask them to restart the agent from this folder.
2. Otherwise call `get_daily_export_quota`. If `has_valid_salesnav` is false, ask the user to sign in to Evaboot in Chrome, open any Sales Navigator search with the Evaboot extension, and click Export with Evaboot, then call the quota again.
3. Run `mkdir -p data queue plans`.
4. Read `BUYERS.md`. If it says `Status: EXAMPLE`, ask the user what they sell in one line, which accounts they target, and who decides, champions and uses it at those accounts. Rewrite the file and set `Status: yours`.

## Step 1: the target accounts

The user brings the accounts one of three ways:

- **A Sales Navigator account list:** find it with `list_account_lists`. The list URL is `https://www.linkedin.com/sales/lists/company/<id>`.
- **Company names or LinkedIn company pages:** build an account search with `build_sn_search_from_prompt`, then save the companies they confirm with `create_account_list_from_ids` (the ids are the numbers in `linkedin.com/company/<id>`).
- **A description** ("French SaaS companies, 51-200 people, growing"): build the account search with `build_sn_search_from_prompt`, export a few with `max_results`, and let the user pick.

Export the account list once with `export_sn_search_or_list` (1 credit per account) and save it:

```bash
set -a; [ -n "$EVABOOT_API_KEY" ] || . ./.env; set +a
curl -s -H "Authorization: Bearer $EVABOOT_API_KEY" https://api.evaboot.com/v1/extractions/<extraction_id>/ > data/accounts.json
```

## Step 2: the buying committee

1. Build the people search on the account list: the `ACCOUNT_LIST` filter plus the functions and seniority of the roles in `BUYERS.md`. For the example offer:

```
https://www.linkedin.com/sales/search/people?query=(filters:List((type:ACCOUNT_LIST,values:List((id:<list id>,selectionType:INCLUDED))),(type:FUNCTION,values:List((id:25,selectionType:INCLUDED),(id:4,selectionType:INCLUDED),(id:15,selectionType:INCLUDED),(id:18,selectionType:INCLUDED),(id:9,selectionType:INCLUDED))),(type:SENIORITY_LEVEL,values:List((id:210,selectionType:INCLUDED),(id:220,selectionType:INCLUDED),(id:300,selectionType:INCLUDED),(id:310,selectionType:INCLUDED),(id:320,selectionType:INCLUDED)))))
```

   Functions: 25 Sales, 4 Business Development, 15 Marketing, 18 Operations, 9 Entrepreneurship (founders). Seniority: 210 Experienced Manager, 220 Director, 300 Vice President, 310 CXO, 320 Owner / Partner. URL-encode it before you send it.
2. On a yes, export it with `export_sn_search_or_list`, poll `get_export` with `limit: 0` until `EXECUTED`, and save it to `data/committee-<date>.json` with the same `curl`.
3. Group the people by account:

```bash
python3 abm.py facts data/committee-2026-10-27.json data/accounts.json > queue/accounts.json
```

   `facts` drops the people whose main current job is at another company. Sales Navigator returns them because of a second position or a company with the same name. Expect a third of the export to go.

## Step 3: map, tier and plan

Write `queue/plan.json`, one entry per account in `queue/accounts.json`:

```json
{"id": "<account id>", "tier": 1, "why": "one line from the account facts",
 "people": [{"id": "<person id>", "role": "champion", "order": 1, "channel": "email", "angle": "one sentence"},
            {"id": "<person id>", "role": "skip"}]}
```

- `tier` follows the tiers in `BUYERS.md`. `why` uses only the account facts (sales team, growth, new people in key roles).
- Every person gets a `role`: `decision_maker`, `champion`, `influencer`, `user` or `skip`. Follow the contact rules in `BUYERS.md`: who goes first, and how many people per account.
- Contacts get an `order` (1, 2, 3 per account), a `channel` (`email` only with a `safe` email, otherwise `linkedin`) and an `angle`: one sentence about their job, from their title, their months in role and the account facts. Never guess gender: use the first name, "they" or the role.

```bash
python3 abm.py check queue/accounts.json queue/plan.json
python3 abm.py render queue/accounts.json queue/plan.json > plans/$(date +%F).md
```

Fix every `FAIL`, render, and show the plan.

## Step 4: keep it current

Buying committees change. Offer `create_recurring_export` on the committee export's `extraction_id` (weekly or monthly): each run exports only the people who are new to the search, such as a new VP Sales. Each run spends credits; say so before creating it. When a run arrives, do step 2.2 to 3 on the new file and tell the user who joined which account. Or set up the n8n version (`docs/n8n.md`), which receives each run by webhook and updates a Google Sheet.
