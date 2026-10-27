# Run it in n8n

[`n8n/ai-abm-agent.json`](../n8n/ai-abm-agent.json) is the same agent for n8n. Evaboot sends the buying committee of your target accounts to a webhook, Claude maps each account, and the plan lands in an n8n Data table, one row per person to contact.

## What runs

1. **Committee from Evaboot** (Webhook): receives an Evaboot export of the people search on your account list.
2. **Settings**: your target accounts, tiers, buying committee, contact rules and offer.
3. **Group by account** (Code): keeps the people whose current company is a target account and groups them, one item per account. Sales Navigator also returns people whose main job is at another company; they are dropped here.
4. **Map the committee** (AI Agent with Claude): a tier and a reason for the account, a role for every person, and for the people to contact an order, a channel and a one-line angle.
5. **Check the plan** (Code): drops an incomplete contact, keeps at most 4 per account, and turns `email` into `linkedin` when the email is not verified.
6. **Add to ABM plan** (Data table): one row per contact.

## Set it up

1. **Create the Data table** in n8n: *Overview > Data tables > Create*, named `ABM plan`, with these columns: `date`, `account`, `tier` (number), `why`, `order` (number), `name`, `title`, `role`, `channel`, `contact`, `angle`. To use Google Sheets or your CRM instead, replace the last node.
2. **Import** the JSON in n8n: *Workflows > Import from file*.
3. **Add the Anthropic credential** on the Claude node, and pick the `ABM plan` table in the last node.
4. **Fill in Settings:** `target_accounts` is the LinkedIn company URLs of your target accounts, comma separated. Adapt `tiers`, `committee`, `contact_rules` and `offer` to what you sell.
5. **Publish** the workflow. Open **Committee from Evaboot** and copy its production URL. It looks like `https://<you>.app.n8n.cloud/webhook/evaboot-abm`.
6. **Connect Evaboot,** from your AI Agent with the Evaboot MCP, or in Evaboot's Integrations page: add an n8n destination with that URL.
7. **Build the committee search:** save your target accounts as a Sales Navigator account list, then run a people search filtered on that list, with the functions and seniority of your buying committee. Export it with Evaboot.
8. **Test:** push the finished export to the n8n destination (no credits), then open the `ABM plan` table.

## Keep it current

Create a recurring export of the committee search (weekly or monthly) and attach it to the n8n destination. Each run sends only the people who are new to the search, such as a VP Sales who joined last month, and the workflow maps them into the plan.

## Good to know

- Each export spends 1 Evaboot credit per person. Pushing a finished export to n8n is free.
- About a third of the people a Sales Navigator account-list search returns work mainly at another company. **Group by account** drops them, so check its output before you blame the search.
- To change who gets contacted, edit `committee` and `contact_rules` in Settings. Keep them in step with `BUYERS.md` if you also run the agent from Claude Code.

Back to the [README](../README.md).
