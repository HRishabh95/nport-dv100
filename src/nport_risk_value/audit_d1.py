"""Deviation D1 (AUDIT.md): keep plain R records whose DV100 is above linear (callable-bond negative convexity)
as R instead of UNRESOLVED "anomaly". Adds STATUS_D1, REASON_D1, SIGN_D1 to audit/fund_quarters.parquet
and writes audit/audit_d1.json. Run after audit.py.

Usage: python src/nport_risk_value/audit_d1.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AU = ROOT / "data/interim/nport_risk_value/audit"


def status_d1(G):
    """Frozen-rule status with every "anomaly" record (a plain fund reporting negative DV100 above linear)
    resolved as convention R from its own sign."""
    a = (G.REASON == "anomaly").values
    st = np.where(a, np.where(G.N_LOCAL_LEGS == 0, "COMPARABLE_AS_FILED", "COMPARABLE_AFTER_TRANSFORM"), G.STATUS)
    reason = np.where(a, "", G.REASON.fillna(""))
    sign = np.where(a, 1.0, G.SIGN.astype(float))
    return st, reason, sign


def summary(G):
    def block(S):
        nav = S.NAV.fillna(0)
        res = S[S.STATUS_D1 != "UNRESOLVED"]
        conv = np.where(res.SIGN_D1 == -1, "F", "R")
        return {"n": int(len(S)), "status": S.STATUS_D1.value_counts().to_dict(),
                "status_share": S.STATUS_D1.value_counts(normalize=True).round(4).to_dict(),
                "nav_share": (nav.groupby(S.STATUS_D1).sum() / nav.sum()).round(4).to_dict(),
                "reasons": S.REASON_D1[S.REASON_D1 != ""].value_counts().to_dict(),
                "F_share_resolved": round(float((conv == "F").mean()), 4), "funds": int(S.FUND_KEY.nunique())}
    m = G[(G.CLEAN == "ok") & (G.O_C >= 0.20) & (G.N_SH >= 0.10)]
    res = G[G.STATUS_D1 != "UNRESOLVED"]
    return {"all": block(G), "multi_currency_offset": block(m),
            "F_nav_share_resolved": round(float(res.NAV[res.SIGN_D1 == -1].sum() / res.NAV.sum()), 4),
            "distinct_registrants_resolved": int(res.CIK.nunique())}


def main():
    G = pd.read_parquet(AU / "fund_quarters.parquet")
    G["STATUS_D1"], G["REASON_D1"], G["SIGN_D1"] = status_d1(G)
    G.to_parquet(AU / "fund_quarters.parquet")
    S = summary(G)
    (AU / "audit_d1.json").write_text(json.dumps(S, indent=1, default=str))
    print(json.dumps(S["all"], indent=1, default=str))


if __name__ == "__main__":
    main()
