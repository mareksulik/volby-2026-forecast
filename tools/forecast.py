"""Forecast engine: fundamentals -> party swing -> AI adjustments -> polls -> Monte Carlo -> market blend.

Inputs:  data/model/fundamentals.json, data/inputs/national.yaml, data/inputs/races/*.yaml
Output:  data/snapshots/<date>-<series>.json and data/latest.json
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
N_SIMS = 20000
SEED = 20261024

# Assumptions (documented on the Model page). Not fitted — no Slovak data to fit them on in time.
KAPPA = {"starosta": 0.25, "primator": 0.25, "predseda VUC": 0.5}  # elasticity of local share to national party swing
BLOC_SHOCK_SD = 0.12      # common national shock (log-utility) gov vs opposition bloc, shared by all races
POLL_HOUSE_SD = 0.05      # share-scale error common to all local polls (house effects, undecided, timing)
POLL_SAMPLE_SD = 0.05     # share-scale error of one poll that averages out across independent polls
POLL_HALF_LIFE_DAYS = 30
SHARE_SD_FUNDAMENTALS = 0.14  # ~ CV MAE 11.2 pp of the fundamentals model, expressed as sd
TRANSFER_SHARE = 0.5      # share of a withdrawn candidate's poll support that follows their endorsement
MARKET_WEIGHT = 0.5       # log-odds weight of de-vigged bookmaker odds in the final win probability
SIZE_RANGE_LOG10 = (3.3, 5.6)  # clamp log10(voters) to the training range (2,000 voters .. Bratislava)


def load_yaml(p: Path):
    return yaml.safe_load(p.read_text())


def features(c: dict, race: dict) -> dict:
    lo, hi = SIZE_RANGE_LOG10
    size = min(max(math.log10(max(race["voters"], 100)), lo), hi) - 4.5
    inc = float(bool(c.get("inc")))
    return {
        "inc": inc,
        "inc_x_size": inc * size,
        "prev_share": float(c.get("prev_share") or 0.0),
        "prev_lost": float(bool(c.get("prev_share")) and not inc),
        "neka": float(bool(c.get("neka"))),
        "log_parties": math.log1p(len(c.get("parties") or [])),
        "gov": 0.0,  # 2022 coefficient ~0; national climate enters via swing + bloc shock instead
        "occ_mayor_noinc": float(bool(c.get("exec_office")) and not inc),
        "local_official": float(bool(c.get("local_official")) and not inc),
        "low_status": float(bool(c.get("low_status"))),
    }


def party_swing(c: dict, national: dict, kappa: float) -> float:
    """kappa * log(current national support / support at the 2022 election), averaged over nominating parties."""
    vals = []
    for p in c.get("parties") or []:
        n = national["parties"].get(p)
        if n and n.get("y2022") and n.get("y2026"):
            vals.append(math.log(n["y2026"] / n["y2022"]))
    return kappa * float(np.mean(vals)) if vals else 0.0


def softmax(u: np.ndarray) -> np.ndarray:
    e = np.exp(u - u.max())
    return e / e.sum()


def poll_average(race: dict, names: list[str], asof: dt.date):
    """Recency-weighted average of polls, normalised among listed candidates. Returns (shares|None, listed mask, sd)."""
    polls = [p for p in race.get("polls") or [] if p.get("results")]
    if not polls:
        return None, None, None
    acc = np.zeros(len(names))
    wsum = np.zeros(len(names))
    eff = 0.0
    others_mass = []
    transfers = {c["name"]: c["transfer_to"] for c in race["candidates"] if c.get("withdrew") and c.get("transfer_to")}
    for p in polls:
        end = dt.date.fromisoformat(str(p["fieldwork_end"]))
        w = 0.5 ** ((asof - end).days / POLL_HALF_LIFE_DAYS) * math.sqrt((p.get("n") or 600) / 600)
        w *= 0.5 if p.get("partisan") else 1.0  # candidate-commissioned polls count half
        res = {k: float(v) for k, v in p["results"].items()}
        for src, dst in transfers.items():
            if src in res and dst in res:
                res[dst] += TRANSFER_SHARE * res.pop(src)
        listed = [n for n in names if n in res]
        tot = sum(res[n] for n in listed)
        if tot <= 0:
            continue
        others = p.get("others_pct")
        others_mass.append((w, None if others is None else others / (tot + others)))
        for i, n in enumerate(names):
            if n in res:
                acc[i] += w * res[n] / tot
                wsum[i] += w
        eff += w
    mask = wsum > 0
    if not mask.any():
        return None, None, None
    sh = np.where(mask, acc / np.where(mask, wsum, 1), 0.0)
    sh = sh / sh[mask].sum()
    known = [(w, o) for w, o in others_mass if o is not None]
    others = sum(w * o for w, o in known) / sum(w for w, _ in known) if known else None
    sd = math.sqrt(POLL_HOUSE_SD ** 2 + POLL_SAMPLE_SD ** 2 / max(eff, 0.25))
    return (sh, mask, sd, others)


def devig_power(odds: dict) -> dict:
    inv = {k: 1.0 / v for k, v in odds.items()}
    lo, hi = 0.5, 5.0
    for _ in range(100):
        k = (lo + hi) / 2
        s = sum(p ** k for p in inv.values())
        lo, hi = (k, hi) if s > 1 else (lo, k)
    return {n: p ** k for n, p in inv.items()}


def market_probs(race: dict, names: list[str]):
    books = [b for b in race.get("odds") or [] if b.get("odds")]
    if not books:
        return None
    acc = {}
    for b in books:
        for n, p in devig_power(b["odds"]).items():
            acc.setdefault(n, []).append(p)
    probs = {n: float(np.mean(v)) for n, v in acc.items() if n in names}
    return probs or None


def blend(p_model: np.ndarray, market: dict, names: list[str]) -> np.ndarray:
    lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))
    out = np.array(p_model, dtype=float)
    covered = [i for i, n in enumerate(names) if n in market]
    for i in covered:
        z = (1 - MARKET_WEIGHT) * lg(p_model[i]) + MARKET_WEIGHT * lg(market[names[i]])
        out[i] = 1 / (1 + math.exp(-z))
    # candidates the market does not quote keep their model probability; renormalise the quoted ones
    rest = 1 - sum(p_model[i] for i in range(len(names)) if i not in covered)
    q = sum(out[i] for i in covered)
    for i in covered:
        out[i] *= rest / q
    return out


def forecast_race(race: dict, beta: dict, sigma_f: float, national: dict, asof: dt.date,
                  bloc_draws: np.ndarray, rng: np.random.Generator, use_polls=True, use_adj=True):
    cands = [c for c in race["candidates"] if not c.get("withdrew")]
    names = [c["name"] for c in cands]
    kappa = KAPPA[race["office"]]
    u_fund = np.array([sum(beta[k] * v for k, v in features(c, race).items()) for c in cands])
    swing = np.array([party_swing(c, national, kappa) for c in cands])
    adj = np.array([float(c.get("adj") or 0.0) if use_adj else 0.0 for c in cands])
    u = u_fund + swing + adj
    f_share = softmax(u)
    sd = np.full(len(cands), sigma_f)
    poll_info = None
    if use_polls:
        pa = poll_average(race, names, asof)
        if pa[0] is not None:
            p_sh, mask, p_sd, others = pa
            w = SHARE_SD_FUNDAMENTALS ** 2 / (SHARE_SD_FUNDAMENTALS ** 2 + p_sd ** 2)
            f_listed = f_share[mask].sum()
            listed_mass = f_listed if others is None else w * (1 - others) + (1 - w) * f_listed
            post = f_share.copy()
            post[mask] = w * p_sh[mask] * listed_mass + (1 - w) * f_share[mask] * listed_mass / f_listed
            post[~mask] = f_share[~mask] * (1 - listed_mass) / max(f_share[~mask].sum(), 1e-9) if (~mask).any() else 0
            post = post / post.sum()
            u = np.log(np.clip(post, 1e-4, 1))
            sd[mask] = max(sigma_f * math.sqrt(1 - w), 0.3)
            poll_info = {"weight": round(w, 3), "poll_sd": round(p_sd, 3), "n_polls": len(race.get("polls") or [])}
    bloc = np.array([{"gov": 1.0, "opp": -1.0}.get(c.get("bloc"), 0.0) for c in cands])
    noise = rng.normal(0, 1, (N_SIMS, len(cands))) * sd
    draws = u[None, :] + noise + bloc_draws[:, None] * bloc[None, :]
    sh = np.exp(draws - draws.max(1, keepdims=True))
    sh /= sh.sum(1, keepdims=True)
    win = np.bincount(sh.argmax(1), minlength=len(cands)) / N_SIMS
    mean = sh.mean(0)
    lo, med, hi = np.quantile(sh, [0.1, 0.5, 0.9], axis=0)
    return {
        "names": names, "u_fund": u_fund, "swing": swing, "adj": adj,
        "share": mean, "median": med, "lo": lo, "hi": hi, "win": win, "poll_info": poll_info,
    }


def run(asof: dt.date, label: str) -> dict:
    fm = json.loads((ROOT / "data/model/fundamentals.json").read_text())
    beta, sigma_f = fm["beta"], fm["sigma"]
    national = load_yaml(ROOT / "data/inputs/national.yaml")
    races = []
    for p in sorted((ROOT / "data/inputs/races").glob("*.yaml")):
        races += load_yaml(p)
    rng = np.random.default_rng(SEED)
    bloc_draws = rng.normal(0, BLOC_SHOCK_SD, N_SIMS)  # one national draw shared by every race
    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "asof": asof.isoformat(), "label": label,
           "n_sims": N_SIMS, "races": []}
    for race in races:
        fund = forecast_race(race, beta, sigma_f, national, asof, bloc_draws, np.random.default_rng(SEED + 1),
                             use_polls=False, use_adj=False)
        main = forecast_race(race, beta, sigma_f, national, asof, bloc_draws, np.random.default_rng(SEED + 2))
        market = market_probs(race, main["names"])
        final_win = blend(main["win"], market, main["names"]) if market else main["win"]
        cands = []
        src = {c["name"]: c for c in race["candidates"]}
        for i, n in enumerate(main["names"]):
            c = src[n]
            cands.append({
                "name": n, "party": c.get("party"), "inc": bool(c.get("inc")), "bloc": c.get("bloc"),
                "share": round(100 * main["median"][i], 1), "mean": round(100 * main["share"][i], 1),
                "lo80": round(100 * main["lo"][i], 1), "hi80": round(100 * main["hi"][i], 1),
                "p_win": round(float(final_win[i]), 4),
                "p_win_blind": round(float(main["win"][i]), 4),
                "p_win_market": None if not market or n not in market else round(market[n], 4),
                "fund_share": round(100 * fund["median"][i], 1), "fund_p_win": round(float(fund["win"][i]), 4),
                "swing": round(float(main["swing"][i]), 3), "adj": round(float(main["adj"][i]), 3),
                "adj_reason": c.get("adj_reason"), "exec_office": bool(c.get("exec_office")),
                "local_official": bool(c.get("local_official")), "prev_share": c.get("prev_share"),
            })
        cands.sort(key=lambda c: -c["share"])
        withdrawn = [{"name": c["name"], "transfer_to": c.get("transfer_to")} for c in race["candidates"] if c.get("withdrew")]
        out["races"].append({
            "id": race["id"], "name": race["name"], "office": race["office"], "group": race["group"],
            "voters": race["voters"], "incumbent": race.get("incumbent"), "history": race.get("history"),
            "polls": race.get("polls") or [], "odds": race.get("odds") or [], "poll_info": main["poll_info"],
            "notes": race.get("notes"), "sources": race.get("sources") or [], "withdrawn": withdrawn,
            "candidates": cands,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default="2026-10-24")
    ap.add_argument("--label", default="final")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()
    res = run(dt.date.fromisoformat(a.asof), a.label)
    snap = ROOT / "data/snapshots" / f"{a.date}-{a.label}.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(res, indent=1, ensure_ascii=False)
    snap.write_text(txt)
    (ROOT / "data/latest.json").write_text(txt)
    for r in res["races"]:
        top = r["candidates"][:3]
        print(f'{r["id"]:28s} ' + " | ".join(f'{c["name"].split()[-1]} {c["share"]:.0f}% ({c["lo80"]:.0f}-{c["hi80"]:.0f}) p={c["p_win"]:.2f}' for c in top))


if __name__ == "__main__":
    main()
