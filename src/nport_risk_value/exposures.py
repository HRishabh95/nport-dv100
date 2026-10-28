"""Per-record exposure vectors for the outcome study (OUTCOME_PROTOCOL.md section 5, OUTCOME_AMENDMENT_1.md M5).

For every audited fund-quarter: E^A (holdings estimate by currency x bucket), E^C (harmonised reported
DV100), E^Craw (as filed), FX weights w_c, and the PRIMARY / BROAD flags. No returns are read.
Writes outcome/exposures_{q}.parquet (wide, one row per record) and outcome/fxw_{q}.parquet (long).

Usage: NRV_V2=1 python src/nport_risk_value/exposures.py 2019q4 ...
"""
import os
import sys
from pathlib import Path

os.environ["NRV_V2"] = "1"  # v2 futures table, as the protocol specifies

import numpy as np
import pandas as pd

import gates

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "data/interim/nport_risk_value/extract"
AU = ROOT / "data/interim/nport_risk_value/audit"
OUT = ROOT / "data/interim/nport_risk_value/outcome"
OUT.mkdir(parents=True, exist_ok=True)
MAPPED = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]
B = gates.B
NODES = np.array([0.25, 1, 5, 10, 30])


def ecb_per_usd():
    """Units of each currency per USD, ECB month-end reference rates (OUTCOME_AMENDMENT_1 M3)."""
    e = pd.read_csv(ROOT / "data/raw/fx/ecb_exr_monthly_eop.csv", usecols=["CURRENCY", "TIME_PERIOD", "OBS_VALUE"])
    p = e.pivot_table(index="TIME_PERIOD", columns="CURRENCY", values="OBS_VALUE")
    x = p.div(p["USD"], axis=0)
    x["EUR"] = 1 / p["USD"]
    x["USD"] = 1.0
    x.index = pd.PeriodIndex(x.index, freq="M")
    return x


def bucket_weights(T):
    """Linear interpolation of a maturity onto the five Item B.3 nodes."""
    T = np.clip(np.asarray(T, float), NODES[0], NODES[-1])
    W = np.zeros((len(T), len(NODES)))
    j = np.clip(np.searchsorted(NODES, T, side="right") - 1, 0, len(NODES) - 2)
    lo, hi = NODES[j], NODES[j + 1]
    a = (T - lo) / (hi - lo)
    W[np.arange(len(T)), j] = 1 - a
    W[np.arange(len(T)), j + 1] += a
    return W


def wide(long, val, prefix):
    """(ACC, CUR, BUCKET) long -> mapped columns {prefix}_{CUR}_{B} and unmapped {prefix}_U_{B}."""
    long = long.copy()
    long["C"] = np.where(long.CUR.isin(MAPPED), long.CUR, "U")
    w = long.pivot_table(index="ACCESSION_NUMBER", columns=["C", "BUCKET"], values=val, aggfunc="sum")
    w.columns = [f"{prefix}_{c}_{b}" for c, b in w.columns]
    cols = [f"{prefix}_{c}_{b}" for c in MAPPED + ["U"] for b in B]
    return w.reindex(columns=cols).fillna(0.0)


def run(q, X):
    fq = pd.read_parquet(AU / "fund_quarters.parquet")
    fq = fq[fq.QUARTER == q].set_index("ACCESSION_NUMBER")
    legs = pd.read_parquet(AU / "legs.parquet")
    legs = legs[legs.QUARTER == q].set_index(["ACCESSION_NUMBER", "CUR"])
    f = pd.read_parquet(EX / f"{q}_funds.parquet")
    f = f[f.ACCESSION_NUMBER.isin(fq.index)]
    accs = set(fq.index)

    # C: reported DV100 by currency x bucket
    irr = pd.read_parquet(EX / f"{q}_irr.parquet")
    irr = irr[irr.ACCESSION_NUMBER.isin(accs)].copy()
    irr["CUR"] = irr.CURRENCY_CODE.str.strip().str.upper()
    rows = []
    for b in B:
        rows.append(pd.DataFrame({"ACCESSION_NUMBER": irr.ACCESSION_NUMBER, "CUR": irr.CUR, "BUCKET": b,
                                  "RAW": pd.to_numeric(irr[f"INTRST_RATE_CHANGE_{b}_DV100"], errors="coerce").fillna(0)}))
    c = pd.concat(rows).groupby(["ACCESSION_NUMBER", "CUR", "BUCKET"], as_index=False).RAW.sum()
    key = pd.MultiIndex.from_frame(c[["ACCESSION_NUMBER", "CUR"]])
    unit = legs.UNIT.reindex(key).fillna("ok").values
    xl = legs.X.reindex(key).values
    sign = c.ACCESSION_NUMBER.map(fq.SIGN_D1).values
    c["HARM"] = c.RAW * sign / np.where(unit == "LOCAL_UNITS", xl, 1.0)

    # A: holdings estimate allocated to buckets by maturity
    est, _ = gates.baseline_parts(q, f, accs)
    est = est[est.EST != 0]
    W = bucket_weights(est.TB.fillna(0).values)
    rows = [pd.DataFrame({"ACCESSION_NUMBER": est.ACCESSION_NUMBER.values, "CUR": est.CUR.values, "BUCKET": b,
                          "A": est.EST.values * W[:, i]}) for i, b in enumerate(B)]
    a = pd.concat(rows)
    a = a[a.A != 0].groupby(["ACCESSION_NUMBER", "CUR", "BUCKET"], as_index=False).A.sum()

    out = pd.concat([wide(a, "A", "A"), wide(c, "HARM", "C"), wide(c, "RAW", "R")], axis=1).fillna(0.0)
    out = out.reindex(sorted(accs)).fillna(0.0)

    # PRIMARY on harmonised currency nets (M5.6)
    n = c.groupby(["ACCESSION_NUMBER", "CUR"]).HARM.sum()
    G = n.abs().groupby(level=0).sum()
    net = n.groupby(level=0).sum()
    nonusd = n[n.index.get_level_values(1) != "USD"].abs().groupby(level=0).sum()
    meta = pd.DataFrame(index=out.index)
    meta["O_C_H"] = (1 - net.abs() / G.replace(0, np.nan)).reindex(meta.index)
    meta["N_SH_H"] = (nonusd.reindex(G.index).fillna(0) / G.replace(0, np.nan)).reindex(meta.index)
    meta["PRIMARY"] = (meta.O_C_H >= 0.20) & (meta.N_SH_H >= 0.10)
    debt = est[est.KIND == "debt"]
    dv = debt.groupby("ACCESSION_NUMBER").EXPO.sum()
    dn = debt[debt.CUR != "USD"].groupby("ACCESSION_NUMBER").EXPO.sum()
    meta["NONUSD_DEBT_SH"] = (dn.reindex(dv.index).fillna(0) / dv.replace(0, np.nan)).reindex(meta.index)
    meta["BROAD"] = meta.NONUSD_DEBT_SH.fillna(0) >= 0.10
    for k in ["FUND_KEY", "QUARTER", "NAV", "CIK", "CRD", "SERIES_NAME", "REGISTRANT_NAME", "STATUS_D1",
              "SIGN_D1", "PARTIAL_COVERAGE", "N_LOCAL_LEGS"]:
        meta[k] = fq[k].reindex(meta.index)
    fi = f.set_index("ACCESSION_NUMBER")
    meta["REPORT_DATE"] = fi.REPORT_DATE_D.reindex(meta.index)
    meta["FILING_DATE"] = fi.FILING_DATE_D.reindex(meta.index)
    meta["FAMILY"] = np.where(meta.CRD.fillna("") != "", "CRD" + meta.CRD.fillna(""), "CIK" + meta.CIK.astype(str))
    pd.concat([meta, out], axis=1).reset_index().rename(columns={"index": "ACCESSION_NUMBER"}) \
        .to_parquet(OUT / f"exposures_{q}.parquet")

    # FX weights (M5.7): non-USD holdings value + net FX forward amounts, over NAV
    h = pd.read_parquet(EX / f"{q}_holdings.parquet", columns=["ACCESSION_NUMBER", "HOLDING_ID", "CURRENCY_CODE",
                                                               "CURRENCY_VALUE"])
    h = h[h.ACCESSION_NUMBER.isin(accs)].copy()
    h["CUR"] = h.CURRENCY_CODE.str.strip().str.upper()
    h["V"] = pd.to_numeric(h.CURRENCY_VALUE, errors="coerce").fillna(0)
    hv = h[~h.CUR.isin(["USD", "", "N/A"])].groupby(["ACCESSION_NUMBER", "CUR"]).V.sum()
    fw = pd.read_parquet(EX / f"{q}_fwd.parquet").merge(h[["HOLDING_ID", "ACCESSION_NUMBER"]], on="HOLDING_ID")
    med = pd.read_parquet(EX / f"{q}_fx.parquet")
    med = med.assign(CUR=med.CURRENCY_CODE.str.strip().str.upper()).groupby("CUR").EXCHANGE_RATE.median()
    med["USD"] = 1.0
    rm = fw.ACCESSION_NUMBER.map(meta.REPORT_DATE).dt.to_period("M")
    legs_fx = []
    for side, s in [("PURCHASED", 1.0), ("SOLD", -1.0)]:
        cur = fw[f"DESC_CURRENCY_{side}"].str.strip().str.upper()
        amt = pd.to_numeric(fw[f"CURRENCY_{side}_AMOUNT"], errors="coerce").abs().fillna(0)
        x = np.array([X.at[m, cc] if (m in X.index and cc in X.columns and pd.notna(X.at[m, cc])) else np.nan
                      for m, cc in zip(rm, cur)])
        x = np.where(np.isnan(x), cur.map(med).values, x)
        legs_fx.append(pd.DataFrame({"ACCESSION_NUMBER": fw.ACCESSION_NUMBER.values, "CUR": cur.values,
                                     "V": s * amt.values / x}))
    fl = pd.concat(legs_fx)
    fl = fl[~fl.CUR.isin(["USD", "", "N/A"]) & np.isfinite(fl.V)].groupby(["ACCESSION_NUMBER", "CUR"]).V.sum()
    w = pd.concat([hv.rename("VH"), fl.rename("VF")], axis=1).fillna(0.0).reset_index()
    nav = w.ACCESSION_NUMBER.map(meta.NAV)
    w["WH"], w["WF"] = w.VH / nav, w.VF / nav
    # OUTCOME_AMENDMENT_2 N2: forward amounts with unit errors -> holdings-only weights, then cap
    gross = (w.WH + w.WF).abs().groupby(w.ACCESSION_NUMBER).transform("sum")
    w["W"] = np.where(gross > 3, w.WH, w.WH + w.WF).clip(-1.5, 1.5)
    w["FWD_DROPPED"] = gross > 3
    w[np.isfinite(w.W)].to_parquet(OUT / f"fxw_{q}.parquet")
    print(q, "records", len(out), "primary", int(meta.PRIMARY.sum()), "broad", int(meta.BROAD.sum()),
          "fx legs", len(w), "fwd unconverted", int(fl.isna().sum()), flush=True)


if __name__ == "__main__":
    X = ecb_per_usd()
    for q in sys.argv[1:]:
        run(q, X)
