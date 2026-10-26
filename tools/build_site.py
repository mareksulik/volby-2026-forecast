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
NAV = [("skore.html", "Výsledky"), ("volby.html", "Voľby"), ("model.html", "Modely"), ("pravidla.html", "Pravidlá"),
       ("archiv.html", "Archív")]
NAV_HIGHLIGHT = "skore.html"
# old URL -> new URL; old pages stay as redirects so shared links keep working
REDIRECTS = {"index.html": "skore.html", "codex.html": "volby.html", "porovnanie.html": "volby.html",
             "codex-model.html": "model.html#codex"}

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


def page(title, body, active, status):
    def link(h, t):
        cls = " ".join(c for c, on in (("hl", h == NAV_HIGHLIGHT), ("active", h == active)) if on)
        attrs = (f' class="{cls}"' if cls else "") + (' aria-current="page"' if h == active else "")
        return f'<a href="{h}"{attrs}>{t}</a>'
    nav = "".join(link(h, t) for h, t in NAV)
    repo = REPO
    return f"""<!DOCTYPE html>
<html lang="sk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="ds.css"><script src="ds.js"></script>
<style>
.iv{{vertical-align:middle}} .race-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:16px}}
.race-grid>*,.grid2>*{{min-width:0}} figure ul a,p code{{overflow-wrap:anywhere}} .race-grid .card h3{{margin:0 0 4px}} .race-grid table td,.race-grid table th{{padding:6px 8px}}
td.nm{{min-width:200px;max-width:280px}} td.ivc{{min-width:140px}} .muted{{color:var(--mu-gray-900)}}
.stats-row{{display:flex;flex-wrap:wrap;gap:16px 32px}} .stats-row .stat{{flex:1 1 160px}}
nav a.hl{{color:var(--mu-blue-700);font-weight:600}} nav a.hl:hover{{color:var(--mu-blue-900)}} nav a.hl.active{{border-bottom-color:var(--mu-blue-700)}}
.summary{{border-color:var(--mu-blue-300)}} .summary ul{{margin:0;padding-left:20px;max-width:none}} .summary li{{margin:8px 0}}
footer.site{{flex-wrap:wrap;gap:8px 24px}} footer.site .status{{display:flex;flex-wrap:wrap;gap:4px 16px;text-transform:uppercase;letter-spacing:.06em;font-size:12px}}
@media (max-width:600px){{.race-grid{{grid-template-columns:1fr}} td.nm{{min-width:150px}}}}
</style></head><body>
<header class="topbar"><div class="wrap"><div class="brand">
<svg viewBox="0 0 110 22" height="22" aria-hidden="true"><text x="0" y="17" font-family="Geist, sans-serif" font-weight="600" font-size="18" fill="currentColor">Voľby 2026</text></svg>
<span class="slash"></span><span class="app">Predpoveď samosprávnych volieb</span><h1 class="sr-only">{e(title)}</h1></div></div></header>
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


def result_table(cr, res):
    """Official result next to both forecasts; cr = comparison.json race, res = {name: share} (empty if unknown)."""
    names = [c["name"] for c in cr["candidates"]] + [n for n in res if n not in {c["name"] for c in cr["candidates"]}]
    names.sort(key=lambda n: -res.get(n, -1))
    cand = {c["name"]: c for c in cr["candidates"]}
    winner = max(res, key=res.get) if res else None
    rows = []
    for n in names:
        c = cand.get(n, {})
        elected = "zvolená" if n.split()[-1].endswith("á") else "zvolený"
        chips = (f' <span class="chip chip-ok">{elected}</span>' if n == winner else "") + \
                (' <span class="chip chip-neutral">obhajca</span>' if c.get("inc") else "")
        actual = pct(res[n]) if n in res else ('<span class="muted">vzdal sa</span>' if res else "–")
        rows.append(f'<tr><td class="nm">{e(n)}{chips}</td><td class="num"><strong>{actual}</strong></td>'
                    f'{cmp_cell(c.get("claude"))}{cmp_cell(c.get("codex"))}</tr>')
    return ('<div class="tbl-scroll"><table class="grouped"><thead><tr class="grp"><th></th><th></th>'
            '<th colspan="3" class="gs">CLAUDE</th><th colspan="3" class="gs">CODEX</th></tr>'
            '<tr><th>Kandidát</th><th class="num">Výsledok</th><th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th>'
            f'<th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def race_page(r, xr, cr, res, status):
    """One page per race: result, Claude (r) and Codex (xr) forecasts, inputs."""
    sources = list(dict.fromkeys((r.get("sources") or []) + (xr.get("sources") or [])))
    srcs = "".join(f'<li><a href="{e(s)}">{e(s)}</a></li>' for s in sources)
    wd = ""
    if r["withdrawn"]:
        names = ", ".join(w["name"] + (f' (v prospech: {w["transfer_to"]})' if w.get("transfer_to") else "") for w in r["withdrawn"])
        wd = f'<div class="note note-warn">Odstúpili (zostávajú na lístku, hlasy pre nich sa nerátajú): {e(names)}.</div>'
    voters = f'{r["voters"]:,}'.replace(",", " ")
    result_src = ("Výsledok: ŠÚ SR, podiel platných hlasov bez kandidátov, ktorí sa vzdali kandidatúry · " if res else "")
    body = f"""<section><div class="wrap">
<div class="sec-num">{e(OFFICE[r["office"]])}</div><h2>{e(r["name"])}</h2>
<p class="muted">Zapísaní voliči: {voters}. Jedno kolo, vyhráva relatívna väčšina.</p>{wd}
<figure><figcaption>Výsledok a predpovede</figcaption>
<div class="fig-sub">{result_src}odhad = bodový odhad podielu (Claude medián 20 000 simulácií, Codex priemer 50 000) · 80 % = 10. až 90. percentil · P(výhra) = podiel simulácií, v ktorých je kandidát prvý</div>
{result_table(cr, res)}</figure>
<details><summary>Podrobnosti predpovede Claude</summary><div class="fig-sub">P(výhra) zahŕňa kurzy · fundamenty = odhad bez prieskumov a úprav</div>{race_table(r, full=True, model="claude")}
<figure><figcaption>Úpravy nad rámec modelu</figcaption><div class="fig-sub">číslo = posun log-skóre kandidáta; +0,3 zvýši jeho relatívny podiel asi o 35 % pred normalizáciou</div>{adjustments_html(r)}</figure></details>
<details><summary>Podrobnosti predpovede Codex</summary>{race_table(xr, full=True, model="codex")}
<figure><figcaption>Prieskumy v modeli Codex</figcaption>{polls_html(xr, "codex")}</figure>
<figure><figcaption>Poznámka Codexu</figcaption><p>{e(xr.get("notes") or "–")}</p></figure></details>
<div class="grid2"><figure><figcaption>Prieskumy</figcaption>{polls_html(r, "claude")}</figure>
<figure><figcaption>Stávkové kurzy</figcaption><div class="fig-sub">Claude ich použil pri pravdepodobnosti výhry, Codex nie</div>{odds_html(r, "claude")}</figure></div>
<figure><figcaption>Poznámky</figcaption><p>{e(r.get("notes") or "–")}</p></figure>
<h3>Výsledky predchádzajúcich volieb (ŠÚ SR)</h3><div class="grid2">{history_html(r)}</div>
<figure><figcaption>Zdroje</figcaption><ul class="text-small">{srcs}</ul></figure>
</div></section>"""
    return page(f'{r["name"]} · Voľby 2026', body, "volby.html", status)


# ---------- content pages ----------

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


def signed(x):
    return ("+" if x > 0 else "−" if x < 0 else "±") + num(abs(x))


def table(head, rows, cls=""):
    return f'<div class="tbl-scroll"><table{cls}><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def fill_skore(src):
    ev = json.loads((ROOT / "data/evaluation.json").read_text())
    c, x = ev["summary"]["claude"], ev["summary"]["codex"]
    stat = lambda label, value, delta: f'<div class="stat"><div class="label">{label}</div><div class="value">{value}</div><div class="delta">{delta}</div></div>'
    stats = ('<div class="card stats-row">'
             + stat("Trafení víťazi", f'{c["winners_hit"]}/{c["n"]} · {x["winners_hit"]}/{x["n"]}', "Claude · Codex")
             + stat("Odchýlka podielu", f'{num(c["share_mae_pp"])} · {num(x["share_mae_pp"])} b.', "Claude · Codex")
             + stat("Brierovo skóre", f'{num(c["brier"], 3)} · {num(x["brier"], 3)}', "Claude · Codex")
             + '</div>')
    pos = [f'<tr><td>{p}. miesto</td><td class="num">{num(c["mae_by_pos"][p])} b.</td><td class="num">{num(x["mae_by_pos"][p])} b.</td></tr>'
           for p in ("1", "2", "3")]
    pos.append(f'<tr><td>všetci kandidáti</td><td class="num">{num(c["share_mae_pp"])} b.</td><td class="num">{num(x["share_mae_pp"])} b.</td></tr>')
    hits = lambda m: " · ".join(f'{m[f"hit_{g}"][0]}/{m[f"hit_{g}"][1]}' for g in ("kraj", "mesto", "mc"))
    metrics = [("Trafení víťazi", f'{c["winners_hit"]}/{c["n"]}', f'{x["winners_hit"]}/{x["n"]}'),
               ("kraje · mestá · mestské časti", hits(c), hits(x)),
               ("Odchýlka podielu, všetci kandidáti", f'{num(c["share_mae_pp"])} b.', f'{num(x["share_mae_pp"])} b.'),
               ("Odchýlka podielu víťaza", f'{num(c["mae_by_pos"]["1"])} b.', f'{num(x["mae_by_pos"]["1"])} b.'),
               ("Brierovo skóre", num(c["brier"], 3), num(x["brier"], 3)),
               ("Log skóre", num(c["log_score"], 3), num(x["log_score"], 3)),
               ("Výsledok v 80 % intervale", f'{num(100 * c["coverage_80"])} %', f'{num(100 * x["coverage_80"])} %')]
    races = []
    for r in ev["races"]:
        cells = ""
        for i, t in enumerate(r["top"][:2]):
            if i == 1:
                cells += f'<td class="num gs">{prob(r["claude"]["p_winner"])}</td><td class="num">{prob(r["codex"]["p_winner"])}</td>'
            miss = lambda m: ' <span class="chip chip-warn">netrafil</span>' if t["pos"] == 1 and not r[m]["hit"] else ""
            cells += (f'<td class="gs">{e(t["name"])}</td><td class="num">{num(t["actual"])} %</td>'
                      f'<td class="num">{signed(t["claude"]["err"])}{miss("claude")}</td><td class="num">{signed(t["codex"]["err"])}{miss("codex")}</td>')
        races.append(f'<tr><td><a href="{r["id"]}.html">{e(r["name"].replace(" samosprávny kraj", " kraj"))}</a></td>{cells}</tr>')
    sub = '<th class="gs">Kandidát</th><th class="num">Výsledok</th><th class="num">Claude</th><th class="num">Codex</th>'
    rep = {
        "stats": stats, "bias_claude": num(abs(c["winner_bias"])), "bias_codex": num(abs(x["winner_bias"])),
        "pos_table": table('<tr><th>Poradie kandidáta</th><th class="num">Claude</th><th class="num">Codex</th></tr>', pos),
        "model_table": table('<tr><th>Metrika</th><th class="num">Claude</th><th class="num">Codex</th></tr>',
                             [f'<tr><td>{a}</td><td class="num">{b}</td><td class="num">{d}</td></tr>' for a, b, d in metrics]),
        "race_table": table(f'<tr class="grp"><th></th><th colspan="4" class="gs">VÍŤAZ</th><th colspan="2" class="gs">P(VÝHRA) VÍŤAZA</th>'
                            f'<th colspan="4" class="gs">2. MIESTO</th></tr>'
                            f'<tr><th>Voľba</th>{sub}<th class="num gs">Claude</th><th class="num">Codex</th>{sub}</tr>', races, ' class="grouped"'),
    }
    for k, v in rep.items():
        src = src.replace("{{" + k + "}}", v)
    return src


def archive_html(cm):
    rows = []
    for p in sorted((ROOT / "data/snapshots").glob("*.json"), reverse=True):
        if p.name.startswith("test"):
            continue
        d = json.loads(p.read_text())
        rows.append(f'<tr><td><a href="data/snapshots/{p.name}"><code>{e(p.name)}</code></a></td><td>{e(d.get("label"))}</td>'
                    f'<td class="num">{stamp(d.get("generated", ""))}</td></tr>')
    lk = '<p>Zámok: <a href="data/lock.json"><code>data/lock.json</code></a></p>' if (ROOT / "data/lock.json").exists() else ""
    codex = (f'<h3>Codex</h3><p>Codex zamkol predpoveď {stamp(cm["locked_at"])} (vstupy uzavreté {stamp(cm["cutoff"])}). '
             f'Zamknutý súbor <a href="{e(cm["source"])}">forecast.json</a> má SHA-256 <code>{e(cm["sha256"])}</code>; '
             'overili sme ho voči <code>LOCK.json</code> v repozitári Codexu a jeho kópia je v <a href="data/codex/forecast.json"><code>data/codex/</code></a>.</p>')
    return ('<div class="sec-num">Archív</div><h2>Snapshoty</h2><h3>Claude</h3><p>Každá verzia predpovede je samostatný JSON súbor. '
            'Staršie verzie neprepisujeme; celá história je aj v gite.</p>' + lk +
            f'<div class="tbl-scroll"><table><thead><tr><th>Súbor</th><th>Séria</th><th class="num">Vytvorené</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            + codex)


def content_page(name, title, status, cm):
    src = archive_html(cm) if name == "archiv" else (ROOT / "content" / f"{name}.html").read_text()
    if name == "skore":
        src = fill_skore(src)
    return page(f"{title} · Voľby 2026", f'<section><div class="wrap">{src}</div></section>', f"{name}.html", status)


def volby_page(data, comp, results, lock, cm, status):
    races = {r["id"]: r for r in comp["races"]}
    lock_txt = (f'Claude zamkol predpoveď {stamp(lock["locked_at"])} (commit <code>{e(lock["commit"])}</code>, tag <code>{e(lock["tag"])}</code>). '
                if lock else "")
    intro = f"""<div class="sec-num">Voľby</div><h2>33 volieb 24. 10. 2026</h2>
<p>8 predsedov samosprávnych krajov, 8 primátorov krajských miest a 17 starostov mestských častí Bratislavy. Všetky voľby majú jedno kolo a vyhráva kandidát s najviac hlasmi. Pri každej voľbe je víťaz a favorit oboch modelov; na stránke voľby sú výsledky všetkých kandidátov vedľa predpovedí Claude a Codex.</p>
<p class="text-small muted">{lock_txt}Codex zamkol predpoveď {stamp(cm["locked_at"])}. Oba modely mali rovnakého favorita v {comp["same_favourite"]} z {comp["n_races"]} volieb. Ako modely počítajú, je na stránke <a href="model.html">Modely</a>.</p>"""
    secs = []
    for g, title in GROUPS:
        rows = []
        for r in [r for r in data["races"] if r["group"] == g]:
            cr, res = races[r["id"]], results.get(r["id"], {})
            winner = max(res, key=res.get) if res else None
            result = ("jediný kandidát" if len(res) == 1 else pct(res[winner])) if winner else "–"
            cells = ""
            for m in ("claude", "codex"):
                fav = cr[f"fav_{m}"]
                p = next(c[m]["p_win"] for c in cr["candidates"] if c["name"] == fav)
                miss = ' <span class="chip chip-warn">netrafil</span>' if winner and len(res) > 1 and fav != winner else ""
                cells += f'<td class="gs">{e(fav)}{miss}</td><td class="num">{prob(p)}</td>'
            rows.append(f'<tr id="{r["id"]}"><td><a href="{r["id"]}.html">{e(r["name"])}</a></td><td>{e(winner or "–")}</td>'
                        f'<td class="num">{result}</td>{cells}</tr>')
        secs.append(f'<h3 id="{g}">{e(title)}</h3><div class="tbl-scroll"><table class="grouped"><thead>'
                    '<tr class="grp"><th></th><th></th><th></th><th colspan="2" class="gs">FAVORIT CLAUDE</th><th colspan="2" class="gs">FAVORIT CODEX</th></tr>'
                    '<tr><th>Voľba</th><th>Víťaz</th><th class="num">Výsledok</th><th class="gs">Kandidát</th><th class="num">P(výhra)</th>'
                    f'<th class="gs">Kandidát</th><th class="num">P(výhra)</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    body = f'<section><div class="wrap">{intro}{"".join(secs)}</div></section>'
    return page("Voľby · Voľby 2026", body, "volby.html", status)


def models_page(meta, status):
    meth = "".join(f'<tr><td><strong>{e(a)}</strong></td><td class="gs">{e(b)}</td><td class="gs">{e(x)}</td></tr>' for a, b, x in METHODS)
    bt = meta.get("backtest") or {}
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
    body = f"""<section><div class="wrap"><div class="sec-num">Modely</div><h2>Ako počítajú Claude a Codex</h2>
<p>Dva samostatné modely tých istých 33 volieb, každý s vlastným výskumom a metodikou. Tabuľka ukazuje, v čom sa líšia; pod ňou je podrobný postup každého modelu.</p>
<div class="tbl-scroll"><table><thead><tr><th>Krok</th><th class="gs">Claude</th><th class="gs">Codex</th></tr></thead><tbody>{meth}</tbody></table></div>
</div></section>
<section id="claude"><div class="wrap">{fill_model((ROOT / "content/model.html").read_text())}</div></section>
<section id="codex"><div class="wrap"><div class="sec-num">Codex</div><h2>Ako počíta Codex</h2>
<p>Zhrnutie podľa <a href="{CODEX_REPO}/blob/main/METHODOLOGY.md">METHODOLOGY.md</a> v repozitári Codexu. Pôvodný web Codexu: <a href="{e(meta["site"])}">{e(meta["site"])}</a>. Počet simulácií na voľbu: {e(meta.get("draws"))}.</p>
{test}</div></section>"""
    return page("Modely · Voľby 2026", body, "model.html", status)


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


def redirect_page(target, race_ids=()):
    """Stub for a moved page. For porovnanie.html, #<race id> goes to that race page and #metodiky to Modely."""
    hashes = {i: f"{i}.html" for i in race_ids} | ({"metodiky": "model.html", "skore": "skore.html"} if race_ids else {})
    return f"""<!DOCTYPE html>
<html lang="sk"><head><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{target}">
<title>Stránka sa presunula · Voľby 2026</title>
<script>var m={json.dumps(hashes)};location.replace(m[location.hash.slice(1)]||"{target}")</script></head>
<body><p>Stránka sa presunula: <a href="{target}">{target}</a></p></body></html>"""


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

    comp = json.loads((ROOT / "data/comparison.json").read_text())
    res_path = ROOT / "data/results/2026.json"
    results = json.loads(res_path.read_text()) if res_path.exists() else {}
    codex_races = {r["id"]: r for r in codex_view.races(data)}
    comp_races = {r["id"]: r for r in comp["races"]}
    for r in data["races"]:
        (DOCS / f'{r["id"]}.html').write_text(race_page(r, codex_races[r["id"]], comp_races[r["id"]], results.get(r["id"], {}), st_both))
        (DOCS / f'codex-{r["id"]}.html').write_text(redirect_page(f'{r["id"]}.html'))
    (DOCS / "volby.html").write_text(volby_page(data, comp, results, lock, cm, st_both))
    (DOCS / "model.html").write_text(models_page(cm, st_both))
    for name, title in [("pravidla", "Pravidlá"), ("skore", "Výsledky"), ("archiv", "Archív")]:
        (DOCS / f"{name}.html").write_text(content_page(name, title, st_both, cm))
    for old, new in REDIRECTS.items():
        ids = [r["id"] for r in data["races"]] if old == "porovnanie.html" else ()
        (DOCS / old).write_text(redirect_page(new, ids))
    (DOCS / ".nojekyll").write_text("")
    print("site built:", len(data["races"]), "races,", len(REDIRECTS) + len(data["races"]), "redirects")


if __name__ == "__main__":
    main()
