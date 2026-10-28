"""Outcome study: does per-currency DV100 change rate-risk assessment beyond holdings and the proposal aggregate?

Implements OUTCOME_PROTOCOL.md (sha fe1c473e) with OUTCOME_AMENDMENT_1.md (sha e6a248e8) and
OUTCOME_AMENDMENT_2.md.

  prep        rate P&L for every approach, factors and FX factor per fund-month (no returns read)
  run dev     development families (sha256 first hex 0-4)
  run conf    confirmation families, once

Outputs in data/interim/nport_risk_value/outcome/.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NRV = ROOT / "data/interim/nport_risk_value"
EX = NRV / "extract"
OUT = NRV / "outcome"
MAPPED = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]
B = ["3MON", "1YR", "5YR", "10YR", "30YR"]
MONTHS = pd.period_range("2016-09", "2026-07", freq="M")
EVAL_START = pd.Period("2019-11", "M")
PERIODS = {"2022": ("2022-01", "2022-12"), "2023": ("2023-01", "2023-12"), "2024": ("2024-01", "2024-12"),
           "2025-26": ("2025-01", "2026-07")}
INSPECTED_Q = {"2026q2", "2026q3"}
CHECK_FUNDS = {
    "Eaton Vance Global Macro Absolute Return Advantage Portfolio", "BlackRock Tactical Opportunities Fund",
    "Campbell Systematic Macro Fund", "T. Rowe Price Dynamic Global Bond Fund",
    "Transamerica JPMorgan Asset Allocation - Moderate VP", "PIMCO Long Duration Credit Bond Portfolio",
    "JPMorgan Strategic Income Opportunities Fund", "American Funds Inflation Linked Bond Fund",
    "iShares Global Govt Bond USD Hedged ETF",  # OUTCOME_AMENDMENT_2 N1
}
# CHECK.md uses display names; these three are filed under other names (or have no resolved record),
# so they are also excluded by series ID: EV Global Macro Absolute Return Advantage Portfolio,
# JPMorgan Strategic Income Opportunities, iShares Global Government Bond USD Hedged Active ETF.
CHECK_KEYS = {"S000029761", "S000022994", "S000092377"}
SEED_PLACEBO = 20261027
SEED_BOOT = 20261028
NBOOT = 2000
APPROACHES = ["A", "B", "C", "Braw", "Craw", "Bmix", "Cplac"]


# ---------------------------------------------------------------- inputs (no returns)
def load_records():
    e = pd.concat(pd.read_parquet(p) for p in sorted(OUT.glob("exposures_*.parquet")))
    e = e[(e.STATUS_D1 != "UNRESOLVED") & (e.NAV > 0)].reset_index(drop=True)
    e["RD_M"] = e.REPORT_DATE.dt.to_period("M")
    e["FD_M"] = e.FILING_DATE.dt.to_period("M")
    e["HASH"] = e.FAMILY.map(lambda s: hashlib.sha256(s.encode()).hexdigest()[0])
    e["DEV"] = e.HASH.isin(list("01234"))
    return e


def yields():
    y = pd.read_parquet(NRV / "yields_monthly.parquet")
    y["MONTH"] = pd.PeriodIndex(y.MONTH, freq="M")
    DY = np.full((len(MONTHS), len(MAPPED), len(B)), np.nan)
    for i, c in enumerate(MAPPED):
        for j, b in enumerate(B):
            s = y[(y.CUR == c) & (y.BUCKET == b)].set_index("MONTH").Y
            s = s.reindex(pd.period_range(MONTHS[0] - 1, MONTHS[-1], freq="M")).ffill(limit=1)
            DY[:, i, j] = (100 * s.diff()).reindex(MONTHS).values
    return DY


def factors():
    b = pd.read_parquet(ROOT / "data/interim/daily_bars.parquet", columns=["symbol", "ts", "close"],
                        filters=[("symbol", "in", ["ACWI", "HYG", "IEI"])])
    b["M"] = b.ts.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.to_period("M")
    px = b.sort_values("ts").groupby(["M", "symbol"]).close.last().unstack()
    r = 100 * px.pct_change()
    return pd.DataFrame({"ACWI": r.ACWI, "CREDIT": r.HYG - 0.8 * r.IEI}).reindex(MONTHS)


def fx_returns(source):
    """Monthly USD return (%) of holding each currency, indexed by month, columns currency."""
    if source == "ecb":
        e = pd.read_csv(ROOT / "data/raw/fx/ecb_exr_monthly_eop.csv", usecols=["CURRENCY", "TIME_PERIOD", "OBS_VALUE"])
        p = e.pivot_table(index="TIME_PERIOD", columns="CURRENCY", values="OBS_VALUE")
        X = p.div(p["USD"], axis=0)
        X["EUR"] = 1 / p["USD"]
        X = X.drop(columns="USD")
        X.index = pd.PeriodIndex(X.index, freq="M")
    else:  # frozen N-PORT median rule (sensitivity 7.10)
        t = pd.read_parquet(NRV / "fx/nport_fx_monthly.parquet")
        X = t[t.OK].pivot_table(index="M", columns="CUR", values="median")
    X = X.reindex(pd.period_range("2019-01", "2026-09", freq="M"))
    return 100 * (X.shift(1) / X - 1)


def assign(e, timing):
    """Fund-month -> record under a timing rule (protocol section 3, amendment M5.1)."""
    if timing == "primary":
        av = e.FD_M + 1
    elif timing == "avail60":
        av = pd.concat([e.FILING_DATE, e.REPORT_DATE + pd.Timedelta(days=60)], axis=1).max(axis=1) \
            .dt.to_period("M") + 1
    else:  # decomposition: month after REPORT_DATE
        av = e.RD_M + 1
    rows = []
    for k in range(10):
        m = av + k
        ok = (m <= e.RD_M + 9) & (m <= MONTHS[-1])
        rows.append(pd.DataFrame({"REC": e.index[ok], "M": m[ok]}))
    fm = pd.concat(rows)
    fm["FUND_KEY"] = e.FUND_KEY.values[fm.REC]
    fm["RD"] = e.REPORT_DATE.values[fm.REC]
    fm["FD"] = e.FILING_DATE.values[fm.REC]
    fm = fm.sort_values(["FUND_KEY", "M", "RD", "FD"]).drop_duplicates(["FUND_KEY", "M"], keep="last")
    return fm[["FUND_KEY", "M", "REC"]].reset_index(drop=True)


def arrays(e):
    def grid(p):
        return e[[f"{p}_{c}_{b}" for c in MAPPED for b in B]].values.reshape(len(e), len(MAPPED), len(B))

    def un(p):
        return e[[f"{p}_U_{b}" for b in B]].values
    EA, EC, ER = grid("A"), grid("C"), grid("R")
    UA, UC, UR = un("A"), un("C"), un("R")
    totC = EC.sum(1) + UC
    totR = ER.sum(1) + UR
    zero = np.zeros_like(EA)
    return {"A": (EA, UA), "B": (EA, totC - EA.sum(1)), "C": (EC, UC), "Braw": (EA, totR - EA.sum(1)),
            "Craw": (ER, UR), "Bmix": (zero, totC), "Cplac": (EC, UC)}, np.abs(EA)


def price(EM, U, mixw, DYm, DYm_mapped=None):
    """Rate P&L in USD for rows: mapped legs at their own Delta y, the rest at the record's mix."""
    av = ~np.isnan(DYm)
    dy = np.nan_to_num(DYm)
    w = mixw * av
    sw = w.sum(1)
    mix = np.where(sw > 0, (w * dy).sum(1) / np.where(sw > 0, sw, 1), np.nan_to_num(DYm[:, 0, :]))
    own = DYm if DYm_mapped is None else DYm_mapped
    av_own = ~np.isnan(own)
    mapped = (EM * np.nan_to_num(own) * av_own).sum((1, 2))
    moved = (EM * ~av_own).sum(1)
    return mapped + ((U + moved) * mix).sum(1)


def prep():
    e = load_records()
    DY = yields()
    rng = np.random.default_rng(SEED_PLACEBO)
    perm = np.array([rng.permutation(len(MAPPED)) for _ in MONTHS])
    DYp = np.stack([DY[t][perm[t]] for t in range(len(MONTHS))])
    fac = factors()
    sets, mixw = arrays(e)
    midx = {m: i for i, m in enumerate(MONTHS)}
    fxw = pd.concat(pd.read_parquet(p) for p in sorted(OUT.glob("fxw_*.parquet")))
    fxw = fxw[fxw.ACCESSION_NUMBER.isin(set(e.ACCESSION_NUMBER))]
    acc2rec = pd.Series(e.index, index=e.ACCESSION_NUMBER)
    fxw["REC"] = fxw.ACCESSION_NUMBER.map(acc2rec)
    fxr = {s: fx_returns(s) for s in ["ecb", "nport"]}
    for timing in ["primary", "avail60", "decomp"]:
        fm = assign(e, timing)
        fm = fm[fm.M >= EVAL_START - 36].reset_index(drop=True)
        t = fm.M.map(midx).values
        rec = fm.REC.values
        nav = e.NAV.values[rec]
        for k in APPROACHES:
            EM, U = sets[k]
            fm[f"P_{k}"] = price(EM[rec], U[rec], mixw[rec], DY[t], DYp[t] if k == "Cplac" else None) / nav
        fm["ACWI"] = fac.ACWI.reindex(fm.M).values
        fm["CREDIT"] = fac.CREDIT.reindex(fm.M).values
        fm["DUS10"] = DY[t, 0, 3]
        fm["DINT10"] = DY[t, 1:, 3].mean(1)
        for s, R in fxr.items():
            L = fm[["REC", "M"]].reset_index().merge(fxw[["REC", "CUR", "W"]], on="REC")
            Rl = R.stack().rename("FXR").reset_index().rename(columns={"level_0": "M", "level_1": "CUR"})
            Rl.columns = ["M", "CUR", "FXR"]
            L = L.merge(Rl, on=["M", "CUR"], how="left")
            fm[f"FX_{s}"] = (L.W * L.FXR.fillna(0)).groupby(L["index"]).sum().reindex(fm.index).fillna(0).values
            Lw = L.assign(AW=L.W.abs())
            fm[f"FXZERO_{s}"] = (Lw.AW * Lw.FXR.isna()).groupby(Lw["index"]).sum().reindex(fm.index).fillna(0).values
            fm[f"FXABS_{s}"] = Lw.AW.groupby(Lw["index"]).sum().reindex(fm.index).fillna(0).values
        fm.to_parquet(OUT / f"fundmonths_{timing}.parquet")
        print(timing, "fund-months", len(fm), "funds", fm.FUND_KEY.nunique(), flush=True)
    keep = ["ACCESSION_NUMBER", "FUND_KEY", "QUARTER", "FAMILY", "DEV", "PRIMARY", "BROAD", "SERIES_NAME",
            "REGISTRANT_NAME", "NAV", "PARTIAL_COVERAGE", "N_LOCAL_LEGS", "RD_M", "FD_M", "O_C_H", "N_SH_H"]
    e[keep].to_parquet(OUT / "records.parquet")


# ---------------------------------------------------------------- returns
def load_returns():
    r = pd.concat(pd.read_parquet(p) for p in sorted(EX.glob("*_returns.parquet")))
    r["RD"] = pd.to_datetime(r.REPORT_DATE, format="%d-%b-%Y", errors="coerce")
    r["FD"] = pd.to_datetime(r.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    rows = []
    for k, lag in [(1, 2), (2, 1), (3, 0)]:
        x = r[["ACCESSION_NUMBER", "FUND_KEY", "RD", "FD"]].copy()
        x["M"] = x.RD.dt.to_period("M") - lag
        x["R"] = pd.to_numeric(r[f"MONTHLY_TOTAL_RETURN{k}"], errors="coerce")
        rows.append(x)
    x = pd.concat(rows).dropna(subset=["R", "M"])
    x = x.groupby(["FUND_KEY", "ACCESSION_NUMBER", "M", "FD"], as_index=False).R.median()
    x = x.sort_values("FD").drop_duplicates(["FUND_KEY", "M"], keep="last")
    return x[["FUND_KEY", "M", "R"]]


def fit(fm, fxcol):
    """Rolling 36-month OLS per fund for every approach at once; returns predictions for eligible months."""
    X_cols = ["ACWI", "CREDIT", fxcol, "DUS10", "DINT10"]
    out = []
    for fk, g in fm.groupby("FUND_KEY", sort=False):
        g = g.sort_values("M")
        ok = g.R.notna() & (g.R.abs() <= 25) & g[X_cols].notna().all(1)
        mi = g.M.astype(int).values if hasattr(g.M, "astype") else None
        Xall = np.column_stack([np.ones(len(g)), g[X_cols].values])
        Yall = np.column_stack([g.R.values - g[f"P_{k}"].values for k in APPROACHES])
        okv = ok.values
        tgt = np.where(g.TARGET.values & okv)[0]
        for i in tgt:
            w = okv & (mi >= mi[i] - 36) & (mi <= mi[i] - 1)
            if w.sum() < 24:
                continue
            beta, *_ = np.linalg.lstsq(Xall[w], Yall[w], rcond=None)
            pred = Xall[i] @ beta
            row = {"FUND_KEY": fk, "M": g.M.values[i], "NTRAIN": int(w.sum())}
            for j, k in enumerate(APPROACHES):
                row[f"e_{k}"] = Yall[i, j] - pred[j]
            out.append(row)
    return pd.DataFrame(out)


def sums_table(d, w=None):
    """Per-row quantities whose sums determine every statistic."""
    D = d.P_C - d.P_B
    Dt = d.e_B - d.e_C
    DAB = d.P_B - d.P_A
    Dr = d.P_Craw - d.P_Braw
    Dp = d.P_Cplac - d.P_B
    Dm = d.P_C - d.P_Bmix
    q = pd.DataFrame({
        "eD": d.e_B * D, "DD": D * D, "eDt": d.e_B * Dt, "DtDt": Dt * Dt,
        "eA2": d.e_A ** 2, "eB2": d.e_B ** 2, "eC2": d.e_C ** 2,
        "eAB": d.e_A * DAB, "ABAB": DAB * DAB,
        "eBr2": d.e_Braw ** 2, "eCr2": d.e_Craw ** 2, "eDr": d.e_Braw * Dr, "DrDr": Dr * Dr,
        "eDp": d.e_B * Dp, "DpDp": Dp * Dp, "eCp2": d.e_Cplac ** 2,
        "eDm": d.e_Bmix * Dm, "DmDm": Dm * Dm, "eBm2": d.e_Bmix ** 2, "n": 1.0,
    }, index=d.index)
    if w is not None:
        q = q.mul(w, axis=0)
    return q


def stats_from(S):
    """Statistics from a dict/Series of sums (works on bootstrap matrices too)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return {
            "theta": S["eD"] / S["DD"], "theta_tilde": S["eDt"] / S["DtDt"],
            "absorbed": 1 - S["DtDt"] / S["DD"],
            "dMSE_CB": 1 - S["eC2"] / S["eB2"], "dMSE_BA": 1 - S["eB2"] / S["eA2"],
            "theta_AB": S["eAB"] / S["ABAB"],
            "rms_D_bp": 100 * np.sqrt(S["DD"] / S["n"]),
            "theta_raw": S["eDr"] / S["DrDr"], "dMSE_CB_raw": 1 - S["eCr2"] / S["eBr2"],
            "theta_placebo": S["eDp"] / S["DpDp"], "dMSE_Cplac_B": 1 - S["eCp2"] / S["eB2"],
            "theta_mixB": S["eDm"] / S["DmDm"], "dMSE_C_Bmix": 1 - S["eC2"] / S["eBm2"],
        }


BOOT_KEYS = ["theta", "theta_tilde", "dMSE_CB", "dMSE_BA", "theta_AB", "theta_raw", "dMSE_CB_raw",
             "theta_placebo", "theta_mixB"]


def boot(q, cl, seed):
    S = q.groupby(cl.values).sum()
    rng = np.random.default_rng(seed)
    n = len(S)
    cnt = rng.multinomial(n, np.full(n, 1 / n), size=NBOOT)
    M = cnt @ S.values
    Sb = {c: M[:, j] for j, c in enumerate(S.columns)}
    st = stats_from(Sb)
    return {k: (float(np.nanpercentile(st[k], 2.5)), float(np.nanpercentile(st[k], 97.5))) for k in BOOT_KEYS}, n


def evaluate(d, weights=None):
    q = sums_table(d, weights)
    S = q.sum()
    point = {k: float(v) for k, v in stats_from(S).items()}
    res = {"n_fund_months": int(len(d)), "n_funds": int(d.FUND_KEY.nunique()), "n_families": int(d.FAMILY.nunique()),
           "n_months": int(d.M.nunique()), "mse_A": float(S.eA2 / S.n), "mse_B": float(S.eB2 / S.n),
           "mse_C": float(S.eC2 / S.n), **point}
    if len(d) < 20:
        return res
    bm, nm = boot(q, d.M.astype(str), SEED_BOOT)
    bf, nf = boot(q, d.FAMILY, SEED_BOOT + 1)
    res["ci_month"], res["ci_family"] = bm, bf
    res["clusters"] = {"months": nm, "families": nf}
    res["ci_conservative"] = {k: (min(bm[k][0], bf[k][0]), max(bm[k][1], bf[k][1])) for k in BOOT_KEYS}
    per = {}
    for p, (a, b) in PERIODS.items():
        s = d[(d.M >= pd.Period(a, "M")) & (d.M <= pd.Period(b, "M"))]
        if len(s):
            Sp = sums_table(s).sum()
            per[p] = {"n": int(len(s)), **{k: float(v) for k, v in stats_from(Sp).items()
                                           if k in ("theta", "dMSE_CB", "theta_tilde", "rms_D_bp")}}
    res["periods"] = per
    lo, hi = res["ci_conservative"]["theta"]
    npos = sum(v["theta"] > 0 for v in per.values())
    if res["theta"] >= 0.5 and lo > 0 and npos >= 3 and res["rms_D_bp"] >= 10:
        verdict = "CURRENCY DETAIL CHANGES RISK ASSESSMENT (incremental calibration)"
    elif hi < 0.5 or res["rms_D_bp"] < 5:
        verdict = "DOES NOT"
    else:
        verdict = "INCONCLUSIVE"
    res["verdict"] = verdict
    res["periods_theta_positive"] = int(npos)
    res["prediction_error_claim_allowed"] = bool(res["ci_conservative"]["dMSE_CB"][0] > 0)
    return res


def run(sample):
    rec = pd.read_parquet(OUT / "records.parquet")
    s6 = set(pd.read_csv(NRV / "audit/s6_sample.csv", dtype=str).FUND_KEY)
    named = set(rec.FUND_KEY[rec.SERIES_NAME.isin(CHECK_FUNDS)]) | CHECK_KEYS
    excluded_funds = s6 | named
    ret = load_returns()
    R = {"sample": sample, "protocol_sha": (NRV / "OUTCOME_PROTOCOL_SHA256").read_text().split()[0],
         "amendment1_sha": (NRV / "OUTCOME_AMENDMENT_1_SHA256").read_text().split()[0],
         "amendment2_sha": (NRV / "OUTCOME_AMENDMENT_2_SHA256").read_text().split()[0],
         "excluded_funds": {"s6": len(s6), "check_named_matched": sorted(rec.SERIES_NAME[rec.FUND_KEY.isin(named)].unique()),
                            "check_keys": sorted(named)}}
    want_dev = sample == "dev"
    results = {}
    for timing, fxcol in [("primary", "FX_ecb"), ("avail60", "FX_ecb"), ("decomp", "FX_ecb"), ("primary", "FX_nport")]:
        fm = pd.read_parquet(OUT / f"fundmonths_{timing}.parquet")
        fm = fm.merge(ret, on=["FUND_KEY", "M"], how="left")
        r = rec.iloc[fm.REC.values]
        for c in ["QUARTER", "FAMILY", "DEV", "PRIMARY", "BROAD", "PARTIAL_COVERAGE", "N_LOCAL_LEGS", "SERIES_NAME"]:
            fm[c] = r[c].values
        fam = fm.FAMILY.isin(set(rec.FAMILY[rec.DEV == want_dev]))
        fmf = fm[fm.FUND_KEY.isin(set(fm.FUND_KEY[fam]))].copy()
        fmf["TARGET"] = (fmf.PRIMARY | fmf.BROAD) & (fmf.M >= EVAL_START)
        pr = fit(fmf, fxcol)
        d = fmf.merge(pr, on=["FUND_KEY", "M"], how="inner")
        d = d[d.FAMILY.isin(set(rec.FAMILY[rec.DEV == want_dev]))]
        base = d[~d.FUND_KEY.isin(excluded_funds)]
        main = base[~base.QUARTER.isin(INSPECTED_Q)]
        tag = f"{timing}/{fxcol}"
        d.to_parquet(OUT / f"pred_{sample}_{timing}_{fxcol}.parquet")
        if tag == "primary/FX_ecb":
            P = main[main.PRIMARY]
            results["primary"] = evaluate(P)
            fz = P.FXZERO_ecb.sum() / P.FXABS_ecb.replace(0, np.nan).sum()
            results["primary"]["fx_exposure_share_zero"] = float(fz)
            results["7.1_broad"] = evaluate(main[main.BROAD])
            fw = 1 / P.groupby("FAMILY").FAMILY.transform("size")
            results["7.5_family_weighted"] = evaluate(P, fw)
            results["7.5_excl_partial_and_converted"] = evaluate(P[~P.PARTIAL_COVERAGE & (P.N_LOCAL_LEGS == 0)])
            results["7.9_inspected_2026q2q3"] = evaluate(base[base.QUARTER.isin(INSPECTED_Q) & base.PRIMARY])
            results["primary"]["coverage"] = {
                "primary_fund_months_with_record": int(((fmf.M >= EVAL_START) & fmf.PRIMARY & fam).sum()),
                "with_return": int(((fmf.M >= EVAL_START) & fmf.PRIMARY & fam & fmf.R.notna()).sum()),
                "evaluated": int(len(P))}
        else:
            results[{"avail60/FX_ecb": "7.3_avail60", "decomp/FX_ecb": "7.4_decomposition",
                     "primary/FX_nport": "7.10_nport_fx"}[tag]] = evaluate(main[main.PRIMARY])
        print(tag, "evaluated primary", int(main.PRIMARY.sum()), flush=True)
    R["results"] = results
    (OUT / f"result_{sample}.json").write_text(json.dumps(R, indent=1, default=str))
    show(R)


def loadings(e):
    """Rate-P&L loadings on the 30 mapped (currency, bucket) cells for B, C and raw C (unmapped -> mix)."""
    sets, mixw = arrays(e)
    sw = mixw.sum(1, keepdims=True)
    usd = np.zeros_like(mixw)
    usd[:, 0, :] = 1.0
    share = np.where(sw > 0, mixw / np.where(sw > 0, sw, 1), usd)
    out = {}
    for k, src in [("B", "B"), ("C", "C"), ("raw", "Craw")]:
        EM, U = sets[src]
        out[k] = (EM + U[:, None, :] * share).reshape(len(e), -1)
    return out


def pairs(sample):
    """Secondary 7.8: predicted rate-P&L correlation of fund pairs under B and C, and what returns did."""
    e = load_records()
    rec = pd.read_parquet(OUT / "records.parquet")
    R = json.loads((OUT / f"result_{sample}.json").read_text())
    excl = set(R["excluded_funds"]["check_keys"]) | set(pd.read_csv(NRV / "audit/s6_sample.csv", dtype=str).FUND_KEY)
    d = pd.read_parquet(OUT / f"pred_{sample}_primary_FX_ecb.parquet")
    eA = d.pivot_table(index="M", columns="FUND_KEY", values="e_A")
    L = loadings(e)
    DY = yields().reshape(len(MONTHS), -1)
    DYf = pd.DataFrame(DY, index=MONTHS)
    want_dev = sample == "dev"
    sel = e.PRIMARY & (e.DEV == want_dev) & ~e.FUND_KEY.isin(excl) & ~e.QUARTER.isin(INSPECTED_Q)
    rows = []
    for q, g in e[sel].groupby("QUARTER"):
        g = g.sort_values("NAV").drop_duplicates("FUND_KEY", keep="last")
        end = g.RD_M.max()
        S = DYf.loc[end - 59:end].cov(min_periods=24).fillna(0).values
        idx = g.index.values
        V = {k: L[k][idx] for k in L}
        C = {k: V[k] @ S @ V[k].T for k in V}
        sd = {k: np.sqrt(np.clip(np.diag(C[k]), 1e-30, None)) for k in C}
        corr = {k: C[k] / np.outer(sd[k], sd[k]) for k in C}
        start = g.FD_M.max() + 1
        win = eA.loc[(eA.index >= start) & (eA.index <= start + 11)]
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if g.FAMILY.iloc[a] == g.FAMILY.iloc[b]:
                    continue
                fa, fb = g.FUND_KEY.iloc[a], g.FUND_KEY.iloc[b]
                rc, nc = np.nan, 0
                if fa in win.columns and fb in win.columns:
                    x = win[[fa, fb]].dropna()
                    nc = len(x)
                    if nc >= 8:
                        rc = x[fa].corr(x[fb])
                rows.append({"QUARTER": q, "A": g.SERIES_NAME.iloc[a], "B": g.SERIES_NAME.iloc[b],
                             "corr_raw": corr["raw"][a, b], "corr_C": corr["C"][a, b], "corr_B": corr["B"][a, b],
                             "realised_eA": rc, "n_common": nc})
    P = pd.DataFrame(rows)
    cls = lambda x: np.where(x < -0.3, "offsetting", np.where(x > 0.3, "similar", "neutral"))
    for k in ["raw", "C", "B"]:
        P[f"class_{k}"] = cls(P[f"corr_{k}"])
    P.to_parquet(OUT / f"pairs_{sample}.parquet")
    diff = P[P.class_B != P.class_C]
    dr = diff.dropna(subset=["realised_eA"])
    opp = dr[np.sign(dr.corr_C) != np.sign(dr.corr_B)]
    res = {"pairs": int(len(P)), "quarters": int(P.QUARTER.nunique()),
           "class_differs_B_vs_C": int(len(diff)), "share_differs": float(len(diff) / max(len(P), 1)),
           "class_differs_raw_vs_C": int((P.class_raw != P.class_C).sum()),
           "share_differs_raw_vs_C": float((P.class_raw != P.class_C).mean()) if len(P) else None,
           "differing_with_realised": int(len(dr)),
           "differing_opposite_sign_predictions": int(len(opp)),
           "opposite_sign_realised_matches_C": int((np.sign(opp.realised_eA) == np.sign(opp.corr_C)).sum()),
           "opposite_sign_realised_matches_B": int((np.sign(opp.realised_eA) == np.sign(opp.corr_B)).sum()),
           "differing_mean_realised_by_class_C": dr.groupby("class_C").realised_eA.mean().round(3).to_dict()}
    top = P.reindex((P.corr_C - P.corr_B).abs().sort_values(ascending=False).index).head(3)
    top.to_csv(OUT / f"pairs_{sample}_chart.csv", index=False)
    R["results"]["7.8_pairs"] = res
    (OUT / f"result_{sample}.json").write_text(json.dumps(R, indent=1, default=str))
    print(json.dumps(res, indent=1))
    print(top[["QUARTER", "A", "B", "corr_raw", "corr_C", "corr_B", "realised_eA", "n_common"]].to_string())


def show(R):
    for k, v in R["results"].items():
        ci = v.get("ci_conservative", {})
        print(f"{k:34s} n={v['n_fund_months']:5d} funds={v['n_funds']:4d} theta={v['theta']:+.3f} "
              f"ci={tuple(round(x, 3) for x in ci.get('theta', (np.nan, np.nan)))} "
              f"dMSE_CB={v['dMSE_CB']:+.4f} ci={tuple(round(x, 4) for x in ci.get('dMSE_CB', (np.nan, np.nan)))} "
              f"thetat={v['theta_tilde']:+.3f} absorbed={v['absorbed']:+.2f} rmsD={v['rms_D_bp']:.1f}bp "
              f"thAB={v['theta_AB']:+.3f} dMSE_BA={v['dMSE_BA']:+.4f} raw={v['theta_raw']:+.3f} "
              f"plac={v['theta_placebo']:+.3f} {v.get('verdict', '')}")
        if "periods" in v:
            print("   periods", {p: (x["n"], round(x["theta"], 3), round(x["dMSE_CB"], 4)) for p, x in v["periods"].items()})


if __name__ == "__main__":
    if sys.argv[1] == "prep":
        prep()
    else:
        run(sys.argv[2])
        pairs(sys.argv[2])
