# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = 40895a22ea484a6f5b90e5f369b58e2b97810dba
origin/main    = 051f30fb04e665538535ec9e96a1a86815c01513
worktree state = DIRTY
```

## 2. Lineage (bound)

```text
40895a2 docs(paper): formal T2b/T2c/T2d theorem blocks, complete citations, worked numerics, structured figure captions, supplementary with full proofs and 88-row baseline table
051f30f docs(paper): freeze working title, novelty positioning, venue class, license; author details deferred to submission
af601ac docs(paper): add fig5 misspecification boundary and fix NOT_ESTABLISHED subscript in caption
07a0ce7 docs(paper): downgrade novelty verdict to METHODS_LEVEL_NOVELTY_ONLY
28660be feat(paper): integrate real SVG figures into LaTeX manuscript + add fig4
9039ab0 chore(paper): refresh submission-readiness manifest snapshot
```

The readiness report is re-generated from the current HEAD (40895a22ea484a6f5b90e5f369b58e2b97810dba), which is a descendant of
051f30f in the lineage af601ac -> 051f30f -> 40895a2.

## 3. Paper artifact hashes (recomputed at gate time)

See `manifests/paper/paper_submission_readiness.json` for the full set. Key files:

```text
manuscript.tex      = f0bc0504a02a36c3caf7dae21e9052eec8c8a00d04fb626e1706ab42c75b5c29
supplementary.tex   = 4fcefb5ce7fe7b40108020ca90be6ad72449848d1e05d114b3572bb86dd98a0f
references.bib      = 33f7d5a802861d5cf9f58573879cf300258d4635e0b64495798b3a8fa5c27cf4
retro_table.tex     = 551adb143e55c122132380c8f532089c0e3e9b6be6d5b2049a140676b1131503
supp88.tex          = 206fd7d588e34bbb12a18e85f8cfc1c1d9f8e7ecac6dce884f298667cb138f58
evidence_lock.json  = f8c2d4deca3dc969c2f8fd7115a0b5b586b2f5fe46e76c565283ba56f41119d2
```

## 4. Paper gates (ALL PASS)

PAPER-EVIDENCE-LOCK-GATE / PAPER-AUTHORITY-PRECEDENCE-GATE / PAPER-CONTRIBUTION-GATE / PAPER-PRIOR-ART-NOVELTY-GATE / PAPER-RESULTS-VALIDATION-GATE / PAPER-CLAIM-BOUNDARY-GATE / PAPER-REVIEWER-AUDIT-GATE / PAPER-REPRODUCIBILITY-GATE.

Abstract: 5 sentences, prohibited hits=none.
Citations: 10 bib entries, 0 uncited (none).
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

- P0 readiness report synced to HEAD 40895a2 (this file).
- P0 formal theorem blocks (T2b/T2c/T2d) written in manuscript.tex with definitions, assumptions,
  iff statements, complete D and gamma(S), witness/attainment conditions, action-map to categorical
  observation-law connection, T2c finite-sample formula and constants, T2d primal/dual, proof
  sketches; full proofs in supplementary.tex.
- P0 complete citations: all 10 .bib entries cited in text via \citep (incl. diaconis1998markov).
- P0 placeholder cleanup: retro_table.tex completed; 88-row baseline table in supplementary
  (supp88.tex); every figure caption gives question/result/interpretation/boundary.
- P1 worked numerical cases in manuscript.tex (exact collision, strict separation, cancellation,
  finite-sample vs exact oracle, cost/no-go, abstention boundary) and 8-baseline comparison table.
- P1 full build on 40895a2 with provenance (see build_provenance).

## 8. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。
- 真实作者列表、通讯信息、最终引用与许可复核须在投稿前提供（rule 6 / RamSci 15）。
