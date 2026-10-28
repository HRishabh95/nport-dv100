# N-PORT risk-metric value check: result

Question: does the SEC's February 2026 Form N-PORT proposal (IC-35962, File S7-2026-05) take away
information that holdings cannot replace?

Protocol: `src/nport_risk_value/PROTOCOL.md`, sha256 `64dcd246...5c07b82` (in
`data/interim/nport_risk_value/PROTOCOL_SHA256`), frozen before any result was computed.
Code: `extract.py`, `gates.py`. Outputs: `data/interim/nport_risk_value/results/` (frozen run) and
`results_v2/` (labelled deviation, see below). Data: N-PORT data sets 2026q2 and 2026q3 already on disk.

## Verdict: GO-TO-OUTCOME-TEST (outcome test not run)

Gate 1 passes on the count rule. Gate 2 shows the per-currency information is NOT REPLACEABLE from
holdings, even after two changes that favour the baseline. The margin is real but narrower than the
frozen number suggests, and half of the frozen failure comes from filers using opposite sign
conventions (see "Main finding about the data").

## Gate 1: prevalence

| | Value | Threshold | Result |
|---|---|---|---|
| Distinct funds with clean risk fields | 4,258 | | |
| Flagged, currency aggregation hides offsets | 106 funds | | |
| Flagged, IG / non-IG aggregation hides offsets | 61 funds | | |
| Flagged in either dimension | **154 funds** | >= 100 | **PASS** |
| Flagged share | 3.6% | >= 5% | (not met, but the rule is either/or) |
| NAV of flagged funds | $228bn | | 2.1% of $11.0tn risk-reporting NAV |

By quarter: 87 / 83 currency-flagged fund-quarters, 30 / 48 spread-flagged (2026q2 / 2026q3).
About 1,000 clean fund-quarters per quarter report more than one currency, and about 480 have
non-USD share of at least 10%. Cleaning excluded 86 of 8,234 IR fund-quarters (82 DV100/DV01 ratio
outside [30, 300], 4 gross DV100 above 0.5 x NAV) and 7 of 7,511 spread fund-quarters.

Flagged funds are mostly global macro, managed futures, tactical asset allocation and
"USD-hedged" global bond funds: the funds that run relative-value duration trades across markets.

**Threshold 25% to 50%.** Using a one-month debt-exposure proxy (debt holdings plus rate-future and
interest-rate-swap notional, over NAV), 466 of 4,240 risk-reporting funds (11.0%) sit at or below
50%; their NAV is $1.19tn (11.0% of $10.8tn). 17 of them are also currency-flagged. The proxy is
noisy: 117 reporting funds come out below 25%, where they should not have had to report at all.

## Gate 2: replaceability (170 flagged fund-quarters, 106 funds, 2,022 fund-currency pairs)

| | Frozen baseline | v2 futures keywords | Oracle sign-aligned (frozen / v2) | Threshold |
|---|---|---|---|---|
| Spearman, estimated vs reported currency DV100 | **0.277** | 0.284 | 0.805 / 0.837 | >= 0.90 |
| Median abs error / fund gross DV100 | **1.2%** | 1.0% | 0.5% / 0.5% | <= 20% |
| Flagged fund-quarters with a wrong-signed major leg (>= 10% of gross) | **54.1%** | 52.4% | 33.5% / 31.8% | (reported) |
| Baseline also shows offset >= 0.20 | 56.5% | 59.4% | | (descriptive) |

**Result: NOT REPLACEABLE** (Spearman fails; the error test passes). It stays not replaceable under
every sensitivity.

How to read the two tests:
- The median-error test passes easily because most pairs are small emerging-market legs, worth 1-2%
  of gross each. It says nothing about the legs that matter. On legs worth at least 10% of gross
  (511 pairs), the sign-aligned Spearman is 0.88 and the median error is 7-9% of gross.
- Measured at fund level, the sign-aligned baseline gets the whole currency vector within 20% (L1
  error over gross) for only 20% of flagged fund-quarters (31% with v2). The median fund-level error
  is 37-42% of gross.
- The baseline works well for funds whose offsets come from cash bonds and standard bond futures
  (Eaton Vance/Morgan Stanley Global Macro, Transamerica/JPM asset allocation, AQR Multi-Asset, JPM
  Global Allocation: estimates within about 10-20% leg by leg). It fails on funds driven by swaps,
  bank-bill/STIR futures and futures with non-standard titles.

Deviations from the protocol, all labelled and none changing the verdict:
1. **v2 futures table** (`NRV_V2=1`). The frozen keyword table missed spelled-out tenors ("JAPAN 10
   YEAR BOND", "U.S. TREASURY 10-YEAR NOTE", "90-DAY BANK BILL", "CANADA 10 YEAR BOND"); only 26% of
   futures rows in flagged funds matched it. v2 adds them.
2. **Oracle sign alignment.** Each fund-quarter's reported vector is flipped when that improves its
   agreement with the estimate. This uses the answer, so it is an upper bound for the baseline, not a
   method anyone could apply.

## Main finding about the data: sign conventions differ across filers

Among clean single-currency funds (mostly plain long-only bond funds, where the holdings estimate is
negative 98% of the time), **49% report a positive net DV100**. Filers do not agree on whether DV100
means the effect of rates rising or falling. Within a fund the sign looks consistent: BlackRock
Tactical Opportunities, the iShares Global Govt Bond USD Hedged ETF and Campbell Systematic Macro all
come out as exact mirror images of the baseline, leg by leg. That means a within-fund cross-currency
offset is still informative. But:
- the aggregated DV100 the proposal keeps already has an ambiguous sign across funds. The proposal
  standardises the currency (USD) but not the sign;
- most of the gap between the frozen Spearman (0.28) and the aligned one (0.80-0.84) is this
  convention issue, not holdings missing exposures.

## Five example funds where aggregation hides offsetting exposures

Per-currency DV100 is the sum of the five maturity buckets, in USD, as reported. "Aggregate" is what
the proposal would leave. Offset = 1 - |aggregate| / gross.

1. **Eaton Vance Global Macro Absolute Return Advantage Portfolio**, report 31-Jul-2026, NAV $7.7bn.
   EUR +$71.6m, TWD +$35.1m, HUF -$36.1m, CNY -$35.4m, NZD -$31.4m (22 currencies). Gross $399m,
   aggregate -$83m, offset 0.79. Holdings baseline reproduces these legs closely.
   https://www.sec.gov/Archives/edgar/data/1493214/000141036826101155/
2. **BlackRock Tactical Opportunities Fund**, 31-Jul-2026, NAV $6.0bn. EUR -$410m, GBP +$217m,
   USD -$207m, CNY +$114m, KRW +$78m (26 currencies). Gross $1,309m, aggregate -$174m, offset 0.87.
   Baseline is the mirror image (sign convention).
   https://www.sec.gov/Archives/edgar/data/844779/000207169126023074/
3. **Campbell Systematic Macro Fund**, 31-May-2026, NAV $2.1bn. AUD -$86.2m (short AUD 3y/10y bond
   and bank-bill futures), CAD +$35.9m, JPY +$31.5m, EUR -$21.3m, GBP +$20.0m. Gross $210m,
   aggregate -$5.5m, offset 0.97: aggregation reports almost no rate risk. AUD legs checked against
   the filing XML.
   https://www.sec.gov/Archives/edgar/data/831114/000119312526319608/
4. **T. Rowe Price Dynamic Global Bond Fund**, 30-Jun-2026, NAV $4.7bn. USD +$161.8m, CAD +$53.0m,
   EUR +$44.3m against AUD -$67.8m, GBP -$60.2m, NZD -$29.5m. Gross $434m, aggregate +$102m,
   offset 0.76. Baseline gets EUR's sign wrong (-$2.6m) and USD/GBP/NZD magnitudes off by 60-160%.
   https://www.sec.gov/Archives/edgar/data/313212/000109926326009563/
5. **Transamerica JPMorgan Asset Allocation - Moderate VP**, 30-Jun-2026, NAV $4.5bn. AUD +$27.6m,
   EUR +$18.1m, USD +$12.4m against JPY -$19.2m, GBP -$15.8m. Gross $100m, aggregate +$15.8m,
   offset 0.84. Baseline reproduces it.
   https://www.sec.gov/Archives/edgar/data/778207/000141036826086891/

IG / non-IG examples (2026q3): PIMCO Long Duration Credit Bond Portfolio (NAV $30bn; IG CS01 +$19.3m,
non-IG -$12.4m, offset 0.78); JPMorgan Strategic Income Opportunities (offset 0.51); American Funds
Inflation Linked Bond (offset 0.72). Public N-PORT has no ratings, so Gate 2 cannot test the SEC's
coupon-proxy claim for these.

## Proposal status (pages opened 2026-10-27)

- Still a **proposal**. On the SEC rulemaking-activity page, "Form N-PORT Reporting (S7-2026-05)" is
  listed as a Proposed Rule dated 18 Feb 2026, IC-35962. No adopting release appears among entries
  up to 9 Oct 2026 (the latest is the Investment Company Cross Trading proposal, S7-2026-36). The only
  N-PORT final action is the Names Rule compliance-date extension (IC-35963, also 18 Feb 2026).
- Comments were due 24 Apr 2026. The SEC comment-file page was down for maintenance (HTTP 503), so
  the comment list was not reviewed.
- The proposal's text (Item B.3, p. 115 of the release) keeps the five maturity buckets, aggregates
  only across currencies at or above 1% of NAV, and adds "report in U.S. dollars". Release pp. 40-41
  give the rationale: "we can use ... the currency denomination of each portfolio holding, to help
  assess significant currency risk", and coupons proxy IG vs non-IG. Release p. 79 says the changes
  are not expected "to significantly affect the utility ... to the Commission." No count of affected
  funds is given for the threshold change.
- ICI's comment letter (24 Apr 2026, pp. 7-8 and n.27) supports every risk-metric change, on the
  same argument that holdings currency and coupons replace them.
- Saved copies: `data/interim/nport_risk_value/ref/ic-35962.pdf` and `ici_comment_2026-04-24.pdf`
  (with text extracts).

## Prior art (quick, bounded)

I found no SEC staff, academic or vendor analysis that tests whether holdings reproduce per-currency
DV100, or that documents the sign-convention split. Searches returned raw filings and law-firm
summaries (Sidley, K&L Gates, Simpson Thacher). Both the SEC's and ICI's replaceability claims are
asserted, not measured, in what I read. The search was short (four or five queries). The comment
file, SSRN and vendor research (e.g. Morningstar, MSCI) were not checked thoroughly.

## Caveats

- Two data-set quarters only, one public report per fund per quarter. The threshold proxy uses one
  month, while the rule uses a three-month average.
- The holdings baseline is simple: duration from a par-bond formula, MBS duration capped at 6, a
  keyword table for futures, no options or swaptions, and no CDS or TRS rate exposure. A vendor-grade
  analytics engine would do better. The relevant question is whether it would reach Spearman 0.90 on
  derivative-heavy funds. Even the oracle-aligned upper bound reached only 0.84.
- Sign conventions differ across filers. Any outcome test must align signs per fund, for example by
  using the sign of a long-only cash-bond sleeve, or it will measure the convention instead of risk.
- The offsets might be reporting artifacts in some funds, such as mixed conventions inside one
  filing. For 56-59% of flagged funds the holdings baseline independently shows an offset of at least
  0.20, which argues against artifacts for most of them.
- Prevalence is narrow: 154 funds, $228bn, concentrated in macro and hedged global bond strategies.
  The 5% share rule was not met; Gate 1 passes on the count rule only.
- An outcome test should ask a decision question. For example: in rate-shock months (by currency),
  does per-currency DV100 predict flagged funds' returns better than aggregate DV100 plus the holdings
  estimate? It has to be frozen before any data is opened.
