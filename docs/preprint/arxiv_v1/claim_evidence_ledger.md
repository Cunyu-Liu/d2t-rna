# D2T-RNA arXiv v1 — Claim–Evidence Ledger

For every quantitative or capability claim in `main.tex`, this ledger binds it to
the current terminal source and to the allowed wording. Claims not listed here are
not made.

| # | Claim (main.tex) | Allowed wording | Evidence (terminal source) | Verified? |
|---|---|---|---|---|
| C1 | discrete-certificate path never calls the convex-hull LP; `DISCRETE_CATALOG` is pure exact enumeration; unsupported combinations fail closed | yes | `src/d2t_rna/t2/spec.py`, `theorem.py`; kill-tests `tests/audit/test_spec_dispatch.py`, `tests/audit/test_empty_discrete_convex.py` | 50-test smoke passed |
| C2 | Bayes average error and randomized minimax error are exposed as separate exact fields | yes | `EvaluationResultV3`; `tests/audit/test_phase4v3_diagnostic.py`, `tests/t2/test_decision_semantics.py` | exact `1/4` vs `1/3`; `81/512` vs `81/337` asserted |
| C3 | registered 20-cell synthetic evaluation: 20/20 solvable, 3 lower / 17 tie / 0 higher, median ΔC = 0, GO not met | yes (core negative result) | `anc/confirmation_v3.csv` (derived from `phase4v3-confirmation/20260811T163031+0800/confirmation_report.json`) | recomputed 3/17/0, median 0, GO=false |
| C4 | post-hoc v5/v6 exact-optimal "never-worse" is definitional and NOT a performance finding | only as audit appendix; never in abstract/main result | `v7_confirmation_verdict_v6.json` (`paper_eligible=false`); random-instance wins=0/ties | accepted as circular (Theorem 1 = definition of optimality) |
| C5 | seven RNA scopes all fail closed: no raw counts / likelihood / action / cost / independent unit | yes | `manifests/data/v7_data_qualification_v3.json`; `anc/data_qualification.csv` | all 7 `TERMINATED_FOR_CURRENT_DATA` |
| C6 | real-data route terminated for current data | yes | `v7_data_qualification_v3.json` `global_state` | `REAL_DATA_ROUTE=TERMINATED_FOR_CURRENT_DATA` |
| C7 | certificate/checker is experimental, not a full independent verification system; two positive-path readiness tests fail | yes (disclosed limitation) | `v7_project_terminal_status_20260818.md` §4.2; known failures in `tests/audit/test_paper_readiness_gate_negative.py` | 2 known failures |
| C8 | project stopped; contribution = limited prototype + negative result + evidence boundary | yes | `v7_project_terminal_status_20260818.md`; tag `project-stop-20260818` | — |

## Explicitly forbidden wording (must NOT appear in title/abstract/body/tables/captions/metadata)
- RNA SOTA; validated RNA experiment design; near-tight
- exact method "never worse" / "strictly better" as a performance claim
- exhaustive optimum as a ranked deployable method
- sealed external confirmation; independent biological validation
- real ADD/glycine/miniTTR gamma; absolute P(correct) from clamped reactivity; n=3/15/3
- wet-lab affordability/saving from unit cost; real cost/no-go
- cross-system / cross-chemistry / biological transfer
- complete self-contained independently-verifiable certificate; "all tests pass"; submission-ready

## Source binding
- Terminal code: tag `project-stop-20260818` (audit branch `audit/p0-semantic-repair-20260811`)
- This preprint: branch `preprint/arxiv-v1-20260820`, `docs/preprint/arxiv_v1/`
- All quantitative claims trace to `paper_eligible=false` committed artifacts or to
  this ledger's verified tests; no claim depends on uncommitted or `/mnt`-only content.
