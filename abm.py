"""Helpers for the AI ABM agent. The agent exports the buying committee of your target accounts through the
Evaboot MCP and maps it; these commands group the people by account, check the agent's map and render the
plan the same way every time. Nothing here touches the network.

    python3 abm.py facts data/committee.json data/accounts.json > queue/accounts.json
                                                       one entry per target account, its people, its facts
    python3 abm.py check queue/accounts.json queue/plan.json    the agent's map: role, order, channel, angle
    python3 abm.py render queue/accounts.json queue/plan.json > plans/<date>.md
"""
import argparse
import json
import re
import sys

ROLES = {"decision_maker", "champion", "influencer", "user", "skip"}
ROLE_LABELS = {"decision_maker": "Decision maker", "champion": "Champion", "influencer": "Influencer",
               "user": "User", "skip": "Skip"}
CHANNELS = {"email", "linkedin"}
TIERS = {1, 2, 3}
MAX_WORDS = 30
GENDERED = re.compile(r"\b(he|she|him|her|his|hers)\b", re.I)


def num(v):
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def clean(text, limit):
    return " ".join((text or "").split())[:limit]


def account_key(p):
    return p.get("Company Linkedin URL Unique ID") or p.get("Company Name") or ""


def facts(committee_path, accounts_path):
    """Group the exported people by target account. The account export decides which companies count: a
    lead search filtered on an account list also returns people whose main current job is somewhere else
    (a second position, a company with the same name), and those are dropped. A target account with nobody
    in the committee export stays in, with no people."""
    accounts = {}
    for a in json.load(open(accounts_path)).get("prospects") or []:
        accounts[account_key(a)] = {"raw": a, "people": []}
    dropped = 0
    for p in json.load(open(committee_path)).get("prospects") or []:
        if account_key(p) in accounts:
            accounts[account_key(p)]["people"].append(p)
        else:
            dropped += 1
    if dropped:
        print(f"dropped {dropped} people whose current company is not a target account", file=sys.stderr)
    out = []
    for key, acc in accounts.items():
        a = acc["raw"]
        people = []
        for p in acc["people"]:
            years, months = num(p.get("Years in Position")), num(p.get("Months in Position"))
            in_role = None if years is None and months is None else int((years or 0) * 12 + (months or 0))
            people.append({
                "id": p.get("Linkedin URL Unique ID") or p.get("Linkedin URL Public") or p.get("Full Name"),
                "name": p.get("Full Name") or "", "first_name": p.get("First Name") or "",
                "title": clean(p.get("Current Job"), 120), "months_in_role": in_role,
                "headline": clean(p.get("Profile Headline"), 160),
                "email": p.get("Email") or "", "email_status": (p.get("Email Status") or "not found").lower(),
                "linkedin": p.get("Linkedin URL Public") or "",
            })
        people.sort(key=lambda r: r["name"])
        out.append({
            "account": a.get("Company Name") or key, "id": key,
            "domain": a.get("Company Domain") or "", "employees": a.get("Company Employee Range") or "",
            "employee_count": num(a.get("Company Employee Exact Count")),
            "growth_1y_pct": num(a.get("Company Employee Growth 1 Year (%)")),
            "sales_team": num(a.get("Sales Team Size")), "bizdev_team": num(a.get("Business Development Size")),
            "description": clean(a.get("Company Description"), 400),
            "people": people,
        })
    out.sort(key=lambda r: (-len(r["people"]), r["account"]))
    print(f"{len(out)} target accounts, {sum(len(r['people']) for r in out)} people: "
          + ", ".join(f"{r['account']} {len(r['people'])}" for r in out), file=sys.stderr)
    return out


def words(text):
    return len((text or "").split())


def check(accounts_path, plan_path):
    """Every account gets a tier and a reason. Every person gets a role. Everyone the plan contacts gets an
    order, a channel that works and a one-line angle. Returns the problems found."""
    accounts = {a["id"]: a for a in json.load(open(accounts_path))}
    plan = json.load(open(plan_path))
    problems = []
    planned = {p.get("id") for p in plan}
    for missing in sorted(set(accounts) - planned):
        problems.append(f"account {accounts[missing]['account']}: not in the plan")
    for entry in plan:
        acc = accounts.get(entry.get("id"))
        if not acc:
            problems.append(f"unknown account {entry.get('id')}")
            continue
        name = acc["account"]
        if entry.get("tier") not in TIERS:
            problems.append(f"{name}: tier must be 1, 2 or 3")
        if not entry.get("why") or words(entry["why"]) > MAX_WORDS:
            problems.append(f"{name}: why is missing or longer than {MAX_WORDS} words")
        people = {p["id"]: p for p in acc["people"]}
        mapped = {m.get("id"): m for m in entry.get("people") or []}
        for pid in sorted(set(people) - set(mapped)):
            problems.append(f"{name}: {people[pid]['name']} has no role")
        orders = []
        for pid, m in mapped.items():
            person = people.get(pid)
            if not person:
                problems.append(f"{name}: unknown person {pid}")
                continue
            who = f"{name} / {person['name']}"
            if m.get("role") not in ROLES:
                problems.append(f"{who}: role must be one of {', '.join(sorted(ROLES))}")
                continue
            if m["role"] == "skip":
                continue
            orders.append(m.get("order"))
            if m.get("channel") not in CHANNELS:
                problems.append(f"{who}: channel must be email or linkedin")
            elif m["channel"] == "email" and person["email_status"] != "safe":
                problems.append(f"{who}: email is not verified, use linkedin")
            angle = m.get("angle") or ""
            if not angle or words(angle) > MAX_WORDS:
                problems.append(f"{who}: angle is missing or longer than {MAX_WORDS} words")
            if GENDERED.search(angle):
                problems.append(f"{who}: angle guesses a gender, use the first name, they or the role")
        if orders and sorted(orders) != list(range(1, len(orders) + 1)):
            problems.append(f"{name}: contact order must run 1, 2, 3... with no gap or repeat")
        roles = {m.get("role") for m in mapped.values()}
        if entry.get("tier") in (1, 2) and not roles & {"decision_maker", "champion"}:
            problems.append(f"{name}: a tier {entry.get('tier')} account needs a decision maker or a champion")
    return problems


def render(accounts_path, plan_path):
    accounts = {a["id"]: a for a in json.load(open(accounts_path))}
    plan = sorted(json.load(open(plan_path)), key=lambda e: (e["tier"], accounts[e["id"]]["account"]))
    lines = ["# ABM plan", ""]
    counts = {t: sum(1 for e in plan if e["tier"] == t) for t in TIERS}
    lines.append(f"{len(plan)} accounts: {counts[1]} tier 1, {counts[2]} tier 2, {counts[3]} tier 3.")
    for e in plan:
        acc = accounts[e["id"]]
        people = {p["id"]: p for p in acc["people"]}
        lines += ["", f"## {acc['account']} (tier {e['tier']})", "", e["why"], ""]
        contacts = sorted((m for m in e["people"] if m["role"] != "skip"), key=lambda m: m["order"])
        if contacts:
            lines += ["| # | Name | Title | Role | Channel | Angle |", "|---|---|---|---|---|---|"]
            for m in contacts:
                p = people[m["id"]]
                channel = p["email"] if m["channel"] == "email" else f"[LinkedIn]({p['linkedin']})"
                lines.append(f"| {m['order']} | {p['name']} | {p['title']} | {ROLE_LABELS[m['role']]} | "
                             f"{channel} | {m['angle']} |")
        else:
            lines.append("Nobody to contact yet: find the right people before this account moves up.")
        skipped = [people[m["id"]]["name"] for m in e["people"] if m["role"] == "skip"]
        if skipped:
            lines += ["", f"Skipped: {', '.join(skipped)}."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("facts")
    f.add_argument("committee")
    f.add_argument("accounts")
    for name in ("check", "render"):
        s = sub.add_parser(name)
        s.add_argument("accounts")
        s.add_argument("plan")
    args = ap.parse_args()
    if args.cmd == "facts":
        json.dump(facts(args.committee, args.accounts), sys.stdout, indent=1, ensure_ascii=False)
        print()
    elif args.cmd == "check":
        problems = check(args.accounts, args.plan)
        for p in problems:
            print("FAIL", p)
        print("OK" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)
    else:
        sys.stdout.write(render(args.accounts, args.plan))


if __name__ == "__main__":
    main()
