"""Pre-outcome check 3 (OUTCOME_AMENDMENT_1.md): coverage of monthly FX returns built from N-PORT EXCHANGE_RATE.

Frozen rule (OUTCOME_PROTOCOL.md section 6): month-end rate = median EXCHANGE_RATE in holdings with that
REPORT_DATE (>= 20 rows), else the FX return is 0. Reads holdings and fund metadata only (no returns).
Writes data/interim/nport_risk_value/fx/nport_fx_monthly.parquet and fx_coverage.json.

Usage: python src/nport_risk_value/fx_coverage.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "data/interim/nport_risk_value/extract"
AU = ROOT / "data/interim/nport_risk_value/audit"
OUT = ROOT / "data/interim/nport_risk_value/fx"
OUT.mkdir(parents=True, exist_ok=True)
QS = sorted(p.name[:6] for p in EX.glob("*_funds.parquet"))
MONTHS = pd.period_range("2019-10", "2026-09", freq="M")


def main():
    fq = pd.read_parquet(AU / "fund_quarters.parquet")
    prim = fq[fq.HID_C & (fq.STATUS_D1 != "UNRESOLVED")]
    prim_acc = set(prim.ACCESSION_NUMBER)
    rates, w = [], []
    for q in QS:
        f = pd.read_parquet(EX / f"{q}_funds.parquet", columns=["ACCESSION_NUMBER", "REPORT_DATE_D", "NET_ASSETS"])
        h = pd.read_parquet(EX / f"{q}_holdings.parquet",
                            columns=["ACCESSION_NUMBER", "CURRENCY_CODE", "EXCHANGE_RATE", "CURRENCY_VALUE"])
        h["CUR"] = h.CURRENCY_CODE.str.strip().str.upper()
        h["M"] = h.ACCESSION_NUMBER.map(f.set_index("ACCESSION_NUMBER").REPORT_DATE_D.dt.to_period("M"))
        e = h[h.EXCHANGE_RATE != ""].copy()
        e["X"] = pd.to_numeric(e.EXCHANGE_RATE, errors="coerce")
        rates.append(e[e.X > 0][["M", "CUR", "X"]])
        p = h[h.ACCESSION_NUMBER.isin(prim_acc) & (h.CUR != "USD") & (h.CUR != "")].copy()
        p["V"] = pd.to_numeric(p.CURRENCY_VALUE, errors="coerce").abs()
        w.append(p.groupby("CUR").V.sum())
    r = pd.concat(rates)
    tab = r.groupby(["CUR", "M"]).X.agg(["median", "size"]).reset_index()
    tab["OK"] = tab["size"] >= 20
    tab.to_parquet(OUT / "nport_fx_monthly.parquet")
    wt = pd.concat(w).groupby(level=0).sum()
    wt = wt / wt.sum()

    ok = tab[tab.OK].set_index(["CUR", "M"])["median"]
    rows = []
    for c in wt.index:
        for m in MONTHS:
            has = (c, m) in ok.index and (c, m - 1) in ok.index
            rows.append({"CUR": c, "M": m, "HAS": has, "W": wt[c]})
    cov = pd.DataFrame(rows)
    per_cur = cov.groupby("CUR").agg(W=("W", "first"), months_ok=("HAS", "sum"), months=("HAS", "size"))
    per_cur["share_zero"] = 1 - per_cur.months_ok / per_cur.months
    per_cur = per_cur.sort_values("W", ascending=False)
    n_cells = len(cov)
    n_zero = int((~cov.HAS).sum())
    R = {
        "months": f"{MONTHS[0]}..{MONTHS[-1]}", "currencies_in_primary": int(len(wt)),
        "currency_month_cells": n_cells, "cells_defaulted_to_zero": n_zero,
        "share_cells_zero": n_zero / n_cells,
        "exposure_weighted_share_zero": float((cov.W * ~cov.HAS).sum() / cov.W.sum()),
        "top20": per_cur.head(20).round(4).reset_index().to_dict("records"),
    }
    # months with no N-PORT report date at all (affects every currency)
    m_any = set(tab.M[tab.OK])
    R["months_without_any_rate"] = [str(m) for m in MONTHS if m not in m_any]
    (OUT / "fx_coverage.json").write_text(json.dumps(R, indent=1, default=str))
    print(json.dumps({k: v for k, v in R.items() if k != "top20"}, indent=1, default=str))
    print(per_cur.head(25).to_string())


if __name__ == "__main__":
    main()
