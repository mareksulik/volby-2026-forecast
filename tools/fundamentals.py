"""Fundamentals layer: conditional-logit model of mayoral vote shares, fitted on 2018 -> 2022.

share_i = exp(u_i) / sum_j exp(u_j),  u_i = beta . x_i
Each contested race has equal weight; loss = -sum_r sum_i s_i log p_i.
Noise model for simulation: u_i + N(0, sigma^2); sigma chosen to maximise held-out winner log score.
Output: data/model/fundamentals.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
GOV_2022 = {"119", "128", "135", "152", "117", "110"}  # OĽaNO(+NOVA,KÚ,ZZ), SaS, Sme rodina, Za ľudí, NOVA, KÚ
FEATURES = ["inc", "inc_x_size", "prev_share", "prev_lost", "neka", "log_parties", "gov", "occ_mayor_noinc",
            "local_official", "low_status"]
MIN_VOTERS = 2000


def design(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["inc"] = df.inc.astype(float)
    x["inc_x_size"] = df.inc * (np.log10(df.voters.clip(lower=100)) - 4.5)  # centred at ~30k voters
    x["prev_share"] = df.prev_share
    x["prev_lost"] = (df.ran_prev & ~df.inc).astype(float)
    x["neka"] = df.neka.astype(float)
    x["log_parties"] = np.log1p(df.n_parties)
    ps = df.PS.fillna("").astype(str).str.split(",")
    x["gov"] = ps.map(lambda xs: float(any(p.strip() in GOV_2022 for p in xs)))
    x["occ_mayor_noinc"] = (df.occ_mayor & ~df.inc).astype(float)  # e.g. sitting mayor of another unit
    occ = df.ZAMESTNANIE.fillna("").str.lower()
    x["local_official"] = (occ.str.contains("zástup|zastup|vicestarost|viceprimátor|poslan|prednost") & ~df.inc).astype(float)
    x["low_status"] = occ.str.contains("dôchod|dochod|nezamest").astype(float)
    return x[FEATURES]


def softmax_by_race(u: np.ndarray, idx: np.ndarray) -> np.ndarray:
    m = pd.Series(u).groupby(idx).transform("max").to_numpy()
    e = np.exp(u - m)
    return e / pd.Series(e).groupby(idx).transform("sum").to_numpy()


def fit(X: np.ndarray, s: np.ndarray, idx: np.ndarray, l2: float = 1e-3) -> np.ndarray:
    def nll(b):
        p = softmax_by_race(X @ b, idx)
        return -(s * np.log(p + 1e-12)).sum() / len(np.unique(idx)) + l2 * (b @ b)
    return minimize(nll, np.zeros(X.shape[1]), method="L-BFGS-B").x


def sim_win(u: np.ndarray, idx: np.ndarray, sigma: float, n: int = 2000, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros(len(u))
    for r in np.unique(idx):
        m = idx == r
        draws = u[m][None, :] + rng.normal(0, sigma, (n, m.sum()))
        w = np.bincount(draws.argmax(1), minlength=m.sum()) / n
        out[m] = w
    return out


def coverage_80(u: np.ndarray, s: np.ndarray, idx: np.ndarray, sigma: float) -> float:
    rng = np.random.default_rng(1)
    cover = []
    for r in np.unique(idx):
        m = idx == r
        d = u[m][None, :] + rng.normal(0, sigma, (2000, m.sum()))
        sh = np.exp(d - d.max(1, keepdims=True))
        sh /= sh.sum(1, keepdims=True)
        lo, hi = np.quantile(sh, [.1, .9], axis=0)
        cover += list((s[m] >= lo) & (s[m] <= hi))
    return float(np.mean(cover))


def main() -> None:
    df = pd.read_csv(ROOT / "data/processed/mayors_2022.csv", dtype={"PS": str, "obec": str})
    df = df[(df.n_cand > 1) & (df.voters >= MIN_VOTERS)].reset_index(drop=True)
    X, s, idx = design(df).to_numpy(), df.share.to_numpy(), df.obec.to_numpy()
    races = np.unique(idx)
    rng = np.random.default_rng(42)
    folds = dict(zip(races, rng.integers(0, 5, len(races))))
    f = np.array([folds[r] for r in idx])

    # cross-validated predictions
    u_cv = np.zeros(len(df))
    for k in range(5):
        b = fit(X[f != k], s[f != k], idx[f != k])
        u_cv[f == k] = X[f == k] @ b
    p_cv = softmax_by_race(u_cv, idx)
    mae = np.abs(p_cv - s).mean() * 100

    # choose sigma on held-out predictions (winner log score)
    grid = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 1.1]
    scores, coverage = {}, {}
    won = df.won.to_numpy()
    for sg in grid:
        pw = sim_win(u_cv, idx, sg)
        scores[sg] = float(np.mean(np.log(np.clip(pw[won], 1e-3, 1))))
        coverage[sg] = coverage_80(u_cv, s, idx, sg)
    # published intervals must be honest: smallest sigma with >= 80 % CV coverage
    sigma = min(sg for sg in grid if coverage[sg] >= 0.8)
    pw = sim_win(u_cv, idx, sigma)
    won = df.won.to_numpy()
    brier = float(pd.Series((pw - won) ** 2).groupby(idx).sum().mean())
    fav_hit = float(np.mean([won[idx == r][pw[idx == r].argmax()] for r in races]))
    # calibration bins
    bins = pd.cut(pw, [0, .1, .3, .5, .7, .9, 1.0], include_lowest=True)
    calib = pd.DataFrame({"bin": bins, "p": pw, "won": won}).groupby("bin", observed=True).agg(
        n=("won", "size"), mean_p=("p", "mean"), win_rate=("won", "mean")).reset_index()
    calib["bin"] = calib.bin.astype(str)


    beta = fit(X, s, idx)
    out = {
        "fitted_on": f"ŠÚ SR mayoral elections 2022 (features from 2018), contested races with >= {MIN_VOTERS} voters",
        "n_races": int(len(races)), "n_candidates": int(len(df)),
        "features": FEATURES, "beta": dict(zip(FEATURES, map(float, beta))),
        "sigma": sigma, "sigma_grid_logscore": scores,
        "cv": {"share_mae_pp": round(float(mae), 2), "brier": round(brier, 3), "favourite_hit_rate": round(fav_hit, 3),
               "coverage_80": round(coverage[sigma], 3), "coverage_by_sigma": coverage, "calibration": calib.to_dict("records")},
        "baselines": {},
    }
    # naive baselines on the same races
    inc_rule = np.where(df.inc_in_race.to_numpy(), df.inc.to_numpy().astype(float),
                        1.0 / df.groupby("obec").obec.transform("count").to_numpy())
    out["baselines"]["incumbent_wins_else_uniform_brier"] = round(float(pd.Series((inc_rule - won) ** 2).groupby(idx).sum().mean()), 3)
    uni = 1.0 / df.groupby("obec").obec.transform("count").to_numpy()
    out["baselines"]["uniform_brier"] = round(float(pd.Series((uni - won) ** 2).groupby(idx).sum().mean()), 3)
    (ROOT / "data/model").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/model/fundamentals.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ["n_races", "beta", "sigma", "cv", "baselines"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
