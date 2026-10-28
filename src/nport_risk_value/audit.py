"""Source audit of Item B.3 sign and unit conventions per AUDIT_PROTOCOL.md (steps S1-S5).

Usage: NRV_V2=1 python src/nport_risk_value/audit.py
Writes data/interim/nport_risk_value/audit/{fund_quarters,legs,notes}.parquet and audit.json.
No return data is read.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["NRV_V2"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gates  # noqa: E402

ROOT = gates.ROOT
EX = gates.EX
OUT = ROOT / "data/interim/nport_risk_value/audit"
OUT.mkdir(parents=True, exist_ok=True)
B = gates.B
QS = sorted(p.name.split("_")[0] for p in (ROOT / "data/raw/nport").glob("*_nport.zip"))
num = gates.num


def adviser_map():
    rows = []
    for p in sorted((ROOT / "data/interim/nport").glob("ncen_adviser_*.parquet")):
        a = pd.read_parquet(p, columns=["FUND_ID", "ADVISER_TYPE", "CRD_NUM", "ADVISER_NAME", "quarter"])
        a = a[a.ADVISER_TYPE.str.strip().str.lower() == "advisor"].copy()
        a["SERIES_ID"] = a.FUND_ID.str.split("_").str[-1]
        a = a[a.SERIES_ID.str.startswith("S")]
        a = a.sort_values(["SERIES_ID", "CRD_NUM"]).drop_duplicates("SERIES_ID")
        rows.append(a[["SERIES_ID", "CRD_NUM", "ADVISER_NAME", "quarter"]])
    return pd.concat(rows)


def adviser_for(adv, q):
    a = adv[adv.quarter <= q].sort_values("quarter").drop_duplicates("SERIES_ID", keep="last")
    return a.set_index("SERIES_ID")


def quarter(q, adv):
    f, cur = gates.load(q)
    g = gates.gate1_q(q, f, cur)
    g = g[g.A100.fillna(0) > 0].copy()
    irr = pd.read_parquet(EX / f"{q}_irr.parquet")
    irr = irr[irr.ACCESSION_NUMBER.isin(g.index)].copy()
    irr["CUR"] = irr.CURRENCY_CODE.str.strip().str.upper()
    d01 = sum(num(irr[f"INTRST_RATE_CHANGE_{b}_DV01"]).fillna(0) for b in B)
    irr["NET01"] = d01
    # S2: per currency-bucket sign disagreement between DV01 and DV100
    dis = 0
    for b in B:
        x1 = num(irr[f"INTRST_RATE_CHANGE_{b}_DV01"]).fillna(0)
        x100 = num(irr[f"INTRST_RATE_CHANGE_{b}_DV100"]).fillna(0)
        dis = dis + np.where((x1 != 0) & (x100 != 0) & (np.sign(x1) != np.sign(x100)), x100.abs(), 0)
    irr["DIS"] = dis
    s2 = irr.groupby("ACCESSION_NUMBER").agg(NET01=("NET01", "sum"), DIS=("DIS", "sum"))
    g = g.join(s2)
    g["MIXED_SHARE"] = g.DIS / g.G.replace(0, np.nan)

    clean = set(g.index[g.CLEAN == "ok"])
    est, _ = gates.baseline_parts(q, f, clean)
    e = est.groupby("ACCESSION_NUMBER")
    debt = est[est.KIND == "debt"].groupby("ACCESSION_NUMBER")
    g["EST_NET"] = e.EST.sum().reindex(g.index)
    g["DEBT_VAL"] = debt.EXPO.sum().reindex(g.index).fillna(0)
    g["DERIV_NOTL"] = est[est.KIND != "debt"].groupby("ACCESSION_NUMBER").EXPO.sum().reindex(g.index).fillna(0)
    g["SHORT_DEBT"] = est[(est.KIND == "debt") & est.SHORT].groupby("ACCESSION_NUMBER").EXPO.sum() \
        .reindex(g.index).fillna(0)
    g["MBS_DEBT"] = est[(est.KIND == "debt") & est.MBS].groupby("ACCESSION_NUMBER").EXPO.sum() \
        .reindex(g.index).fillna(0)
    g["PLAIN"] = ((g.CLEAN == "ok") & (g.DEBT_VAL >= 0.5 * g.NAV) & (g.DERIV_NOTL < 0.05 * g.DEBT_VAL)
                  & (g.SHORT_DEBT < 0.01 * g.DEBT_VAL) & (g.EST_NET < 0)
                  & (g.EST_NET.abs() >= 0.005 * g.NAV))
    g["PCLASS"] = np.where(g.NET < 0, "R", np.where(g.NET > 0, "F", "Z"))
    g["MAG"] = g.NET.abs() / g.EST_NET.abs()
    g["MAGFLAG"] = (g.MAG < 1 / 3) | (g.MAG > 3)
    k = g.NET.abs() / (100 * g.NET01.abs().replace(0, np.nan))
    g["K"] = k.where(g.MBS_DEBT < 0.20 * g.DEBT_VAL)
    g["KDIR"] = np.where(g.K < 0.995, "+100", np.where(g.K > 1.005, "-100",
                         np.where(g.K.notna(), "LINEAR", "NA")))
    ser = g.FUND_KEY.where(g.FUND_KEY.str.startswith("S"), "")
    a = adviser_for(adv, q)
    g["CRD"] = ser.map(a.CRD_NUM).fillna("")
    g["ADVISER"] = ser.map(a.ADVISER_NAME).fillna("")

    # S4 units, per non-USD leg
    by = est.groupby(["ACCESSION_NUMBER", "CUR"]).EST.sum().rename("EST_C")
    legs = cur[cur.ACCESSION_NUMBER.isin(clean)].set_index(["ACCESSION_NUMBER", "CUR"]).join(by)
    legs = legs.reset_index()
    fx = pd.read_parquet(EX / f"{q}_fx.parquet")
    fx["CURRENCY_CODE"] = fx.CURRENCY_CODE.str.strip().str.upper()
    fx = fx.groupby("CURRENCY_CODE").EXCHANGE_RATE.median()
    legs["X"] = legs.CUR.map(fx)
    legs.loc[legs.CUR == "USD", "X"] = 1.0
    r = legs.DV100.abs() / legs.EST_C.abs().replace(0, np.nan)
    legs["RATIO"] = r
    nonusd = legs.CUR != "USD"
    loc = nonusd & (legs.X >= 20) & (r >= legs.X / 4) & (r <= 4 * legs.X) & (r >= 5)
    legs["UNIT"] = np.where(loc, "LOCAL_UNITS", np.where(nonusd & (r > 20), "UNIT_UNRESOLVED", "ok"))
    legs["G"] = legs.ACCESSION_NUMBER.map(g.G)
    uu = legs[legs.UNIT == "UNIT_UNRESOLVED"].groupby("ACCESSION_NUMBER").DV100.apply(lambda s: s.abs().sum())
    g["UNIT_UNRES_SHARE"] = (uu.reindex(g.index) / g.G).fillna(0)
    g["N_LOCAL_LEGS"] = legs[legs.UNIT == "LOCAL_UNITS"].groupby("ACCESSION_NUMBER").size() \
        .reindex(g.index).fillna(0).astype(int)
    legs["QUARTER"] = q

    # S5 notes
    n = pd.read_parquet(EX / f"{q}_notes.parquet")
    n = n[n.ITEM_NO.str.strip().str.upper().str.startswith("B.3") & n.ACCESSION_NUMBER.isin(g.index)].copy()
    t = n.EXPLANATORY_NOTE.str.lower()
    n["TAG"] = np.select(
        [t.str.contains(r"exclud|do(es)? not (consider|include|reflect|capture)|not included|look.?through|"
                        r"not captured|excluding"),
         t.str.contains(r"increase|decrease|\brise\b|\bfall\b|shift|positive|negative|parallel|upward|downward"),
         t.str.contains(r"currenc|cnh|convert|u\.s\. dollar|usd")],
        ["COVERAGE", "CONVENTION", "CURRENCY"], "OTHER")
    n["QUARTER"] = q
    g["PARTIAL_COVERAGE"] = g.index.isin(n.ACCESSION_NUMBER[n.TAG == "COVERAGE"])
    g["QUARTER"] = q
    print(q, len(g), "clean", len(clean), "plain", int(g.PLAIN.sum()), flush=True)
    return g, legs, n


def majority(sub):
    if len(sub) < 2:
        return None
    vc = sub.value_counts()
    return vc.index[0] if vc.iloc[0] / len(sub) >= 0.90 else None


def infer(G):
    ev = G[G.PLAIN & ~G.MAGFLAG & G.PCLASS.isin(["R", "F"])]
    reg = ev.groupby(["QUARTER", "CIK"]).PCLASS
    adv = ev[ev.CRD != ""].groupby(["QUARTER", "CRD"]).PCLASS
    reg_lists = {k: v for k, v in reg}
    adv_lists = {k: v for k, v in adv}

    def peer(key, lists, idx):
        s = lists.get(key)
        if s is None:
            return None
        return majority(s.drop(index=[i for i in [idx] if i in s.index]))

    # leave-one-out validation on plain evidence
    pred, rule = [], []
    for idx, row in ev.iterrows():
        p = peer((row.QUARTER, row.CIK), reg_lists, idx)
        ru = "registrant"
        if p is None and row.CRD:
            p = peer((row.QUARTER, row.CRD), adv_lists, idx)
            ru = "adviser"
        pred.append(p)
        rule.append(ru if p is not None else None)
    loo = pd.DataFrame({"TRUE": ev.PCLASS, "PRED": pred, "RULE": rule}, index=ev.index)
    covered = loo[loo.PRED.notna()]
    acc = float((covered.PRED == covered.TRUE).mean()) if len(covered) else float("nan")
    accepted = bool(len(covered) >= 200 and acc >= 0.95)

    conv, crule = [], []
    for idx, row in G.iterrows():
        if row.CLEAN != "ok":
            conv.append(None); crule.append("cleaning"); continue
        if row.PLAIN and not row.MAGFLAG and row.PCLASS in ("R", "F"):
            conv.append(row.PCLASS); crule.append("own"); continue
        p, ru = None, None
        if accepted:
            p = peer((row.QUARTER, row.CIK), reg_lists, idx)
            ru = "registrant"
            if p is None and row.CRD:
                p = peer((row.QUARTER, row.CRD), adv_lists, idx)
                ru = "adviser"
        conv.append(p); crule.append(ru if p is not None else "no_evidence")
    G["CONV"] = conv
    G["CONV_RULE"] = crule
    # conflicts: own plain class vs registrant majority
    G["OWN_VS_REG_CONFLICT"] = False
    for idx in ev.index:
        row = G.loc[idx]
        p = peer((row.QUARTER, row.CIK), reg_lists, idx)
        if p is not None and p != row.PCLASS:
            G.loc[idx, "OWN_VS_REG_CONFLICT"] = True
    loo_stats = {"evidence_fund_quarters": int(len(ev)), "predicted": int(len(covered)),
                 "accuracy": acc, "accepted": accepted,
                 "by_rule": {r: {"n": int(len(s)), "accuracy": float((s.PRED == s.TRUE).mean())}
                             for r, s in covered.groupby("RULE")}}
    return G, loo_stats


def status(G):
    st = np.full(len(G), "", dtype=object)
    reason = np.full(len(G), "", dtype=object)
    for i, (idx, r) in enumerate(G.iterrows()):
        if r.CLEAN != "ok":
            reason[i] = "cleaning:" + r.CLEAN
        elif r.MIXED_SHARE >= 0.05:
            reason[i] = "internal_mixed"
        elif r.PLAIN and r.PCLASS == "R" and r.KDIR == "-100":
            reason[i] = "anomaly"
        elif r.PLAIN and r.PCLASS == "Z":
            reason[i] = "zero"
        elif r.CONV is None:
            reason[i] = "no_evidence"
        elif r.UNIT_UNRES_SHARE >= 0.10:
            reason[i] = "units"
        if reason[i]:
            st[i] = "UNRESOLVED"
        elif r.CONV == "R" and r.N_LOCAL_LEGS == 0:
            st[i] = "COMPARABLE_AS_FILED"
        else:
            st[i] = "COMPARABLE_AFTER_TRANSFORM"
    G["STATUS"] = st
    G["REASON"] = reason
    G["SIGN"] = np.where(G.CONV == "F", -1.0, np.where(G.CONV == "R", 1.0, np.nan))
    G.loc[G.STATUS == "UNRESOLVED", "SIGN"] = np.nan
    return G


def pairs_flip(G):
    """Cross-registrant pairs of resolved fund-quarters: opposite raw net sign vs harmonised."""
    out = {}
    R = G[(G.STATUS != "UNRESOLVED") & (G.NET != 0)].copy()
    R["RAW"] = np.sign(R.NET)
    R["HAR"] = np.sign(R.NET * R.SIGN)
    tot = opp_raw = opp_har = flip = 0
    for q, s in R.groupby("QUARTER"):
        n = len(s)
        within = s.groupby("CIK").size()
        tot += n * (n - 1) / 2 - (within * (within - 1) / 2).sum()

        def cross(a_mask):
            a, b = a_mask.sum(), (~a_mask).sum()
            wa = s[a_mask].groupby("CIK").size()
            wb = s[~a_mask].groupby("CIK").size()
            return a * b - (wa * wb.reindex(wa.index).fillna(0)).sum()
        opp_raw += cross(s.RAW > 0)
        opp_har += cross(s.HAR > 0)
        flip += cross(s.CONV == "F")
    out["cross_registrant_pairs"] = float(tot)
    out["opposite_raw_share"] = opp_raw / tot
    out["opposite_harmonised_share"] = opp_har / tot
    out["pairs_whose_offset_conclusion_flips_share"] = flip / tot
    return out


def summarise(G, legs, notes, loo):
    S = {"audit_protocol_sha256": (ROOT / "data/interim/nport_risk_value/AUDIT_PROTOCOL_SHA256").read_text().split()[0],
         "quarters": QS, "fund_quarters_with_ir_fields": int(len(G)), "loo": loo}
    nav = G.NAV.fillna(0)
    for lab, sub in [("all", G), ("multi_currency_offset", G[(G.CLEAN == "ok") & (G.O_C >= 0.2) & (G.N_SH >= 0.1)])]:
        S[lab] = {"n": int(len(sub)),
                  "status_share": sub.STATUS.value_counts(normalize=True).round(4).to_dict(),
                  "status_nav_share": (nav[sub.index].groupby(sub.STATUS).sum() / nav[sub.index].sum()).round(4).to_dict(),
                  "reason_counts": sub.REASON[sub.REASON != ""].value_counts().to_dict(),
                  "conv_rule_counts": sub.CONV_RULE.value_counts().to_dict(),
                  "conv_F_share_of_resolved": float((sub.CONV[sub.STATUS != "UNRESOLVED"] == "F").mean())}
    P = G[G.PLAIN]
    S["plain"] = {"n": int(len(P)), "class": P.PCLASS.value_counts().to_dict(),
                  "mag_flag_share": float(P.MAGFLAG.mean()),
                  "mag_median": float(P.MAG.median()),
                  "direction_by_class": pd.crosstab(P.PCLASS, P.KDIR).to_dict(),
                  "F_share_by_quarter": P[P.PCLASS != "Z"].groupby("QUARTER").PCLASS.apply(
                      lambda s: round(float((s == "F").mean()), 3)).to_dict(),
                  "own_vs_registrant_conflicts": int(G.OWN_VS_REG_CONFLICT.sum())}
    ev = P[~P.MAGFLAG & P.PCLASS.isin(["R", "F"])]
    rq = ev.groupby(["QUARTER", "CIK"]).PCLASS.agg(["size", lambda s: s.value_counts(normalize=True).iloc[0]])
    rq.columns = ["n", "top"]
    big = rq[rq.n >= 3]
    S["plain"]["registrant_quarters_ge3"] = int(len(big))
    S["plain"]["registrant_quarters_ge3_unanimous_share"] = float((big.top == 1).mean())
    # persistence: registrants whose majority convention changes across quarters
    maj = ev.groupby(["CIK", "QUARTER"]).PCLASS.agg(lambda s: s.value_counts().index[0]).reset_index()
    ch = maj.groupby("CIK").PCLASS.nunique()
    S["plain"]["registrants_with_evidence"] = int(len(ch))
    S["plain"]["registrants_switching_convention"] = int((ch > 1).sum())
    top = ev.groupby("CIK").agg(n=("PCLASS", "size"), F=("PCLASS", lambda s: (s == "F").mean()),
                                name=("REGISTRANT_NAME", "last"))
    S["plain"]["largest_F_registrants"] = top[top.F >= 0.9].sort_values("n", ascending=False).head(15) \
        .assign(F=lambda d: d.F.round(3)).to_dict("index")
    S["plain"]["largest_R_registrants"] = top[top.F <= 0.1].sort_values("n", ascending=False).head(10) \
        .assign(F=lambda d: d.F.round(3)).to_dict("index")
    S["units"] = {"legs_tested": int(legs.RATIO.notna().sum()),
                  "unit_counts": legs.UNIT.value_counts().to_dict(),
                  "local_units_by_currency": legs[legs.UNIT == "LOCAL_UNITS"].CUR.value_counts().head(10).to_dict()}
    S["notes"] = {"b3_notes": int(len(notes)), "tags": notes.TAG.value_counts().to_dict(),
                  "fund_quarters_partial_coverage": int(G.PARTIAL_COVERAGE.sum())}
    S["pairs"] = pairs_flip(G)
    return S


def main():
    adv = adviser_map()
    Gs, Ls, Ns = [], [], []
    for q in QS:
        g, l, n = quarter(q, adv)
        Gs.append(g); Ls.append(l); Ns.append(n)
    G = pd.concat(Gs)
    G.index.name = "ACCESSION_NUMBER"
    legs, notes = pd.concat(Ls), pd.concat(Ns)
    G, loo = infer(G)
    G = status(G)
    G.reset_index().to_parquet(OUT / "fund_quarters.parquet")
    legs.to_parquet(OUT / "legs.parquet")
    notes.to_parquet(OUT / "notes.parquet")
    S = summarise(G, legs, notes, loo)
    (OUT / "audit.json").write_text(json.dumps(S, indent=1, default=str))
    print(json.dumps(S, indent=1, default=str))


if __name__ == "__main__":
    main()
