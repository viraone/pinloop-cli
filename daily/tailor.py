"""Builds a resume tailored to one posting from resume.json and a pinloop ats report.

Nothing is invented. The same facts are kept; what changes is the wording and
the order: skills the posting names are moved to the front and written the way
the posting writes them, and bullets that speak to the posting's skills come
first inside each job. A skill the resume does not carry is never added.
"""
import json
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer)

import skills

HERE = Path(__file__).parent
QA_TITLE = re.compile(r"\b(qa|quality|test|tester|testing|sdet)\b", re.I)
JUNK_TITLE = re.compile(r"\s*[-–—]\s*job\s+\d+.*$", re.I)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", s.lower()).strip()


def resume_name() -> str:
    profile = json.loads((HERE / "profile.json").read_text())
    configured = profile.get("resume_filename", "Resume").removesuffix(".pdf")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", configured).strip("._") or "Resume"


def mentions(text: str, hit: dict) -> bool:
    words = {norm(hit["keyword"]), norm(hit["posting_spelling"])}
    t = norm(text)
    return any(w and re.search(rf"(?<![a-z0-9]){re.escape(w)}(?:s|es|ed|ing)?(?![a-z0-9])", t) for w in words)


ACRONYMS = {"qa", "api", "apis", "sql", "ci/cd", "ci cd", "ux", "ui", "ai", "uat", "sdlc", "stlc", "bdd", "tdd",
            "rca", "e2e", "saas", "aws", "gcp", "json", "xml", "html", "css", "rest", "oop", "adb"}


def label_for(hit: dict) -> str:
    """The posting's own spelling when it is a proper noun phrase, else the skill's clean name.

    A posting says "defects" and "troubleshoot" where a skills line wants "defect
    tracking" and "troubleshooting", so a bare or plural form gives way to the name.
    """
    spelling, name = hit["posting_spelling"], hit["keyword"]
    bare = len(spelling.split()) < len(name.split())
    plural = spelling.lower().endswith("s") and not name.lower().endswith("s")
    stem = name.lower().startswith(spelling.lower()) and spelling.lower() != name.lower()
    chosen = name if (bare or plural or stem) else spelling
    if chosen == chosen.lower():
        chosen = " ".join(w.upper() if w in ACRONYMS else w.capitalize() for w in chosen.split())
    return chosen


def clean_title(title: str) -> str:
    return JUNK_TITLE.sub("", title).strip()


def tailor(base: dict, posting: dict, report: dict) -> dict:
    """Returns a resume dict with the same shape as resume.json, reordered and reworded."""
    matched = [h for h in report["ats_matched"] if h["kind"] != "soft"]
    matched_soft = [h for h in report["ats_matched"] if h["kind"] == "soft"]
    all_hits = report["ats_matched"] + report["ats_missing"]

    title = clean_title(posting.get("title") or "")
    header_title = title if QA_TITLE.search(title) else base["title"]

    # Skills: every skill the posting names and the resume carries, spelled the
    # posting's way, goes first under one heading. The rest of the base skills
    # follow in their own groups, minus anything already listed.
    core = []
    seen = set()
    for h in matched:
        label = label_for(h)
        if norm(label) in seen:
            continue
        seen.add(norm(label))
        core.append(label)
    groups = []
    for name, items in base["skills"]:
        kept = [i for i in items if norm(i) not in seen and not any(norm(c) in norm(i) for c in core)]
        if kept:
            groups.append([name, kept])
    skills = ([["Core Competencies (aligned to this role)", core]] if core else []) + groups

    # Summary: the base summary plus one sentence naming the posting's own skills.
    top = [label_for(h) for h in matched[:6]]
    summary = base["summary"]
    if top:
        summary += f" Directly relevant to this role: {', '.join(top[:-1])}{' and ' if len(top) > 1 else ''}{top[-1]}."
    if matched_soft:
        summary += f" Known for {', '.join(h['keyword'] for h in matched_soft[:3])}."

    # Bullets: inside each job, the ones speaking to the posting's skills come first.
    experience = []
    for job in base["experience"]:
        scored = [(sum(mentions(b, h) for h in all_hits), i, b) for i, b in enumerate(job["bullets"])]
        scored.sort(key=lambda x: (-x[0], x[1]))
        experience.append({**job, "bullets": [b for _, _, b in scored]})

    return {**base, "title": header_title, "summary": summary, "skills": skills, "experience": experience}


def to_text(r: dict) -> str:
    out = [r["name"], r["title"], r["contact"], "", "SUMMARY", r["summary"], "", "TECHNICAL SKILLS"]
    for name, items in r["skills"]:
        out.append(f"{name}: {', '.join(items)}")
    out += ["", "PROFESSIONAL EXPERIENCE"]
    for job in r["experience"]:
        out.append(f"{job['title']} | {job['company']}, {job['location']} | {job['dates']}")
        out += [f"- {b}" for b in job["bullets"]]
        out.append("")
    out += ["KEY ACHIEVEMENTS"] + [f"- {a}" for a in r["achievements"]]
    if r.get("statements"):
        out += ["", "ADDITIONAL EXPERIENCE"] + [f"- {a}" for a in r["statements"]]
    out += ["", "EDUCATION"]
    for degree, school, dates in r["education"]:
        out.append(f"{degree} | {school} | {dates}")
    return "\n".join(out) + "\n"


def to_pdf(r: dict, path: Path) -> None:
    name = ParagraphStyle("name", fontName="Times-Bold", fontSize=15, alignment=1, spaceAfter=1)
    sub = ParagraphStyle("sub", fontName="Times-Roman", fontSize=11, alignment=1, spaceAfter=1)
    contact = ParagraphStyle("contact", fontName="Times-Roman", fontSize=10, alignment=1, spaceAfter=6)
    h = ParagraphStyle("h", fontName="Times-Bold", fontSize=11.5, spaceBefore=7, spaceAfter=1)
    body = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=12.4)
    job = ParagraphStyle("job", fontName="Times-Bold", fontSize=10.5, spaceBefore=5, spaceAfter=2)
    bullet = ParagraphStyle("bullet", fontName="Times-Roman", fontSize=10, leading=12.4)

    def section(t):
        return [Paragraph(t, h), HRFlowable(width="100%", thickness=0.7, spaceAfter=3)]

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(esc(i), bullet), leftIndent=12) for i in items],
                            bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8)

    story = [Paragraph(esc(r["name"]), name), Paragraph(esc(r["title"]), sub), Paragraph(esc(r["contact"]), contact)]
    story += section("SUMMARY") + [Paragraph(esc(r["summary"]), body)]
    story += section("TECHNICAL SKILLS")
    for gname, items in r["skills"]:
        story.append(Paragraph(f"<b>{esc(gname)}</b>: {esc(', '.join(items))}", body))
    story += section("PROFESSIONAL EXPERIENCE")
    for j in r["experience"]:
        story.append(Paragraph(f"{esc(j['title'])} | {esc(j['company'])}, {esc(j['location'])} "
                               f"&nbsp;&nbsp;&nbsp;&nbsp; {esc(j['dates'])}", job))
        story.append(bullets(j["bullets"]))
    story += section("KEY ACHIEVEMENTS") + [bullets(r["achievements"])]
    if r.get("statements"):
        story += section("ADDITIONAL EXPERIENCE") + [bullets(r["statements"])]
    story += section("EDUCATION")
    for degree, school, dates in r["education"]:
        story.append(Paragraph(f"{esc(degree)} &nbsp;&nbsp;&nbsp;&nbsp; {esc(dates)}", job))
        story.append(Paragraph(f"<i>{esc(school)}</i>", body))
    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                      topMargin=0.5 * inch, bottomMargin=0.5 * inch).build(story)


def base_resume() -> dict:
    """resume.json plus the Additional Skills line (inferred + confirmed), the true base for every score."""
    return skills.with_additional(json.loads((HERE / "resume.json").read_text()))


def build_base(out_dir: Path) -> tuple[Path, Path]:
    r = base_resume()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = resume_name()
    pdf, txt = out_dir / f"{stem}.pdf", out_dir / f"{stem}.txt"
    txt.write_text(to_text(r))
    to_pdf(r, pdf)
    return pdf, txt


def build(posting: dict, report: dict, out_dir: Path, stem: str) -> tuple[Path, Path]:
    r = tailor(base_resume(), posting, report)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf, txt = out_dir / f"{stem}.pdf", out_dir / f"{stem}.txt"
    txt.write_text(to_text(r))
    to_pdf(r, pdf)
    return pdf, txt
