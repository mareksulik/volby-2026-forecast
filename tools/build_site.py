"""Static site generator (mars-ui) -> docs/ for GitHub Pages: Claude forecast, Codex forecast, comparison."""
import html
import json
import math
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARS = Path.home() / "Documents/GitHub/mars-ui/dist"
REPO = "https://github.com/mareksulik/volby-2026-forecast"
CODEX_REPO = "https://github.com/mareksulik/volebny-model-codex"
GROUPS = [("kraj", "Predsedovia samosprávnych krajov"), ("mesto", "Primátori krajských miest"),
          ("mc", "Starostovia mestských častí Bratislavy")]
OFFICE = {"predseda VUC": "predseda VÚC", "primator": "primátor", "starosta": "starosta"}
TOP = [("claude", "index.html", "Claude"), ("codex", "codex.html", "Codex"), ("porovnanie", "porovnanie.html", "Porovnanie")]
SUBNAV = {
    "claude": ([("index.html", "Prehľad"), ("model.html", "Model"), ("pravidla.html", "Pravidlá"),
                ("skore.html", "Skóre"), ("archiv.html", "Archív")], REPO),
    "codex": ([("codex.html", "Prehľad"), ("codex-model.html", "Model")], CODEX_REPO),
    "porovnanie": ([("#suhrn", "Súhrn"), ("#vsetky", "Všetky voľby"), ("#metodiky", "Metodiky")], REPO),
}
PREFIX = {"claude": "", "codex": "codex-"}

e = lambda s: html.escape(str(s if s is not None else ""))


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=1):
    return "–" if x is None else f"{num(x, d)} %"


def prob(p):
    if p is None:
        return "–"
    if p >= 0.995:
        return "> 99 %"
    if p < 0.005:
        return "< 1 %"
    return f"{round(100 * p)} %"


def prob_chip(p):
    tone = "ok" if p >= 0.7 else "info" if p >= 0.4 else "warn" if p >= 0.15 else "neutral"
    return f'<span class="chip chip-{tone}">{prob(p)}</span>'


def stamp(s):
    return e(str(s)[:16].replace("T", " "))


def interval_svg(c, scale):
    w, h = 180, 16
    x = lambda v: round(v / scale * w, 1)
    return (f'<svg class="iv" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<line x1="0" y1="8" x2="{w}" y2="8" stroke="var(--mu-gray-200)"/>'
            f'<rect x="{x(c["lo80"])}" y="4" width="{max(x(c["hi80"]) - x(c["lo80"]), 1)}" height="8" rx="4" fill="var(--mu-blue-200)"/>'
            f'<circle cx="{x(c["share"])}" cy="8" r="4" fill="var(--mu-blue-700)"/></svg>')


def page(title, body, top, active, status):
    items, repo = SUBNAV[top]
    nav = "".join(f'<a href="{h}"{" class=active" if h == active else ""}>{t}</a>' for h, t in items)
    topmenu = "".join(f'<a href="{h}"{" class=active aria-current=page" if k == top else ""}>{t}</a>' for k, h, t in TOP)
    return f"""<!DOCTYPE html>
<html lang="sk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="ds.css"><script src="ds.js"></script>
<style>
.iv{{vertical-align:middle}} .race-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:16px}}
.race-grid>*{{min-width:0}} .race-grid .card h3{{margin:0 0 4px}} .race-grid table td,.race-grid table th{{padding:6px 8px}}
td.nm{{min-width:200px;max-width:280px}} td.ivc{{min-width:140px}} .muted{{color:var(--mu-gray-900)}}
.topmenu{{display:flex;gap:4px;align-items:center;margin-left:auto}}
.topmenu a{{font-size:14px;line-height:20px;font-weight:500;padding:6px 12px;border-radius:var(--mu-radius-sm);color:var(--mu-gray-900);text-decoration:none}}
.topmenu a:hover{{background:var(--mu-gray-100);color:var(--mu-gray-1000)}}
.topmenu a.active{{background:var(--mu-gray-1000);color:var(--mu-background-100)}}
.stats-row{{display:flex;flex-wrap:wrap;gap:16px 32px}} .stats-row .stat{{flex:1 1 160px}}
footer.site{{flex-wrap:wrap;gap:8px 24px}} footer.site .status{{display:flex;flex-wrap:wrap;gap:4px 16px;text-transform:uppercase;letter-spacing:.06em;font-size:12px}}
@media (max-width:600px){{.race-grid{{grid-template-columns:1fr}} td.nm{{min-width:150px}}}}
</style></head><body>
<header class="topbar"><div class="wrap"><div class="brand">
<svg viewBox="0 0 110 22" height="22" aria-hidden="true"><text x="0" y="17" font-family="Geist, sans-serif" font-weight="600" font-size="18" fill="currentColor">Voľby 2026</text></svg>
<span class="slash"></span><span class="app">Predpoveď samosprávnych volieb</span><h1 class="sr-only">{e(title)}</h1></div>
<div class="topmenu" role="navigation" aria-label="Model">{topmenu}</div></div></header>
<nav aria-label="Sekcie"><div class="wrap">{nav}<a href="{repo}" class="right">GitHub</a></div></nav>
{body}
<footer class="site"><span class="status">{status}</span><span>Marek Šulík · obsah CC BY 4.0, kód MIT · predpovede pripravili Claude a Codex, nie sú to tipy na stávkovanie</span></footer>
</body></html>"""


# ---------- shared race views ----------

def race_table(r, full=False, model="claude"):
    scale = max(60, max(c["hi80"] for c in r["candidates"]) + 5)
    scale = min(100, ((scale + 9) // 10) * 10)
    rows = []
    for c in r["candidates"]:
        inc = ' <span class="chip chip-neutral">obhajca</span>' if c["inc"] else ""
        party = f'<div class="text-small muted">{e(c["party"])}</div>' if full else ""
        svg = f'<td class="ivc">{interval_svg(c, scale)}</td>' if full else ""
        extra = ""
        if full:
            extra = f'<td class="num gs">{pct(c["fund_share"])}</td><td class="num">{prob(c["fund_p_win"])}</td>'
            if model == "claude":
                extra += f'<td class="num">{prob(c["p_win_blind"])}</td><td class="num">{prob(c["p_win_market"])}</td>'
        rows.append(f'<tr><td class="nm">{e(c["name"])}{inc}{party}</td><td class="num">{pct(c["share"])}</td>'
                    f'<td class="num">{c["lo80"]:.0f}–{c["hi80"]:.0f} %</td>{svg}'
                    f'<td class="num">{prob_chip(c["p_win"])}</td>{extra}</tr>')
    head = ('<tr><th>Kandidát</th><th class="num">Odhad</th><th class="num">80 % interval</th>'
            + (f'<th>0–{scale} %</th>' if full else "") + '<th class="num">P(výhra)</th>')
    if full:
        head += '<th class="num gs">Fundamenty</th><th class="num">P fund.</th>'
        if model == "claude":
            head += '<th class="num">P bez trhu</th><th class="num">P trh</th>'
    return f'<div class="tbl-scroll"><table><thead>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def history_html(r):
    out = []
    for year, h in sorted((r.get("history") or {}).items(), reverse=True):
        if not h or not h.get("results"):
            continue
        rows = "".join(f'<tr><td>{e(x.get("name"))}</td><td>{e(x.get("party"))}</td><td class="num">{pct(x.get("pct"), 2)}</td></tr>'
                       for x in sorted(h["results"], key=lambda x: -(x.get("pct") or 0))[:8])
        src = f' · <a href="{e(h.get("source"))}">zdroj</a>' if h.get("source") else ""
        out.append(f'<figure><figcaption>Voľby {e(year)}</figcaption><div class="fig-sub">účasť {pct(h.get("turnout_pct"), 2)}{src}</div>'
                   f'<div class="tbl-scroll"><table><thead><tr><th>Kandidát</th><th>Strana</th><th class="num">Podiel</th></tr></thead><tbody>{rows}</tbody></table></div></figure>')
    return "".join(out) or '<p class="muted">Historické výsledky nie sú k dispozícii.</p>'


def polls_html(r, model):
    if not r["polls"]:
        return '<p class="muted">Žiadny prieskum.</p>'
    rows = []
    for p in r["polls"]:
        res = ", ".join(f"{e(k)} {pct(v)}" for k, v in sorted(p["results"].items(), key=lambda kv: -kv[1]))
        if model == "codex":
            used = "áno" if p["included"] else "nie"
            extra = f'<td>{used}</td><td class="num">{e(p.get("effective_n") or "–")}</td>'
        else:
            extra = ""
        rows.append(f'<tr><td>{e(p.get("pollster"))}</td><td class="num">{e(p.get("fieldwork_end"))}</td><td class="num">{e(p.get("n") or "–")}</td>'
                    f'{extra}<td>{res}</td><td><a href="{e(p.get("source"))}">zdroj</a></td></tr>')
    if model == "codex":
        head = '<th>Použitý</th><th class="num">Efektívne n</th>'
        sub = "efektívne n = váha prieskumu v modeli (pseudopozorovania)"
    else:
        head = ""
        pi = r.get("poll_info") or {}
        sub = f'váha prieskumov v modeli {round(100 * pi["weight"])} %' if pi else ""
    return (f'<div class="fig-sub">{sub}</div><div class="tbl-scroll"><table><thead><tr><th>Agentúra</th><th class="num">Koniec zberu</th>'
            f'<th class="num">n</th>{head}<th>Výsledky</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def odds_html(r, model):
    if not r["odds"]:
        return '<p class="muted">Kurzy nie sú k dispozícii.</p>'
    rows = "".join(f'<tr><td>{e(o["bookmaker"])}</td><td class="num">{e(o.get("date"))}</td><td>{", ".join(f"{e(k)} {v}" for k, v in o["odds"].items())}</td>'
                   f'<td><a href="{e(o.get("source"))}">zdroj</a></td></tr>' for o in r["odds"])
    sub = '<div class="fig-sub">kurzy do predpovede nevstupujú, slúžia na porovnanie</div>' if model == "codex" else ""
    return f'{sub}<div class="tbl-scroll"><table><thead><tr><th>Kancelária</th><th class="num">Dátum</th><th>Kurzy</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>'


def adjustments_html(r):
    li = []
    for c in r["candidates"]:
        if c.get("adj") or c.get("adj_reason"):
            tag = f' ({c["adj"]:+.1f})'.replace(".", ",") if c.get("adj") else ""
            li.append(f'<li><strong>{e(c["name"])}{tag}.</strong> {e(c.get("adj_reason"))}</li>')
    for w in r["withdrawn"]:
        if w.get("transfer_to"):
            li.append(f'<li><strong>{e(w["name"])} → {e(w["transfer_to"])}.</strong> Odstúpil v prospech tohto kandidáta. '
                      'V prieskumoch mu pripisujeme polovicu podielu odstúpeného, zvyšok rozdeľujeme pomerne.</li>')
    if not li:
        return '<p class="muted">Žiadne úpravy.</p>'
    return "<ul>" + "".join(li) + "</ul>"


def race_page(r, model, status):
    srcs = "".join(f'<li><a href="{e(s)}">{e(s)}</a></li>' for s in r.get("sources") or [])
    wd = ""
    if r["withdrawn"]:
        names = ", ".join(w["name"] + (f' (v prospech: {w["transfer_to"]})' if w.get("transfer_to") else "") for w in r["withdrawn"])
        wd = f'<div class="note note-warn">Odstúpili (zostávajú na lístku, hlasy pre nich sa nerátajú): {e(names)}.</div>'
    voters = f'{r["voters"]:,}'.replace(",", " ")
    other = "codex-" if model == "claude" else ""
    other_name = "Codex" if model == "claude" else "Claude"
    if model == "claude":
        sub = "odhad = medián 20 000 simulácií · interval = 10. až 90. percentil · P(výhra) = podiel simulácií, v ktorých je kandidát prvý; zahŕňa kurzy"
        adj = (f'<figure><figcaption>Úpravy nad rámec modelu</figcaption><div class="fig-sub">číslo = posun log-skóre kandidáta; '
               f'+0,3 zvýši jeho relatívny podiel asi o 35 % pred normalizáciou</div>{adjustments_html(r)}</figure>')
    else:
        sub = "odhad = priemer 50 000 simulácií · interval = 10. až 90. percentil · P(výhra) = podiel simulácií, v ktorých je kandidát prvý"
        adj = ""
    body = f"""<section><div class="wrap">
<div class="sec-num">{e(OFFICE[r["office"]])} · {"Claude" if model == "claude" else "Codex"}</div><h2>{e(r["name"])}</h2>
<p class="muted">Zapísaní voliči: {voters}. Jedno kolo, vyhráva relatívna väčšina. <a href="{other}{r["id"]}.html">Predpoveď modelu {other_name}</a> · <a href="porovnanie.html#{r["id"]}">porovnanie</a></p>{wd}
<figure><figcaption>Predpoveď</figcaption><div class="fig-sub">{sub}</div>
{race_table(r, full=True, model=model)}</figure>
<div class="grid2"><figure><figcaption>Prieskumy</figcaption>{polls_html(r, model)}</figure>
<figure><figcaption>Stávkové kurzy</figcaption>{odds_html(r, model)}</figure></div>
{adj}
<figure><figcaption>Poznámky</figcaption><p>{e(r.get("notes") or "–")}</p></figure>
<h3>Výsledky predchádzajúcich volieb (ŠÚ SR)</h3><div class="grid2">{history_html(r)}</div>
<figure><figcaption>Zdroje</figcaption><ul class="text-small">{srcs}</ul></figure>
</div></section>"""
    return page(f'{r["name"]} · {"Claude" if model == "claude" else "Codex"} · Voľby 2026', body, model, "", status)


def overview(races, model):
    prefix = PREFIX[model]
    secs = []
    for i, (g, title) in enumerate(GROUPS, 1):
        cards = []
        for r in [r for r in races if r["group"] == g]:
            fav = max(r["candidates"], key=lambda c: c["p_win"])
            top = dict(r, candidates=r["candidates"][:5])
            more = len(r["candidates"]) - 5
            more_txt = f' · ďalší kandidáti: {more}' if more > 0 else ""
            cards.append(f'<div class="card"><h3><a href="{prefix}{r["id"]}.html">{e(r["name"])}</a></h3>'
                         f'<div class="fig-sub">favorit: {e(fav["name"])} ({prob(fav["p_win"])}){more_txt}</div>'
                         f'{race_table(top, model=model)}</div>')
        secs.append(f'<section id="{g}"><div class="wrap"><div class="sec-num">0{i} — {e(title)}</div><h2>{e(title)}</h2>'
                    f'<div class="race-grid">{"".join(cards)}</div></div></section>')
    return "".join(secs)


# ---------- Claude pages ----------

FEATURE_SK = {
    "inc": "obhajca (kandiduje úradujúci starosta/primátor)", "inc_x_size": "obhajca × (log10 počtu voličov − 4,5)",
    "prev_share": "podiel v minulých voľbách (0–1)", "prev_lost": "kandidoval minule a prehral",
    "neka": "nezávislý kandidát (NEKA)", "log_parties": "ln(1 + počet nominujúcich strán)",
    "gov": "nominovaný vládnou stranou 2022", "occ_mayor_noinc": "úradujúci starosta inej samosprávy",
    "local_official": "miestny funkcionár (vicestarosta, poslanec)", "low_status": "dôchodca alebo nezamestnaný",
}


def fill_model(src):
    fm = json.loads((ROOT / "data/model/fundamentals.json").read_text())
    nat = yaml.safe_load((ROOT / "data/inputs/national.yaml").read_text())
    reg = json.loads((ROOT / "data/model/regional.json").read_text())
    b, cv, bl = fm["beta"], fm["cv"], fm["baselines"]
    beta = "".join(f'<tr><td>{e(FEATURE_SK.get(k, k))}</td><td class="num">{num(v, 2)}</td></tr>' for k, v in b.items())
    calib = "".join(f'<tr><td class="num">{e(c["bin"])}</td><td class="num">{c["n"]}</td><td class="num">{num(100 * c["mean_p"], 0)} %</td>'
                    f'<td class="num">{num(100 * c["win_rate"], 0)} %</td></tr>' for c in cv["calibration"])
    swing = "".join(f'<tr><td>{e(k)}</td><td class="num">{num(v["y2022"])} %</td><td class="num">{num(v["y2026"])} %</td>'
                    f'<td class="num">{num(math.log(v["y2026"] / v["y2022"]), 2)}</td></tr>'
                    for k, v in nat["parties"].items() if v.get("y2022") and v.get("y2026"))
    rep = {
        "n_races": str(fm["n_races"]), "n_candidates": str(fm["n_candidates"]),
        "inc": num(b["inc"], 2), "inc_size": num(b["inc_x_size"], 2), "prev": num(b["prev_share"], 2), "neka": num(b["neka"], 2),
        "gamma": num(reg["gamma"], 2), "reg_loo": num(reg["loo_mae_pp"]), "reg_base": num(reg["mae_without_base_pp"]),
        "brier": num(cv["brier"], 3), "brier_inc": num(bl["incumbent_wins_else_uniform_brier"], 3),
        "brier_uni": num(bl["uniform_brier"], 3), "fav": f'{round(100 * cv["favourite_hit_rate"])} %',
        "mae": num(cv["share_mae_pp"]), "sigma": num(fm["sigma"], 2), "coverage": f'{round(100 * cv["coverage_80"])} %',
        "beta_table": f'<div class="tbl-scroll"><table><thead><tr><th>Rys</th><th class="num">β</th></tr></thead><tbody>{beta}</tbody></table></div>',
        "calib_table": ('<div class="tbl-scroll"><table><thead><tr><th class="num">Pásmo P(výhra)</th><th class="num">Kandidátov</th>'
                        f'<th class="num">Priemerná P</th><th class="num">Skutočne vyhrali</th></tr></thead><tbody>{calib}</tbody></table></div>'),
        "swing_table": ('<div class="tbl-scroll"><table><thead><tr><th>Strana</th><th class="num">2022</th><th class="num">2026</th>'
                        f'<th class="num">ln(pomer)</th></tr></thead><tbody>{swing}</tbody></table></div>'),
    }
    for k, v in rep.items():
        src = src.replace("{{" + k + "}}", v)
    return src


SERIES_SK = {"final": "Finálna", "bez_trhu": "Bez trhu", "fundamenty": "Fundamenty", "trh": "Trh (len voľby s kurzami)",
             "obhajca": "Pravidlo: vyhrá obhajca", "rovnomerne": "Rovnomerne"}


def score_html(s):
    rows = "".join(f'<tr><td>{SERIES_SK.get(k, k)}</td><td class="num">{v["n"]}</td><td class="num">{num(v["brier"], 3)}</td>'
                   f'<td class="num">{num(v["log_score"], 3)}</td><td class="num">{v["favourites_hit"]}</td></tr>' for k, v in s["series"].items())
    races = "".join(f'<tr><td><a href="{r["id"]}.html">{e(r["id"])}</a></td><td>{e(r["winner"])}</td>'
                    f'<td class="num">{prob(r.get("p_winner_final"))}</td><td class="num">{prob(r.get("p_winner_fundamenty"))}</td>'
                    f'<td class="num">{prob(r.get("p_winner_trh"))}</td></tr>' for r in s["races"])
    return (f'<h3>Výsledky ({e(s["snapshot"])})</h3><div class="tbl-scroll"><table><thead><tr><th>Séria</th><th class="num">Volieb</th>'
            f'<th class="num">Brier ↓</th><th class="num">Log skóre ↑</th><th class="num">Trafení favoriti</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p>Priemerná chyba podielu: {num(s["share_mae_pp"])} b. (fundamenty {num(s["fund_share_mae_pp"])} b.). '
            f'Pokrytie 80 % intervalov: {round(100 * s["coverage_80"])} %.</p>'
            f'<div class="tbl-scroll"><table><thead><tr><th>Voľba</th><th>Víťaz</th><th class="num">P finálna</th><th class="num">P fundamenty</th>'
            f'<th class="num">P trh</th></tr></thead><tbody>{races}</tbody></table></div>')


def archive_html():
    rows = []
    for p in sorted((ROOT / "data/snapshots").glob("*.json"), reverse=True):
        if p.name.startswith("test"):
            continue
        d = json.loads(p.read_text())
        rows.append(f'<tr><td><a href="data/snapshots/{p.name}"><code>{e(p.name)}</code></a></td><td>{e(d.get("label"))}</td>'
                    f'<td class="num">{stamp(d.get("generated", ""))}</td></tr>')
    lk = '<p>Zámok: <a href="data/lock.json"><code>data/lock.json</code></a></p>' if (ROOT / "data/lock.json").exists() else ""
    return ('<div class="sec-num">Archív</div><h2>Snapshoty</h2><p>Každá verzia predpovede je samostatný JSON súbor. '
            'Staršie verzie neprepisujeme; celá história je aj v gite.</p>' + lk +
            f'<div class="tbl-scroll"><table><thead><tr><th>Súbor</th><th>Séria</th><th class="num">Vytvorené</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def content_page(name, title, active, status):
    src = archive_html() if name == "archiv" else (ROOT / "content" / f"{name}.html").read_text()
    if name == "model":
        src = fill_model(src)
    if name == "skore" and (ROOT / "data/score.json").exists():
        src += score_html(json.loads((ROOT / "data/score.json").read_text()))
    return page(f"{title} · Claude · Voľby 2026", f'<section><div class="wrap">{src}</div></section>', "claude", active, status)


def claude_index(data, status, lock):
    if lock:
        note = (f'<div class="note note-ok"><strong>Predpoveď je zamknutá</strong> ({stamp(lock["locked_at"])}). Commit <code>{e(lock["commit"])}</code>, '
                f'tag <code>{e(lock["tag"])}</code>. Prípadné opravy zverejníme ako novú verziu s vysvetlením.</div>')
    else:
        note = ('<div class="note note-warn"><strong>Pracovná verzia.</strong> Finálnu predpoveď zamkneme najneskôr v stredu 21. 10. 2026 o 23:59. '
                'Od štvrtka platí zákaz zverejňovania prieskumov.</div>')
    intro = f"""<section><div class="wrap"><div class="sec-num">Sobota 24. 10. 2026 · Claude</div>
<h2>Predpoveď 33 volieb</h2>
<p>8 predsedov samosprávnych krajov, 8 primátorov krajských miest a 17 starostov mestských častí Bratislavy. Pri každom kandidátovi uvádzame odhad podielu platných hlasov, 80 % interval a pravdepodobnosť výhry. Všetky voľby majú jedno kolo a vyhráva kandidát s najviac hlasmi.</p>
{note}
<p class="text-small muted">Vstupy: model nafitovaný na 2 914 komunálnych voľbách 2018 → 2022 (obhajca, minulý výsledok, nominácia), zmena podpory strán od roku 2022, prieskumy a stávkové kurzy. Výstup je z 20 000 simulácií. Podrobnosti sú na stránke <a href="model.html">Model</a>.</p>
</div></section>"""
    return page("Claude · Voľby 2026", intro + overview(data["races"], "claude"), "claude", "index.html", status)


# ---------- Codex pages ----------

def codex_index(races, meta, status):
    intro = f"""<section><div class="wrap"><div class="sec-num">Sobota 24. 10. 2026 · Codex</div>
<h2>Predpoveď 33 volieb</h2>
<p>Predpoveď modelu Codex pre tých istých 33 volieb. Codex mal vlastný výskum aj vlastnú metodiku a predpoveď zamkol {stamp(meta["locked_at"])} (vstupy uzavreté {stamp(meta["cutoff"])}). Čísla sú prevzaté zo zamknutého súboru <a href="{e(meta["source"])}">forecast.json</a>; jeho SHA-256 sme overili voči <code>LOCK.json</code> v repozitári Codexu.</p>
<p class="text-small muted">Pôvodný web Codexu: <a href="https://mareksulik.github.io/volebny-model-codex/">mareksulik.github.io/volebny-model-codex</a>. Metodika je na stránke <a href="codex-model.html">Model</a>.</p>
</div></section>"""
    return page("Codex · Voľby 2026", intro + overview(races, "codex"), "codex", "codex.html", status)


def codex_model(meta, status):
    bt = meta.get("backtest") or {}
    rows = "".join(f'<tr><td><strong>{e(a)}</strong></td><td>{e(x)}</td></tr>' for a, _, x in METHODS)
    test = ""
    if bt:
        test = (f'<h3>Spätný test (komunálne voľby 2022, odložená množina)</h3><div class="tbl-scroll"><table><tbody>'
                f'<tr><td>Volieb / kandidátov</td><td class="num">{bt["races"]} / {bt["candidates"]}</td></tr>'
                f'<tr><td>Priemerná chyba podielu</td><td class="num">{num(bt["mae_pp"])} b.</td></tr>'
                f'<tr><td>Trafený víťaz</td><td class="num">{round(100 * bt["winner_accuracy"])} %</td></tr>'
                f'<tr><td>Brier</td><td class="num">{num(bt["brier"], 3)}</td></tr>'
                f'<tr><td>Pokrytie 80 % intervalov</td><td class="num">{round(100 * bt["coverage80"])} %</td></tr>'
                f'<tr><td>Priemerná šírka intervalu</td><td class="num">{num(bt["mean_interval_width_pp"])} b.</td></tr>'
                '</tbody></table></div>')
    body = f"""<section><div class="wrap"><div class="sec-num">Model · Codex</div><h2>Ako počíta Codex</h2>
<p>Zhrnutie podľa <a href="{CODEX_REPO}/blob/main/METHODOLOGY.md">METHODOLOGY.md</a> v repozitári Codexu. Počet simulácií na voľbu: {e(meta.get("draws"))}.</p>
<div class="tbl-scroll"><table><thead><tr><th>Krok</th><th>Postup</th></tr></thead><tbody>{rows}</tbody></table></div>
{test}</div></section>"""
    return page("Model · Codex · Voľby 2026", body, "codex", "codex-model.html", status)


# ---------- comparison ----------

METHODS = [
    ("Fundamenty", "Podmienený logit na 2 914 voľbách starostov 2018 → 2022 (obce s aspoň 2 000 voličmi). Rysy: obhajca a jeho interakcia s veľkosťou obce, minulý podiel, nezávislý kandidát, počet strán, povolanie.",
     "Softmax na komunálnych voľbách 2018 → 2022 s aspoň 1 000 platnými hlasmi. Rysy: minulý podiel, minulé víťazstvo, počet strán, funkcia z registrácie, nezávislý kandidát. Obce sú rozdelené na tréning, kalibráciu a test."),
    ("Kraje", "Fundamenty z obcí plus podpora nominujúcich strán s koeficientom 0,29 nafitovaným na 8 krajských voľbách 2022.",
     "Fundamenty z obcí. Kraje 2017 → 2022 slúžia len ako test."),
    ("Neistota", "Normálny šum na log-škále (σ = 0,95) nastavený na 80 % pokrytie na odložených obciach. Navyše jeden spoločný šok pre kandidátov vlády a opozície vo všetkých 33 voľbách.",
     "Dirichletovo rozdelenie s koncentráciou nastavenou na 80 % pokrytie na kalibračných obciach. Voľby sa simulujú nezávisle."),
    ("Prieskumy", "Vážený priemer: polčas 30 dní, váha √(n/600), prieskumy objednané kandidátom polovičnou váhou. S fundamentmi sa kombinuje podľa odhadnutej presnosti.",
     "Bayesovská aktualizácia s váhou min(200, n/2) × 2^(−vek/30) × kvalita, koncentrácia najviac 80. Prieskumy bez úplného zoznamu kandidátov vyraďuje."),
    ("Odstúpenia", "Polovica prieskumného podielu odstúpeného ide kandidátovi, ktorého podporil; zvyšok sa rozdelí pomerne.",
     "Podiel odstúpených sa rozdelí podľa fundamentov; podporený kandidát nedostáva viac."),
    ("Kurzy", "Kurzy bez marže menia pravdepodobnosť výhry (váha 0,5 v log-odds), podiely nie.", "Do predpovede nevstupujú, slúžia len na porovnanie."),
    ("Bodový odhad", "Medián 20 000 simulácií.", "Priemer 50 000 simulácií."),
    ("Ručné úpravy", "Áno, zapísané v overrides.yaml, každá s dôvodom.", "Nie."),
]


def cmp_cell(x):
    if not x:
        return '<td class="num gs">–</td><td class="num">–</td><td class="num">–</td>'
    return (f'<td class="num gs">{pct(x["share"])}</td><td class="num">{x["lo80"]:.0f}–{x["hi80"]:.0f} %</td>'
            f'<td class="num">{prob_chip(x["p_win"])}</td>')


def comparison_page(status):
    c = json.loads((ROOT / "data/comparison.json").read_text())
    cx = c["codex"]
    n, same = c["n_races"], c["same_favourite"]
    stats = ('<div class="card stats-row">'
             f'<div class="stat"><div class="label">Rovnaký favorit</div><div class="value">{same}/{n}</div><div class="delta">volieb</div></div>'
             f'<div class="stat"><div class="label">Rozdiel podielu</div><div class="value">{num(c["mean_abs_share_diff_pp"])} b.</div><div class="delta">priemer cez kandidátov</div></div>'
             f'<div class="stat"><div class="label">Rozdiel P(výhra)</div><div class="value">{num(100 * c["mean_abs_pwin_diff"])} b.</div><div class="delta">priemer cez kandidátov</div></div>'
             '</div>')
    rows = []
    for r in sorted(c["races"], key=lambda r: (r["same_favourite"], -r["max_dp"]))[:12]:
        cc = {x["name"]: x for x in r["candidates"]}
        fc, fx = cc[r["fav_claude"]], cc[r["fav_codex"]]
        chip = "" if r["same_favourite"] else ' <span class="chip chip-warn">iný favorit</span>'
        rows.append(f'<tr><td><a href="#{r["id"]}">{e(r["name"])}</a>{chip}</td><td>{e(r["fav_claude"])}</td><td class="num">{prob(fc["claude"]["p_win"])}</td>'
                    f'<td class="gs">{e(r["fav_codex"])}</td><td class="num">{prob(fx["codex"]["p_win"])}</td>'
                    f'<td class="num gs">{round(100 * r["max_dp"])} b.</td></tr>')
    gaps = [f'{", ".join(r["unmatched_codex"])} ({r["name"]})' for r in c["races"] if r["unmatched_codex"]]
    lk = json.loads((ROOT / "data/lock.json").read_text()) if (ROOT / "data/lock.json").exists() else None
    claude_lock = f'Claude zamkol predpoveď {stamp(lk["locked_at"])}' if lk else 'Claude predpoveď ešte nezamkol'
    inputs = (f'Codex uzavrel vstupy {stamp(cx["cutoff"])}. {claude_lock}; zahŕňa aj prieskum AKO pre Bratislavu zverejnený 20. 10. večer. '
              + (f'Codex počíta ako aktívnych kandidátov, ktorí podľa našich zdrojov odstúpili: {e("; ".join(gaps))}.' if gaps else ""))
    cards = []
    for g, _ in GROUPS:
        for r in [r for r in c["races"] if r["group"] == g]:
            trs = "".join(f'<tr><td class="nm">{e(x["name"])}{" <span class=\"chip chip-neutral\">obhajca</span>" if x["inc"] else ""}</td>'
                          f'{cmp_cell(x["claude"])}{cmp_cell(x["codex"])}</tr>' for x in r["candidates"])
            badge = '' if r["same_favourite"] else ' <span class="chip chip-warn">iný favorit</span>'
            cards.append(f'<figure id="{r["id"]}"><figcaption>{e(r["name"])}{badge}</figcaption>'
                         f'<div class="fig-sub"><a href="{r["id"]}.html">Claude</a> · <a href="codex-{r["id"]}.html">Codex</a></div>'
                         f'<div class="tbl-scroll"><table class="grouped"><thead><tr class="grp"><th></th><th colspan="3" class="gs">CLAUDE</th><th colspan="3" class="gs">CODEX</th></tr>'
                         f'<tr><th>Kandidát</th><th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th>'
                         f'<th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th></tr></thead><tbody>{trs}</tbody></table></div></figure>')
    meth = "".join(f'<tr><td><strong>{e(a)}</strong></td><td class="gs">{e(b)}</td><td class="gs">{e(x)}</td></tr>' for a, b, x in METHODS)
    scores = ""
    if c.get("scores"):
        sr = "".join(f'<tr><td>{k.capitalize()}</td><td class="num">{v["n"]}</td><td class="num">{num(v["brier"], 3)}</td><td class="num">{num(v["log_score"], 3)}</td>'
                     f'<td class="num">{v["favourites_hit"]}</td><td class="num">{num(v["share_mae_pp"])} b.</td><td class="num">{round(100 * v["coverage_80"])} %</td></tr>'
                     for k, v in c["scores"].items() if v)
        scores = (f'<section id="skore"><div class="wrap"><div class="sec-num">04 — Skóre</div><h2>Presnosť po voľbách</h2>'
                  f'<div class="tbl-scroll"><table><thead><tr><th>Model</th><th class="num">Volieb</th><th class="num">Brier ↓</th><th class="num">Log skóre ↑</th>'
                  f'<th class="num">Trafení favoriti</th><th class="num">Chyba podielu</th><th class="num">Pokrytie 80 %</th></tr></thead><tbody>{sr}</tbody></table></div></div></section>')
    body = f"""<section id="suhrn"><div class="wrap"><div class="sec-num">01 — Súhrn</div>
<h2>Claude a Codex</h2>
<p>Dva samostatné modely tých istých 33 volieb, každý s vlastným výskumom a metodikou. Claude: snapshot <code>{e(c["claude_snapshot"])}</code>. Codex: zamknutý {stamp(cx["locked_at"])}.</p>
{stats}
<figure><figcaption>Kde sa modely líšia najviac</figcaption><div class="fig-sub">max |ΔP| = najväčší rozdiel v pravdepodobnosti výhry jedného kandidáta</div>
<div class="tbl-scroll"><table class="grouped"><thead><tr class="grp"><th></th><th colspan="2">CLAUDE</th><th colspan="2" class="gs">CODEX</th><th class="gs"></th></tr>
<tr><th>Voľba</th><th>Favorit</th><th class="num">P</th><th class="gs">Favorit</th><th class="num">P</th><th class="num gs">max |ΔP|</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p class="text-small muted">{inputs}</p></figure>
</div></section>
<section id="vsetky"><div class="wrap"><div class="sec-num">02 — Všetky voľby</div><h2>Kandidáti</h2>
<div class="race-grid">{"".join(cards)}</div></div></section>
<section id="metodiky"><div class="wrap"><div class="sec-num">03 — Metodiky</div><h2>Rozdiely v metodike</h2>
<div class="tbl-scroll"><table><thead><tr><th>Krok</th><th class="gs">Claude</th><th class="gs">Codex</th></tr></thead><tbody>{meth}</tbody></table></div>
<p class="text-small">Po voľbách obe predpovede vyhodnotíme rovnakými metrikami.</p>
</div></section>{scores}"""
    return page("Porovnanie · Voľby 2026", body, "porovnanie", "", status)


# ---------- build ----------

def main():
    import codex_view
    data = json.loads((ROOT / "data/latest.json").read_text())
    DOCS.mkdir(exist_ok=True)
    for f in ["ds.css", "ds.js"]:
        shutil.copy(MARS / f, DOCS / f)
    shutil.copytree(MARS / "fonts", DOCS / "fonts", dirs_exist_ok=True)
    shutil.copytree(ROOT / "data/snapshots", DOCS / "data/snapshots", dirs_exist_ok=True, ignore=shutil.ignore_patterns("test-*"))
    for f in ["lock.json", "latest.json", "comparison.json"]:
        if (ROOT / "data" / f).exists():
            shutil.copy(ROOT / "data" / f, DOCS / "data" / f)
    shutil.copy(ROOT / "data/model/fundamentals.json", DOCS / "data/fundamentals.json")
    shutil.copytree(ROOT / "data/codex", DOCS / "data/codex", dirs_exist_ok=True)
    lock = json.loads((ROOT / "data/lock.json").read_text()) if (ROOT / "data/lock.json").exists() else None

    st_claude = (f'<span>Claude</span><span>snapshot {e(data["label"])}</span><span>stav k {stamp(data["generated"])}</span>'
                 + ('<span>zamknuté</span>' if lock else '<span>pracovná verzia</span>'))
    cm = codex_view.meta()
    st_codex = f'<span>Codex</span><span>zamknuté {stamp(cm["locked_at"])}</span><span>uzáver vstupov {stamp(cm["cutoff"])}</span>'
    st_both = f'{st_claude}<span>·</span>{st_codex}'

    (DOCS / "index.html").write_text(claude_index(data, st_claude, lock))
    for r in data["races"]:
        (DOCS / f'{r["id"]}.html').write_text(race_page(r, "claude", st_claude))
    for name, title in [("model", "Model"), ("pravidla", "Pravidlá"), ("skore", "Skóre"), ("archiv", "Archív")]:
        (DOCS / f"{name}.html").write_text(content_page(name, title, f"{name}.html", st_claude))

    codex_races = codex_view.races(data)
    (DOCS / "codex.html").write_text(codex_index(codex_races, cm, st_codex))
    (DOCS / "codex-model.html").write_text(codex_model(cm, st_codex))
    for r in codex_races:
        (DOCS / f'codex-{r["id"]}.html').write_text(race_page(r, "codex", st_codex))

    (DOCS / "porovnanie.html").write_text(comparison_page(st_both))
    (DOCS / ".nojekyll").write_text("")
    print("site built:", len(data["races"]), "Claude races,", len(codex_races), "Codex races")


if __name__ == "__main__":
    main()
