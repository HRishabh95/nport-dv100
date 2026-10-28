"""Figures (figs/*.pdf) and data-driven LaTeX tables (tables/*.tex) for the working paper.

Reads only frozen audit / outcome / lookup outputs; no new analysis.
Usage: python reports/nport_dv100/paper/figs.py
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
NRV = ROOT / "data/interim/nport_risk_value"
D = Path(__file__).resolve().parent
FIG, TAB = D / "figs", D / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)
INK, MUTED, GRID = "#1F2937", "#6B7280", "#E5E7EB"
POS, NEG, GREY, GREEN = "#D97706", "#2563EB", "#9CA3AF", "#059669"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "legend.frameon": False})


def fq():
    return pd.read_parquet(NRV / "audit/fund_quarters.parquet")


def plain(f):
    return f[f.PLAIN & f.PCLASS.isin(["R", "F"])]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ figures
def fig_scatter(f):
    """Reported vs holdings-estimated DV100 for plain funds: two mirrored clouds (evidence set: no MAGFLAG)."""
    p = plain(f)
    p = p[~p.MAGFLAG]
    x = (p.EST_NET / p.NAV * 100).clip(-25, 25)
    y = (p.NET / p.NAV * 100).clip(-25, 25)
    fig, a = plt.subplots(figsize=(6.4, 5.2))
    for cls, c, lab in [("R", NEG, "Reported negative (R)"), ("F", POS, "Reported positive (F)")]:
        m = p.PCLASS == cls
        a.scatter(x[m], y[m], s=3, alpha=0.18, color=c, lw=0, rasterized=True, label=lab)
    g = np.linspace(-20, 0, 2)
    a.plot(g, g, color=INK, lw=1, ls="--")
    a.plot(g, -g, color=INK, lw=1, ls="--")
    a.text(-17, -14.5, "reported = estimate", rotation=38, fontsize=8.5, color=INK)
    a.text(-17, 14.0, "reported = $-$estimate", rotation=-38, fontsize=8.5, color=INK)
    a.axhline(0, color=MUTED, lw=0.8)
    a.set_xlim(-20, 1)
    a.set_ylim(-20, 20)
    a.set_xlabel("Holdings-estimated DV100, % of NAV (value change if rates rise 100bp)")
    a.set_ylabel("Reported DV100, % of NAV")
    lg = a.legend(loc="lower right", markerscale=5)
    for h in lg.legend_handles:
        h.set_alpha(1)
    save(fig, "fig1_scatter")


def fig_quarters(f):
    p = plain(f)
    byq = p.groupby("QUARTER").PCLASS.apply(lambda s: (s == "F").mean() * 100)
    n = p.groupby("QUARTER").size()
    fig, a = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(byq))
    a.bar(x, 100, color=NEG, width=0.8, label="Negative (R)")
    a.bar(x, byq.values, color=POS, width=0.8, label="Positive (F)")
    a.axhline(50, color="white", lw=1, ls=":")
    a.set_xticks(x[::4])
    a.set_xticklabels([q.upper() for q in byq.index[::4]])
    a.set_ylim(0, 100)
    a.set_ylabel("% of plain bond fund-quarters")
    a.grid(axis="x", visible=False)
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    save(fig, "fig2_quarters")
    return byq, n


def fig_complexes(f):
    p = plain(f)
    reg = p.groupby("REGISTRANT_NAME").agg(n=("PCLASS", "size"), f=("PCLASS", lambda s: (s == "F").mean() * 100))
    reg = reg.sort_values("n", ascending=False).head(25).sort_values(["f", "n"])
    fig, a = plt.subplots(figsize=(6.8, 6.4))
    y = np.arange(len(reg))
    a.scatter(reg.f, y, s=np.clip(reg.n / 5, 12, 200), color=[POS if v > 50 else NEG for v in reg.f], zorder=3)
    a.set_yticks(y)
    a.set_yticklabels([n[:44] for n in reg.index], fontsize=8)
    a.set_xlim(-5, 105)
    a.set_xlabel("% of plain fund-quarters reporting positive")
    save(fig, "fig3_complexes")


def fig_status():
    a1 = json.loads((NRV / "audit/audit_d1.json").read_text())
    rows = [("All funds, by count", a1["all"]["status_share"]), ("All funds, by NAV", a1["all"]["nav_share"]),
            ("Multi-currency offset funds,\nby count", a1["multi_currency_offset"]["status_share"]),
            ("Multi-currency offset funds,\nby NAV", a1["multi_currency_offset"]["nav_share"])]
    cats = [("COMPARABLE_AS_FILED", "Comparable as filed", NEG), ("COMPARABLE_AFTER_TRANSFORM",
            "Comparable after sign flip / unit conversion", POS), ("UNRESOLVED", "Unresolved", GREY)]
    fig, a = plt.subplots(figsize=(7.4, 3.3))
    for i, (lab, s) in enumerate(rows[::-1]):
        left = 0
        for k, cl, c in cats:
            v = 100 * s[k]
            a.barh(i, v, left=left, color=c, height=0.6, label=cl if i == 0 else None)
            if v > 6:
                a.text(left + v / 2, i, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=9)
            left += v
    a.set_yticks(range(len(rows)))
    a.set_yticklabels([r[0] for r in rows[::-1]])
    a.set_xlim(0, 100)
    a.set_xlabel("%")
    a.grid(axis="y", visible=False)
    a.legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=3, fontsize=8.5)
    save(fig, "fig4_status")


def fig_pairs():
    sens = json.loads((NRV / "audit/signcheck_sensitivity.json").read_text())
    pr = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.8_pairs"]
    fr = sens["frozen"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.6, 3.2))
    v = [100 * fr["opposite_raw_share"], 100 * fr["opposite_harmonised_share"]]
    a.barh([1, 0], v, color=[POS, NEG], height=0.55)
    a.set_yticks([1, 0])
    a.set_yticklabels(["As filed", "Signs\nharmonised"])
    a.set_title(f"(a) Opposite-signed pairs\n{fr['cross_registrant_pairs'] / 1e6:.0f}m cross-complex pairs",
                loc="left", fontsize=10, color=INK)
    v2 = [100 * pr["share_differs_raw_vs_C"], 100 * pr["share_differs"]]
    b.barh([1, 0], v2, color=[POS, GREY], height=0.55)
    b.set_yticks([1, 0])
    b.set_yticklabels(["As filed vs\nharmonised", "Aggregate vs\nper-currency"])
    b.set_title(f"(b) Diversification class changes\n{pr['pairs']:,} multi-currency pairs", loc="left",
                fontsize=10, color=INK)
    for ax, vals in [(a, v), (b, v2)]:
        for yy, vv in zip([1, 0], vals):
            ax.text(vv + 1, yy, f"{vv:.1f}%", va="center", color=INK)
        ax.set_xlim(0, 62)
        ax.set_xlabel("% of pairs")
        ax.grid(axis="y", visible=False)
    save(fig, "fig5_pairs")


def fig_returns():
    ci = json.loads((NRV / "outcome/posthoc_rawcost_ci_conf.json").read_text())["broad"]["B"]
    mse = json.loads((NRV / "outcome/posthoc_mse_conf.json").read_text())["broad"]
    br = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.1_broad"]
    rows = [("Harmonising signs and units\n(as filed $\\rightarrow$ harmonised)$^\\dagger$", 100 * mse["raw_cost_B"],
             [100 * x for x in ci], POS),
            ("Adding per-currency detail\n(aggregate $\\rightarrow$ per-currency)", 100 * br["dMSE_CB"],
             [100 * x for x in br["ci_conservative"]["dMSE_CB"]], GREY)]
    fig, a = plt.subplots(figsize=(7.2, 2.8))
    for yy, (lab, v, (lo, hi), c) in zip([1, 0], rows):
        a.barh(yy, v, color=c, height=0.5)
        a.errorbar(v, yy, xerr=[[v - lo], [hi - v]], fmt="none", ecolor=INK, capsize=4, lw=1.2)
        a.text(hi + 0.4, yy, f"{v:.1f}%  [{lo:.1f}, {hi:.1f}]", va="center", color=INK)
    a.set_yticks([1, 0])
    a.set_yticklabels([r[0] for r in rows])
    a.set_xlim(0, 20)
    a.set_xlabel("Reduction in conditional prediction error (MSE), %")
    a.grid(axis="y", visible=False)
    save(fig, "fig6_returns")


def fig_example(f, social=False):
    """Two aggregate index funds with opposite-signed DV100, and a 50/50 $100m portfolio summed two ways."""
    names = ["iShares Core U.S. Aggregate Bond ETF", "VANGUARD TOTAL BOND MARKET INDEX FUND"]
    m = f[(f.QUARTER == "2025q4") & f.SERIES_NAME.isin(names)].set_index("SERIES_NAME").loc[names]
    rep = 100 * m.NET / m.NAV
    est = 100 * m.EST_NET / m.NAV
    w = 50e6
    face = (w * m.NET / m.NAV).sum() / 1e6
    harm = (w * (-m.NET.iloc[0]) / m.NAV.iloc[0] + w * m.NET.iloc[1] / m.NAV.iloc[1]) / 1e6
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.3) if social else (8.6, 3.5),
                               gridspec_kw={"width_ratios": [1.25, 1]})
    lab = ["iShares Core U.S.\nAggregate Bond ETF", "Vanguard Total Bond\nMarket Index Fund"]
    y = np.array([1, 0])
    a.barh(y + 0.18, rep.values, height=0.34, color=[POS, NEG], label="Reported DV100")
    a.barh(y - 0.18, est.values, height=0.34, color=GREY, label="Estimated from holdings")
    for yy, v in zip(y + 0.18, rep.values):
        a.text(v + (0.3 if v > 0 else -0.3), yy, f"{v:+.1f}%".replace("-", "−"), va="center", ha="left" if v > 0 else "right", color=INK)
    for yy, v in zip(y - 0.18, est.values):
        a.text(v - 0.3, yy, f"{v:+.1f}%".replace("-", "−"), va="center", ha="right", color=MUTED)
    a.axvline(0, color=INK, lw=0.8)
    a.set_yticks(y)
    a.set_yticklabels(lab)
    a.set_xlim(-9.5, 9.5)
    a.set_xlabel("DV100, % of net assets (2025Q4 filings)")
    a.set_title("(a) Same kind of bonds, opposite reported signs", loc="left", fontsize=10.5, color=INK)
    a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=8.5)
    a.grid(axis="y", visible=False)
    v = [face, harm]
    b.barh([1, 0], v, color=[POS, NEG], height=0.5)
    b.text(face + 0.25, 1, f"+${face:.2f}m\nlooks rate-neutral", va="center", color=INK, fontsize=9.5)
    b.text(harm / 2, 0, f"−${-harm:.2f}m", va="center", ha="center", color="white", fontsize=11, weight="bold")
    b.axvline(0, color=INK, lw=0.8)
    b.set_yticks([1, 0])
    b.set_yticklabels(["Reported figures\nadded as filed", "Signs\nharmonised"])
    b.set_xlim(-7, 2.5)
    b.set_xlabel("Portfolio DV100, $m")
    b.set_title("(b) $100m split 50/50", loc="left", fontsize=10.5, color=INK)
    b.grid(axis="y", visible=False)
    if social:
        fig.suptitle("Two big bond index funds report the same kind of rate risk with opposite signs",
                     x=0.01, ha="left", fontsize=13, weight="bold", color=INK)
        fig.text(0.01, 0.01, "DV100: reported change in value for a 100bp change in rates (SEC Form N-PORT, 2025Q4 data set). "
                 "\nPortfolio figures are DV100-based sensitivities to a +100bp parallel rise, not realised losses.\n"
                 "Source: SEC Form N-PORT; author's calculations. Paper: Same Exposure, Opposite Signs (Upadhyay, 2026).",
                 fontsize=7.5, color=MUTED, va="bottom")
        fig.tight_layout(rect=(0, 0.1, 1, 0.92))
        fig.savefig(D.parent / "fig_linkedin_example.png", dpi=220)
        plt.close(fig)
    else:
        save(fig, "fig0_example")
    return face, harm


# ------------------------------------------------------------------ tables
def fmt(x, d=1):
    return f"{x:,.{d}f}"


def tab_example(f):
    names = ["iShares Core U.S. Aggregate Bond ETF", "Fidelity U.S. Bond Index Fund", "Schwab U.S. Aggregate Bond ETF",
             "VANGUARD TOTAL BOND MARKET INDEX FUND", "SPDR Portfolio Aggregate Bond ETF"]
    pretty = {"VANGUARD TOTAL BOND MARKET INDEX FUND": "Vanguard Total Bond Market Index Fund"}
    m = f[(f.QUARTER == "2025q4") & f.SERIES_NAME.isin(names)].set_index("SERIES_NAME").loc[names]
    lines = []
    for n, r in m.iterrows():
        rep, est = r.NET / 1e9, r.EST_NET / 1e9
        lines.append(f"{pretty.get(n, n)} & {pd.to_datetime(r.REPORT_DATE).strftime('%b %Y')} & {fmt(r.NAV / 1e9)} & "
                     f"{rep:+,.2f} & {est:+,.2f} & {100 * r.NET / r.NAV:+.1f} & {r.PCLASS} \\\\")
    (TAB / "example.tex").write_text("\n".join(lines) + "\n")
    ag, vg = m.loc[names[0]], m.loc[names[3]]
    # illustrative 50/50 portfolio of $100m: face-value sum vs harmonised
    w = 50e6
    face = w * ag.NET / ag.NAV + w * vg.NET / vg.NAV
    harm = w * (-ag.NET) / ag.NAV + w * vg.NET / vg.NAV
    return {"face_m": face / 1e6, "harm_m": harm / 1e6, "ag_pct": 100 * ag.NET / ag.NAV, "vg_pct": 100 * vg.NET / vg.NAV}


def tab_complexes(f):
    t = pd.read_csv(D.parent / "data/fund_complex_dv100_conventions.csv", dtype={"REGISTRANT_ID": str})
    p = plain(f)
    g = p.groupby("CIK").agg(name=("REGISTRANT_NAME", "last"), n=("PCLASS", "size"),
                             share_f=("PCLASS", lambda s: (s == "F").mean()))
    res = t[t.CONVENTION.isin(["R", "F"])].groupby("REGISTRANT_ID").agg(
        q=("QUARTER", "nunique"), ch=("CHANGED_FROM_PREVIOUS_RESOLVED", "sum"))
    g = g.join(res, how="left").fillna({"q": 0, "ch": 0}).sort_values("n", ascending=False).head(12)
    lines = []
    for cik, r in g.iterrows():
        dom = "F" if r.share_f > 0.5 else "R"
        lines.append(f"{r['name'][:46].replace('&', chr(92) + '&')} & {int(r.n):,} & {dom} & "
                     f"{100 * max(r.share_f, 1 - r.share_f):.1f} & {int(r.q)} & {int(r.ch)} \\\\")
    (TAB / "complexes.tex").write_text("\n".join(lines) + "\n")


def tab_changes():
    t = pd.read_csv(D.parent / "data/fund_complex_dv100_conventions.csv", dtype={"REGISTRANT_ID": str})
    c = t[t.CHANGED_FROM_PREVIOUS_RESOLVED].copy()
    lines = []
    for _, r in c.sort_values(["QUARTER", "REGISTRANT_NAME"]).iterrows():
        prev = t[(t.REGISTRANT_ID == r.REGISTRANT_ID) & (t.QUARTER < r.QUARTER) & t.CONVENTION.isin(["R", "F"])]
        frm = prev.sort_values("QUARTER").CONVENTION.iloc[-1]
        lines.append((r.REGISTRANT_NAME, r.QUARTER, frm, r.CONVENTION, int(r.N_PLAIN_R + r.N_PLAIN_F)))
    df = pd.DataFrame(lines, columns=["name", "q", "frm", "to", "n"])
    out = [f"{n[:46].replace('&', chr(92) + '&')} & {q.upper()} & {a} $\\rightarrow$ {b} & {k} \\\\"
           for n, q, a, b, k in df.head(10).itertuples(index=False)]
    (TAB / "changes.tex").write_text("\n".join(out) + "\n")
    return len(df), df.name.nunique()


def main():
    f = fq()
    fig_example(f)
    fig_example(f, social=True)
    fig_scatter(f)
    byq, n = fig_quarters(f)
    fig_complexes(f)
    fig_status()
    fig_pairs()
    fig_returns()
    ex = tab_example(f)
    tab_complexes(f)
    nch, nreg = tab_changes()
    print(json.dumps({"example": ex, "changes_rows": nch, "changes_registrants": nreg,
                      "F_share_min": byq.min(), "F_share_max": byq.max()}, indent=1, default=float))


if __name__ == "__main__":
    main()
