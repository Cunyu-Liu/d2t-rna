# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = 28660be7185d1fb3f6cc3729711210b934d1c964
origin/main    = 28660be7185d1fb3f6cc3729711210b934d1c964
worktree state = clean
```

## 2. Paper artifact hashes

Synthesized hashes (computed at gate time; see
`manifests/paper/paper_submission_readiness.json` for the full set). The claim
register, manuscript, reviewer audit, and submission readiness manifests are
tracked in git and their current SHAs are bound by the commit history.

## 3. Paper gates (all PASS)

PAPER-EVIDENCE-LOCK-GATE / PAPER-AUTHORITY-PRECEDENCE-GATE / PAPER-CONTRIBUTION-GATE /
PAPER-PRIOR-ART-NOVELTY-GATE / PAPER-RESULTS-VALIDATION-GATE / PAPER-CLAIM-BOUNDARY-GATE /
PAPER-REVIEWER-AUDIT-GATE / PAPER-REPRODUCIBILITY-GATE.

Abstract: exactly 5 sentences, 0 prohibited-word hits, >=4 required phrases present.

## 4. Novelty verdict (revised 2026-08-05)

`METHODS_LEVEL_NOVELTY_ONLY` — theorem-level novelty **NOT ESTABLISHED** (all mathematical
components classical: Markov-basis fiber connectivity, fixed-horizon Hellinger/Chernoff
bounds, Test-Cover, LP duality). Framework-level novelty is **modest and methods-only**:
RNA-feasible composite registration (complete registered difference set, explicit
cross-class nuisance coupling, exact replayable certificate, finite-sample/no-go
consequences tied to RNA action geometry, fail-closed retrospective data qualification).

The paper is publishable as a **methods / experimental-design contribution** at a methods
venue, **not** as a novel theorem paper. Position accordingly; do not headline any single
mathematical component as novel. See `docs/paper/prior_art_novelty_matrix_REVISED.md`.

## 5. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。

## 6. Remaining author decisions

- 确认 working title（现为中性候选，未冻结）：Certified Collision-or-Separation Design for
  Finite RNA State Discrimination。
- 确认 novelty 定位为 METHODS_LEVEL_NOVELTY_ONLY（methods/experimental-design 论文）。
- 确认投稿 venue（建议 methods/experimental-design 类，非 broad-theory 顶会）。
- 作者列表、通讯信息、最终引用与许可复核（§0.1 rule 6 / §15）。