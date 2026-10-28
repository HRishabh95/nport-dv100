# N-PORT risk-metric outcome study: result

**Versions.**
- Frozen protocol `OUTCOME_PROTOCOL.md` (sha fe1c473e), unchanged.
- Amendment 1 (sha e6a248e8): theta versus MSE, conditional framing, FX source, distribution
  statement, clarifications.
- Amendment 2 (sha 8ae3f579): ninth inspected fund, FX-weight cleaning, seeds.

Both amendments were frozen before any fund return was read.

**Code.** `exposures.py` (E^A, E^C, E^Craw, FX weights), `outcome.py` (`prep`, `run dev`, `run conf`)
and `extract_outcome.py`. Outputs are in `data/interim/nport_risk_value/outcome/`: `result_dev.json`,
`result_conf.json`, `pred_*.parquet`, `pairs_*.parquet`, `conf_run.log`, and the post-hoc files
named below.

**Order of work.**
1. Prep (no returns).
2. Amendment 2.
3. Return extraction.
4. Development run.
5. Two fixes (below).
6. Confirmation, run once on 2026-10-28.

## Deviations after development (no change to any definition)

1. **Exclusion matching bug.** Exact-name matching found only 6 of the 9 inspected funds. The other
   three appear in N-PORT under different names or have no resolved record. They are now excluded
   by series ID: S000029761, S000022994, S000092377. Development numbers were identical before and
   after, because none of the three is in a development family.
2. **Secondary 7.8 implemented.** The pair illustration was implemented and tested on development
   after the first development run, as frozen in the protocol.

No specification was chosen or changed on the basis of development results. For the record,
development gave theta 0.996, a conservative interval of 0.43-2.23 and dMSE_CB +2.8% (-1.7% to
+7.0%), on 563 fund-months and 44 funds.

## Primary result (confirmation; frozen rule): INCONCLUSIVE

The population is PRIMARY records (harmonised cross-currency offset >= 0.20, non-USD share >= 0.10)
from 42 confirmation families: 2,117 fund-months, 153 funds, 2021-12 to 2026-06. 4,360 PRIMARY
fund-months had a record and 4,142 a return; the rest lacked 24 months of estimation history.

| Frozen criterion | Required | Result | Met |
|---|---|---|---|
| theta | >= 0.5 | **0.496** | no (just) |
| Conservative lower bound of theta | > 0 | 0.135 (month 0.135-0.946; family 0.308-0.992) | yes |
| theta > 0 by period | >= 3 of 4 | 4 of 4 (2022 0.51; 2023 0.70; 2024 0.13; 2025-26 0.09) | yes |
| RMS(D) | >= 10 bp/month | 50.5 bp | yes |
| DOES NOT: upper bound < 0.5 | | 0.992 | no |

**Verdict: INCONCLUSIVE.** It misses the frozen theta threshold by 0.004.

Amendment 1 (M1) asks for the prediction-error result to be reported separately from this
calibration result:

| | Point | Conservative 95% interval |
|---|---|---|
| dMSE_CB = 1 - MSE_C / MSE_B | +6.7% | **-1.3% to +32.4%** |
| thetat (slope on the actual prediction difference) | 0.88 | 0.24 to 1.41 |
| Share of D absorbed by the refit | -0.10 (the refit adds variation rather than absorbing it) | |

The prediction-error claim is **not allowed**: the lower bound is not above 0. So the full-weight
per-currency model does not measurably reduce prediction error relative to the proposal-equivalent
set.

These are conditional predictions (amendment 1, M2): exposures disclosed before month m, priced with
the factor moves and yield changes realised in m. The test does not produce a forecast of returns and
is not a tradable signal.

### One fund carries the primary result

The heavy tail recorded in amendment 2 before the run is decisive.
- **Dunham Dynamic Macro Fund** (a managed-futures fund, NAV $25-110m) accounts for 89% of sum D^2
  and 85% of theta's numerator. The top 10 funds account for 95%.
- Its holdings estimate swings by +/-20% of NAV a month on futures notionals. B inherits that
  per-currency profile, and C's reported legs (2-6% of NAV gross) correct it.
- That is the mechanism the test is meant to detect, but it is concentrated in one fund, mostly in
  the first half of 2022.

Post hoc and descriptive, not a test (`posthoc_conf.json`), excluding that fund:

| | Value |
|---|---|
| theta | 0.69 (conservative interval -0.08 to 1.54) |
| dMSE_CB | +0.8% (-2.2% to +2.2%) |
| RMS(D) | 16.5 bp |
| theta by period | 2022 1.43; 2023 0.72; 2024 0.11; 2025-26 -0.07 |

## Secondary analyses (reported in full, no gate)

| Analysis | Fund-months | theta (conservative interval) | dMSE_CB (conservative interval) | Rule applied as if gated |
|---|---|---|---|---|
| 7.1 broad (non-USD debt >= 10%, defined from holdings) | 10,988 / 343 funds / 91 families | **0.72 (0.41-1.02)** | **+0.92% (+0.25% to +1.50%)** | passes |
| 7.3 available at max(FILING, REPORT + 60 days) | 2,114 | 0.52 (0.16-1.06) | +6.8% (-1.4% to +32.9%) | passes |
| 7.4 decomposition (month after REPORT_DATE) | 2,233 | 0.18 (-0.20 to 1.20) | +7.1% (-1.8% to +34.6%) | inconclusive |
| 7.5 family-equal weights | 2,117 | 0.47 (-0.32 to 0.89) | +12.6% (-1.6% to +36.1%) | inconclusive |
| 7.5 excluding partial-coverage and unit-converted records | 2,045 | 0.51 (0.16-1.12) | +7.3% (-0.8% to +36.0%) | passes |
| 7.6 B priced on the mix only (C vs B_mix) | 2,117 | 0.69 (0.26-1.11) | +1.8% | |
| 7.7 placebo: currency labels permuted | 2,117 | 0.13 (-0.18 to 0.41) | -8.0% | includes 0, as expected |
| 7.9 inspected 2026q2-q3 records | 34 | -7.1 | -3.9% | too small to read |
| 7.10 frozen N-PORT FX factor | 2,117 | 0.49 (0.12-0.93) | +6.2% | inconclusive |

**7.1 broad population.**
- The top fund is only 9.6% of sum D^2. Without it (post hoc), theta is 0.74 (0.38-1.12) and dMSE_CB
  is +0.94% (+0.28% to +1.56%).
- By period, theta is 2022 0.95, 2023 0.40, 2024 1.08 and 2025-26 0.07; dMSE in 2025-26 is about 0.
- So in the larger holdings-defined population, currency detail gives a small but statistically
  reliable improvement in prediction error, about 1% of MSE. It is absent in the most recent period.

**Holdings vs the retained aggregate (B vs A).**
- B's prediction MSE is 34% lower than A's in PRIMARY (theta_AB 0.63) and 27% lower in broad.
- The family-bootstrap intervals include 0: PRIMARY -2% to +72%, broad -2.5% to +58%.
- Most of the gain comes from a few funds whose holdings estimates are poor.

**7.2 convention cost** (reading signs and units as filed rather than harmonised; descriptive, with
the interval computed post hoc, `posthoc_mse_conf.json`, `posthoc_rawcost_ci_conf.json`):

| Population | 1 - MSE_B / MSE_Braw | 1 - MSE_C / MSE_Craw | Currency detail, dMSE_CB |
|---|---|---|---|
| PRIMARY | +10.0% (-1.2% to +13.8%) | +11.1% (-1.1% to +15.9%) | +6.7% |
| PRIMARY excluding Dunham | +9.5% | +11.0% | +0.8% |
| Broad | **+9.7% (+4.7% to +13.7%)** | **+9.2% (+4.4% to +13.2%)** | +0.9% |

**In every population, reading the filings at face value costs about 10% of prediction MSE. That is
roughly ten times what per-currency detail adds once a single fund is set aside.**

**7.8 pairs** (frozen rule, descriptive; 23,566 cross-family PRIMARY pairs over 26 quarters):
- Predicted rate-P&L correlation changes class (offsetting / neutral / similar) between B and C for
  **18.9%** of pairs.
- It changes class between raw and harmonised for **48.9%** of pairs.
- Of the B-vs-C changes, 366 have opposite-signed predictions and realised e^A data (at least 8 of
  12 months). The realised sign matched C 186 times and B 180 times.
- So whether a pair looks diversified depends on the information set, but at the pair level, returns
  do not confirm that C's call is the right one.
- Chart pairs (largest |corr_C - corr_B|, `pairs_conf_chart.csv`). None has the realised data needed
  to check it:
  - Fixed Income SHares Series LD / Destinations International Equity (2020q2): raw -0.93,
    harmonised C +0.93, B -0.96.
  - First Trust Managed Futures / Multi-Manager Alternative Strategies (2026q1): raw +0.88,
    C +0.88, B -0.98.
  - Transamerica JPM Moderate Growth VP / PIMCO Total Return (2022q3): raw -0.92, C +0.92, B -0.93.

## What this means for the question asked

*Do these two managers offset each other's interest-rate exposure, or are we doubling the same
exposure?*
1. **The sign convention matters more than currency aggregation.** Half of cross-family pairs change
   diversification class when signs are harmonised. Reading filings as filed raises prediction error
   by about 10%, and in the broad population the interval excludes zero. The proposal mandates USD,
   which addresses units. It does not address direction.
2. **Currency detail adds something, but little.** In the broad population it is about 1% of
   prediction MSE: reliable, but economically small and absent in 2025-26. In the population the
   proposal targets, the frozen test is inconclusive, and the evidence rests on one managed-futures
   fund.
3. **The proposal's own method (holdings currencies plus aggregate) can fail badly for
   derivatives-heavy funds.** In those funds the holdings profile is far from the reported risk. That
   failure is visible, but it is rare.

## Limits

- **Distributions.** Factor returns are price returns. Omitted distributions shift the intercepts
  and, because they vary over time (ACWI pays twice a year, HYG and IEI pay monthly amounts that move
  with yields), add measurement error that slightly attenuates the slopes. The size of this effect
  was not measured. It is common to A, B and C (amendment 1, M4).
- **Factor window.** The estimation window includes returns that may not yet have been public at m
  (amendment 1, M2).
- **Exposure model.** DV100 is linear and parallel by bucket, with no convexity. Positions are 1-9
  months stale. Rates are mapped for six currencies; others are priced at the mix.
- **FX.** 8.1% of PRIMARY FX exposure has no ECB rate, and its FX return is set to 0.
- **Clusters.** There are 42 confirmation families in PRIMARY. The family bootstrap is wide, and one
  fund dominates.
- **Scope.** Nothing here speaks to the threshold change, the IG/non-IG merge or the removal of DV01.
