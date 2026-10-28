# N-PORT risk-metric value check: frozen protocol

Question: does the SEC's February 2026 Form N-PORT proposal (IC-35962, File S7-2026-05) remove
information that holdings cannot replace? The proposal: (a) report DV100 aggregated across currencies
(maturity buckets kept), (b) one credit-spread metric instead of separate IG / non-IG, (c) raise the
risk-metric threshold from debt > 25% of NAV to > 50% of NAV, (d) drop DV01, keep DV100.

The SEC's own claim (release pp. 40-41): currency of each holding replaces per-currency DV100, and
coupons proxy the IG / non-IG split. Gate 2 tests the first claim directly.

Frozen 2026-10-27, before any result was computed. Any change after this point is reported as a
deviation in CHECK.md.

## Data

- SEC N-PORT public data sets already on disk: `data/raw/nport/2026q2_nport.zip` and
  `data/raw/nport/2026q3_nport.zip` (the two most recent; filings made Apr-Jun 2026 and Jul-Sep 2026).
  Nothing is re-downloaded.
- Tables: SUBMISSION, REGISTRANT, FUND_REPORTED_INFO (NAV, CREDIT_SPREAD_*_INVEST / _NONINVEST),
  INTEREST_RATE_RISK (DV01 and DV100 by currency x 5 maturity buckets), FUND_REPORTED_HOLDING,
  DEBT_SECURITY, FUT_FWD_NONFOREIGNCUR_CONTRACT, NONFOREIGN_EXCHANGE_SWAP.
- Fund key: SERIES_ID; if blank, the registrant CIK; if still blank, ACCESSION_NUMBER. N-PORT is filed
  per series, so share classes are already one portfolio; the key de-duplicates amendments and repeat
  reports. Within each data-set quarter keep one filing per fund: latest REPORT_DATE, then latest
  FILING_DATE (so an NPORT-P/A replaces its original).
- A fund-quarter "has IR risk fields" if it has at least one INTEREST_RATE_RISK row with a non-zero
  DV100 bucket. It "has spread risk fields" if any CREDIT_SPREAD field is non-zero.
- Per-currency reported DV100_c = sum of the five DV100 buckets for currency c. Spread legs:
  IG = sum of the five _INVEST buckets, NIG = sum of the five _NONINVEST buckets.

## Cleaning (same rule everywhere; failures are "unresolved", excluded and counted)

IR dimension, fund-quarter excluded if any of:
1. NAV missing or <= 0.
2. Gross DV100 G = sum_c |DV100_c| > 0.5 x NAV (implied absolute duration > 50).
3. Both DV01 and DV100 present and non-zero and the ratio sum_c,b |DV100| / sum_c,b |DV01| lies
   outside [30, 300] (a 100 bp number should be ~100x the 1 bp number; outside that band the units
   are inconsistent).
4. Duplicate currency codes in the same filing are summed (not an exclusion).
Spread dimension, fund-quarter excluded if NAV missing/<= 0 or |IG| + |NIG| > 0.005 x NAV
(implied spread duration > 50).
Values reported in a non-USD currency cannot be detected; this is a caveat, not a rule.

## Gate 1: prevalence

Per clean fund-quarter:
- currency-offset ratio O_c = 1 - |sum_c DV100_c| / sum_c |DV100_c|
- non-USD share N = sum_{c != USD} |DV100_c| / sum_c |DV100_c|
- hidden by currency aggregation: O_c >= 0.20 AND N >= 0.10.
- spread offset O_s = 1 - |IG + NIG| / (|IG| + |NIG|); hidden by spread aggregation:
  O_s >= 0.20 AND min(|IG|, |NIG|) >= 0.10 x (|IG| + |NIG|).
A fund is flagged if any of its clean fund-quarters is flagged in either dimension.
PASS if flagged distinct funds >= 100 OR flagged / distinct funds with any clean risk field >= 5%.
Also reported (descriptive, no gate): per-dimension counts, AUM (NAV) of flagged funds, and the
threshold change.

Threshold proxy: debt exposure = (sum |CURRENCY_VALUE| of holdings with a DEBT_SECURITY row or ASSET_CAT
in {DBT, LON, ABS-MBS, ABS-ABCP, ABS-APCP, ABS-CBDO, ABS-O, SN, STIV debt}) + sum |notional| (USD) of
interest-rate futures and fixed/floating swaps per the Gate 2 rules, divided by NAV, on the single
public month (the rule uses a 3-month average; caveat). Funds with clean IR risk fields and proxy
<= 0.50 are reported as "would drop out", with count, share and NAV. Concretely ASSET_CAT set used:
any holding with a DEBT_SECURITY row, plus ASSET_CAT starting with "ABS" or equal to DBT or LON.

## Gate 2: replaceability (only fund-quarters flagged by currency aggregation)

Holdings baseline, per holding, estimated DV100 contribution in USD = -0.01 x E x D, assigned to the
holding's currency, where E is signed USD exposure and D modified duration (years):
- Debt holdings (DEBT_SECURITY row): E = CURRENCY_VALUE, negated if PAYOFF_PROFILE = Short.
  T = years from REPORT_DATE to MATURITY_DATE (floor 0; missing -> holding skipped and counted).
  COUPON_TYPE Fixed: y = ANNUALIZED_RATE/100, floored at 0.001; D = (1/y) x (1 - (1 + y/2)^(-2T)).
  COUPON_TYPE None (zero coupon): D = T / 1.04. Floating / Variable: D = min(T, 0.25).
  ASSET_CAT starting "ABS-MBS": D capped at 6 (prepayment). D capped at 30 for everything.
- Interest-rate futures (DERIVATIVE_CAT FUT, row in FUT_FWD_NONFOREIGNCUR_CONTRACT, ISSUER_TITLE or
  ISSUER_NAME matches a rate keyword): E = |NOTIONAL_AMOUNT| converted to USD, sign + for Long, - for
  Short; D from a fixed keyword table (case-insensitive, first match wins):
  ULTRA BOND / ULTRA LONG / WN 17; ULTRA 10 / ULTRA T / TN 8.5; US BOND / LONG BOND / T-BOND / US LONG /
  30Y 11.5; 10Y / 10 YR / TY 6.5; 5Y / 5 YR / FV 4.2; 2Y / 2 YR / TU 1.9; BUXL 20; BUND 8; BOBL 4.3;
  SCHATZ 1.9; OAT 8; BTP 7.5; GILT 9; JGB 7; CAN 10 / CGB 8; AUST 10 / AUD 10 8.5; AUST 3 / 3YR 2.8;
  KOREA 10 8; KOREA 3 2.8; SOFR / EURIBOR / SONIA / EURODOLLAR / FED FUND / BANKERS / 3M / 90 DAY 0.25.
  Futures with no keyword match get 0 and are counted. Currency = the futures row CURRENCY_CODE.
- Interest-rate swaps (row in NONFOREIGN_EXCHANGE_SWAP with one leg Fixed and the other Floating):
  E = +|NOTIONAL_AMOUNT| (USD) if receipt leg Fixed, - if payment leg Fixed; T = termination date;
  D from the fixed-coupon formula with the fixed rate. Other swaps (CDS, TRS, basis): 0, counted.
- Options, swaptions, FX forwards, equities, cash, repo: 0.
- Notional to USD: divide by the data-set median holding EXCHANGE_RATE for that currency (units per
  USD, as N-PORT reports it); USD = 1; currency with no rate -> holding skipped and counted.

Comparison unit: (fund-quarter, reported currency) pairs among Gate-1 currency-flagged fund-quarters.
- Spearman rank correlation of estimated vs reported DV100_c, pooled over all pairs.
- Error per pair = |est_c - rep_c| / G (the fund-quarter's reported gross DV100); median over pairs.
- REPLACEABLE if Spearman >= 0.90 AND median error <= 0.20.
- Sign-wrong share: fraction of Gate-1 currency-flagged fund-quarters with at least one reported
  currency where |rep_c| >= 0.10 x G and sign(est_c) != sign(rep_c) (est_c = 0 counts as wrong).
Secondary (descriptive, not gating): does the baseline reproduce the hidden offset itself, i.e. share
of flagged fund-quarters where the baseline also gives O_c >= 0.20 on the reported currencies.
Spread dimension: public N-PORT has no ratings, so no holdings baseline is gated for IG/non-IG; the
SEC's coupon-proxy claim is noted but not tested here.

## Verdict

CLOSE if Gate 1 fails, or Gate 2 = REPLACEABLE. Otherwise GO-TO-OUTCOME-TEST (not run here).

## Also

Open actual pages to check whether the proposal was adopted, withdrawn or modified after Feb 2026, and
a quick prior-art pass (SEC staff, academic, vendor work on the usefulness of N-PORT risk metrics).
