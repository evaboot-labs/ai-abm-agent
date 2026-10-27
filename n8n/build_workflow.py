"""Builds n8n/ai-abm-agent.json. Run: python3 n8n/build_workflow.py

Evaboot exports the buying committee of your target accounts (a Sales Navigator people search filtered on
an account list) and posts it to the webhook, once or on a recurring schedule. The workflow keeps the people
who work at a target account, groups them by account, lets Claude map each committee (role, contact order,
channel, angle) and tier the account, checks the answer like abm.py, and writes one row per contact into
the "ABM plan" Data table.
"""
import json
import uuid
from pathlib import Path

ANTHROPIC_CRED = {"anthropicApi": {"id": "", "name": "Anthropic"}}
MODEL = "claude-sonnet-5-5"

nodes, connections = [], {}


def node(name, type_, version, params, pos, creds=None, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_,
         "typeVersion": version, "position": pos, **extra}
    if creds:
        n["credentials"] = creds
    nodes.append(n)


def link(a, b, kind="main", out=0):
    connections.setdefault(a, {}).setdefault(kind, [])
    while len(connections[a][kind]) <= out:
        connections[a][kind].append([])
    connections[a][kind][out].append({"node": b, "type": kind, "index": 0})


def code(name, js, pos, **extra):
    node(name, "n8n-nodes-base.code", 2, {"jsCode": js}, pos, **extra)


SETTINGS = [
    ("target_accounts", "PASTE_THE_LINKEDIN_COMPANY_URLS_OF_YOUR_TARGET_ACCOUNTS, comma separated"),
    ("tiers", "Tier 1: a sales team of 15 or more, or a team that grew in the last year. Tier 2: a sales team of 5 "
              "to 14. Tier 3: a smaller team, or no sign that they prospect."),
    ("committee", "Decision maker: Head or VP of Sales, CRO, Chief Commercial Officer, CEO or founder under 100 "
                  "people. Champion: Sales Ops, RevOps, Head of SDR or BDR team, Head of Growth. Influencer: "
                  "Marketing Ops, Head of Marketing, Demand Generation. User: SDRs, BDRs, Account Executives, "
                  "Business Developers. Skip: everyone else."),
    ("contact_rules", "Start with the champion, then the decision maker with what the champion cares about, then one "
                      "user. An influencer comes last, and only on a tier 1 account. At most 4 people per account."),
    ("offer", "Evaboot exports LinkedIn Sales Navigator searches and lists to a spreadsheet or CRM, with verified "
              "professional emails, and keeps lead lists fresh with recurring exports."),
]

GROUP_JS = r"""
// Same as abm.py facts: keep the people whose current company is a target account, one item per account.
// A people search filtered on an account list also returns people whose main job is elsewhere.
const s = $('Settings').first().json;
const id = v => (String(v || '').match(/company\/(\d+)/) || [])[1] || String(v || '').trim();
const targets = new Set(String(s.target_accounts).split(',').map(id).filter(Boolean));
const num = v => { const n = parseFloat(String(v ?? '').replace(/[,%]/g, '')); return isNaN(n) ? null : n; };
const words = (t, n) => String(t || '').split(/\s+/).join(' ').trim().slice(0, n);
const accounts = {};
let dropped = 0;
for (const p of $('Committee from Evaboot').first().json.body.prospects || []) {
  const key = id(p['Company Linkedin URL Unique ID']);
  if (!targets.has(key)) { dropped++; continue; }
  const a = accounts[key] ??= { id: key, account: p['Company Name'] || key, employees: p['Company Employee Range'] || '',
    growth_1y_pct: num(p['Company Employee Growth 1 Year (%)']), sales_team: num(p['Sales Team Size']),
    bizdev_team: num(p['Business Development Size']), description: words(p['Company Description'], 400), people: [] };
  const y = num(p['Years in Position']), m = num(p['Months in Position']);
  a.people.push({ id: p['Linkedin URL Unique ID'] || p['Linkedin URL Public'] || p['Full Name'],
    name: p['Full Name'] || '', first_name: p['First Name'] || '', title: words(p['Current Job'], 120),
    months_in_role: y === null && m === null ? null : (y || 0) * 12 + (m || 0),
    email: p['Email'] || '', email_status: String(p['Email Status'] || 'not found').toLowerCase(),
    linkedin: p['Linkedin URL Public'] || '' });
}
return Object.values(accounts).map(a => ({ json: { ...a, dropped } }));
"""

PLAN_JS = r"""
// Same rules as abm.py check: an incomplete contact is dropped, email only with a verified address,
// the contact order runs 1, 2, 3 per account. One row per contact for the Data table.
const today = new Date().toISOString().slice(0, 10);
const out = [];
$input.all().forEach((item, i) => {
  const acc = $('Group by account').all()[i].json;
  const plan = item.json.output || {};
  const people = Object.fromEntries(acc.people.map(p => [p.id, p]));
  const contacts = (plan.people || []).filter(m => people[m.id] && m.role && m.role !== 'skip' && m.angle)
    .sort((a, b) => (a.order || 99) - (b.order || 99)).slice(0, 4);
  contacts.forEach((m, n) => {
    const p = people[m.id];
    const channel = m.channel === 'email' && p.email_status === 'safe' ? 'email' : 'linkedin';
    out.push({ json: { date: today, account: acc.account, tier: Number(plan.tier) || 3, why: plan.why || '',
      order: n + 1, name: p.name, title: p.title, role: m.role, channel,
      contact: channel === 'email' ? p.email : p.linkedin, angle: m.angle } });
  });
});
return out;
"""

MAP_SYSTEM = """You map the buying committee of one target account for an account-based campaign. The JSON is the account (sales team, growth, description) and the people Evaboot found there (title, months in role, email status). Use only these facts; never invent anything.

Return {tier, why, people: [{id, role, order, channel, angle}]}:
- tier: 1, 2 or 3, from the tiers below. why: one line under 30 words from the account facts.
- role: decision_maker, champion, influencer, user or skip, from the committee below. Every person gets a role.
- order, channel and angle only for the people you contact, following the contact rules. order runs 1, 2, 3.
- channel: "email" only if email_status is safe, otherwise "linkedin".
- angle: one sentence under 25 words about their own job, from their title and the account facts. State facts, never guesses: no \"likely\", \"probably\" or \"could\". Mention months in role only when it is under 6.
- A row whose name is not a person (a team or company page, such as \"Marketing <Company>\") is skip.
- Never guess anyone's gender: no he, she, him or her. Use the first name, \"they\" or the role.

Tiers:
{{ $('Settings').first().json.tiers }}

Committee:
{{ $('Settings').first().json.committee }}

Contact rules:
{{ $('Settings').first().json.contact_rules }}

What we sell:
{{ $('Settings').first().json.offer }}"""

node("Committee from Evaboot", "n8n-nodes-base.webhook", 2, {
    "httpMethod": "POST", "path": "evaboot-abm", "responseMode": "onReceived", "options": {},
}, [0, 0], webhookId=str(uuid.uuid4()))
node("Settings", "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [
    {"id": str(uuid.uuid4()), "name": k, "type": "string", "value": v} for k, v in SETTINGS]},
    "includeOtherFields": True, "options": {}}, [260, 0])
code("Group by account", GROUP_JS, [520, 0], executeOnce=True)
node("Map the committee", "@n8n/n8n-nodes-langchain.agent", 2.2, {
    "promptType": "define", "hasOutputParser": True,
    "text": "={{ JSON.stringify({ account: $json.account, employees: $json.employees, growth_1y_pct: $json.growth_1y_pct, "
            "sales_team: $json.sales_team, bizdev_team: $json.bizdev_team, description: $json.description, "
            "people: $json.people.map(p => ({ id: p.id, first_name: p.first_name, title: p.title, "
            "months_in_role: p.months_in_role, email_status: p.email_status })) }) }}",
    "options": {"systemMessage": "=" + MAP_SYSTEM, "maxIterations": 3},
}, [800, 0], retryOnFail=True, maxTries=3, waitBetweenTries=2000)
node("Claude", "@n8n/n8n-nodes-langchain.lmChatAnthropic", 1.3, {
    "model": {"__rl": True, "mode": "list", "value": MODEL, "cachedResultName": MODEL},
    "options": {"maxTokensToSample": 4000},
}, [760, 240], ANTHROPIC_CRED)
node("Committee map", "@n8n/n8n-nodes-langchain.outputParserStructured", 1.3, {
    "schemaType": "manual",
    "inputSchema": json.dumps({"type": "object", "required": ["tier", "why", "people"], "properties": {
        "tier": {"type": "number"}, "why": {"type": "string"}, "people": {
            "type": "array", "items": {"type": "object", "required": ["id", "role"], "properties": {
                "id": {"type": "string"}, "role": {"type": "string"}, "order": {"type": "number"},
                "channel": {"type": "string"}, "angle": {"type": "string"}}}}}}, indent=2),
}, [960, 240])
code("Check the plan", PLAN_JS, [1180, 0])
node("Add to ABM plan", "n8n-nodes-base.dataTable", 1, {
    "dataTableId": {"__rl": True, "mode": "name", "value": "ABM plan"},
    "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []},
    "options": {},
}, [1440, 0])

for a, b in [("Committee from Evaboot", "Settings"), ("Settings", "Group by account"),
             ("Group by account", "Map the committee"), ("Map the committee", "Check the plan"),
             ("Check the plan", "Add to ABM plan")]:
    link(a, b)
link("Claude", "Map the committee", "ai_languageModel")
link("Committee map", "Map the committee", "ai_outputParser")

workflow = {"name": "AI ABM agent (Evaboot + Claude)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
out = Path(__file__).with_name("ai-abm-agent.json")
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(out, len(nodes), "nodes")
