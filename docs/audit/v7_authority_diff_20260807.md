# v6/v7/README/Paper Authority Diff — P0-0 (Phase 0 analysis, no modification)

This is a read-only analysis of the authority declarations across the repo,
the v7 contract activation, and the paper. It does NOT change any authority
document (contract §13.3 requires explicit user approval for that).

## Declared authorities

| Object | Declared authority | SHA-256 / status |
|---|---|---|
| AGENTS.md (repo execution rules) | `contracts/D2T-RNA-v6.1-frozen-plan.md` sole active | `87ccadd2…` |
| README.md (repo authority) | v6.1 sole active; Tasks 1–4 accepted, Task 5 pending | `87ccadd2…` |
| v7 activation manifest (`manifests/m0/m0_v7_activation.json`) | `ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS`, supersedes for future tasks only | `eae4ba94…`; `scientific_claim_authorized=false` |
| Paper evidence lock | `PAPER_EVIDENCE_LOCKED`; authority precedence lists v7 activation + approved amendment first | — |

## Mismatch

- The repo runtime authority (AGENTS.md/README.md) still declares **v6.1** as the
  only active contract, while the **v7 contract has been activated** as the
  successor for future tasks (approved amendment `v7_amend_12_3_6_20260805`).
- The paper/evidence lock already follows v7 precedence; only the two human-facing
  repo authority pointers lag behind.

## Resolution status

- **Recorded**: yes (this diff + `v7_science_blocker_20260807.md` §2.1).
- **Approved**: user-approved 2026-08-08 (§13.3 authority alignment).
- **Modified**: **DONE** — `AGENTS.md` and `README.md` authority pointers aligned to the
  activated v7 contract (`D2T-RNA-v7-THEORETICAL-RNA-METHODS`, id in
  `manifests/m0/m0_v7_activation.json`) and the approved amendment
  `V7_AMEND_12_3_6_20260805`. v6.1 (`contracts/D2T-RNA-v6.1-frozen-plan.md`) is
  marked **retained as legacy** (historical tasks 1-5), not deleted.

## Status

RESOLVED (aligned to v7 on 2026-08-08, commit ca8c05f).
