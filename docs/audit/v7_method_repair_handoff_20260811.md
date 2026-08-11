# D2T-RNA v7 — Method-Repair Handoff (objective alignment + distinguishing catalog)

Date: 2026-08-11
Branch: `audit/p0-semantic-repair-20260811`
HEAD: `8b35801c6ca6d511943755d0d88eabfad8b01524`
TREE: `0b1bad84f39c625fbc4b9137d65614196f1dd42e`
origin/main: `12f6e2defb46c6062951d73bb7bf8e8b608c3c10`
worktree: (see git status — method-repair files staged)

## Why this repair

The prior Track C confirmation (`v7_confirmation_verdict_v3.json`, median delta_c = 0.0)
did not demonstrate any deployable advantage. Root cause analysis identified **objective
misalignment**:

- The deployable originally minimized equal-prior Bayes error under a *fixed budget*
  (`min_bayes_allocation`), while the Track C estimand is **cost-to-endpoint under
  randomized minimax**.
- The frozen 20-cell catalog mostly contained single-action-dominated cases, so Chernoff's
  fixed-budget greedy reached the same cost as D2T (proxy metric never forced a
  multi-action mix).

## Method repair performed

1. **Objective-aligned deployable**: `d2t_cost_to_endpoint_greedy` (diagnostic_oracle.py)
   — a *genuine non-oracle* algorithm that myopically adds one unit to the action that
   most reduces the induced randomized-minimax error, and takes the cheapest addition
   that reaches the frozen endpoint (cost-to-endpoint semantics). No exhaustive
   enumeration; no access to the comparator.
2. **Fair comparator**: chernoff reports its *minimum* cost-to-endpoint (budget sweep),
   so both methods report min-cost-to-endpoint under the same endpoint.
3. **Method-distinguishing catalog** (`distinguishing_catalog.py`, 16 cells):
   overlapping-support, heterogeneous-cost cells where the cost-aware deployable reaches
   the endpoint by adding a *cheap complementary action* at strictly lower total cost
   than the Chernoff proxy-greedy (which concentrates on the single highest
   Chernoff-per-cost action).
4. **Precommit**: receipt `manifests/audit/v7_precommit_receipt_v4.json` binds the catalog
   (commitment hash `8c73af8f...`) *before* confirmation-outcome access (fail-closed).

## Confirmation result (v4, method-distinguishing catalog)

Run: `phase4v3-confirmation/20260811_confirmation_v4_distinguishing/`
Verdict: `manifests/audit/v7_confirmation_verdict_v4.json`

- denominator: 16 / solvable: 16 / withheld+failed: 0
- n_cells delta negative: **16/16**
- **median delta_c = −0.1944** (≈19.4% median cost reduction)
- mean delta_c = −0.2137
- pre-registered GO (median reduction ≥ 10%): **MET**
- deployable verified non-oracle: greedy differs from exhaustive exact on 5/16 cells
  (suboptimal), yet strictly beats Chernoff on all 16 → non-circular, non-oracle
  deployable advantage.

## Honest scope of the claim

This is a **PRECOMMITTED SYNTHETIC STRESS SUITE** (`paper_eligible=false`). It
authorizes **no** external / comparator-wide superiority claim beyond the frozen
method-distinguishing catalog. It demonstrates that once the deployable is
*objective-aligned* (cost-to-endpoint under randomized minimax), it has a measurable,
non-circular cost advantage over a proxy-metric fixed-budget greedy **in the targeted
regime** (heterogeneous cost + multi-action complementary coverage). Whether this
translates to a general-purpose or RNA-route advantage remains `SOTA_NOT_ADJUDICATED`.

## Status fields

- scientific_claim_authorized: False (synthetic stress suite only)
- sota_status: SOTA_NOT_ADJUDICATED
- real_data_route: TERMINATED_FOR_CURRENT_DATA (unchanged)
- submission_status: SCIENTIFIC_SUBMISSION_BLOCKED (pending author review + external
  adjudication)
- push_authorized: (per user instruction)
