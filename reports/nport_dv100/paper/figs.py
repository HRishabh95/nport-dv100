"""Publication figures (figs/*.pdf, vector, embedded TrueType) and data-driven LaTeX tables (tables/*.tex).

Every figure is drawn at its printed size (text width 6.4 in) and included at 100% scale, so font sizes are
true points (minimum 8 pt). Reads only frozen audit / outcome / lookup outputs; no new analysis.
Also writes the LinkedIn image ../fig_linkedin_example.png.
Usage: python reports/nport_dv100/paper/figs.py
"""
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
NRV = ROOT / "data/interim/nport_risk_value"
D = Path(__file__).resolve().parent
FIG, TAB = D / "figs", D / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

W = 6.4                      # LaTeX text width, inches
INK, MUTED, GRID = "#1F2937", "#4B5563", "#E5E7EB"
R_COL, F_COL, GREY = "#1D4ED8", "#C2410C", "#9CA3AF"   # rise convention, fall/magnitude convention, neutral
BASE = {"font.family": "Palatino", "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.linewidth": 0.7,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.frameon": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 600}


def _register_fonts():
    """Palatino on macOS is a .ttc collection and matplotlib only reads its first face, so the four faces are
    extracted to a local cache (not committed: Apple-licensed). Falls back to DejaVu Serif elsewhere."""
    ttc = Path("/System/Library/Fonts/Palatino.ttc")
    cache = D / ".fonts"
    if not ttc.exists():
        BASE["font.family"] = "DejaVu Serif"
        return
    from matplotlib import font_manager as fm
    from fontTools.ttLib import TTCollection
    cache.mkdir(exist_ok=True)
    for i, font in enumerate(TTCollection(str(ttc)).fonts):
        out = cache / f"palatino_{i}.ttf"
        if not out.exists():
            font.save(str(out))
        fm.fontManager.addfont(str(out))


_register_fonts()
plt.rcParams.update(BASE)

ABBR = {"Spdr": "SPDR", "Dfa": "DFA", "Jnl": "JNL", "Tiaa-Cref": "TIAA-CREF", "Ssga": "SSGA", "Aim": "AIM",
        "Mfs": "MFS", "Pimco": "PIMCO", "Etf": "ETF", "Ii": "II", "Iii": "III", "Iv": "IV", "Vaneck": "VanEck",
        "Ishares": "iShares", "Bondbloxx": "BondBloxx", "Doubleline": "DoubleLine", "Inc": "", "Inc.": "", "Inc,": ""}


def pretty(name):
    w = [ABBR.get(t, t) for t in str(name).replace(",", " ").title().split()]
    out = " ".join(t for t in w if t).replace("Sa Funds", "SA Funds").replace("/Il", "/IL")
    return out.replace("Self-Indexed Fund Trust", "Self-Indexed").replace(
        "(Invesco Tax-Exempt Funds)", "").strip()


def fq():
    return pd.read_parquet(NRV / "audit/fund_quarters.parquet")


def plain(f):
    return f[f.PLAIN & f.PCLASS.isin(["R", "F"])]


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def money(x):
    return ("+" if x >= 0 else "\u2212") + f"${abs(x):.2f}m"


# ------------------------------------------------------------------ Figure 1: two-fund example
def example_numbers(f):
    names = ["iShares Core U.S. Aggregate Bond ETF", "VANGUARD TOTAL BOND MARKET INDEX FUND"]
    m = f[(f.QUARTER == "2025q4") & f.SERIES_NAME.isin(names)].set_index("SERIES_NAME").loc[names]
    w = 50e6
    a = w * m.NET.iloc[0] / m.NAV.iloc[0] / 1e6       # iShares contribution as filed (positive)
    v = w * m.NET.iloc[1] / m.NAV.iloc[1] / 1e6       # Vanguard contribution as filed (negative)
    return a, v


def fig_example(f, social=False):
    a, v = example_numbers(f)
    rows = [("As filed", "reported figures added", [(a, F_COL, "iShares Core U.S.\nAggregate Bond ETF"),
                                                    (v, R_COL, "Vanguard Total Bond\nMarket Index Fund")]),
            ("Harmonised", "one convention (R)", [(-a, R_COL, "iShares Core U.S.\nAggregate Bond ETF"),
                                                           (v, R_COL, "Vanguard Total Bond\nMarket Index Fund")])]
    k = 1.9 if social else 1.0
    if social:
        fig = plt.figure(figsize=(12, 6.75))
        ax = fig.add_axes([0.25, 0.2, 0.72, 0.5])
    else:
        fig, ax = plt.subplots(figsize=(W, 2.85))
    ys = [1, 0]
    for y, (lab, sub, segs) in zip(ys, rows):
        negl, posl = 0.0, 0.0
        for val, col, name in segs:
            left = posl if val > 0 else negl + val
            ax.barh(y, abs(val), left=left, height=0.56, color=col, edgecolor="white", linewidth=1.2)
            ax.text(left + abs(val) / 2, y, f"{name}\n{money(val)}", ha="center", va="center", color="white",
                    fontsize=8 * k, linespacing=1.15)
            if val > 0:
                posl += val
            else:
                negl += val
        net = sum(s[0] for s in segs)
        ax.plot([net, net], [y - 0.36, y + 0.36], color=INK, lw=1.6 * k)
        ax.text(net + (0.12 if net > 0 else 0), y + 0.43, f"Net {money(net)}", ha="left" if net > 0 else "center",
                va="bottom", fontsize=9.5 * k, weight="bold")
        tr = ax.get_yaxis_transform()
        ax.text(-0.03, y + 0.1, lab, transform=tr, ha="right", va="center", fontsize=9.5 * k, weight="bold")
        ax.text(-0.03, y - 0.14, sub, transform=tr, ha="right", va="center", fontsize=8 * k, color=MUTED)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlim(-6.4, 3.6)
    ax.set_ylim(-0.55, 1.75)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", visible=False)
    ax.set_xticks(np.arange(-6, 4, 1))
    ax.set_xticklabels([("\u2212" if t < 0 else "") + f"{abs(t)}" for t in range(-6, 4)], fontsize=8.5 * k)
    ax.set_xlabel("Change in portfolio value for a parallel +100bp rise in rates ($ million)", fontsize=9 * k)
    if social:
        fig.text(0.03, 0.93, "Similar bonds, opposite signs: a $100m portfolio split 50/50", fontsize=24, weight="bold")
        fig.text(0.03, 0.865, "Two of the largest US bond index funds report their rate sensitivity (DV100) to the SEC "
                 "with opposite signs.\nAdded as filed they look rate-neutral; on one convention the portfolio's "
                 "sensitivity is about \u2212$5.7m.", fontsize=14, color=MUTED, va="top", linespacing=1.3)
        fig.text(0.03, 0.04, "DV100 from SEC Form N-PORT, 2025Q4 data set (report dates Aug/Sep 2025). Illustrative "
                 "DV100-based sensitivities, not realised losses.\nSource: Upadhyay (2026), Same Exposure, Opposite "
                 "Signs: Interest-Rate Risk Reporting Conventions in SEC Form N-PORT.", fontsize=11, color=MUTED,
                 linespacing=1.3)
        fig.savefig(D.parent / "fig_linkedin_example.png", dpi=200)
        plt.close(fig)
    else:
        fig.subplots_adjust(left=0.22, right=0.98, top=0.97, bottom=0.17)
        save(fig, "fig0_example")
    return a + v, -a + v


# ------------------------------------------------------------------ Figure 2: scatter
def fig_scatter(f):
    p = plain(f)
    p = p[~p.MAGFLAG]
    x = (p.EST_NET / p.NAV * 100).clip(-20, 20)
    y = (p.NET / p.NAV * 100).clip(-20, 20)
    fig, a = plt.subplots(figsize=(W, 4.1))
    for cls, c in [("R", R_COL), ("F", F_COL)]:
        m = p.PCLASS == cls
        a.scatter(x[m], y[m], s=2.2, alpha=0.22, color=c, lw=0, rasterized=True)
    g = np.array([-20, 0])
    a.plot(g, g, color=INK, lw=0.8, ls=(0, (4, 3)))
    a.plot(g, -g, color=INK, lw=0.8, ls=(0, (4, 3)))
    a.axhline(0, color=MUTED, lw=0.6)
    a.text(-0.6, -18.6, "Dashed lines: reported = estimate and reported = \u2212estimate", fontsize=8.5,
           ha="right", va="center", color=MUTED)
    nF, nR = int((p.PCLASS == "F").sum()), int((p.PCLASS == "R").sum())
    a.text(-1.0, 13.5, f"Convention F: reported positive\n{nF:,} fund-quarters", color=F_COL, ha="right",
           fontsize=9, weight="bold")
    a.text(-1.0, -14.5, f"Convention R: reported negative\n{nR:,} fund-quarters", color=R_COL, ha="right",
           fontsize=9, weight="bold")
    a.set_xlim(-20, 0.8)
    a.set_ylim(-20, 20)
    a.set_xlabel("DV100 estimated from the fund's own holdings (% of net assets, change for a +100bp rise)")
    a.set_ylabel("Reported DV100 (% of net assets)")
    fig.subplots_adjust(left=0.1, right=0.98, top=0.98, bottom=0.12)
    save(fig, "fig1_scatter")


# ------------------------------------------------------------------ Figure 3: share by quarter
def fig_quarters(f):
    p = plain(f)
    byq = p.groupby("QUARTER").PCLASS.apply(lambda s: (s == "F").mean() * 100)
    allf = 100 * (p.PCLASS == "F").mean()
    fig, a = plt.subplots(figsize=(W, 2.3))
    x = np.arange(len(byq))
    edges = np.arange(len(byq) + 1) - 0.5
    a.stairs(np.full(len(byq), 100.0), edges, fill=True, color=R_COL, alpha=0.9, lw=0)
    a.stairs(byq.values, edges, fill=True, color=F_COL, alpha=0.95, lw=0)
    a.axhline(50, color="white", lw=0.8, ls=(0, (3, 2)))
    a.text(x[-1] + 0.7, (byq.values[-1]) / 2, "Positive (F)", color=F_COL, va="center", fontsize=9, weight="bold")
    a.text(x[-1] + 0.7, (100 + byq.values[-1]) / 2, "Negative (R)", color=R_COL, va="center", fontsize=9,
           weight="bold")
    a.text(0.3, 4, f"Positive share: {byq.min():.0f}% to {byq.max():.0f}% each quarter; {allf:.0f}% overall",
           color="white", fontsize=8.5, va="bottom")
    a.set_xlim(-0.5, len(x) - 0.5)
    a.set_ylim(0, 100)
    a.set_yticks([0, 25, 50, 75, 100])
    a.set_xticks(x[::4])
    a.set_xticklabels([q.upper() for q in byq.index[::4]])
    a.set_ylabel("% of plain fund-quarters")
    a.grid(False)
    fig.subplots_adjust(left=0.09, right=0.83, top=0.97, bottom=0.14)
    save(fig, "fig2_quarters")
    return byq


# ------------------------------------------------------------------ Figure 4: fund complexes
def fig_complexes(f):
    p = plain(f)
    reg = p.groupby("CIK").agg(name=("REGISTRANT_NAME", "last"), n=("PCLASS", "size"),
                               fs=("PCLASS", lambda s: (s == "F").mean() * 100))
    top = pd.concat([reg[reg.fs > 50].nlargest(8, "n"), reg[reg.fs <= 50].nlargest(8, "n")])
    top = top.sort_values(["fs", "n"], ascending=[True, True])
    fig, a = plt.subplots(figsize=(W, 3.6))
    y = np.arange(len(top))
    a.barh(y, top.fs, color=F_COL, height=0.66, lw=0)
    a.barh(y, 100 - top.fs, left=top.fs, color=R_COL, height=0.66, lw=0)
    for yy, (_, r) in zip(y, top.iterrows()):
        a.text(101.5, yy, f"{int(r.n):,}", va="center", fontsize=8, color=MUTED)
    a.text(101.5, len(top) - 0.2, "Plain fund-\nquarters", va="bottom", fontsize=8, color=MUTED)
    a.set_yticks(y)
    a.set_yticklabels([pretty(n) for n in top.name], fontsize=8.5)
    a.set_xlim(0, 100)
    a.set_xticks([0, 25, 50, 75, 100])
    a.set_xlabel("% of the registrant's plain fund-quarters reporting positive (orange) or negative (blue)")
    a.grid(False)
    a.spines["left"].set_visible(False)
    a.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.37, right=0.89, top=0.9, bottom=0.12)
    save(fig, "fig3_complexes")


# ------------------------------------------------------------------ Figure 5: status
def fig_status():
    a1 = json.loads((NRV / "audit/audit_d1.json").read_text())
    rows = [("All funds, by count", a1["all"]["status_share"]), ("All funds, by net assets", a1["all"]["nav_share"]),
            ("Multi-currency offset funds, by count", a1["multi_currency_offset"]["status_share"]),
            ("Multi-currency offset funds, by net assets", a1["multi_currency_offset"]["nav_share"])]
    cats = [("COMPARABLE_AS_FILED", "Comparable as filed", R_COL),
            ("COMPARABLE_AFTER_TRANSFORM", "Comparable after sign flip / unit conversion", F_COL),
            ("UNRESOLVED", "Unresolved", GREY)]
    fig, a = plt.subplots(figsize=(W, 1.95))
    for i, (lab, s) in enumerate(rows[::-1]):
        left = 0
        for k, cl, c in cats:
            v = 100 * s[k]
            a.barh(i, v, left=left, color=c, height=0.62, lw=0, label=cl if i == 0 else None)
            if v >= 8:
                a.text(left + v / 2, i, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=9,
                       weight="bold")
            left += v
    a.set_yticks(range(len(rows)))
    a.set_yticklabels([r[0] for r in rows[::-1]])
    a.set_xlim(0, 100)
    a.set_xticks([])
    a.spines["bottom"].set_visible(False)
    a.spines["left"].set_visible(False)
    a.tick_params(axis="y", length=0)
    a.grid(False)
    fig.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=3, handlelength=1.2, columnspacing=1.0)
    fig.subplots_adjust(left=0.36, right=0.99, top=0.84, bottom=0.03)
    save(fig, "fig4_status")


# ------------------------------------------------------------------ Figure 6: pairs
def fig_pairs():
    sens = json.loads((NRV / "audit/signcheck_sensitivity.json").read_text())
    pr = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.8_pairs"]
    fr = sens["frozen"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.3))
    panels = [(a, f"(a) Opposite-signed net DV100\n{fr['cross_registrant_pairs'] / 1e6:.0f} million cross-complex pairs",
               ["As filed", "Signs harmonised"], [100 * fr["opposite_raw_share"], 100 * fr["opposite_harmonised_share"]],
               [F_COL, R_COL]),
              (b, f"(b) Diversification class changes\n{pr['pairs']:,} multi-currency pairs",
               ["As filed vs\nharmonised", "Aggregate vs\nper-currency"],
               [100 * pr["share_differs_raw_vs_C"], 100 * pr["share_differs"]], [F_COL, GREY])]
    for ax, title, labels, vals, cols in panels:
        ax.barh([1, 0], vals, color=cols, height=0.58, lw=0)
        for yy, vv in zip([1, 0], vals):
            ax.text(vv + 1.2, yy, f"{vv:.1f}%", va="center", fontsize=9.5, weight="bold")
        ax.set_yticks([1, 0])
        ax.set_yticklabels(labels)
        ax.set_xlim(0, 62)
        ax.set_xticks([0, 20, 40, 60])
        ax.set_xlabel("% of pairs")
        ax.set_title(title, loc="left", fontsize=9)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.16, right=0.98, top=0.8, bottom=0.18, wspace=0.62)
    save(fig, "fig5_pairs")


# ------------------------------------------------------------------ Figure 7: returns
def fig_returns():
    ci = json.loads((NRV / "outcome/posthoc_rawcost_ci_conf.json").read_text())["broad"]["B"]
    mse = json.loads((NRV / "outcome/posthoc_mse_conf.json").read_text())["broad"]
    br = json.loads((NRV / "outcome/result_conf.json").read_text())["results"]["7.1_broad"]
    rows = [("Harmonising signs and units\u2020", 100 * mse["raw_cost_B"], [100 * x for x in ci], F_COL),
            ("Adding per-currency detail", 100 * br["dMSE_CB"], [100 * x for x in br["ci_conservative"]["dMSE_CB"]],
             GREY)]
    fig, a = plt.subplots(figsize=(W, 1.75))
    for yy, (lab, v, (lo, hi), c) in zip([1, 0], rows):
        a.barh(yy, v, color=c, height=0.5, lw=0)
        a.errorbar(v, yy, xerr=[[v - lo], [hi - v]], fmt="none", ecolor=INK, capsize=3, lw=0.9)
        a.text(hi + 0.35, yy, f"{v:.1f}%  [{lo:.1f}, {hi:.1f}]", va="center", fontsize=9)
    a.set_yticks([1, 0])
    a.set_yticklabels([r[0] for r in rows])
    a.set_xlim(0, 18)
    a.set_xlabel("Reduction in conditional prediction error (MSE) of monthly fund returns, %")
    a.grid(axis="y", visible=False)
    a.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.3, right=0.98, top=0.96, bottom=0.25)
    save(fig, "fig6_returns")


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
        lines.append(f"{pretty(r['name']).replace('&', chr(92) + '&')} & {int(r.n):,} & {dom} & "
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
    out = [f"{pretty(n).replace('&', chr(92) + '&')} & {q.upper()} & {a} $\\rightarrow$ {b} & {k} \\\\"
           for n, q, a, b, k in df.head(10).itertuples(index=False)]
    (TAB / "changes.tex").write_text("\n".join(out) + "\n")
    return len(df), df.name.nunique()


def main():
    f = fq()
    face, harm = fig_example(f)
    fig_example(f, social=True)
    fig_scatter(f)
    byq = fig_quarters(f)
    fig_complexes(f)
    fig_status()
    fig_pairs()
    fig_returns()
    ex = tab_example(f)
    tab_complexes(f)
    nch, nreg = tab_changes()
    print(json.dumps({"example": ex, "fig1_face": face, "fig1_harm": harm, "changes_rows": nch,
                      "changes_registrants": nreg, "F_share_min": byq.min(), "F_share_max": byq.max()},
                     indent=1, default=float))


if __name__ == "__main__":
    main()
