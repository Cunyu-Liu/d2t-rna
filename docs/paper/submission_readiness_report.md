# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = cf1126a5d00aad765e1f84c308e94801c8f70cf9
origin/main    = cf1126a5d00aad765e1f84c308e94801c8f70cf9
worktree state = clean
```

## 2. Lineage (bound)

```text
cf1126a chore(paper): regeneration of readiness report + manifest bound to c690aaf and commit build provenance
c690aaf docs(paper): tighten theorem rigor per reviewer 1 and rebalance novelty framing per reviewer 2
cae90f3 chore(paper): sync readiness report + manifest to 947ef1f and commit build provenance
947ef1f chore(paper): refresh readiness report bound to 74e4553
74e4553 docs(paper): reword abbreviated baseline caption (remove placeholder phrasing)
1ef13f4 chore(paper): refresh readiness report + manifest bound to eb69f19 (origin/main in sync)
```

The readiness report is re-generated from the current HEAD (cf1126a5d00aad765e1f84c308e94801c8f70cf9), which is a descendant of
051f30f in the lineage af601ac -> 051f30f -> cf1126a.

## 3. Paper artifact hashes (recomputed at gate time)

See `manifests/paper/paper_submission_readiness.json` for the full set. Key files:

```text
manuscript.tex      = a23e576980f87ef536c7d3c70c5d7be29a356a3fc161efb04ea6b8478560d45e
supplementary.tex   = f659b38099c38f6d6c125b422ce1897d4a2f73e16b62a4d33eb7dcef287dd338
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

- P0 readiness report synced to HEAD cf1126a (this file).
- P0 formal theorem blocks (T2b/T2c/T2d) written in manuscript.tex with definitions, assumptions,
  iff statements, complete D and gamma(S), witness/attainment conditions, action-map to categorical
  observation-law connection, T2c finite-sample formula and constants, T2d primal/dual, proof
  sketches; full proofs in supplementary.tex.
- P0 complete citations: all 10 .bib entries cited in text via \citep (incl. diaconis1998markov).
- P0 placeholder cleanup: retro_table.tex completed; 88-row baseline table in supplementary
  (supp88.tex); every figure caption gives question/result/interpretation/boundary.
- P1 worked numerical cases in manuscript.tex (exact collision, strict separation, cancellation,
  finite-sample vs exact oracle, cost/no-go, abstention boundary) and 8-baseline comparison table.
- P1 full build on cf1126a with provenance (see build_provenance).

## 8. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。
- 真实作者列表、通讯信息、最终引用与许可复核须在投稿前提供（rule 6 / RamSci 15）。
