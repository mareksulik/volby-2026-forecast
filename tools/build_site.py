"""Static site generator (mars-ui) -> docs/ for GitHub Pages."""
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARS = Path.home() / "Documents/GitHub/mars-ui/dist"
REPO = "https://github.com/mareksulik/volby-2026-forecast"
GROUPS = [("kraj", "Predsedovia samosprávnych krajov"), ("mesto", "Primátori krajských miest"),
          ("mc", "Starostovia mestských častí Bratislavy")]
OFFICE = {"predseda VUC": "predseda VÚC", "primator": "primátor", "starosta": "starosta"}
NAV = [("index.html", "Prehľad"), ("model.html", "Model"), ("pravidla.html", "Pravidlá"),
       ("skore.html", "Skóre"), ("archiv.html", "Archív")]

e = lambda s: html.escape(str(s if s is not None else ""))


def pct(x, d=1):
    return "–" if x is None else f"{x:.{d}f} %".replace(".", ",")


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


def interval_svg(c, scale):
    w, h = 180, 16
    x = lambda v: round(v / scale * w, 1)
    return (f'<svg class="iv" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<line x1="0" y1="8" x2="{w}" y2="8" stroke="var(--mu-gray-200)"/>'
            f'<rect x="{x(c["lo80"])}" y="4" width="{max(x(c["hi80"]) - x(c["lo80"]), 1)}" height="8" rx="4" fill="var(--mu-blue-200)"/>'
            f'<circle cx="{x(c["share"])}" cy="8" r="4" fill="var(--mu-blue-700)"/></svg>')


CODEX_URL = "https://mareksulik.github.io/volebny-model-codex/"
TOP = [("claude", "index.html", "Claude"), ("codex", CODEX_URL, "Codex ↗"), ("porovnanie", "porovnanie.html", "Porovnanie")]
CMP_NAV = [("#suhrn", "Súhrn"), ("#rozdiely", "Kde sa líšia"), ("#vsetky", "Všetky voľby"), ("#metodiky", "Metodiky")]


def page(title, body, active, meta, top="claude", subnav=None):
    items = NAV if subnav is None else subnav
    nav = "".join(f'<a href="{h}"{" class=active" if h == active else ""}>{t}</a>' for h, t in items)
    topmenu = "".join(f'<a href="{h}"{" class=active aria-current=page" if k == top else ""}>{t}</a>' for k, h, t in TOP)
    return f"""<!DOCTYPE html>
<html lang="sk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="ds.css"><script src="ds.js"></script>
<style>
.iv{{vertical-align:middle}} .race-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:16px}}
.race-grid>*{{min-width:0}} .race-grid .card h3{{margin:0 0 4px}} .race-grid table td,.race-grid table th{{padding:6px 8px}}
.lock{{margin:16px 0}} td.nm{{max-width:220px}} .muted{{color:var(--mu-gray-900)}}
.topmenu{{display:flex;gap:4px;align-items:center}}
.topmenu a{{font-size:14px;line-height:20px;font-weight:500;padding:6px 12px;border-radius:var(--mu-radius-sm);color:var(--mu-gray-900);text-decoration:none}}
.topmenu a:hover{{background:var(--mu-gray-100);color:var(--mu-gray-1000)}}
.topmenu a.active{{background:var(--mu-gray-1000);color:var(--mu-background-100)}}
@media (max-width:600px){{.race-grid{{grid-template-columns:1fr}} .iv{{width:110px}} .topbar .meta-row{{display:none}}}}
</style></head><body>
<header class="topbar"><div class="wrap"><div class="brand">
<svg viewBox="0 0 110 22" height="22" aria-hidden="true"><text x="0" y="17" font-family="Geist, sans-serif" font-weight="600" font-size="18" fill="currentColor">Voľby 2026</text></svg>
<span class="slash"></span><span class="app">Predpoveď samosprávnych volieb</span><h1 class="sr-only">{e(title)}</h1></div>
<div class="topmenu" role="navigation" aria-label="Model">{topmenu}</div>
<div class="meta-row">{meta}</div></div></header>
<nav aria-label="Sekcie"><div class="wrap">{nav}<a href="{REPO}" class="right">GitHub</a></div></nav>
{body}
<footer class="site"><span>Marek Šulík · obsah CC BY 4.0, kód MIT</span><span>Predpovede vytvorili AI pipeline (Claude a Codex) s človekom v slučke. Nie sú to tipy na stávkovanie.</span></footer>
</body></html>"""


def race_table(r, full=False):
    scale = max(60, max(c["hi80"] for c in r["candidates"]) + 5)
    scale = min(100, ((scale + 9) // 10) * 10)
    rows = []
    for c in r["candidates"]:
        inc = ' <span class="chip chip-neutral">obhajca</span>' if c["inc"] else ""
        extra = ""
        if full:
            extra = (f'<td class="num gs">{pct(c["fund_share"])}</td><td class="num">{prob(c["fund_p_win"])}</td>'
                     f'<td class="num">{prob(c["p_win_blind"])}</td><td class="num">{prob(c["p_win_market"])}</td>')
        party = f'<div class="text-small muted">{e(c["party"])}</div>' if full else ""
        svg = f'<td>{interval_svg(c, scale)}</td>' if full else ""
        rows.append(f'<tr><td class="nm">{e(c["name"])}{inc}{party}</td><td class="num">{pct(c["share"])}</td>'
                    f'<td class="num">{c["lo80"]:.0f}–{c["hi80"]:.0f} %</td>{svg}'
                    f'<td class="num">{prob_chip(c["p_win"])}</td>{extra}</tr>')
    head = ('<tr><th>Kandidát</th><th class="num">Odhad</th><th class="num">80 % interval</th>'
            + (f'<th>0–{scale} %</th>' if full else "") + '<th class="num">P(výhra)</th>')
    if full:
        head += ('<th class="num gs">Fundamenty</th><th class="num">P fund.</th><th class="num">P bez trhu</th>'
                 '<th class="num">P trh</th>')
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


def polls_html(r):
    if not r["polls"]:
        return '<p class="muted">Prieskum k tejto voľbe sme nenašli.</p>'
    rows = []
    for p in r["polls"]:
        res = ", ".join(f"{e(k)} {pct(v)}" for k, v in sorted(p["results"].items(), key=lambda kv: -kv[1]))
        rows.append(f'<tr><td>{e(p.get("pollster"))}</td><td class="num">{e(p.get("fieldwork_end"))}</td><td class="num">{e(p.get("n") or "–")}</td>'
                    f'<td>{res}</td><td><a href="{e(p.get("source"))}">zdroj</a></td></tr>')
    pi = r.get("poll_info") or {}
    sub = f'váha prieskumov v modeli {round(100 * pi["weight"])} %' if pi else ""
    return (f'<div class="fig-sub">{sub}</div><div class="tbl-scroll"><table><thead><tr><th>Agentúra</th><th class="num">Koniec zberu</th>'
            f'<th class="num">n</th><th>Výsledky (bez nerozhodnutých)</th><th></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def odds_html(r):
    if not r["odds"]:
        return '<p class="muted">Stávkové kancelárie na túto voľbu kurzy nevypísali (alebo sme ich nenašli).</p>'
    rows = "".join(f'<tr><td>{e(o["bookmaker"])}</td><td class="num">{e(o.get("date"))}</td><td>{", ".join(f"{e(k)} {v}" for k, v in o["odds"].items())}</td>'
                   f'<td><a href="{e(o.get("source"))}">zdroj</a></td></tr>' for o in r["odds"])
    return f'<div class="tbl-scroll"><table><thead><tr><th>Kancelária</th><th class="num">Dátum</th><th>Kurzy</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>'


def adjustments_html(r):
    li = []
    for c in r["candidates"]:
        if c.get("adj") or c.get("adj_reason"):
            tag = f' ({c["adj"]:+.1f})'.replace(".", ",") if c.get("adj") else ""
            li.append(f'<li><strong>{e(c["name"])}{tag}.</strong> {e(c.get("adj_reason"))}</li>')
    for w in r["withdrawn"]:
        if w.get("transfer_to"):
            li.append(f'<li><strong>{e(w["name"])} → {e(w["transfer_to"])}.</strong> Odstúpil(a) v prospech kandidáta; v prieskumoch presúvame polovicu jeho/jej podielu, zvyšok sa rozdelí pomerne.</li>')
    if not li:
        return '<p class="muted">Žiadne úpravy nad rámec modelu.</p>'
    return "<ul>" + "".join(li) + "</ul>"


def race_page(r, meta):
    srcs = "".join(f'<li><a href="{e(s)}">{e(s)}</a></li>' for s in r.get("sources") or [])
    wd = ""
    if r["withdrawn"]:
        names = ", ".join(w["name"] + (f' (v prospech: {w["transfer_to"]})' if w.get("transfer_to") else "") for w in r["withdrawn"])
        wd = f'<div class="note note-warn">Odstúpili, na lístku zostávajú, hlasy pre nich sa nerátajú: {e(names)}.</div>'

    body = f"""<section><div class="wrap">
<div class="sec-num">{e(OFFICE[r["office"]])}</div><h2>{e(r["name"])}</h2>
<p class="muted">Zapísaní voliči: {r["voters"]:,}. Jedno kolo, vyhráva relatívna väčšina.</p>{wd}
<figure><figcaption>Predpoveď</figcaption><div class="fig-sub">odhad = medián simulácií · interval = 10.–90. percentil · P(výhra) = podiel zo 20 000 simulácií, kde je kandidát prvý (finálna séria vrátane trhu)</div>
{race_table(r, full=True)}</figure>
<div class="grid2"><figure><figcaption>Prieskumy</figcaption>{polls_html(r)}</figure>
<figure><figcaption>Stávkové kurzy</figcaption>{odds_html(r)}</figure></div>
<figure><figcaption>Úpravy nad rámec modelu</figcaption><div class="fig-sub">číslo = posun v log-skóre kandidáta (+0,3 ≈ o tretinu vyšší relatívny podiel pred normalizáciou)</div>{adjustments_html(r)}</figure>
<figure><figcaption>Kontext</figcaption><p>{e(r.get("notes"))}</p></figure>
<h3>História</h3><div class="grid2">{history_html(r)}</div>
<figure><figcaption>Zdroje</figcaption><ul class="text-small">{srcs}</ul></figure>
</div></section>""".replace(",", ",") .replace(f'{r["voters"]:,}', f'{r["voters"]:,}'.replace(",", " "))
    return page(f'{r["name"]} · Voľby 2026', body, "", meta)


def index_page(data, meta, lock_note):
    secs = []
    for i, (g, title) in enumerate(GROUPS, 1):
        cards = []
        for r in [r for r in data["races"] if r["group"] == g]:
            fav = r["candidates"][0]
            top = dict(r, candidates=r["candidates"][:5])
            more = len(r["candidates"]) - 5
            more_txt = f' · ďalší {more} kandidáti' if more > 0 else ""
            cards.append(f'<div class="card"><h3><a href="{r["id"]}.html">{e(r["name"])}</a></h3>'
                         f'<div class="fig-sub">favorit: {e(fav["name"])} ({prob(max(c["p_win"] for c in r["candidates"]))}){more_txt}</div>'
                         f'{race_table(top)}</div>')
        secs.append(f'<section id="{g}"><div class="wrap"><div class="sec-num">0{i} — {e(title)}</div><h2>{e(title)}</h2>'
                    f'<div class="race-grid">{"".join(cards)}</div></div></section>')
    intro = f"""<section><div class="wrap"><div class="sec-num">Sobota 24. 10. 2026</div>
<h2>Kto vyhrá župy, krajské mestá a bratislavské mestské časti</h2>
<p>Pravdepodobnostná predpoveď 33 volieb: 8 predsedov samosprávnych krajov, 8 primátorov krajských miest a 17 starostov mestských častí Bratislavy. Pre každého kandidáta uvádzame odhad podielu hlasov, 80 % interval a pravdepodobnosť výhry. Voľby majú jedno kolo a vyhráva relatívna väčšina, aj pri županoch.</p>
{lock_note}
<p class="text-small muted">Ako to vzniklo: fundamentálny model nafitovaný na 2 914 komunálnych voľbách 2018 → 2022 (efekt obhajcu, predchádzajúci výsledok, nominácia), celoštátny posun strán, prieskumy a stávkové kurzy, 20 000 korelovaných simulácií. Podrobnosti na stránke <a href="model.html">Model</a>.</p>
</div></section>"""
    return page("Voľby 2026 · predpoveď", intro + "".join(secs), "index.html", meta)


FEATURE_SK = {
    "inc": "obhajca (kandiduje úradujúci starosta/primátor)", "inc_x_size": "obhajca × log10(voliči) − 4,5",
    "prev_share": "podiel v minulých voľbách (0–1)", "prev_lost": "kandidoval minule a prehral",
    "neka": "nezávislý kandidát (NEKA)", "log_parties": "ln(1 + počet nominujúcich strán)",
    "gov": "nominovaný vládnou stranou 2022", "occ_mayor_noinc": "úradujúci starosta inej samosprávy",
    "local_official": "miestny funkcionár (vicestarosta, poslanec)", "low_status": "dôchodca / nezamestnaný",
}


def fill_model(src):
    fm = json.loads((ROOT / "data/model/fundamentals.json").read_text())
    nat = __import__("yaml").safe_load((ROOT / "data/inputs/national.yaml").read_text())
    b, cv, bl = fm["beta"], fm["cv"], fm["baselines"]
    reg = json.loads((ROOT / "data/model/regional.json").read_text())
    num = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")
    beta = "".join(f'<tr><td>{e(FEATURE_SK.get(k, k))}</td><td class="num">{num(v)}</td></tr>' for k, v in b.items())
    calib = "".join(f'<tr><td class="num">{e(c["bin"])}</td><td class="num">{c["n"]}</td><td class="num">{num(100 * c["mean_p"], 0)} %</td>'
                    f'<td class="num">{num(100 * c["win_rate"], 0)} %</td></tr>' for c in cv["calibration"])
    swing = "".join(f'<tr><td>{e(k)}</td><td class="num">{num(v["y2022"], 1)} %</td><td class="num">{num(v["y2026"], 1)} %</td>'
                    f'<td class="num">{num(__import__("math").log(v["y2026"] / v["y2022"]), 2)}</td></tr>'
                    for k, v in nat["parties"].items() if v.get("y2022") and v.get("y2026"))
    rep = {
        "n_races": str(fm["n_races"]), "n_candidates": str(fm["n_candidates"]),
        "inc": num(b["inc"]), "inc_size": num(b["inc_x_size"]), "prev": num(b["prev_share"]), "neka": num(b["neka"]),
        "gamma": num(reg["gamma"]), "reg_loo": num(reg["loo_mae_pp"], 1), "reg_base": num(reg["mae_without_base_pp"], 1),
        "brier": num(cv["brier"], 3), "brier_inc": num(bl["incumbent_wins_else_uniform_brier"], 3),
        "brier_uni": num(bl["uniform_brier"], 3), "fav": f'{round(100 * cv["favourite_hit_rate"])} %',
        "mae": num(cv["share_mae_pp"], 1), "sigma": num(fm["sigma"]), "coverage": f'{round(100 * cv["coverage_80"])} %',
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
    num = lambda x, d=3: f"{x:.{d}f}".replace(".", ",")
    rows = "".join(f'<tr><td>{SERIES_SK.get(k, k)}</td><td class="num">{v["n"]}</td><td class="num">{num(v["brier"])}</td>'
                   f'<td class="num">{num(v["log_score"])}</td><td class="num">{v["favourites_hit"]}</td></tr>' for k, v in s["series"].items())
    races = "".join(f'<tr><td><a href="{r["id"]}.html">{e(r["id"])}</a></td><td>{e(r["winner"])}</td>'
                    f'<td class="num">{prob(r.get("p_winner_final"))}</td><td class="num">{prob(r.get("p_winner_fundamenty"))}</td>'
                    f'<td class="num">{prob(r.get("p_winner_trh"))}</td></tr>' for r in s["races"])
    return (f'<h3>Výsledky ({e(s["snapshot"])})</h3><div class="tbl-scroll"><table><thead><tr><th>Séria</th><th class="num">Volieb</th>'
            f'<th class="num">Brier ↓</th><th class="num">Log skóre ↑</th><th class="num">Trafení favoriti</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p>Priemerná chyba podielu: {num(s["share_mae_pp"], 1)} b. (fundamenty {num(s["fund_share_mae_pp"], 1)} b.). '
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
                    f'<td class="num">{e(d.get("generated", "")[:16].replace("T", " "))}</td></tr>')
    lock = (ROOT / "data/lock.json")
    lk = f'<p>Zámok: <a href="data/lock.json"><code>data/lock.json</code></a></p>' if lock.exists() else ""
    return ('<div class="sec-num">Archív</div><h2>Snapshoty</h2><p>Každá verzia predpovede je nemenný JSON súbor. '
            'Staršie verzie sa nikdy neprepisujú; história je aj v gite.</p>' + lk +
            f'<div class="tbl-scroll"><table><thead><tr><th>Súbor</th><th>Séria</th><th class="num">Vytvorené</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def md_page(name, title, active, meta):
    if name == "archiv":
        src = archive_html()
    else:
        src = (ROOT / "content" / f"{name}.html").read_text()
    if name == "model":
        src = fill_model(src)
    if name == "skore" and (ROOT / "data/score.json").exists():
        src += score_html(json.loads((ROOT / "data/score.json").read_text()))
    return page(f"{title} · Voľby 2026", f'<section><div class="wrap">{src}</div></section>', active, meta)


METHODS = [
    ("Tréning fundamentov", "Podmienený logit na 2 914 voľbách starostov 2018 → 2022 (obce s aspoň 2 000 voličmi). Rysy: obhajca × veľkosť obce, minulý podiel, nezávislý, počet strán, povolanie.",
     "Softmax na komunálnych súbojoch 2018 → 2022 s aspoň 1 000 platnými hlasmi. Rysy: minulý podiel, minulé víťazstvo, počet strán, funkcia z registrácie, nezávislý. Delenie na tréning, kalibráciu a test podľa hashu obce."),
    ("Kraje", "Fundamenty z obcí plus straníckej základne γ = 0,29, nafitovanej na 8 krajských voľbách 2022 (leave-one-out chyba 5,5 b.).",
     "Fundamenty z obcí; kraje 2017 → 2022 len ako samostatný test prenosu."),
    ("Neistota", "Logistic-normal šum σ = 0,95 nastavený na 80 % pokrytie na odložených obciach a spoločný celoštátny šok vládneho a opozičného bloku naprieč voľbami.",
     "Dirichletovo rozdelenie s koncentráciou vybranou na 80 % pokrytie na kalibračnej množine; voľby sa simulujú nezávisle."),
    ("Prieskumy", "Priemer s polčasom 30 dní, váha √(n/600). Prieskumy kandidátov majú polovičnú váhu. Kombinácia s fundamentmi podľa presnosti (spoločná chyba 5 b.).",
     "Bayesovská aktualizácia: pseudopozorovania min(200, n/2) × 2^(−vek/30) × kvalita, koncentrácia najviac 80. Neúplné polia vyradené."),
    ("Odstúpenia", "Polovica prieskumného podielu odstúpeného ide kandidátovi, ktorého podporil, zvyšok sa rozdelí pomerne.",
     "Masa odstúpených sa rozdelí podľa fundamentálneho základu (Dirichletov scenár); podporený kandidát nedostáva prednostný presun."),
    ("Trh", "Kurzy bez marže sa miešajú s modelom v log-odds s váhou 0,5. Menia len pravdepodobnosť výhry, nie podiely.",
     "Kurzy sú len porovnávací benchmark, do predpovede nevstupujú."),
    ("Bodový odhad", "Medián 20 000 simulácií.", "Stredná hodnota (priemer) 50 000 simulácií."),
    ("Ručné úpravy", "Zdokumentované úpravy pri faktoch mimo modelu (overrides.yaml, každá s dôvodom).", "Žiadne; len pravidlá zaradenia prieskumov a odstúpení."),
]


def num1(x):
    return f"{x:.1f}".replace(".", ",")


def cmp_cell(x):
    if not x:
        return '<td class="num gs">–</td><td class="num">–</td><td class="num">–</td>'
    return (f'<td class="num gs">{pct(x["share"])}</td><td class="num">{x["lo80"]:.0f}–{x["hi80"]:.0f} %</td>'
            f'<td class="num">{prob_chip(x["p_win"])}</td>')


def comparison_page(meta):
    c = json.loads((ROOT / "data/comparison.json").read_text())
    cx = c["codex"]
    n, same = c["n_races"], c["same_favourite"]
    diff = [r for r in c["races"] if not r["same_favourite"]]
    gaps = [r for r in c["races"] if r["unmatched_codex"]]
    stats = (f'<div class="grid3"><div class="card"><div class="stat"><div class="label">Rovnaký favorit</div><div class="value">{same}/{n}</div>'
             f'<div class="delta">volieb</div></div></div>'
             f'<div class="card"><div class="stat"><div class="label">Priemerný rozdiel podielu</div><div class="value">{num1(c["mean_abs_share_diff_pp"])} b.</div>'
             f'<div class="delta">percentuálne body, priemer cez kandidátov</div></div></div>'
             f'<div class="card"><div class="stat"><div class="label">Priemerný rozdiel P(výhra)</div><div class="value">{num1(100 * c["mean_abs_pwin_diff"])} b.</div>'
             f'<div class="delta">percentuálne body, priemer cez kandidátov</div></div></div></div>')
    gap_li = "".join(f'<li><strong>{e(r["name"])}.</strong> Codex počíta ako aktívnych aj {e(", ".join(r["unmatched_codex"]))}. '
                     'V našom výskume odstúpili (hlasy pre nich sa nerátajú), preto ich Claude nemá.</li>' for r in gaps)
    diff_li = "".join(f'<li><strong><a href="#{r["id"]}">{e(r["name"])}</a>.</strong> Claude: {e(r["fav_claude"])}, Codex: {e(r["fav_codex"])}.</li>' for r in diff)
    top = sorted(c["races"], key=lambda r: -r["max_dp"])[:12]
    rows = []
    for r in top:
        cc = {x["name"]: x for x in r["candidates"]}
        fc, fx = cc[r["fav_claude"]], cc[r["fav_codex"]]
        rows.append(f'<tr><td><a href="#{r["id"]}">{e(r["name"])}</a></td><td>{e(r["fav_claude"])}</td><td class="num">{prob(fc["claude"]["p_win"])}</td>'
                    f'<td class="gs">{e(r["fav_codex"])}</td><td class="num">{prob(fx["codex"]["p_win"])}</td>'
                    f'<td class="num gs">{round(100 * r["max_dp"])} b.</td></tr>')
    cards = []
    for g, title in GROUPS:
        for r in [r for r in c["races"] if r["group"] == g]:
            trs = "".join(f'<tr><td class="nm">{e(x["name"])}{" <span class=\"chip chip-neutral\">obhajca</span>" if x["inc"] else ""}</td>'
                          f'{cmp_cell(x["claude"])}{cmp_cell(x["codex"])}</tr>' for x in r["candidates"])
            badge = '' if r["same_favourite"] else ' <span class="chip chip-warn">iný favorit</span>'
            cards.append(f'<figure id="{r["id"]}"><figcaption><a href="{r["id"]}.html">{e(r["name"])}</a>{badge}</figcaption>'
                         f'<div class="tbl-scroll"><table class="grouped"><thead><tr class="grp"><th></th><th colspan="3" class="gs">CLAUDE</th><th colspan="3" class="gs">CODEX</th></tr>'
                         f'<tr><th>Kandidát</th><th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th>'
                         f'<th class="num gs">Odhad</th><th class="num">80 %</th><th class="num">P(výhra)</th></tr></thead><tbody>{trs}</tbody></table></div></figure>')
    meth = "".join(f'<tr><td><strong>{e(a)}</strong></td><td class="gs">{e(b)}</td><td class="gs">{e(x)}</td></tr>' for a, b, x in METHODS)
    scores = ""
    if c.get("scores"):
        sr = "".join(f'<tr><td>{k.capitalize()}</td><td class="num">{v["n"]}</td><td class="num">{v["brier"]:.3f}</td><td class="num">{v["log_score"]:.3f}</td>'
                     f'<td class="num">{v["favourites_hit"]}</td><td class="num">{pct(v["share_mae_pp"])}</td><td class="num">{round(100 * v["coverage_80"])} %</td></tr>'
                     for k, v in c["scores"].items() if v)
        scores = (f'<section id="skore"><div class="wrap"><div class="sec-num">05 — Skóre</div><h2>Ktorý model bol presnejší</h2>'
                  f'<div class="tbl-scroll"><table><thead><tr><th>Model</th><th class="num">Volieb</th><th class="num">Brier ↓</th><th class="num">Log skóre ↑</th>'
                  f'<th class="num">Trafení favoriti</th><th class="num">Chyba podielu</th><th class="num">Pokrytie 80 %</th></tr></thead><tbody>{sr}</tbody></table></div></div></section>')
    body = f"""<section id="suhrn"><div class="wrap"><div class="sec-num">01 — Súhrn</div>
<h2>Claude a Codex: dva nezávislé modely tých istých 33 volieb</h2>
<p>Obe predpovede vznikli na rovnaké zadanie (vzor: Šlerkova predpoveď Senátu 2026), ale každý model mal vlastný výskum, vlastné dáta a vlastnú metodiku. Porovnávame <a href="index.html">Claude</a> (snapshot <code>{e(c["claude_snapshot"])}</code>) a <a href="{CODEX_URL}">Codex</a> (zamknutý {e(cx["locked_at"][:16].replace("T", " "))}, uzáver vstupov {e(cx["cutoff"][:16].replace("T", " "))}, kópia overená cez SHA-256 voči jeho <code>LOCK.json</code>, <a href="{e(cx["source"])}">zdroj</a>).</p>
{stats}
<div class="grid2"><figure><figcaption>Iný favorit</figcaption><ul>{diff_li or "<li>Nikde.</li>"}</ul></figure>
<figure><figcaption>Rozdiely vo vstupoch</figcaption><ul>{gap_li or "<li>Žiadne.</li>"}<li><strong>Uzáver vstupov.</strong> Codex zamkol predpoveď 20. 10. popoludní, Claude ju zamyká 21. 10. večer, takže môže zahrnúť aj neskoršie prieskumy (napríklad AKO pre Bratislavu z 20. 10. večer).</li></ul></figure></div>
</div></section>
<section id="rozdiely"><div class="wrap"><div class="sec-num">02 — Kde sa líšia</div><h2>Najväčšie rozdiely v pravdepodobnosti výhry</h2>
<div class="fig-sub">max |ΔP| = najväčší rozdiel v pravdepodobnosti výhry jedného kandidáta medzi modelmi</div>
<div class="tbl-scroll"><table class="grouped"><thead><tr class="grp"><th></th><th colspan="2">CLAUDE</th><th colspan="2" class="gs">CODEX</th><th class="gs"></th></tr>
<tr><th>Voľba</th><th>Favorit</th><th class="num">P</th><th class="gs">Favorit</th><th class="num">P</th><th class="num gs">max |ΔP|</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</div></section>
<section id="vsetky"><div class="wrap"><div class="sec-num">03 — Všetky voľby</div><h2>Kandidát po kandidátovi</h2>
<div class="race-grid">{"".join(cards)}</div></div></section>
<section id="metodiky"><div class="wrap"><div class="sec-num">04 — Metodiky</div><h2>Čím sa modely líšia</h2>
<div class="tbl-scroll"><table><thead><tr><th>Krok</th><th class="gs">Claude</th><th class="gs">Codex</th></tr></thead><tbody>{meth}</tbody></table></div>
<p class="text-small">Opis Codexovej metodiky je zhrnutie jeho <a href="https://github.com/mareksulik/volebny-model-codex/blob/main/METHODOLOGY.md">METHODOLOGY.md</a>. Po voľbách obe predpovede oskórujeme rovnakými metrikami.</p>
</div></section>{scores}"""
    return page("Porovnanie Claude a Codex · Voľby 2026", body, "", meta, top="porovnanie", subnav=CMP_NAV)


def main():
    data = json.loads((ROOT / "data/latest.json").read_text())
    DOCS.mkdir(exist_ok=True)
    for f in ["ds.css", "ds.js"]:
        shutil.copy(MARS / f, DOCS / f)
    shutil.copytree(MARS / "fonts", DOCS / "fonts", dirs_exist_ok=True)
    shutil.copytree(ROOT / "data/snapshots", DOCS / "data/snapshots", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("test-*"))
    if (ROOT / "data/lock.json").exists():
        shutil.copy(ROOT / "data/lock.json", DOCS / "data/lock.json")
    shutil.copy(ROOT / "data/latest.json", DOCS / "data/latest.json")
    shutil.copy(ROOT / "data/model/fundamentals.json", DOCS / "data/fundamentals.json")
    lock = json.loads((ROOT / "data/lock.json").read_text()) if (ROOT / "data/lock.json").exists() else None
    meta = (f'<span>SNAPSHOT {e(data["label"]).upper()}</span><span>STAV K {e(data["generated"][:16].replace("T", " "))}</span>'
            + ('<span>ZAMKNUTÉ</span>' if lock else '<span>PRACOVNÁ VERZIA</span>'))
    lock_note = (f'<div class="note note-ok"><strong>Predpoveď je zamknutá</strong> ({e(lock["locked_at"])}). Commit <code>{e(lock["commit"])}</code>, tag <code>{e(lock["tag"])}</code>. Ďalšie zmeny už len ako nové verzie s vysvetlením.</div>'
                 if lock else '<div class="note note-warn"><strong>Pracovná verzia.</strong> Finálna predpoveď sa zamkne najneskôr v stredu 21. 10. 2026 o 23:59 (od štvrtka platí moratórium na zverejňovanie prieskumov).</div>')
    (DOCS / "index.html").write_text(index_page(data, meta, lock_note))
    for r in data["races"]:
        (DOCS / f'{r["id"]}.html').write_text(race_page(r, meta))
    for name, title in [("model", "Model"), ("pravidla", "Pravidlá"), ("skore", "Skóre"), ("archiv", "Archív")]:
        (DOCS / f"{name}.html").write_text(md_page(name, title, f"{name}.html", meta))
    if (ROOT / "data/comparison.json").exists():
        (DOCS / "porovnanie.html").write_text(comparison_page(meta))
        shutil.copytree(ROOT / "data/codex", DOCS / "data/codex", dirs_exist_ok=True)
        shutil.copy(ROOT / "data/comparison.json", DOCS / "data/comparison.json")
    (DOCS / ".nojekyll").write_text("")
    print("site built:", len(data["races"]), "races")


if __name__ == "__main__":
    main()
