"""Skills the resume proves but never names, and the person's one-tap yes/no decisions.

Three sources feed the "Additional Skills" line of the base resume:
  1. IMPLIED — evidence already in resume.json (Charles Proxy => REST APIs, and so on).
  2. AUTO_NO — automation frameworks and programming languages, ruled out because the
     person asked for manual-tester work only. Never added; never asked about.
  3. skills.json — decisions made in the web app: {"have": {skill: note}, "not": {skill: note}}.
Nothing here writes a skill into the resume without either evidence or a tap.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
DECISIONS = HERE / "skills.json"

IMPLIED: list[tuple[str, str, str]] = [
    (r"charles proxy|postman|\bapis?\b", "REST APIs", "you inspected and validated API traffic with Charles Proxy"),
    (r"charles proxy|postman", "API Testing", "Charles Proxy work is API-level testing"),
    (r"\bios\b|\bandroid\b|mobile", "Mobile Testing", "iOS/Android release QA"),
    (r"testrail|test cases", "Test Cases", "test cases authored in TestRail"),
    (r"testrail|test suites|scripted test", "Test Scripts", "scripted manual test suites"),
    (r"test plans?", "Test Documentation", "authored test plans and process documentation"),
    (r"\bjira\b|defect", "Bug Reporting", "defect tracking in Jira"),
    (r"end-to-end|cross-system", "End-to-End Testing", "end-to-end cross-system scenarios"),
    (r"web platform|web surfaces", "Web Testing", "regulated web platform QA"),
    (r"web platform|web surfaces", "Web Applications", "regulated web platform QA"),
    (r"\bsaas\b", "SaaS", "SaaS product experience"),
    (r"regulat|compliance|audit", "Compliance Testing", "regulatory compliance and QA audits"),
    (r"acceptance criteria", "Acceptance Criteria", "refined acceptance criteria with PM/Eng"),
    (r"release", "Release Testing", "production release-gate experience"),
    (r"console logs|log analysis|xcode", "Debugging", "Xcode / console-log debugging"),
    (r"traceab", "Requirements Traceability", "traceable test evidence across releases"),
    (r"data integrity", "Data Validation", "verified data integrity across platforms"),
    (r"edge-case|edge case", "Edge Case Testing", "edge-case discovery in exploratory sessions"),
    (r"cross-platform|platform configurations|\bios\b.*\bandroid\b", "Cross-Platform Testing", "iOS, Android and web"),
    (r"cross-browser|browsers", "Cross-Browser Testing", "web surface coverage"),
    (r"azure|devops", "Azure DevOps", "Azure / DevOps listed in tools"),
    (r"sprint|scrum|agile", "Sprint Planning", "sprint planning with product and engineering"),
    (r"stakeholder|cross-functional", "Stakeholder Management", "communication bridge across QA, Eng and PM"),
    (r"root cause", "Root Cause Analysis", "collaborated on root-cause resolution"),
    (r"usability|qualitative ux", "Usability Testing", "qualitative UX testing"),
    (r"beta|testflight", "Beta Testing", "TestFlight beta distribution"),
    (r"checklist|standards|quality standards", "Quality Standards", "quality standards and release checklists"),
]

AUTO_NO = {
    "test automation", "automation testing", "automated testing", "automation", "selenium", "cypress", "playwright",
    "appium", "cucumber", "gherkin", "webdriverio", "rest assured", "junit", "testng", "pytest", "nunit", "specflow",
    "robot framework", "katalon", "k6", "jmeter", "gatling", "locust", "java", "python", "c++", "c#", "ruby",
    "javascript", "typescript", "bash", "shell scripting", "go", "kotlin", "swift", "scala", "php", "perl", "rust",
    "node.js", "react", "angular", "vue", "docker", "kubernetes", "terraform", "sdet", "tdd", "bdd", "unit testing",
    "oop", "data structures", "algorithms", "jest", "mocha", "jasmine", "penetration testing", "ethical hacking",
    "burp suite", "metasploit",
}
AUTO_NO_NOTE = "automation / programming — skipped because you want manual-tester roles"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", s.lower()).strip()


def load() -> dict:
    d = json.loads(DECISIONS.read_text()) if DECISIONS.exists() else {}
    return {"have": dict(d.get("have") or {}), "not": dict(d.get("not") or {}),
            "statements": dict(d.get("statements") or {})}


def save(d: dict) -> None:
    DECISIONS.write_text(json.dumps(d, indent=1, ensure_ascii=False))


def resume_text(base: dict) -> str:
    parts = [base.get("summary", ""), base.get("title", "")]
    for _, items in base.get("skills", []):
        parts += items
    for job in base.get("experience", []):
        parts += job.get("bullets", [])
    parts += base.get("achievements", [])
    return " ".join(parts).lower()


def inferred(base: dict) -> dict[str, str]:
    text = resume_text(base)
    return {skill: note for pat, skill, note in IMPLIED if re.search(pat, text)}


def listed(base: dict) -> set[str]:
    return {norm(i) for _, items in base.get("skills", []) for i in items}


def decide(name: str, base: dict, decisions: dict) -> tuple[str, str] | None:
    """Returns ('have'|'not', note) for a missing skill when it can be settled without a tap."""
    n = norm(name)
    if n in decisions["have"] or n in decisions["not"]:
        return None
    if n in AUTO_NO:
        return "not", AUTO_NO_NOTE
    for skill, note in inferred(base).items():
        if norm(skill) == n:
            return "have", f"inferred: {note}"
    return None


def auto_decide(missing_names: list[str], base: dict) -> dict:
    """Settles every missing skill it can, saves, and returns the decisions."""
    d = load()
    changed = False
    for name in missing_names:
        got = decide(name, base, d)
        if got:
            d[got[0]][norm(name)] = got[1]
            changed = True
    if changed:
        save(d)
    return d


def additional(base: dict) -> list[tuple[str, str]]:
    """(skill, note) pairs that belong on the Additional Skills line: inferred + tapped-yes, minus tapped-no and duplicates."""
    d = load()
    have = listed(base)
    out: list[tuple[str, str]] = []
    for skill, note in inferred(base).items():
        n = norm(skill)
        if n not in have and n not in d["not"]:
            out.append((skill, f"inferred: {note}"))
            have.add(n)
    for n, note in d["have"].items():
        if n not in have:
            out.append((pretty(n), note))
            have.add(n)
    return out


def with_additional(base: dict) -> dict:
    """The base resume as it should print: removed skills gone, Additional Skills on, your own statements as bullets."""
    d = load()
    groups = []
    for name, items in base["skills"]:
        kept = [i for i in items if norm(i) not in d["not"]]
        if kept:
            groups.append([name, kept])
    extra = [s for s, _ in additional(base)]
    if extra:
        groups.append(["Additional Skills", extra])
    out = {**base, "skills": groups}
    st = [f"{pretty(k)}: {v}" for k, v in statements().items() if k not in d["not"]]
    if st:
        out["statements"] = st
    return out


ACRONYMS = {"qa", "api", "apis", "sql", "ci/cd", "ci cd", "ux", "ui", "ai", "uat", "sdlc", "stlc", "rca", "e2e",
            "saas", "aws", "gcp", "json", "xml", "html", "css", "rest", "adb", "etl", "erp", "crm", "hipaa", "gdpr",
            "soc", "pci", "iso", "sox", "gaap", "sla", "kpi"}


PROPER = {"ci cd": "CI/CD", "gitlab": "GitLab", "github": "GitHub", "github actions": "GitHub Actions",
          "circleci": "CircleCI", "testrail": "TestRail", "jira": "Jira", "confluence": "Confluence",
          "microsoft excel": "Microsoft Excel", "rest apis": "REST APIs", "postman": "Postman", "jenkins": "Jenkins",
          "sql": "SQL", "nosql": "NoSQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "macos": "macOS", "ios": "iOS",
          "devops": "DevOps", "azure devops": "Azure DevOps", "testflight": "TestFlight", "xcode": "Xcode",
          "browserstack": "BrowserStack", "saucelabs": "Sauce Labs", "salesforce": "Salesforce", "servicenow": "ServiceNow",
          "powershell": "PowerShell", "javascript": "JavaScript", "typescript": "TypeScript", "node.js": "Node.js"}


def pretty(n: str) -> str:
    if n in PROPER:
        return PROPER[n]
    return " ".join(w.upper() if w in ACRONYMS else w.capitalize() for w in n.split())


def pending(jobs: list[dict], base: dict) -> list[dict]:
    """Missing skills across all jobs that still need a tap, most-asked first.

    Anything IMPLIED or AUTO_NO can settle is recorded on the way and never shown."""
    d = load()
    changed = False
    have = listed(base) | {norm(s) for s, _ in additional(base)}
    agg: dict[str, dict] = {}
    for j in jobs:
        for m in j.get("missing", []):
            if m.get("kind") == "soft":
                continue
            n = norm(m["k"])
            if n in have or n in d["have"] or n in d["not"]:
                continue
            got = decide(m["k"], base, d)
            if got:
                d[got[0]][n] = got[1]
                changed = True
                continue
            a = agg.setdefault(n, {"skill": m["k"], "jobs": 0, "mentions": 0})
            a["jobs"] += 1
            a["mentions"] += int(m.get("p") or 0)
    if changed:
        save(d)
    return sorted(agg.values(), key=lambda a: (-a["jobs"], -a["mentions"], a["skill"]))


QUESTIONS = {
    "sql": "Have you run SQL queries (SELECT, joins) to check data in a database?",
    "rest apis": "Have you tested or inspected REST API calls (Postman, Charles, curl)?",
    "ci/cd": "Have you worked with build pipelines (Jenkins, GitHub Actions, Azure Pipelines) — even just triggering or reading them?",
    "ci cd": "Have you worked with build pipelines (Jenkins, GitHub Actions, Azure Pipelines) — even just triggering or reading them?",
    "cloud": "Have you tested apps hosted on AWS, Azure or GCP?",
    "aws": "Have you tested apps hosted on AWS or used the AWS console?",
    "data analysis": "Have you analysed test or production data to find patterns or defects?",
    "excel": "Do you use Excel/Google Sheets for test data, tracking or reporting?",
    "microsoft excel": "Do you use Excel/Google Sheets for test data, tracking or reporting?",
    "performance testing": "Have you done load or performance testing?",
    "accessibility testing": "Have you tested for accessibility (WCAG, screen readers, VoiceOver)?",
    "security testing": "Have you done security-focused testing (auth, permissions, OWASP basics)?",
    "salesforce": "Have you tested Salesforce apps?",
    "sap": "Have you tested SAP systems?",
    "linux": "Are you comfortable on a Linux command line?",
    "git": "Have you used Git (clone, branches, pull requests)?",
    "github": "Have you used GitHub for issues, PRs or reviews?",
    "confluence": "Have you written docs in Confluence?",
    "localization testing": "Have you tested localized / translated versions of an app?",
    "payments": "Have you tested payment or checkout flows?",
    "healthcare": "Have you worked on healthcare software?",
    "hipaa": "Have you worked under HIPAA requirements?",
    "fintech": "Have you worked on financial software?",
}


def question(skill: str) -> str:
    return QUESTIONS.get(norm(skill), f"Do you have real, hands-on experience with {skill}?")


# ---------------------------------------------------------------------------
# Evidence: every skill that reaches a resume must point at something real.
# ---------------------------------------------------------------------------
STOP = {"and", "the", "of", "&", "/", "a", "an", "tools", "skills", "with"}


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ies", "ing", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if len(w) >= 4 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    return w


def _words(skill: str) -> list[str]:
    return [stem(w) for w in re.split(r"[^a-z0-9+#.]+", skill.lower()) if w and w not in STOP and len(w) >= 2]


def _hits(skill: str, texts: list[str]) -> list[str]:
    ws = _words(skill)
    out = []
    for t in texts:
        stems = {stem(w) for w in re.split(r"[^a-z0-9+#.]+", t.lower()) if w}
        need = len(ws) if len(ws) <= 2 else len(ws) - 1
        if ws and sum(w in stems for w in ws) >= need:
            out.append(t)
    return out


def evidence(base: dict) -> list[dict]:
    """One row per skill that can appear on a resume: where it is proven, or that it is not."""
    d = load()
    texts = [base.get("summary", "")]
    for job in base.get("experience", []):
        texts += job.get("bullets", [])
    texts += base.get("achievements", [])
    rows: list[dict] = []
    seen: set[str] = set()
    for group, items in base.get("skills", []):
        for s in items:
            n = norm(s)
            seen.add(n)
            if n in d["not"]:
                rows.append({"skill": s, "group": group, "source": "removed", "proof": [], "note": d["not"][n], "verified": False})
                continue
            hits = _hits(s, texts)
            st = d["statements"].get(n, "")
            rows.append({"skill": s, "group": group, "source": "listed", "proof": hits[:3] or ([st] if st else []),
                         "note": "" if hits else ("your own words" if st else "listed in resume.json but no bullet backs it up"),
                         "verified": bool(hits or st), "statement": st})
    for s, note in inferred(base).items():
        n = norm(s)
        if n in seen or n in d["not"]:
            continue
        seen.add(n)
        rows.append({"skill": s, "group": "Additional Skills", "source": "inferred", "proof": _hits(s, texts)[:2] or [],
                     "note": note, "verified": True})
    for n, note in d["have"].items():
        if n in seen:
            continue
        seen.add(n)
        st = d["statements"].get(n, "")
        rows.append({"skill": pretty(n), "group": "Additional Skills", "source": "confirmed", "proof": [st] if st else [],
                     "note": note, "verified": bool(st), "statement": st})
    return rows


def statements() -> dict[str, str]:
    """One sentence per confirmed skill, written by the person, that goes on the resume as a bullet."""
    d = json.loads(DECISIONS.read_text()) if DECISIONS.exists() else {}
    return {k: v for k, v in (d.get("statements") or {}).items() if v.strip()}


def set_statement(skill: str, text: str) -> None:
    d = json.loads(DECISIONS.read_text()) if DECISIONS.exists() else {}
    st = d.setdefault("statements", {})
    n = norm(skill)
    if text.strip():
        st[n] = text.strip()
    else:
        st.pop(n, None)
    DECISIONS.write_text(json.dumps(d, indent=1, ensure_ascii=False))
