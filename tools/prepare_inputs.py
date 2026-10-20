"""Convert research JSON (data/research/*.json) + manual overrides into model inputs (data/inputs/races/*.yaml).

Automatic features: incumbency, previous share in the same race (latest election), nominating parties,
government/opposition bloc. Judgement calls live in data/inputs/overrides.yaml, keyed by race id and
candidate surname, each with a reason.
"""
import json
import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUP = {"kraj": "kraj", "mesto": "mesto", "mc": "mc"}
OFFICE = {"predseda VUC": "predseda VUC", "primator": "primator", "starosta": "starosta"}

# canonical party keys used for the national swing and the bloc
PARTY_PATTERNS = [
    ("PS", r"progres[ií]vne slovensko|\bps\b"),
    ("SMER", r"\bsmer"),
    ("HLAS", r"\bhlas\b"),
    ("SNS", r"slovensk[aá] n[aá]rodn[aá] strana|\bsns\b"),
    ("SAS", r"sloboda a solidarita|\bsas\b"),
    ("KDH", r"kres[tť]anskodemokratick|\bkdh\b"),
    ("SLOVENSKO", r"hnutie slovensko|ol'ano|oľano|obyčajn[ií] ľudia|(^|, )slovensko(,|$)|\(slovensko\)"),
    ("DEMOKRATI", r"demokrati\b"),
    ("REPUBLIKA", r"republika"),
    ("ALIANCIA", r"aliancia|sz[oö]vets[eé]g"),
    ("SR", r"sme rodina"),
    ("KU", r"kres[tť]ansk[aá] [uú]nia"),
    ("ZL", r"za ľud[ií]"),
]
GOV = {"SMER", "HLAS", "SNS"}
LOCAL_RE = re.compile(r"councillor|council member|poslan|vice-?mayor|deputy mayor|viceprim|vicestarost|zástup|vicežup|prednost", re.I)
PARTISAN_RE = re.compile(r"campaign|kampa|commissioned by|objedn|released by .*(team|tím)", re.I)
CONTEXT_RACE = {
    "Bratislava primator": "mesto-bratislava", "Kosice primator": "mesto-kosice",
    "Banska Bystrica primator": "mesto-banska-bystrica", "Nitra primator": "mesto-nitra",
    "Presov primator": "mesto-presov", "Trencin primator": "mesto-trencin", "Trnava primator": "mesto-trnava",
    "Zilina primator": "mesto-zilina", "BSK predseda": "kraj-ba", "TTSK predseda": "kraj-tt",
    "TSK predseda": "kraj-tn", "NSK predseda": "kraj-nr", "ZSK predseda": "kraj-za", "BBSK predseda": "kraj-bb",
    "PSK predseda": "kraj-po", "KSK predseda": "kraj-ke",
}
OPP = {"PS", "SAS", "KDH", "SLOVENSKO", "DEMOKRATI"}
TITLE_RE = re.compile(r"\b(Ing|Mgr|Bc|JUDr|MUDr|RNDr|PhDr|PaedDr|PharmDr|MVDr|ThDr|ThLic|PhD|CSc|DrSc|MBA|MPH|LL\.?M|"
                      r"doc|prof|Dr|art|arch|ArtD|MSc|MA|BSc|DBA|MPA|MHA|MJur|Mag|Mgr\. art|akad|Ph\.D)\.?(?=[\s,]|$)", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


def clean_name(s: str) -> str:
    s = re.sub(r"\bM\.\s?A\.|\bM\.\s?Sc\.|\bB\.\s?A\.", "", s)
    s = TITLE_RE.sub("", s)
    s = re.sub(r"[,.]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def surname(s: str) -> str:
    return norm(clean_name(s)).split()[-1]


def parties(label: str) -> list[str]:
    t = (label or "").lower()
    if not t or t.startswith("neka") or "nezávisl" in t and "," not in t:
        return []
    return [k for k, pat in PARTY_PATTERNS if re.search(pat, t)]


def is_independent(label: str) -> bool:
    t = (label or "").strip().lower()
    return not t or t.startswith("neka") or t.startswith("nezávisl")


def match(name: str, pool: list[dict]):
    """Find a person in a list of {name: ...}: first + last name; a bare surname only if it is unique."""
    n = norm(clean_name(name)).split()
    if not n:
        return None
    full = [p for p in pool if {n[0], n[-1]} <= set(norm(clean_name(p["name"])).split())]
    if len(full) == 1:
        return full[0]
    if len(n) == 1:
        sur = [p for p in pool if surname(p["name"]) == n[0]]
        return sur[0] if len(sur) == 1 else None
    return None


def build_race(r: dict, ov: dict) -> dict:
    hist = r.get("history") or {}
    years = sorted(y for y, h in hist.items() if h and h.get("results"))
    last = hist[years[-1]] if years else None
    voters = (last or {}).get("registered_voters") or r.get("registered_voters_2026") or 0
    inc_name = (r.get("incumbent") or {}).get("name")
    cands = []
    for c in r["candidates_2026"]:
        name = clean_name(c["name"])
        prev = match(name, last["results"]) if last else None
        is_inc = bool(c.get("incumbent")) or (inc_name and surname(inc_name) == surname(name)
                                              and norm(clean_name(inc_name)).split()[0] == norm(name).split()[0])
        ps = parties(c.get("party"))
        bloc = "gov" if GOV & set(ps) else "opp" if OPP & set(ps) else None
        cand = {
            "name": name, "ballot_no": c.get("ballot_no"), "party": c.get("party"),
            "parties": ps, "bloc": bloc, "inc": bool(is_inc),
            "prev_share": round(prev["pct"] / 100, 4) if prev and prev.get("pct") is not None else 0.0,
            "neka": is_independent(c.get("party")), "withdrew": bool(c.get("withdrew")),
            "profile": c.get("profile"), "prior_runs": c.get("prior_runs"),
            "local_official": not is_inc and bool(LOCAL_RE.search(c.get("profile") or "")),
        }
        ovc = ov.get("candidates") or {}
        o = ovc.get(norm(name)) or ovc.get(surname(name)) or {}
        cand.update(o)
        cands.append(cand)
    polls = []
    for p in r.get("polls") or []:
        end = poll_end(str(p.get("fieldwork") or p.get("date") or "") + " " + str(p.get("published") or ""))
        res = {}
        for k, v in (p.get("results") or {}).items():
            if v is None:
                continue
            m = match(k, cands)
            if m:
                res[m["name"]] = float(v)
        if len(res) >= 2 and end:
            polls.append({"pollster": p.get("pollster"), "fieldwork_end": end, "n": p.get("n"),
                          "sponsor": p.get("sponsor"), "results": res,
                          "others_pct": p.get("others_pct"), "source": p.get("source"),
                          "partisan": bool(PARTISAN_RE.search(" ".join(str(p.get(k) or "") for k in ("sponsor", "note"))))})
    for p in polls:
        if p["pollster"] in (ov.get("partisan_polls") or []):
            p["partisan"] = True
    polls = dedup_polls(polls)
    odds = []
    for b in r.get("odds") or []:
        od = {}
        for k, v in (b.get("odds") or {}).items():
            m = match(k, cands)
            if m and v:
                od[m["name"]] = float(v)
        if od:
            odds.append({"bookmaker": b.get("bookmaker"), "date": b.get("date"), "odds": od, "source": b.get("source")})
    race = {
        "id": r["race_id"], "name": r["name"], "group": r["race_id"].split("-")[0],
        "office": OFFICE[r["office"]], "voters": int(voters or 0),
        "incumbent": r.get("incumbent"), "history": hist,
        "candidates": cands, "polls": polls + (ov.get("polls") or []), "odds": odds + (ov.get("odds") or []),
        "notes": r.get("notes"), "key_events": r.get("key_events"),
        "sources": sorted(set((r.get("candidates_source") or []) +
                              [h.get("source") for h in hist.values() if h and h.get("source")])),
    }
    for k in ("voters", "notes"):
        if k in ov:
            race[k] = ov[k]
    return race


MONTHS = {"august": "2026-08-20", "september": "2026-09-20", "october": "2026-10-10", "október": "2026-10-10"}


def poll_end(text: str) -> str | None:
    """Last ISO date in the fieldwork text; else mid-month for a bare month name (documented approximation)."""
    dates = re.findall(r"20\d\d-\d\d-\d\d", text)
    if dates:
        return max(dates)
    for m, d in MONTHS.items():
        if m in text.lower():
            return d
    return None


def dedup_polls(polls: list[dict]) -> list[dict]:
    """The same poll often arrives twice (race agent + context agent): same house, end dates within 7 days."""
    out = []
    for p in polls:
        house = re.split(r"[\s(]", str(p["pollster"]).strip())[0].lower()
        end = p["fieldwork_end"]
        dup = any(re.split(r"[\s(]", str(q["pollster"]).strip())[0].lower() == house and
                  (abs((__import__("datetime").date.fromisoformat(end) - __import__("datetime").date.fromisoformat(q["fieldwork_end"])).days) <= 7
                   or max(p["results"].values()) == max(q["results"].values()))
                  for q in out)
        if not dup:
            out.append(p)
    return out


def key_of(item: dict) -> tuple:
    return (str(item.get("bookmaker") or item.get("pollster")), str(item.get("date") or item.get("fieldwork")),
            json.dumps(item.get("odds") or item.get("results"), sort_keys=True))


def merge_context(r: dict, extra: dict | None) -> dict:
    """Add odds and race polls found by the cross-cutting context search; keep only the latest odds per bookmaker."""
    if not extra:
        return r
    r = dict(r)
    for k in ("odds", "polls"):
        seen = {key_of(x) for x in r.get(k) or []}
        r[k] = list(r.get(k) or []) + [x for x in extra[k] if key_of(x) not in seen]
    latest = {}
    for o in r["odds"]:
        b = o.get("bookmaker")
        if b not in latest or str(o.get("date")) > str(latest[b].get("date")):
            latest[b] = o
    r["odds"] = list(latest.values())
    return r


def main() -> None:
    overrides = yaml.safe_load((ROOT / "data/inputs/overrides.yaml").read_text()) or {}
    notes_path = ROOT / "data/inputs/notes_sk.yaml"
    notes_sk = yaml.safe_load(notes_path.read_text()) if notes_path.exists() else {}
    out = ROOT / "data/inputs/races"
    out.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list] = {}
    ctx = json.loads((ROOT / "data/research/context.json").read_text())
    extra = {}
    for o in ctx.get("odds") or []:
        if o.get("race") in CONTEXT_RACE:
            extra.setdefault(CONTEXT_RACE[o["race"]], {"odds": [], "polls": []})["odds"].append(o)
    for p in ctx.get("extra_race_polls") or []:
        if p.get("race") in CONTEXT_RACE and p.get("results"):
            extra.setdefault(CONTEXT_RACE[p["race"]], {"odds": [], "polls": []})["polls"].append(p)
    for p in sorted((ROOT / "data/research").glob("*.json")):
        if p.name == "context.json":
            continue
        for r in json.loads(p.read_text()):
            r = merge_context(r, extra.get(r["race_id"]))
            race = build_race(r, overrides.get(r["race_id"], {}))
            race["notes"] = notes_sk.get(r["race_id"], race["notes"])
            groups.setdefault(r["race_id"].split("-")[0], []).append(race)
    for g, races in groups.items():
        (out / f"{g}.yaml").write_text(yaml.safe_dump(races, allow_unicode=True, sort_keys=False, width=140))
        print(g, len(races), "races,", sum(len(r["candidates"]) for r in races), "candidates")


if __name__ == "__main__":
    main()
