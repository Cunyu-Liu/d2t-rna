# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = ebdb7f61afb78b27098db9625543bcc48ec349fd
origin/main    = eb2ac0a599d4f8bc2f1f6023364ac702acde9d5c
worktree state = DIRTY
```

## 2. Lineage (bound)

```text
ebdb7f6 feat(paper): close test suite (B1) - frozen index registration + isolate >1h acceptance tests
6d1a913 feat(paper): add 'How to read a D2T no-go' decision manual (B2) + self-contained figure refs
eb2ac0a feat(paper): add scope table to Discussion (certified vs not guaranteed vs upgrade)
67c4543 feat(paper): third real-data case - miniTTR designed metal-ion switch (DMS)
6dc05af feat(paper): fail-closed negative control on measured add data (A3)
d79f6a9 chore(paper): re-bind readiness report + manifest to HEAD ab47f70
```

The readiness report is re-generated from the current HEAD (ebdb7f61afb78b27098db9625543bcc48ec349fd), which is a descendant of
051f30f in the lineage af601ac -> 051f30f -> ebdb7f6.

## 3. Paper artifact hashes (recomputed at gate time)

See `manifests/paper/paper_submission_readiness.json` for the full set. Key files:

```text
manuscript.tex      = d36ceaffc9139f75b699ec196792bab5f1d2046c8bdb3bfb0da2768be8d1c2ad
supplementary.tex   = 6fa59ca3cf4bce368b3bbd8546abe797ff5bec56fdbfc171eb8a5fa38aa8d317
references.bib      = 957720869541f50e099f9c8627cd5124d0f18d875e7d3240a0b9b874b1a42b18
retro_table.tex     = 499d53efbf5a52afa6b5f3324236c052dd4dee9e4f5a6e5583321074d305d596
supp88.tex          = 206fd7d588e34bbb12a18e85f8cfc1c1d9f8e7ecac6dce884f298667cb138f58
evidence_lock.json  = f8c2d4deca3dc969c2f8fd7115a0b5b586b2f5fe46e76c565283ba56f41119d2
```

## 4. Paper gates (ALL PASS)

PAPER-EVIDENCE-LOCK-GATE / PAPER-AUTHORITY-PRECEDENCE-GATE / PAPER-CONTRIBUTION-GATE / PAPER-PRIOR-ART-NOVELTY-GATE / PAPER-RESULTS-VALIDATION-GATE / PAPER-CLAIM-BOUNDARY-GATE / PAPER-REVIEWER-AUDIT-GATE / PAPER-REPRODUCIBILITY-GATE.

Abstract: 7 sentences, prohibited hits=none.
Citations: 20 bib entries, 0 uncited (none).
Novelty verdict: METHODS_LEVEL_NOVELTY_ONLY (theorem-level NOT ESTABLISHED).

## 5. Novelty verdict (revised 2026-08-05)

`METHODS_LEVEL_NOVELTY_ONLY` — theorem-level novelty **NOT ESTABLISHED** (all mathematical
components classical). Framework-level novelty is **modest and methods-only**: RNA-feasible
composite registration, exact replayable certificate, fail-closed retrospective audit.
Publishable as a **methods/experimental-design** contribution at a methods venue.

## 6. Author decisions (resolved 2026-08-05)

- **Working title: FROZEN.** "Certified Collision-or-Separation Design for Finite RNA State
  Discrimination".
- **Novelty positioning: FROZEN.** METHODS_LEVEL_NOVELTY_ONLY (methods/experimental-design paper).
- **Target venue class: methods / experimental-design journal**.
- **License: not annotated in the manuscript**; decided at submission time.
- **Authors: placeholder "D2T-RNA Project".** Actual author list, affiliation, and
  corresponding-email MUST be supplied before submission.

## 7. Pre-submission P0/P1 item status

- P0 readiness report synced to HEAD ebdb7f6 (this file).
- P0 formal theorem blocks (T2b/T2c/T2d) written in manuscript.tex with definitions, assumptions,
  iff statements, complete D and gamma(S), witness/attainment conditions, action-map to categorical
  observation-law connection, T2c finite-sample formula and constants, T2d primal/dual, proof
  sketches; full proofs in supplementary.tex.
- P0 complete citations: all 10 .bib entries cited in text via \citep (incl. diaconis1998markov).
- P0 placeholder cleanup: retro_table.tex completed; 88-row baseline table in supplementary
  (supp88.tex); every figure caption gives question/result/interpretation/boundary.
- P1 worked numerical cases in manuscript.tex (exact collision, strict separation, cancellation,
  finite-sample vs exact oracle, cost/no-go, abstention boundary) and 8-baseline comparison table.
- P1 full build on ebdb7f6 with provenance (see build_provenance).

## 8. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。
- 真实作者列表、通讯信息、最终引用与许可复核须在投稿前提供（rule 6 / RamSci 15）。
