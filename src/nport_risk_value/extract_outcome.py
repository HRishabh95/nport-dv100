"""Extract the extra N-PORT tables for the outcome study (OUTCOME_PROTOCOL.md + OUTCOME_AMENDMENT_1.md).

  fwd      FX forwards/swaps of study holdings -> extract/{q}_fwd.parquet (no returns)
  returns  MONTHLY_TOTAL_RETURN of every NPORT-P filing -> extract/{q}_returns.parquet

Usage: python src/nport_risk_value/extract_outcome.py fwd 2019q4 ...
"""
import sys
import zipfile

import pandas as pd

from extract import OUT, RAW, read


def fwd(q):
    z = zipfile.ZipFile(RAW / f"{q}_nport.zip")
    ids = set(pd.read_parquet(OUT / f"{q}_holdings.parquet", columns=["HOLDING_ID"]).HOLDING_ID)
    d = pd.concat(ch[ch.HOLDING_ID.isin(ids)] for ch in read(z, "FWD_FOREIGNCUR_CONTRACT_SWAP", chunks=True))
    d.to_parquet(OUT / f"{q}_fwd.parquet")
    print(q, "fwd", len(d), flush=True)


def returns(q):
    z = zipfile.ZipFile(RAW / f"{q}_nport.zip")
    sub = read(z, "SUBMISSION", ["ACCESSION_NUMBER", "SUB_TYPE", "REPORT_DATE", "FILING_DATE"])
    reg = read(z, "REGISTRANT", ["ACCESSION_NUMBER", "CIK"])
    fri = read(z, "FUND_REPORTED_INFO", ["ACCESSION_NUMBER", "SERIES_ID"])
    f = sub[sub.SUB_TYPE.str.startswith("NPORT-P")].merge(reg, on="ACCESSION_NUMBER", how="left") \
        .merge(fri, on="ACCESSION_NUMBER", how="left")
    f["SERIES_ID"] = f.SERIES_ID.fillna("").str.strip()
    f["CIK"] = f.CIK.fillna("").str.strip()
    f["FUND_KEY"] = f.SERIES_ID.where(f.SERIES_ID != "", "CIK" + f.CIK)
    f.loc[f.FUND_KEY == "CIK", "FUND_KEY"] = "ACC" + f.ACCESSION_NUMBER
    r = read(z, "MONTHLY_TOTAL_RETURN")
    r = r[r.ACCESSION_NUMBER.isin(set(f.ACCESSION_NUMBER))]
    r = r.merge(f[["ACCESSION_NUMBER", "FUND_KEY", "REPORT_DATE", "FILING_DATE"]], on="ACCESSION_NUMBER")
    r.to_parquet(OUT / f"{q}_returns.parquet")
    print(q, "return rows", len(r), flush=True)


if __name__ == "__main__":
    fn = {"fwd": fwd, "returns": returns}[sys.argv[1]]
    for q in sys.argv[2:]:
        fn(q)
