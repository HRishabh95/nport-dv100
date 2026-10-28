"""Figures for the N-PORT DV100 sign-convention write-up. Reads audit/outcome outputs only.

Usage: python reports/nport_dv100/figures.py  -> reports/nport_dv100/fig{1,2,3}.png
"""
import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NRV = ROOT / "data/interim/nport_risk_value"
OUT = Path(__file__).resolve().parent
INK, MUTED, GRID = "#1F2937", "#6B7280", "#E5E7EB"
POS, NEG = "#D97706", "#2563EB"   # positive-for-a-long-bond (F), negative (R)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True})
PAPER = False
SRC = "Source: SEC Form N-PORT public data sets 2019q4-2026q3; author's calculations."


def note(fig, text):
    if PAPER:
        return
    w = int(fig.get_figwidth() * 16)
    fig.text(0.01, 0.01, "\n".join(textwrap.wrap(text, w)), fontsize=7.5, color=MUTED, va="bottom")


def fig1():
    fq = pd.read_parquet(NRV / "audit/fund_quarters.parquet")
    p = fq[fq.PLAIN & fq.PCLASS.isin(["R", "F"])]
    byq = p.groupby("QUARTER").PCLASS.apply(lambda s: (s == "F").mean() * 100)
    reg = p.groupby("REGISTRANT_NAME").agg(n=("PCLASS", "size"), f=("PCLASS", lambda s: (s == "F").mean() * 100))
    reg = reg.sort_values("n", ascending=False).head(20).sort_values("f")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    x = np.arange(len(byq))
    a.bar(x, 100, color=NEG, width=0.8)
    a.bar(x, byq.values, color=POS, width=0.8)
    st = 8 if PAPER else 4
    a.set_xticks(x[::st]); a.set_xticklabels([q[2:4] + "q" + q[-1] for q in byq.index[::st]])
    a.set_ylim(0, 100); a.set_ylabel("% of plain long-only bond fund-quarters")
    a.set_title("Each quarter, about half report a positive DV100", loc="left", color=INK, fontsize=11)
    from matplotlib.patches import Patch
    a.legend([Patch(color=NEG), Patch(color=POS)], ["Negative (value change if rates rise)", "Positive (rates-fall or magnitude reading)"],
             loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False, fontsize=8.5)
    a.grid(axis="x", visible=False)
    y = np.arange(len(reg))
    b.scatter(reg.f, y, s=np.clip(reg.n / 4, 12, 160), color=[POS if v > 50 else NEG for v in reg.f], zorder=3)
    b.set_yticks(y); b.set_yticklabels([n[:38] for n in reg.index], fontsize=8)
    b.set_xlim(-5, 105); b.set_xlabel("% of plain fund-quarters positive" if PAPER else "% of registrant's plain fund-quarters positive")
    b.set_title("...but within a complex, almost all agree", loc="left", color=INK, fontsize=11)
    if not PAPER:
        fig.suptitle("Figure 1. The sign of N-PORT DV100 depends on who files it", x=0.01, ha="left", fontsize=13, color=INK, weight="bold")
    note(fig, "Plain = long-only, debt >= 50% of NAV, little derivatives; a true +100bp rate rise lowers their value. "
         "53,603 plain fund-quarters. Right: 20 largest registrants by plain fund-quarters. " + SRC)
    fig.tight_layout(rect=(0, 0, 1, 1) if PAPER else (0, 0.07, 1, 0.95))
    fig.savefig(OUT / ("fig1_paper.pdf" if PAPER else "fig1.png"), dpi=200)


def fig2():
    sens = json.loads((NRV / "audit/signcheck_sensitivity.json").read_text())
    s, d1 = sens["frozen"], sens["D1"]
    pr = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.8_pairs"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8))
    v = [100 * s["opposite_raw_share"], 100 * s["opposite_harmonised_share"]]
    a.barh([1, 0], v, color=[POS, NEG], height=0.55)
    a.set_yticks([1, 0]); a.set_yticklabels(["As filed", "Signs harmonised\n(units not converted)"])
    for yy, vv in zip([1, 0], v):
        a.text(vv + 1, yy, f"{vv:.1f}%", va="center", color=INK)
    a.set_xlim(0, 60); a.set_xlabel("% of pairs with opposite net signs" if PAPER else "% of cross-complex fund pairs whose net DV100s have opposite signs")
    a.set_title(f"Apparent rate hedges between funds ({s['cross_registrant_pairs']/1e6:.0f}m pairs)", loc="left", color=INK, fontsize=11)
    a.grid(axis="y", visible=False)
    v2 = [100 * pr["share_differs_raw_vs_C"], 100 * pr["share_differs"]]
    b.barh([1, 0], v2, color=[POS, MUTED], height=0.55)
    b.set_yticks([1, 0]); b.set_yticklabels(["As filed vs signs and\nunits harmonised", "Proposal aggregate vs\nper-currency detail"])
    for yy, vv in zip([1, 0], v2):
        b.text(vv + 1, yy, f"{vv:.1f}%", va="center", color=INK)
    b.set_xlim(0, 60); b.set_xlabel("% of pairs whose class changes" if PAPER else "% of fund pairs whose diversification class changes")
    b.set_title(f"Multi-currency funds ({pr['pairs']:,} pairs)", loc="left", color=INK, fontsize=11)
    b.grid(axis="y", visible=False)
    if not PAPER:
        fig.suptitle("Figure 2. Sign harmonisation changes model-based fund comparisons more than currency detail",
                     x=0.01, ha="left", fontsize=13, color=INK, weight="bold")
    note(fig, "Classes: predicted rate-P&L correlation < -0.3 offsetting, > +0.3 similar, else neutral (60-month yield covariance). "
             "Model-based classifications, not observed investor decisions; neither change is validated by realised returns. "
         f"Left: pairs of resolved fund-quarters, unweighted, frozen audit rule (labelled deviation D1: "
         f"{100*d1['opposite_raw_share']:.1f}% -> {100*d1['opposite_harmonised_share']:.1f}% of {d1['cross_registrant_pairs']/1e6:.0f}m pairs). " + SRC)
    fig.tight_layout(rect=(0, 0, 1, 1) if PAPER else (0, 0.09, 1, 0.93))
    fig.savefig(OUT / ("fig2_paper.pdf" if PAPER else "fig2.png"), dpi=200)


def fig3():
    ci = json.loads((NRV / "outcome/posthoc_rawcost_ci_conf.json").read_text())["broad"]["B"]
    mse = json.loads((NRV / "outcome/posthoc_mse_conf.json").read_text())["broad"]
    br = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.1_broad"]
    rows = [("Harmonising signs and units\n(as filed -> harmonised)\u2020", 100 * mse["raw_cost_B"], [100 * x for x in ci], POS),
            ("Adding per-currency detail\n(proposal aggregate -> full)", 100 * br["dMSE_CB"],
             [100 * x for x in br["ci_conservative"]["dMSE_CB"]], MUTED)]
    fig, a = plt.subplots(figsize=(9, 3.4))
    for yy, (lab, v, (lo, hi), c) in zip([1, 0], rows):
        a.barh(yy, v, color=c, height=0.5)
        a.errorbar(v, yy, xerr=[[v - lo], [hi - v]], fmt="none", ecolor=INK, capsize=4, lw=1.2)
        a.text(hi + 0.4, yy, f"{v:.1f}%  [{lo:.1f}, {hi:.1f}]", va="center", color=INK)
    a.set_yticks([1, 0]); a.set_yticklabels([r[0] for r in rows])
    a.set_xlim(0, 20); a.axvline(0, color=MUTED, lw=0.8)
    a.set_xlabel("Reduction in conditional prediction error (MSE) of monthly fund returns, %")
    a.grid(axis="y", visible=False)
    if not PAPER:
        fig.suptitle("Figure 3 (secondary). Harmonising signs and units vs adding currency detail", x=0.01, ha="left",
                     fontsize=13, color=INK, weight="bold")
    note(fig, f"Broad population: {br['n_fund_months']:,} fund-months, {br['n_funds']} funds with >= 10% non-USD debt, "
             "confirmation sample. Exposures disclosed before each month, priced at that month's realised yield and factor moves; "
             "not a tradable forecast. 95% intervals: worse of month and family bootstraps; \u2020interval computed after the frozen run; sign and unit effects are not separated. "
             "The pre-registered primary test (proposal-relevant funds) was inconclusive. " + SRC)
    fig.tight_layout(rect=(0, 0, 1, 1) if PAPER else (0, 0.15, 1, 0.92))
    fig.savefig(OUT / ("fig3_paper.pdf" if PAPER else "fig3.png"), dpi=200)


if __name__ == "__main__":
    for PAPER in (False, True):
        plt.rcParams["font.size"] = 12.5 if PAPER else 10
        fig1(); fig2(); fig3()
