"""Opens a job's apply page in a real browser, attaches the tailored resume and fills the form.

    .venv/bin/python apply.py <url> <resume.pdf>

Best effort across Greenhouse, Lever, Ashby, Workday, iCIMS and plain career pages.
Answers come from profile.json. Only empty fields are filled; nothing is submitted;
legal acknowledgement checkboxes are left for the person. The browser profile is kept
between runs so logins stick. It keeps watching the page while the window is open, so
each step of a multi-page form is filled as it appears.
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
PROFILE_DIR = Path.home() / "Desktop" / "pinloop-jobs" / ".browser-profile"
RESUME_WORDS = re.compile(r"resume|résumé|\bcv\b|curriculum", re.I)
COVER_WORDS = re.compile(r"cover\s*letter|other\s*attachment|transcript|portfolio", re.I)

# Descriptor regex → profile key. First match wins, so specific rules come first.
RULES: list[tuple[re.Pattern, str]] = [(re.compile(p, re.I), k) for p, k in [
    (r"first.?name|given.?name|\bfname\b|legalname.*first", "first_name"),
    (r"last.?name|family.?name|surname|\blname\b|legalname.*last", "last_name"),
    (r"preferred.?name|nick.?name", "first_name"),
    (r"full.?name|legal.?name|your.?name|^name$|\bname\b(?!.*(company|employer|school|referr|contact|file))", "full_name"),
    (r"e-?mail", "email"),
    (r"^country|country\*? \||country.?code|\| country", "country"),
    (r"phone|mobile|telephone|\bcell\b", "phone"),
    (r"linkedin", "linkedin"),
    (r"github", "github"),
    (r"website|portfolio|personal.?site|\burl\b|other.?link", "website"),
    (r"address.?line.?1|street|addressline1|^address$", "address"),
    (r"\bcity\b|\btown\b", "city"),
    (r"\bstate\b(?!.?of.?the)|province|region", "state"),
    (r"\bzip|postal", "zip"),
    (r"country", "country"),
    (r"current.?(company|employer)|company.?name|employer|organization|\borg\b", "current_company"),
    (r"current.?(title|role|position)|job.?title|^title$", "current_title"),
    (r"years?.?of.?experience|how.?many.?years", "years_experience"),
    (r"authoriz|eligible.?to.?work|legally|right.?to.?work|work.?permit", "work_authorized"),
    (r"sponsor|visa", "needs_sponsorship"),
    (r"\b18\b|eighteen|\bage\b|years.?old", "over_18"),
    (r"relocat", "willing_to_relocate"),
    (r"work.?remote|remote.?(work|position|role)|comfortable.*remote", "remote_ok"),
    (r"start.?date|available.?to.?start|earliest|notice.?period|availability", "start_date"),
    (r"salary|compensation|pay.?expect|desired.?pay|\bpay\b", "salary"),
    (r"how.?did.?you.?hear|hear.?about|referral.?source|^source$|where.?did.?you.?(find|see)|\bsource\b(?!.?control)", "how_heard"),
    (r"referr", "referred_by"),
    (r"pronoun", "pronouns"),
    (r"hispanic|latin", "hispanic"),
    (r"gender|\bsex\b", "gender"),
    (r"race|ethnic", "race"),
    (r"veteran|military", "veteran"),
    (r"disabilit", "disability"),
    (r"previously.?(worked|employed)|worked.?(here|for).*before|former.?employee|current.?or.?former", "worked_here_before"),
    (r"non.?compete|non.?solicit", "non_compete"),
    (r"cover.?letter|why.?(are you|do you want)|additional.?information|anything.?else|comments", "cover_letter"),
    (r"location|where.?are.?you.?(based|located)", "location"),
]]
YES = re.compile(r"^\s*(yes|y|i am|i do|true)\b", re.I)
NO = re.compile(r"^\s*(no|n|i am not|i do not|false)\b", re.I)
DECLINE = re.compile(r"decline|prefer not|do not wish|don.?t wish|not to (answer|self|disclose)|choose not|rather not|i do not want", re.I)

COLLECT_JS = r"""
() => {
  const seen = new Set();
  const out = [];
  const text = (el) => (el && el.textContent || '').replace(/\s+/g, ' ').trim();
  const labelFor = (el) => {
    let s = [];
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) s.push(text(l)); }
    const wrap = el.closest('label'); if (wrap) s.push(text(wrap));
    const lb = el.getAttribute('aria-labelledby');
    if (lb) lb.split(/\s+/).forEach(id => { const n = document.getElementById(id); if (n) s.push(text(n)); });
    const desc = el.getAttribute('aria-describedby');
    if (desc) desc.split(/\s+/).forEach(id => { const n = document.getElementById(id); if (n) s.push(text(n)); });
    const fs = el.closest('fieldset'); if (fs) { const lg = fs.querySelector('legend'); if (lg) s.push(text(lg)); }
    if (s.join('').trim() || el.getAttribute('aria-label') || el.getAttribute('placeholder')) return s.join(' | ');
    // Only for controls with no label at all: the nearest question text above the control.
    let box = el.closest('div, li, td, section'); let hops = 0;
    while (box && hops < 4 && text(box).length < 12) { box = box.parentElement; hops++; }
    if (box) { const q = box.querySelector('label, legend, h1, h2, h3, h4, h5, span, p, div');
               if (q && q !== el && text(q).length < 220) s.push(text(q)); }
    return s.join(' | ');
  };
  let i = 0;
  const mark = (el) => { if (!el.dataset.plId) el.dataset.plId = 'pl' + (Date.now() % 1e7) + '_' + (i++); return el.dataset.plId; };
  const visible = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
                            return cs.visibility !== 'hidden' && cs.display !== 'none' && (r.width > 0 || r.height > 0); };
  document.querySelectorAll('input, textarea, select, [role=combobox], [role=radiogroup], button[aria-haspopup=listbox]').forEach(el => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || (tag === 'input' ? 'text' : tag)).toLowerCase();
    if (['hidden', 'submit', 'button', 'password', 'search', 'file', 'image', 'reset'].includes(type)) return;
    if (el.dataset.plDone) return;
    if (!visible(el) && type !== 'radio') return;
    const cs0 = getComputedStyle(el);
    if (tag !== 'select' && (el.readOnly || cs0.opacity === '0' || el.getAttribute('aria-hidden') === 'true'
        || (el.getAttribute('tabindex') === '-1' && tag === 'input' && !el.getAttribute('role')))) return;
    const role = el.getAttribute('role') || '';
    let kind = type;
    if (tag === 'select') kind = 'select';
    else if (role === 'combobox' && tag !== 'input') kind = 'combobox';
    else if (role === 'combobox' && tag === 'input' && (el.getAttribute('aria-autocomplete') || el.closest('[class*=select]'))) kind = 'combobox';
    else if (role === 'radiogroup') kind = 'radiogroup';
    else if (tag === 'button') kind = 'listbutton';
    else if (tag === 'textarea') kind = 'textarea';
    const desc = [el.getAttribute('name'), el.id, el.getAttribute('aria-label'), el.getAttribute('placeholder'),
                  el.getAttribute('autocomplete'), el.getAttribute('data-automation-id'), el.getAttribute('data-qa'),
                  el.getAttribute('data-testid'), labelFor(el)].filter(Boolean).join(' | ');
    let value = '';
    if (kind === 'select') value = el.options[el.selectedIndex] && el.value ? text(el.options[el.selectedIndex]) : '';
    else if (kind === 'radio' || kind === 'checkbox') value = el.checked ? 'on' : '';
    else if (kind === 'combobox' || kind === 'listbutton' || kind === 'radiogroup') value = (el.value || text(el)).replace(/select\.\.\.|select one|choose|please select/i, '').trim();
    else value = el.value || '';
    let options = [];
    if (kind === 'select') options = Array.from(el.options).map(o => text(o));
    if (kind === 'radio') {
      const lab = labelFor(el); options = [lab];
      // Radios share a question through their name; the question text is what the group's fieldset/legend says.
      const grp = el.name ? Array.from(document.querySelectorAll(`input[type=radio][name="${CSS.escape(el.name)}"]`)) : [el];
      const q = grp.map(r => r.closest('fieldset, [role=radiogroup], div')).find(Boolean);
      out.push({ id: mark(el), kind, desc: (q ? text(q).slice(0, 300) + ' | ' : '') + desc, value, options, group: el.name || '' });
      return;
    }
    if (kind === 'radiogroup') options = Array.from(el.querySelectorAll('[role=radio], label, button')).map(text).filter(Boolean);
    out.push({ id: mark(el), kind, desc, value, options, group: '' });
  });
  return out;
}
"""

FILL_JS = r"""
([id, value]) => {
  const el = document.querySelector(`[data-pl-id="${id}"]`); if (!el) return false;
  const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  el.focus(); setter.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
  el.blur(); el.dataset.plDone = '1'; return true;
}
"""
SELECT_JS = r"""
([id, idx]) => {
  const el = document.querySelector(`[data-pl-id="${id}"]`); if (!el) return false;
  el.selectedIndex = idx; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dataset.plDone = '1'; return true;
}
"""
DONE_JS = "(id) => { const el = document.querySelector(`[data-pl-id=\"${id}\"]`); if (el) el.dataset.plDone = '1'; }"
OVERLAY_JS = r"""
(t) => { let d = document.getElementById('pl-note');
  if (!d) { d = document.createElement('div'); d.id = 'pl-note';
    d.style = 'position:fixed;top:12px;right:12px;z-index:2147483647;background:#111;color:#fff;padding:10px 14px;'
            + 'border-radius:8px;font:14px system-ui;box-shadow:0 4px 16px #0006;max-width:340px;line-height:1.4';
    document.body.appendChild(d); }
  d.textContent = t; }
"""


def direct_apply_url(url: str) -> str:
    """The form itself, when the hiring system has a known address for it."""
    m = re.match(r"https?://jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})/?(?:\?.*)?$", url)
    if m:
        return f"https://jobs.lever.co/{m.group(1)}/{m.group(2)}/apply"
    m = re.match(r"https?://jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})/?(?:\?.*)?$", url)
    if m:
        return f"https://jobs.ashbyhq.com/{m.group(1)}/{m.group(2)}/application"
    return url


def greenhouse_fallback(url: str) -> str | None:
    """A company page embedding Greenhouse (…?gh_jid=123) has its form at Greenhouse itself."""
    m = re.search(r"gh_jid=(\d+)", url)
    if not m:
        return None
    host = re.sub(r"^www\.", "", re.match(r"https?://([^/]+)", url).group(1))
    slug = host.split(".")[0]
    return f"https://job-boards.greenhouse.io/embed/job_app?for={slug}&token={m.group(1)}"


def load_profile() -> dict:
    p = json.loads((HERE / "profile.json").read_text())
    p["full_name"] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    p["location"] = ", ".join(x for x in [p.get("city"), p.get("state"), p.get("country")] if x)
    return p


def key_for(desc: str) -> str | None:
    d = desc.lower()
    for rx, key in RULES:
        if rx.search(d):
            return key
    return None


def pick_option(options: list[str], value: str, key: str) -> int | None:
    """Index of the option that means `value`, or None. Yes/no and decline answers are matched by meaning."""
    v = value.strip().lower()
    if not v:
        return None
    low = [o.strip().lower() for o in options]
    for i, o in enumerate(low):
        if o == v:
            return i
    if key in ("gender", "race", "hispanic", "veteran", "disability", "pronouns") and DECLINE.search(value):
        for i, o in enumerate(options):
            if DECLINE.search(o):
                return i
    if YES.match(value):
        for i, o in enumerate(low):
            if YES.match(o) and not NO.match(o):
                return i
    if NO.match(value):
        for i, o in enumerate(low):
            if NO.match(o):
                return i
    if key == "country":
        for i, o in enumerate(low):
            if re.search(r"^united states|^usa$|^us$|u\.s\.a?\.?$|united states of america", o):
                return i
    if key == "state":
        abbr = {"washington": "wa"}.get(v, "")
        for i, o in enumerate(low):
            if o == abbr or o.startswith(v):
                return i
    if key == "how_heard":
        for i, o in enumerate(low):
            if re.search(r"job board|linkedin|indeed|online|other|job site|search", o):
                return i
    if key == "veteran":
        for i, o in enumerate(low):
            if re.search(r"not a (protected )?veteran|no\b", o):
                return i
    for i, o in enumerate(low):
        if v in o or (len(o) > 3 and o in v):
            return i
    return None


def file_inputs(page):
    for frame in page.frames:
        try:
            for el in frame.query_selector_all("input[type=file]:not([data-pl-attached])"):
                yield frame, el
        except Exception:
            continue


def describe(frame, el) -> str:
    try:
        return frame.evaluate(
            """(el) => {
                const id = el.id;
                const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                return [el.name, el.id, el.getAttribute('aria-label'), el.getAttribute('data-qa'),
                        label && label.textContent, el.closest('div,fieldset,section')?.textContent?.slice(0, 200)]
                       .filter(Boolean).join(' ');
            }""", el)
    except Exception:
        return ""


def click_apply(page) -> bool:
    for frame in page.frames:
        for sel in ["a:has-text('Apply')", "button:has-text('Apply')", "[data-qa*='apply']",
                    "a[href*='apply']", "a:has-text('Easy Apply')"]:
            try:
                el = frame.locator(sel).first
                if el.count() and el.is_visible():
                    el.click(timeout=3000)
                    return True
            except Exception:
                continue
    return False


def attach_resume(page, resume: str) -> bool:
    candidates = list(file_inputs(page))
    best = None
    for frame, el in candidates:
        d = describe(frame, el)
        if RESUME_WORDS.search(d):
            best = (frame, el)
            break
    if best is None:
        for frame, el in candidates:
            if not COVER_WORDS.search(describe(frame, el)):
                best = (frame, el)
                break
    if best is None:
        return False
    frame, el = best
    try:
        el.set_input_files(resume)
        frame.evaluate("(el) => { el.dataset.plAttached = '1'; }", el)
        return True
    except Exception:
        return False


FAILS: dict[str, int] = {}


def menu_options(frame, control):
    """The options of the menu this control just opened: by aria-controls/owns, else the visible menu."""
    try:
        owns = control.get_attribute("aria-controls") or control.get_attribute("aria-owns")
    except Exception:
        owns = None
    if owns:
        for oid in owns.split():
            loc = frame.locator(f'[id="{oid}"] [role=option], [id="{oid}"] [class*="option"], [id="{oid}"] li')
            if loc.count():
                return loc
    for sel in ("[class*='menu'] [class*='option']:visible", "[role=listbox]:visible [role=option]", "[role=option]:visible"):
        loc = frame.locator(sel)
        if loc.count():
            return loc
    return None


def fill_frame(frame, profile: dict, log: list[str]) -> int:
    try:
        fields = frame.evaluate(COLLECT_JS)
    except Exception:
        return 0
    n = 0
    radios_done: set[str] = set()
    for f in fields:
        if FAILS.get(f["desc"], 0) >= 3:
            continue
        key = key_for(f["desc"])
        if not key:
            continue
        value = str(profile.get(key) or "")
        if not value:
            continue
        kind = f["kind"]
        try:
            if kind in ("text", "email", "tel", "url", "number", "textarea"):
                if f["value"]:
                    continue
                if key in ("work_authorized", "needs_sponsorship", "over_18", "willing_to_relocate", "remote_ok",
                           "worked_here_before", "non_compete", "gender", "race", "hispanic", "veteran", "disability"):
                    continue  # a free-text box with a yes/no question is for the person to answer
                if kind == "number" and not re.fullmatch(r"[\d.]+", value):
                    continue
                if frame.evaluate(FILL_JS, [f["id"], value]):
                    n += 1
                    log.append(f"{key} ← {value[:30]}")
            elif kind == "select":
                if f["value"] and not re.search(r"select|choose|please|^-+$|^$", f["value"], re.I):
                    continue
                idx = pick_option(f["options"], value, key)
                if idx is not None and frame.evaluate(SELECT_JS, [f["id"], idx]):
                    n += 1
                    log.append(f"{key} ← {f['options'][idx][:30]}")
            elif kind == "radio":
                if f["group"] in radios_done or f["value"]:
                    continue
                idx = pick_option(f["options"], value, key)
                if idx is not None:
                    loc = frame.locator(f'[data-pl-id="{f["id"]}"]')
                    loc.check(force=True, timeout=2000)
                    frame.evaluate(DONE_JS, f["id"])
                    radios_done.add(f["group"])
                    n += 1
                    log.append(f"{key} ← {f['options'][0][:30]}")
            elif kind == "radiogroup":
                if f["value"] and pick_option([f["value"]], value, key) is not None:
                    continue
                idx = pick_option(f["options"], value, key)
                if idx is not None:
                    frame.locator(f'[data-pl-id="{f["id"]}"] [role=radio], [data-pl-id="{f["id"]}"] label, '
                                  f'[data-pl-id="{f["id"]}"] button').nth(idx).click(timeout=2000)
                    frame.evaluate(DONE_JS, f["id"])
                    n += 1
                    log.append(f"{key} ← {f['options'][idx][:30]}")
            elif kind in ("combobox", "listbutton"):
                if f["value"] and not re.search(r"select|choose|please|^$", f["value"], re.I):
                    continue
                loc = frame.locator(f'[data-pl-id="{f["id"]}"]')
                loc.click(timeout=2000)
                frame.wait_for_timeout(400)
                options = menu_options(frame, loc)
                texts = [t.strip() for t in options.all_inner_texts()[:300]] if options else []
                idx = pick_option(texts, value, key) if texts else None
                if idx is not None:
                    options.nth(idx).click(timeout=2000)
                elif kind == "combobox":
                    typed = value.split(",")[0][:40] if key in ("city", "location") else value[:40]
                    frame.page.keyboard.type(typed, delay=20)
                    opts = None
                    for _ in range(8):  # autocomplete suggestions arrive asynchronously
                        frame.wait_for_timeout(400)
                        opts = menu_options(frame, loc)
                        if opts and opts.count() and not re.search(r"loading|no options", opts.first.inner_text(), re.I):
                            break
                    if opts and opts.count():
                        texts = [t.strip() for t in opts.all_inner_texts()[:50]]
                        j = pick_option(texts, value, key)
                        opts.nth(j if j is not None else 0).click(timeout=2000)
                    else:
                        frame.page.keyboard.press("Enter")
                else:
                    frame.page.keyboard.press("Escape")
                    continue
                frame.evaluate(DONE_JS, f["id"])
                n += 1
                log.append(f"{key} ← {value[:30]}")
        except Exception:
            if os.environ.get("PL_DEBUG"):
                traceback.print_exc()
            # React forms re-render controls between fills; leave it for the next pass, up to a limit.
            FAILS[f["desc"]] = FAILS.get(f["desc"], 0) + 1
            if FAILS[f["desc"]] >= 3:
                try:
                    frame.evaluate(DONE_JS, f["id"])
                except Exception:
                    pass
            continue
    return n


def fill_all(page, profile: dict, log: list[str]) -> int:
    return sum(fill_frame(fr, profile, log) for fr in page.frames)


def main(url: str, resume: str) -> None:
    profile = load_profile()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False, viewport=None,
                                                   args=["--start-maximized"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(direct_apply_url(url), wait_until="domcontentloaded", timeout=60000)

        attached = False
        clicked = False
        fell_back = False
        filled = 0
        log: list[str] = []
        started = time.time()
        last_url = ""
        while True:
            try:
                if not ctx.pages:
                    break
                page = ctx.pages[-1]
                if page.url != last_url:
                    last_url = page.url
                    time.sleep(1.5)
                if not attached and attach_resume(page, resume):
                    attached = True
                if not attached and not clicked and time.time() - started > 4:
                    clicked = click_apply(page)
                if not attached and not fell_back and time.time() - started > 25 and greenhouse_fallback(url):
                    fell_back = True
                    page.goto(greenhouse_fallback(url), wait_until="domcontentloaded", timeout=60000)
                got = fill_all(page, profile, log)
                filled += got
                note = (("Resume attached. " if attached else "Looking for the resume upload… ")
                        + (f"Filled {filled} field{'s' if filled != 1 else ''}. " if filled else "")
                        + "Check everything, then submit it yourself.")
                page.evaluate(OVERLAY_JS, note)
            except Exception:
                pass
            time.sleep(2)
        print(f"attached={attached} filled={filled}", flush=True)
        for line in log:
            print("  " + line, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
