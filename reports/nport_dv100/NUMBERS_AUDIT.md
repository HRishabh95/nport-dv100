# Number reconciliation and review log (2026-10-28)

Every numerical statement in `DRAFT.md` was checked against the frozen outputs:
- `audit/audit.json`, `audit_d1.json`, `signcheck*.json`;
- `outcome/result_conf.json` and the `posthoc_*.json` files;
- the replication outputs.

Changes are listed with their original values. Nothing here comes from a new analysis. One
descriptive breakdown of the existing sign-check sample was added (item 5).

## Substantive corrections

| # | Original statement | Corrected | Source |
|---|---|---|---|
| 1 | Sibling prediction "99.8% of the time" | 99.76% accuracy covering 41,074 of 51,201 plain evidence fund-quarters (80.2%) | audit.json `loo` |
| 2 | Replication "99.9%" with "84% coverage" | 99.9% covering 33,434 of 39,810 (84.0%) | replication/output_plaus.txt |
| 3 | "Harmonised figures explain the rate component better: 9.7% lower prediction error" (Summary) | Prediction error of **total monthly returns**. Secondary and descriptive, interval computed after the frozen run, **signs and units together**. | OUTCOME.md 7.2; posthoc_rawcost_ci_conf.json |
| 4 | "Sign convention is a larger comparability problem than the loss of currency detail" and Figure 3 "matters about ten times more" | Withdrawn as a comparative claim. Now: harmonising signs and units reduces error more than adding currency detail in a secondary analysis. The effects are not separated and are not like-for-like (the convention is user-recoverable; aggregated detail is not). | reviewer finding 2 |
| 5 | (my reply to the user) The 99.7% sign-check agreement "comes mostly from near-plain funds" | **Wrong.** 59% of the checked legs (49% of exposure) come from funds whose derivative notional is at least 25% of NAV. The real limits: 6,093 of 35,645 inferred fund-quarters (17%) are unchecked, and only exposure the holdings model values is tested. | breakdown of signcheck sample |
| 6 | Opposite-sign pairs 50.2% -> 3.4% on 133m pairs, unlabelled | Labelled as following deviation D1 and as unweighted pairs of resolved fund-quarters. Frozen rule: 49.2% -> 4.0% on 97.0m pairs. | audit.json `pairs`; signcheck_sensitivity.json |
| 7 | "48% of plain long-only bond funds" | 48% of plain long-only bond **fund-quarters** (25,735 of 53,603) | audit.json `plain` |
| 8 | "A complex-level lookup recovers the convention for 82%" | 81.8% are resolved at fund level (own evidence, registrant or adviser). The published registrant-then-adviser lookup resolves 76.9% and agrees with the audit on 99.96% of 80,407. | audit_d1.json; lookup check |
| 9 | Replication: "conventions change for a whole complex at once; Allspring switched in 2023q1" | No replication output contained this. Now sourced from the audit-based lookup table: Allspring F through 2022q4, R from 2023q1. 26 registrants changed between resolved quarters, 113 of 1,096 on the audit's looser definition. | lookup CSV; audit.json |
| 10 | Replication "with no access to this analysis" | A separate model run on the **same SEC bulk data**, briefed on the question, with no access to the audit code or results. Covers only the plain-fund census. | replication/README.md |
| 11 | Per-currency detail "adds a small, reliable amount on average" | About 0.9% [0.25, 1.5] in the secondary population, with none in 2025-26. The proposal-relevant gain rests on one fund (post hoc). | result_conf 7.1; posthoc_conf.json |
| 12 | Results table: harmonisation intervals unmarked, secondary results in bold | Marked † (post hoc; signs and units). Primary column labelled pre-registered. Bold only on the primary verdict. | reviewer finding 10 |
| 13 | Pair classes: "harmonising signs changes 48.9%" | "Signs and units". Neither change is validated by realised returns (366 of 4,454 B-vs-C changes checkable, split 186/180; no raw-vs-harmonised check). | result_conf 7.8 |
| 14 | Figure 1 legend "Positive (value change if rates fall)" | "Positive (rates-fall or magnitude reading)". The y-axis now says fund-quarters. | AUDIT.md (MassMutual) |
| 15 | Comment letters: "none of those we read" | All 15 public letters and 2 memos text-searched. One (Sharma, Aspen Institute) raises currency-aggregation risk; none raises direction. | scratchpad/comments |
| 16 | Summary led with the D1 pair figures (50.2% -> 3.4%, 133m) | The frozen rule now comes first (49.2% -> 4.0%, 97m pairs) and D1 second, each with its pair count. Labelled "signs only; units not converted": `pairs_flip` uses the raw net DV100 without unit conversion, so "signs and units" would be wrong for this figure. Figure 2's left panel now shows the frozen values. | audit.json `pairs`; signcheck_sensitivity.json `frozen` |
| 17 | "Both readings comply with the form" | Removed as a legal conclusion. Now: the form does not specify the direction, and filers use different conventions. The data dictionary has the same change. | user review |
| 18 | No references section | Added 10 primary-source references, every URL checked (HTTP 200): form, 2016 release, IC-35962 and the Federal Register version, comment file, ICI, Sharma, SIFMA AMG, N-PORT and N-CEN data sets, yield and FX sources. | |
| 19 | Adviser table contained `ADVISER_ID = N/A` (20 rows, Cambria and others) | N-CEN's "N/A" placeholder is excluded: the adviser table drops from 9,315 to 9,295 rows (510 to 509 advisers; 4,337 to 4,333 resolved). **The audit itself** had resolved 15 F records by "adviser" inference through "N/A". Treating them as unresolved leaves every figure unchanged at the reported precision (frozen 49.2%/4.0%; D1 50.2%/3.4%). None of them is in the outcome sample. Lookup coverage stays 76.9%. | signcheck_sensitivity.json `na_adviser_records` |
| 20 | F described as "fall or magnitude" without a usage warning | Draft section 3 and the data dictionary now say F is a reporting convention, not a transformation rule; check the fund before reversing numbers | |

## Verified unchanged

- 105,416 fund-quarters, 6,073 funds; 18.2% unresolved (13.4% NAV); reasons 15,442 / 2,131 / 1,419 /
  148.
- 493 local-unit legs, 676 unresolved legs; 19 filings / 950 cells.
- 99.0% unanimity (4,844 registrant-quarters >= 3); F share 43-50% by quarter.
- Sign check 99.70% weighted, 98.26% unweighted on 45,467 legs and 29,552 records; R 99.76%,
  F 99.64%; 68 records in flagged families.
- Primary theta 0.496 [0.135, 0.992]; dMSE_CB 6.7% [-1.3, 32.4]; 89% top-fund share; 0.8%
  [-2.2, 2.2] without it.
- Broad theta 0.72 [0.41, 1.02]; dMSE_CB 0.92% [0.25, 1.50]; raw cost 9.7% [4.7, 13.7] (broad) and
  10.0% [-1.2, 13.8] (primary).
- Pairs 23,566; 48.9% / 18.9%; 186 / 180.
- Replication: 39,810; 45.5%; 41.1-48.1%; 99.4%; top-15 dominant signs all match the audit.

## Reviewer findings not adopted

- **"Run a sign-only B_raw before release."** Not run: the brief allows no new experiments. The claim
  was weakened instead (item 4). It can be run later as a labelled post-hoc decomposition if the
  author approves.

## Files added for reproducibility

- `src/nport_risk_value/signcheck_sensitivity.py`, which regenerates `signcheck_sensitivity.json`.
- `reports/nport_dv100/replication/` (code, README, saved outputs; the panel is in
  `data/interim/nport_risk_value/replication/`).
- `reports/nport_dv100/lookup.py` and `data/` (two lookup tables plus a data dictionary).

## Paper rewrite (2026-10-28)

The working paper (`paper/note.tex`) adds descriptive material generated by `paper/figs.py` from the
frozen outputs. Nothing in it is new analysis.
- Table 2, the worked example, comes from `fund_quarters.parquet` for 2025q4. The 50/50 portfolio
  illustration gives +$0.09m at face value and -$5.72m once harmonised.
- Tables 3 and 4 come from the lookup CSV: 31 changes at 26 registrants.
- Figure 1 shows the scatter for the 51,201 evidence fund-quarters.

Related-work references were verified by a separate agent: 18 of 18 exist, and 4 needed detail
corrections, which are applied. The paper also adds Iorio, Li and Petrasek (2024). Their FEDS Note
defines N-PORT DV01 as the value change for a decrease in rates; they pick a convention without
discussing the split. Fetched 2026-10-28.
