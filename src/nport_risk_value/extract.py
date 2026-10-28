"""Extract the tables needed for the N-PORT risk-value check (PROTOCOL.md) into parquet.

Usage: python src/nport_risk_value/extract.py 2026q2 2026q3
"""
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/nport"
OUT = ROOT / "data/interim/nport_risk_value/extract"
OUT.mkdir(parents=True, exist_ok=True)


def read(z, name, usecols=None, chunks=False):
    kw = dict(sep="\t", dtype=str, usecols=usecols, quoting=3, keep_default_na=False,
              on_bad_lines="warn", encoding_errors="replace")
    f = z.open(name + ".tsv")
    if chunks:
        return pd.read_csv(f, chunksize=1_000_000, **kw)
    return pd.read_csv(f, **kw)


def run(q):
    z = zipfile.ZipFile(RAW / f"{q}_nport.zip")
    sub = read(z, "SUBMISSION")
    reg = read(z, "REGISTRANT", ["ACCESSION_NUMBER", "CIK", "REGISTRANT_NAME"])
    fri = read(z, "FUND_REPORTED_INFO")
    irr = read(z, "INTEREST_RATE_RISK")
    keep = ["ACCESSION_NUMBER", "SERIES_NAME", "SERIES_ID", "NET_ASSETS", "TOTAL_ASSETS"] + \
        [c for c in fri.columns if c.startswith("CREDIT_SPREAD")]
    fri = fri[keep]
    f = sub.merge(reg, on="ACCESSION_NUMBER", how="left").merge(fri, on="ACCESSION_NUMBER", how="left")
    f = f[f.SUB_TYPE.str.startswith("NPORT-P")]
    f["SERIES_ID"] = f.SERIES_ID.fillna("").str.strip()
    f["CIK"] = f.CIK.fillna("").str.strip()
    f["FUND_KEY"] = f.SERIES_ID.where(f.SERIES_ID != "", "CIK" + f.CIK)
    f.loc[f.FUND_KEY == "CIK", "FUND_KEY"] = "ACC" + f.ACCESSION_NUMBER
    f["REPORT_DATE_D"] = pd.to_datetime(f.REPORT_DATE, format="%d-%b-%Y", errors="coerce")
    f["FILING_DATE_D"] = pd.to_datetime(f.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    n_all = len(f)
    f = f.sort_values(["FUND_KEY", "REPORT_DATE_D", "FILING_DATE_D"]).drop_duplicates("FUND_KEY", keep="last")
    print(q, "filings", n_all, "-> one per fund", len(f))
    accs = set(f.ACCESSION_NUMBER)
    irr = irr[irr.ACCESSION_NUMBER.isin(accs)]
    cs_cols = [c for c in f.columns if c.startswith("CREDIT_SPREAD")]
    cs = f[cs_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    has_cs = (cs != 0).any(axis=1)
    risk_accs = set(irr.ACCESSION_NUMBER) | set(f.ACCESSION_NUMBER[has_cs])
    print(q, "funds with IR rows", irr.ACCESSION_NUMBER.nunique(), "with spread fields", int(has_cs.sum()),
          "union", len(risk_accs))
    f["QUARTER"] = q
    f.to_parquet(OUT / f"{q}_funds.parquet")
    irr.to_parquet(OUT / f"{q}_irr.parquet")
    en = read(z, "EXPLANATORY_NOTE")
    en[en.ACCESSION_NUMBER.isin(accs)].to_parquet(OUT / f"{q}_notes.parquet")

    hcols = ["ACCESSION_NUMBER", "HOLDING_ID", "ISSUER_NAME", "ISSUER_TITLE", "BALANCE", "UNIT",
             "CURRENCY_CODE", "CURRENCY_VALUE", "EXCHANGE_RATE", "PAYOFF_PROFILE", "ASSET_CAT",
             "DERIVATIVE_CAT"]
    parts, fx = [], []
    for ch in read(z, "FUND_REPORTED_HOLDING", hcols, chunks=True):
        e = ch[ch.EXCHANGE_RATE != ""][["CURRENCY_CODE", "EXCHANGE_RATE"]]
        fx.append(e)
        parts.append(ch[ch.ACCESSION_NUMBER.isin(risk_accs)])
    h = pd.concat(parts)
    fxd = pd.concat(fx)
    fxd["EXCHANGE_RATE"] = pd.to_numeric(fxd.EXCHANGE_RATE, errors="coerce")
    fxt = fxd.dropna().groupby("CURRENCY_CODE").EXCHANGE_RATE.median().reset_index()
    fxt.to_parquet(OUT / f"{q}_fx.parquet")
    h.to_parquet(OUT / f"{q}_holdings.parquet")
    ids = set(h.HOLDING_ID)
    print(q, "holdings kept", len(h))
    for t in ["DEBT_SECURITY", "FUT_FWD_NONFOREIGNCUR_CONTRACT", "NONFOREIGN_EXCHANGE_SWAP"]:
        parts = [ch[ch.HOLDING_ID.isin(ids)] for ch in read(z, t, chunks=True)]
        d = pd.concat(parts)
        d.to_parquet(OUT / f"{q}_{t}.parquet")
        print(q, t, len(d))


if __name__ == "__main__":
    for q in sys.argv[1:]:
        run(q)
