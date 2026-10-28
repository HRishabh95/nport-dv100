# Amendment 2 to the outcome protocol (2026-10-28)

Written after building the exposure and factor pipeline (`exposures.py`, `outcome.py prep`) and
**before any fund return has been read**. The return table is extracted only after this file's sha256
is stored in `data/interim/nport_risk_value/OUTCOME_AMENDMENT_2_SHA256`.
`OUTCOME_PROTOCOL.md` (fe1c473e) and `OUTCOME_AMENDMENT_1.md` (e6a248e8) are unchanged.

## N1. A ninth inspected fund is excluded from confirmation

Section 8 of the protocol excludes eight funds named in `CHECK.md`. `CHECK.md` also names the
**iShares Global Govt Bond USD Hedged ETF**: its legs were compared with the holdings baseline
there. It is excluded from confirmation as well. This only removes data.

## N2. FX weights with unit errors in forward amounts

The prep check found FX weights that are impossible:
- 29 of 382,375 currency legs have |w| > 2, up to -92 x NAV. The cause is FX forward amounts reported
  in the wrong units.
- 47 records have a sum over currencies of |w| above 3.
- The fund FX factor reached -188% and +375% in single months.

Rule, identical for A, B and C, since FX weights are a shared control:
1. If a record's sum over c of |w_c| (holdings plus forwards) exceeds 3, its weights use holdings only.
   This applies to 47 records.
2. Every w_c is then capped at +/-1.5. This applies to 36 legs before step 1.

## N3. Details fixed before reading returns

1. **Development sample.** It uses the same exclusions as confirmation: no 2026q2-q3 records, no S6
   or `CHECK.md` funds. This keeps the two comparable. 7.9 within development uses development
   families only.
2. **Bootstrap seeds.** 20261028 for calendar months and 20261029 for families. The placebo seed is
   20261027, as frozen.
3. **Pooled theta.** It uses every evaluated month. With 24 required estimation months, the first is
   about 2021-12. The four reported periods start in 2022.
4. **Measures in amendment 1, M1.** The share absorbed by the refit is computed as
   1 - sum(Dt^2) / sum(D^2) (uncentred), and RMS(D) is uncentred as well.
5. **Prep facts on record before returns.**
   - PRIMARY fund-months with an exposure record: 5,557 in total, 1,197 development and 4,269
     confirmation after the 2026q2-q3 exclusion. Those with a return and enough history will be
     fewer.
   - RMS(D) is 46 bp, while the median |D| is 4 bp, so D is heavy-tailed. theta will be driven by the
     funds with large currency offsets. Results are reported by fund concentration (top-10 funds'
     share of sum D^2), descriptively.
   - The share of FX exposure without an ECB rate is 7.2% (2.6% under the frozen N-PORT rule).
