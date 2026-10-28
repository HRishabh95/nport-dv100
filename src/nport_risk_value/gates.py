"""Gate 1 (prevalence) and Gate 2 (replaceability) per PROTOCOL.md.

Usage: python src/nport_risk_value/gates.py 2026q2 2026q3
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "data/interim/nport_risk_value/extract"
import os as _os
OUT = ROOT / ("data/interim/nport_risk_value/results_v2" if _os.environ.get("NRV_V2") == "1"
              else "data/interim/nport_risk_value/results")
OUT.mkdir(parents=True, exist_ok=True)
B = ["3MON", "1YR", "5YR", "10YR", "30YR"]

FUT_TABLE = [
    (r"ULTRA BOND|ULTRA LONG|\bWN\b", 17), (r"ULTRA 10|ULTRA T|\bTN\b", 8.5),
    (r"US BOND|LONG BOND|T-BOND|US LONG|30Y", 11.5), (r"10Y|10 YR|\bTY\b", 6.5),
    (r"5Y|5 YR|\bFV\b", 4.2), (r"2Y|2 YR|\bTU\b", 1.9), (r"BUXL", 20), (r"BUND", 8), (r"BOBL", 4.3),
    (r"SCHATZ", 1.9), (r"\bOAT\b", 8), (r"\bBTP\b", 7.5), (r"GILT", 9), (r"\bJGB\b", 7),
    (r"CAN 10|\bCGB\b", 8), (r"AUST 10|AUD 10", 8.5), (r"AUST 3|3YR", 2.8), (r"KOREA 10", 8),
    (r"KOREA 3", 2.8),
    (r"SOFR|EURIBOR|SONIA|EURODOLLAR|FED FUND|BANKERS|\b3M\b|90 DAY", 0.25),
]
# Deviation (post-result, labelled v2 in CHECK.md): spelled-out tenors the frozen table missed.
FUT_TABLE_V2 = [
    (r"ULTRA BOND|ULTRA LONG|\bWN\b|ULTRA U\.?S\.? TREASURY BOND", 17),
    (r"ULTRA 10|ULTRA T|\bTN\b", 8.5),
    (r"BUXL", 20), (r"BUND", 8), (r"BOBL", 4.3), (r"SCHATZ", 1.9), (r"\bOAT\b", 8), (r"\bBTP\b", 7.5),
    (r"GILT", 9), (r"MINI.*JGB|JGB|JAPAN 10", 7),
    (r"BANK BILL|SOFR|EURIBOR|SONIA|EURODOLLAR|FED FUND|BANKERS|\b3M\b|90.DAY|3 MONTH|CORRA|SARON|ESTR|TONA", 0.25),
    (r"(30|20).?(YR|YEAR|Y\b)|US BOND|LONG BOND|T-BOND|US LONG|TREASURY BOND", 11.5),
    (r"10.?(YR|YEAR|Y\b)|\bTY\b", 6.5),
    (r"5.?(YR|YEAR|Y\b)|\bFV\b", 4.2),
    (r"3.?(YR|YEAR|Y\b)", 2.8),
    (r"2.?(YR|YEAR|Y\b)|\bTU\b", 1.9),
]
import os
if os.environ.get("NRV_V2") == "1":
    FUT_TABLE = FUT_TABLE_V2
FUT_RE = [(re.compile(p, re.I), d) for p, d in FUT_TABLE]


def num(s):
    return pd.to_numeric(s, errors="coerce")


def fixed_dur(y, T):
    y = np.maximum(y, 0.001)
    return (1 / y) * (1 - (1 + y / 2) ** (-2 * T))


def fixed_mat(y, D):
    """Inverse of fixed_dur: maturity of a par bond with duration D (OUTCOME_AMENDMENT_1 M5.4)."""
    y = np.maximum(y, 0.001)
    return -np.log(np.maximum(1 - y * D, 1e-9)) / (2 * np.log(1 + y / 2))


# OUTCOME_PROTOCOL.md section 5: futures maturity equivalents for bucket allocation
FUT_MAT = {0.25: 0.25, 1.9: 2, 2.8: 3, 4.2: 5, 4.3: 5, 6.5: 10, 7: 10, 7.5: 10, 8: 10, 8.5: 10, 9: 10,
           11.5: 20, 17: 30, 20: 30}


def load(q):
    f = pd.read_parquet(EX / f"{q}_funds.parquet")
    irr = pd.read_parquet(EX / f"{q}_irr.parquet")
    f["NAV"] = num(f.NET_ASSETS)
    for b in B:
        for k in ["DV01", "DV100"]:
            irr[f"{k}_{b}"] = num(irr[f"INTRST_RATE_CHANGE_{b}_{k}"]).fillna(0)
    irr["DV100"] = irr[[f"DV100_{b}" for b in B]].sum(axis=1)
    irr["ABS100"] = irr[[f"DV100_{b}" for b in B]].abs().sum(axis=1)
    irr["ABS01"] = irr[[f"DV01_{b}" for b in B]].abs().sum(axis=1)
    irr["CUR"] = irr.CURRENCY_CODE.str.strip().str.upper()
    cur = irr.groupby(["ACCESSION_NUMBER", "CUR"], as_index=False)[["DV100", "ABS100", "ABS01"]].sum()
    return f, cur


def gate1_q(q, f, cur):
    acc_nav = f.set_index("ACCESSION_NUMBER").NAV
    g = cur.groupby("ACCESSION_NUMBER").agg(G=("DV100", lambda s: s.abs().sum()),
                                            NET=("DV100", "sum"), A100=("ABS100", "sum"),
                                            A01=("ABS01", "sum"))
    nonusd = cur[cur.CUR != "USD"].groupby("ACCESSION_NUMBER").DV100.apply(lambda s: s.abs().sum())
    g["NONUSD"] = nonusd.reindex(g.index).fillna(0)
    g["NCUR"] = cur.groupby("ACCESSION_NUMBER").size()
    g["NAV"] = acc_nav.reindex(g.index)
    g = g[g.A100 > 0]  # has IR risk fields
    r = pd.Series("ok", index=g.index)
    r[(g.NAV.isna()) | (g.NAV <= 0)] = "nav"
    r[(r == "ok") & (g.G > 0.5 * g.NAV)] = "gross>0.5NAV"
    ratio = g.A100 / g.A01.replace(0, np.nan)
    r[(r == "ok") & ratio.notna() & ((ratio < 30) | (ratio > 300))] = "dv100/dv01 ratio"
    g["CLEAN"] = r
    g["O_C"] = 1 - g.NET.abs() / g.G.replace(0, np.nan)
    g["N_SH"] = g.NONUSD / g.G.replace(0, np.nan)
    g["HID_C"] = (g.CLEAN == "ok") & (g.O_C >= 0.20) & (g.N_SH >= 0.10)

    cs = f.set_index("ACCESSION_NUMBER")
    ig = sum(num(cs[f"CREDIT_SPREAD_{b}_INVEST"]).fillna(0) for b in B)
    ng = sum(num(cs[f"CREDIT_SPREAD_{b}_NONINVEST"]).fillna(0) for b in B)
    s = pd.DataFrame({"IG": ig, "NIG": ng, "NAV": cs.NAV})
    s = s[(s.IG != 0) | (s.NIG != 0)]
    s["GS"] = s.IG.abs() + s.NIG.abs()
    s["CLEAN_S"] = np.where(s.NAV.isna() | (s.NAV <= 0), "nav",
                            np.where(s.GS > 0.005 * s.NAV, "gross>0.005NAV", "ok"))
    s["O_S"] = 1 - (s.IG + s.NIG).abs() / s.GS
    s["HID_S"] = (s.CLEAN_S == "ok") & (s.O_S >= 0.20) & (np.minimum(s.IG.abs(), s.NIG.abs()) >= 0.10 * s.GS)
    out = g.join(s[["IG", "NIG", "GS", "CLEAN_S", "O_S", "HID_S"]], how="outer")
    out["NAV"] = acc_nav.reindex(out.index)
    meta = f.set_index("ACCESSION_NUMBER")[["FUND_KEY", "SERIES_NAME", "REGISTRANT_NAME", "CIK", "REPORT_DATE"]]
    out = out.join(meta)
    out["QUARTER"] = q
    out["HID_C"] = out.HID_C.fillna(False).astype(bool)
    out["HID_S"] = out.HID_S.fillna(False).astype(bool)
    return out


def baseline_q(q, f, accs):
    est, counts = baseline_parts(q, f, accs)
    by = est.groupby(["ACCESSION_NUMBER", "CUR"], as_index=False).EST.sum()
    expo = est.groupby("ACCESSION_NUMBER").EXPO.sum()
    return by, expo, counts


def baseline_parts(q, f, accs):
    """Per-holding estimated DV100 contributions (EST, USD) with KIND, EXPO, SHORT, MBS."""
    h = pd.read_parquet(EX / f"{q}_holdings.parquet")
    h = h[h.ACCESSION_NUMBER.isin(accs)].copy()
    rd = f.set_index("ACCESSION_NUMBER").REPORT_DATE_D
    h["RD"] = h.ACCESSION_NUMBER.map(rd)
    h["VAL"] = num(h.CURRENCY_VALUE).fillna(0)
    h["SGN"] = np.where(h.PAYOFF_PROFILE.str.strip().str.lower() == "short", -1.0, 1.0)
    h["CUR"] = h.CURRENCY_CODE.str.strip().str.upper()
    fx = pd.read_parquet(EX / f"{q}_fx.parquet").set_index("CURRENCY_CODE").EXCHANGE_RATE
    fx = fx.copy()
    fx.index = fx.index.str.strip().str.upper()
    fx["USD"] = 1.0
    counts = {}

    ds = pd.read_parquet(EX / f"{q}_DEBT_SECURITY.parquet")
    d = h.merge(ds, on="HOLDING_ID", how="inner")
    d["MAT"] = pd.to_datetime(d.MATURITY_DATE, format="%d-%b-%Y", errors="coerce")
    counts["debt_rows"] = len(d)
    counts["debt_missing_maturity"] = int(d.MAT.isna().sum())
    d = d[d.MAT.notna()].copy()
    d["T"] = ((d.MAT - d.RD).dt.days / 365.25).clip(lower=0)
    y = num(d.ANNUALIZED_RATE).fillna(0) / 100
    ct = d.COUPON_TYPE.str.strip().str.lower()
    D = np.where(ct == "fixed", fixed_dur(y, d["T"]),
                 np.where(ct == "none", d["T"] / 1.04, np.minimum(d["T"], 0.25)))
    D = np.where(d.ASSET_CAT.str.startswith("ABS-MBS"), np.minimum(D, 6), D)
    D = np.minimum(D, 30)
    d["EST"] = -0.01 * d.VAL * d.SGN * D
    d["EXPO"] = (d.VAL).abs()
    d["SHORT"] = d.SGN < 0
    d["MBS"] = d.ASSET_CAT.str.startswith("ABS-MBS")
    # bucket maturity (OUTCOME_AMENDMENT_1 M5.4): floaters at reset, MBS at duration-equivalent maturity
    tb = np.where((ct != "fixed") & (ct != "none"), np.minimum(d["T"], 0.25), d["T"])
    d["TB"] = np.where(d.MBS, np.minimum(tb, fixed_mat(y, D)), tb)
    parts = [d[["ACCESSION_NUMBER", "CUR", "EST", "EXPO", "SHORT", "MBS", "TB"]].assign(KIND="debt")]

    fu = pd.read_parquet(EX / f"{q}_FUT_FWD_NONFOREIGNCUR_CONTRACT.parquet")
    fu = h[["HOLDING_ID", "ACCESSION_NUMBER", "ISSUER_NAME", "ISSUER_TITLE", "DERIVATIVE_CAT"]].merge(
        fu, on="HOLDING_ID", how="inner")
    fu = fu[fu.DERIVATIVE_CAT.str.strip() == "FUT"].copy()
    txt = (fu.ISSUER_TITLE.fillna("") + " | " + fu.ISSUER_NAME.fillna("")).str.upper()

    def fdur(t):
        for rx, dd in FUT_RE:
            if rx.search(t):
                return dd
        return np.nan
    fu["D"] = txt.map(fdur)
    fu["CUR"] = fu.CURRENCY_CODE.str.strip().str.upper()
    fu["FX"] = fu.CUR.map(fx)
    counts["futures_rows"] = len(fu)
    counts["futures_unmatched"] = int(fu.D.isna().sum())
    counts["futures_no_fx"] = int(fu.FX.isna().sum())
    fu = fu[fu.D.notna() & fu.FX.notna()].copy()
    sg = np.where(fu.PAYOFF_PROFILE.str.strip().str.lower() == "short", -1.0, 1.0)
    notl = num(fu.NOTIONAL_AMOUNT).abs().fillna(0) / fu.FX
    fu["EST"] = -0.01 * notl * sg * fu.D
    fu["EXPO"] = notl
    fu["TB"] = fu.D.map(FUT_MAT)
    parts.append(fu[["ACCESSION_NUMBER", "CUR", "EST", "EXPO", "TB"]].assign(KIND="future"))

    sw = pd.read_parquet(EX / f"{q}_NONFOREIGN_EXCHANGE_SWAP.parquet")
    sw = h[["HOLDING_ID", "ACCESSION_NUMBER", "RD"]].merge(sw, on="HOLDING_ID", how="inner")
    rcv = sw.FIXED_OR_FLOATING_RECEIPT.str.strip().str.lower()
    pay = sw.FIXED_OR_FLOATING_PAYMENT.str.strip().str.lower()
    counts["swap_rows"] = len(sw)
    irs = ((rcv == "fixed") & (pay == "floating")) | ((rcv == "floating") & (pay == "fixed"))
    counts["swap_not_fixed_floating"] = int((~irs).sum())
    sw = sw[irs].copy()
    rcv = rcv[irs]
    sw["CUR"] = sw.CURRENCY_CODE.str.strip().str.upper()
    sw["FX"] = sw.CUR.map(fx)
    counts["swap_no_fx"] = int(sw.FX.isna().sum())
    sw = sw[sw.FX.notna()].copy()
    rcv = rcv[sw.index]
    T = ((pd.to_datetime(sw.TERMINATION_DATE, format="%d-%b-%Y", errors="coerce") - sw.RD).dt.days / 365.25).clip(lower=0).fillna(0)
    fr = np.where(rcv == "fixed", num(sw.FIXED_RATE_RECEIPT), num(sw.FIXED_RATE_PAYMENT))
    fr = pd.Series(fr, index=sw.index).fillna(0) / 100
    D = np.minimum(fixed_dur(fr, T), 30)
    sg = np.where(rcv == "fixed", 1.0, -1.0)
    notl = num(sw.NOTIONAL_AMOUNT).abs().fillna(0) / sw.FX
    sw["EST"] = -0.01 * notl * sg * D
    sw["EXPO"] = notl
    sw["TB"] = T
    parts.append(sw[["ACCESSION_NUMBER", "CUR", "EST", "EXPO", "TB"]].assign(KIND="swap"))

    est = pd.concat(parts)
    est["SHORT"] = est.SHORT.fillna(False).astype(bool)
    est["MBS"] = est.MBS.fillna(False).astype(bool)
    return est, counts


def main(qs):
    g1, pairs_all, counts_all, expo_all = [], [], {}, []
    for q in qs:
        f, cur = load(q)
        g = gate1_q(q, f, cur)
        g1.append(g)
        accs = set(g.index)
        by, expo, counts = baseline_q(q, f, accs)
        counts_all[q] = counts
        expo_all.append(pd.DataFrame({"EXPO": expo, "QUARTER": q}))
        flagged = set(g.index[g.HID_C])
        rep = cur[cur.ACCESSION_NUMBER.isin(flagged)].merge(by, on=["ACCESSION_NUMBER", "CUR"], how="left")
        rep["EST"] = rep.EST.fillna(0)
        rep["G"] = rep.ACCESSION_NUMBER.map(g.G)
        rep["QUARTER"] = q
        pairs_all.append(rep)
        by.assign(QUARTER=q).to_parquet(OUT / f"{q}_baseline_by_currency.parquet")
    g1 = pd.concat(g1)
    g1.index.name = "ACCESSION_NUMBER"
    expo = pd.concat(expo_all)
    g1["DEBT_PROXY"] = expo.EXPO.reindex(g1.index) / g1.NAV
    g1.reset_index().to_parquet(OUT / "gate1_fund_quarters.parquet")
    pairs = pd.concat(pairs_all)
    pairs.to_parquet(OUT / "gate2_pairs.parquet")

    R = {"protocol_sha256": (ROOT / "data/interim/nport_risk_value/PROTOCOL_SHA256").read_text().split()[0]}
    R["baseline_counts"] = counts_all
    ir = g1[g1.A100.fillna(0) > 0]
    R["ir_fund_quarters"] = int(len(ir))
    R["ir_clean_status"] = ir.CLEAN.value_counts().to_dict()
    sp = g1[g1.CLEAN_S.notna()]
    R["spread_fund_quarters"] = int(len(sp))
    R["spread_clean_status"] = sp.CLEAN_S.value_counts().to_dict()
    clean = g1[(g1.CLEAN == "ok") | (g1.CLEAN_S == "ok")]
    funds_clean = clean.FUND_KEY.nunique()
    fl_c = set(g1.FUND_KEY[g1.HID_C])
    fl_s = set(g1.FUND_KEY[g1.HID_S])
    fl = fl_c | fl_s
    navf = g1.groupby("FUND_KEY").NAV.max()
    R["gate1"] = {
        "distinct_funds_with_clean_risk_fields": int(funds_clean),
        "flagged_currency": len(fl_c), "flagged_spread": len(fl_s), "flagged_either": len(fl),
        "share_flagged": len(fl) / funds_clean,
        "flagged_nav_usd_bn": float(navf.reindex(list(fl)).sum() / 1e9),
        "clean_ir_nav_usd_bn": float(navf.reindex(clean.FUND_KEY.unique()).sum() / 1e9),
        "PASS": bool(len(fl) >= 100 or len(fl) / funds_clean >= 0.05),
    }
    for q in qs:
        gq = g1[g1.QUARTER == q]
        R["gate1"][q] = {"clean_ir": int((gq.CLEAN == "ok").sum()), "clean_spread": int((gq.CLEAN_S == "ok").sum()),
                         "hid_c": int(gq.HID_C.sum()), "hid_s": int(gq.HID_S.sum()),
                         "multi_currency_clean": int(((gq.CLEAN == "ok") & (gq.NCUR > 1)).sum()),
                         "nonusd_ge10_clean": int(((gq.CLEAN == "ok") & (gq.N_SH >= 0.10)).sum())}
    # threshold change
    t = g1[(g1.CLEAN == "ok")].copy()
    tf = t.sort_values("QUARTER").groupby("FUND_KEY").last()
    drop = tf[tf.DEBT_PROXY <= 0.50]
    R["threshold"] = {
        "funds_clean_ir_latest": int(len(tf)), "drop_out_proxy_le_50": int(len(drop)),
        "share": len(drop) / len(tf), "drop_nav_usd_bn": float(drop.NAV.sum() / 1e9),
        "total_nav_usd_bn": float(tf.NAV.sum() / 1e9),
        "drop_proxy_le_25": int((tf.DEBT_PROXY <= 0.25).sum()),
        "drop_out_and_hid_c_any_q": int(len(set(drop.index) & fl_c)),
    }
    # gate 2
    p = pairs.copy()
    rho = spearmanr(p.EST, p.DV100).correlation
    p["ERR"] = (p.EST - p.DV100).abs() / p.G
    big = p[p.DV100.abs() >= 0.10 * p.G]
    wrong = big[np.sign(big.EST) != np.sign(big.DV100)]
    fq = p.ACCESSION_NUMBER.nunique()
    # secondary: baseline offset on reported currencies
    agg = p.groupby("ACCESSION_NUMBER").agg(NE=("EST", "sum"), GE=("EST", lambda s: s.abs().sum()))
    agg["OE"] = 1 - agg.NE.abs() / agg.GE.replace(0, np.nan)
    R["gate2"] = {
        "fund_quarters": int(fq), "distinct_funds": int(g1.loc[p.ACCESSION_NUMBER.unique(), "FUND_KEY"].nunique()),
        "pairs": int(len(p)), "spearman": float(rho), "median_err_over_G": float(p.ERR.median()),
        "p75_err": float(p.ERR.quantile(.75)),
        "sign_wrong_fund_quarter_share": wrong.ACCESSION_NUMBER.nunique() / fq,
        "sign_wrong_fund_quarters": int(wrong.ACCESSION_NUMBER.nunique()),
        "baseline_also_offset_ge_0.20_share": float((agg.OE >= 0.20).mean()),
        "REPLACEABLE": bool(rho >= 0.90 and p.ERR.median() <= 0.20),
    }
    # robustness, descriptive: usd-only pairs vs non-usd pairs
    for lab, sub in [("usd_pairs", p[p.CUR == "USD"]), ("nonusd_pairs", p[p.CUR != "USD"])]:
        R["gate2"][lab] = {"n": int(len(sub)), "spearman": float(spearmanr(sub.EST, sub.DV100).correlation),
                           "median_err": float(sub.ERR.median())}
    print(json.dumps(R, indent=1, default=str))
    (OUT / "results.json").write_text(json.dumps(R, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
