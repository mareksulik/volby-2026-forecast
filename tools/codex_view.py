"""Convert the frozen Codex forecast (data/codex/*.json) into the race structure used by build_site.py."""
import json
from pathlib import Path

from compare import key, race_id

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "data/codex" / f"{name}.json").read_text())


def polls_for(race: dict, polls: list) -> list:
    used = {u["id"]: u for u in race.get("polls_used") or []}
    out = []
    for p in polls:
        if p["race_id"] != race["id"]:
            continue
        u = used.get(p.get("id"))
        out.append({"pollster": p.get("agency"), "fieldwork_end": p.get("fieldwork_end") or p.get("published"),
                    "n": p.get("n_decided") or p.get("n_local"), "results": p.get("shares") or {},
                    "source": p.get("source_url"), "included": bool(p.get("included", True)),
                    "effective_n": round(u["effective_n"]) if u else None, "note": p.get("notes")})
    return out


def source_urls(race: dict, sources) -> list:
    ids = race.get("source")
    ids = ids if isinstance(ids, list) else [ids] if ids else []
    table = {s["id"]: s for s in sources} if isinstance(sources, list) else sources
    return [(table.get(i) or {}).get("url") or i for i in ids]


def odds_for(codex_race_id: str, odds: list, names: dict) -> list:
    out = []
    for o in odds:
        if o["race_id"] != codex_race_id:
            continue
        books = {}
        for cid, quotes in (o.get("quotes") or {}).items():
            for book, q in quotes.items():
                books.setdefault(book, {})[names.get(cid, cid)] = q
        out += [{"bookmaker": b, "date": o.get("observed_date"), "odds": q, "source": o.get("source_url")}
                for b, q in books.items()]
    return out


def races(claude: dict) -> list:
    """Codex races in Claude's structure; incumbency, office, voters and history come from the Claude record of the same race."""
    fc, polls, odds, events = load("forecast"), load("polls"), load("odds"), load("events")
    sources = load("sources")
    sources = sources.get("sources", sources) if isinstance(sources, dict) else sources
    cl = {r["id"]: r for r in claude["races"]}
    out = []
    for x in fc["races"]:
        rid = race_id(x["id"])
        c = cl[rid]
        inc = {key(k["name"]) for k in c["candidates"] if k["inc"]}
        names = {k["id"]: k["name"] for k in x["candidates"]}
        cands = [{"name": k["name"], "party": k.get("party"), "inc": key(k["name"]) in inc,
                  "share": round(k["estimate_pct"], 1), "lo80": round(k["low80_pct"], 1), "hi80": round(k["high80_pct"], 1),
                  "p_win": k["win_probability"], "fund_share": round(k["fundamental_pct"], 1),
                  "fund_p_win": k["fundamental_win_probability"], "job": k.get("job")}
                 for k in x["candidates"] if k["active"]]
        cands.sort(key=lambda k: -k["share"])
        withdrawn = [{"name": ev["name"], "source": ev.get("source_url")} for ev in events
                     if ev["race_id"] == x["id"] and ev.get("type") == "withdrawal"]
        out.append({"id": rid, "name": c["name"], "office": c["office"], "group": c["group"], "voters": c["voters"],
                    "history": c.get("history"), "candidates": cands, "withdrawn": withdrawn,
                    "polls": polls_for(x, polls), "odds": odds_for(x["id"], odds, names), "evidence": x.get("evidence"),
                    "notes": " ".join(x["notes"]) if isinstance(x.get("notes"), list) else x.get("notes"),
                    "sources": source_urls(x, sources)})
    return out


def meta() -> dict:
    fc = load("forecast")
    m = json.loads((ROOT / "data/codex/meta.json").read_text())
    return {**m, "backtest": fc.get("backtest"), "draws": fc.get("draws_per_race"), "status": fc.get("status")}
