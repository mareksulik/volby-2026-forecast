"""Build a candidate-level dataset of Slovak mayoral races 2018 -> 2022 from ŠÚ SR open data.

Output: data/processed/mayors_2022.csv — one row per 2022 mayoral candidate with features
known before the 2022 election (incumbency, 2018 share, field size, independent label).
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "susr"
OUT = ROOT / "data" / "processed"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def load_2018() -> pd.DataFrame:
    df = pd.read_excel(RAW / "OSO_2018_xlsx" / "OSO_2018_tab05.xlsx", header=2, dtype={"Kód obce": str})
    df = df.dropna(subset=["Kód obce"])
    df = df.rename(columns={
        "Kód obce": "obec", "Názov obce": "obec_name", "Meno": "meno", "Priezvisko": "priezvisko",
        "Politický subjekt": "party", "Počet platných hlasov": "votes", "Kandidát": "elected",
    })
    df["key"] = df.meno.map(norm) + "|" + df.priezvisko.map(norm)
    df["votes"] = pd.to_numeric(df.votes, errors="coerce").fillna(0)
    tot = df.groupby("obec").votes.transform("sum")
    df["share"] = df.votes / tot
    df["won"] = df.elected.astype(str).str.startswith("zvolen")
    return df[["obec", "obec_name", "key", "party", "votes", "share", "won"]]


def load_2022() -> pd.DataFrame:
    c = pd.read_csv(RAW / "OSO2022_SK_csv" / "OSO2022_SK_tab0ad.csv", sep="|", dtype=str)
    r = pd.read_csv(RAW / "OSO2022_SK_csv" / "OSO2022_SK_tab05f.csv", sep="|", dtype=str)
    r["P_HL"] = pd.to_numeric(r.P_HL)
    votes = r.groupby(["OBEC", "PC_HL"]).P_HL.sum().rename("votes").reset_index()
    won = r[r.KANDIDAT == "1"][["OBEC", "PC_HL"]].drop_duplicates().assign(won=True)
    t = pd.read_csv(RAW / "OSO2022_SK_csv" / "OSO2022_SK_tab02bf.csv", sep="|", dtype=str)
    t["P_ZAP"] = pd.to_numeric(t.P_ZAP)
    size = t.groupby("OBEC").P_ZAP.sum().rename("voters").reset_index()
    df = c.merge(votes, on=["OBEC", "PC_HL"], how="left").merge(won, on=["OBEC", "PC_HL"], how="left")
    df = df.merge(size, on="OBEC", how="left")
    df["won"] = df.won.fillna(False).astype(bool)
    df = df[df.POZNAMKA.isna()]  # drop withdrawn candidates
    df["votes"] = df.votes.fillna(0)
    df["share"] = df.votes / df.groupby("OBEC").votes.transform("sum")
    df["key"] = df.MENO.map(norm) + "|" + df.PRIEZVISKO.map(norm)
    df["occ_mayor"] = df.ZAMESTNANIE.fillna("").str.lower().str.contains("starost|primátor|primator")
    df["neka"] = df.PS.fillna("").str.split(",").map(lambda xs: any(x.strip() == "001" for x in xs) or xs == [""])
    df["n_parties"] = df.PS.fillna("").str.split(",").map(lambda xs: 0 if xs == [""] or xs == ["001"] else len(xs))
    return df.rename(columns={"OBEC": "obec"})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    a, b = load_2018(), load_2022()
    prev = a.groupby(["obec", "key"]).agg(prev_share=("share", "max"), prev_won=("won", "max")).reset_index()
    df = b.merge(prev, on=["obec", "key"], how="left")
    df["prev_share"] = df.prev_share.fillna(0.0)
    df["ran_prev"] = df.prev_share > 0
    df["inc"] = df.prev_won.fillna(False).astype(bool)
    df["n_cand"] = df.groupby("obec").key.transform("count")
    # incumbent-in-race flag: does the 2018 winner run again?
    df["inc_in_race"] = df.groupby("obec").inc.transform("max")
    cols = ["obec", "PC_HL", "MENO", "PRIEZVISKO", "ZAMESTNANIE", "PS", "voters", "votes", "share", "won",
            "prev_share", "ran_prev", "inc", "occ_mayor", "neka", "n_parties", "n_cand", "inc_in_race"]
    df[cols].to_csv(OUT / "mayors_2022.csv", index=False)
    races = df.groupby("obec").agg(n=("key", "count"), inc=("inc", "max"), voters=("voters", "first"))
    print(f"candidates={len(df)} races={len(races)} contested={int((races.n > 1).sum())}")
    print(f"races with incumbent running={int(races.inc.sum())}; inc win rate (contested)=",
          round(df[df.inc & (df.n_cand > 1)].won.mean(), 3))
    big = races[races.voters >= 10000].index
    sub = df[df.obec.isin(big) & df.inc & (df.n_cand > 1)]
    print(f"towns >=10k voters: races={len(big)} inc running={len(sub)} inc win rate={sub.won.mean():.3f}")
    print("occupation-flag vs name-match agreement:", round((df.occ_mayor == df.inc).mean(), 3))


if __name__ == "__main__":
    main()
