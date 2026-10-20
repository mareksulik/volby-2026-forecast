"""Regional (VÚC) party-base term, fitted on the 2022 regional chair elections.

u_i = beta . x_i (municipal fundamentals, fixed)  +  gamma * ln(1 + base_i)
base_i = sum of national poll support (%) of the candidate's nominating parties at election time.
gamma is chosen by maximising sum_r sum_i s_i log p_i over the 8 races of 2022 (features from 2017);
leave-one-race-out MAE is reported.  Output: data/model/regional.json
"""
import json
import math
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import minimize_scalar

import prepare_inputs as P

ROOT = Path(__file__).resolve().parents[1]


def race_rows(r, beta, national, year_key="y2022"):
    h = r["history"]
    prev, cur = h["2017"], h["2022"]
    winner = max(prev["results"], key=lambda x: x["pct"])
    size = min(max(math.log10(cur["registered_voters"]), 3.3), 5.6) - 4.5
    rows = []
    for x in cur["results"]:
        p = P.match(x["name"], prev["results"])
        inc = bool(p) and p["name"] == winner["name"]
        ps = P.parties(x["party"])
        f = {"inc": inc, "inc_x_size": inc * size, "prev_share": p["pct"] / 100 if p else 0.0,
             "prev_lost": bool(p) and not inc, "neka": P.is_independent(x["party"]),
             "log_parties": math.log1p(len(ps))}
        u = sum(beta.get(k, 0.0) * float(v) for k, v in f.items())
        base = sum((national["parties"].get(k) or {}).get(year_key) or 0.0 for k in ps)
        rows.append((x["name"], x["pct"] / 100, u, math.log1p(base)))
    return rows


def probs(rows, gamma):
    u = np.array([r[2] + gamma * r[3] for r in rows])
    e = np.exp(u - u.max())
    return e / e.sum()


def nll(gamma, races):
    return -sum(sum(s * math.log(p + 1e-9) for (_, s, _, _), p in zip(rows, probs(rows, gamma))) for rows in races)


def main():
    beta = json.loads((ROOT / "data/model/fundamentals.json").read_text())["beta"]
    national = yaml.safe_load((ROOT / "data/inputs/national.yaml").read_text())
    research = []
    for f in ("kraje-west.json", "kraje-east.json"):
        research += json.loads((ROOT / "data/research" / f).read_text())
    races = [race_rows(r, beta, national) for r in research if r["history"].get("2017") and r["history"].get("2022")]
    fit = minimize_scalar(lambda g: nll(g, races), bounds=(0, 3), method="bounded")
    gamma = float(fit.x)
    loo_err, base_err, fav = [], [], 0
    for i in range(len(races)):
        g = minimize_scalar(lambda g: nll(g, races[:i] + races[i + 1:]), bounds=(0, 3), method="bounded").x
        rows = races[i]
        p, p0 = probs(rows, g), probs(rows, 0.0)
        s = np.array([r[1] for r in rows])
        loo_err += list(np.abs(p - s))
        base_err += list(np.abs(p0 - s))
        fav += int(p.argmax() == s.argmax())
    out = {"gamma": round(gamma, 3), "n_races": len(races),
           "loo_mae_pp": round(100 * float(np.mean(loo_err)), 2),
           "mae_without_base_pp": round(100 * float(np.mean(base_err)), 2),
           "loo_favourite_hits": fav,
           "note": "base = sum of national poll % of nominating parties (Sep-Nov 2022 polls for the fit; Sep-Oct 2026 for the forecast)"}
    (ROOT / "data/model/regional.json").write_text(json.dumps(out, indent=1))
    print(out)


if __name__ == "__main__":
    main()
