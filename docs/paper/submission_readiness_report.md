# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = 24627d2315b7f2e53d63a812986f651273a305e6
origin/main    = a31f060c190fd00cb7f34d58a9ae37acafa4b256
worktree state = clean
```

## 2. Lineage (bound)

```text
24627d2 docs(P0-0): add v6/v7/README/paper authority diff and claim retraction ledger
6ebf8b4 docs(P0-1/P0-2): freeze v7 snapshot/strong-claim blocker ledger and T2 semantics v2 spec
b1e0285 chore(paper): re-bind readiness gate to HEAD 3198de4 after P0-7 evidence rebind (ALL PASS, clean worktree)
3198de4 chore(paper): P0-7 fresh evidence rebind to HEAD 5772eca (TV-normalized gamma + corrected semantics)
5772eca fix(P0-3..6): semantic kernel rescue, decision semantics, measured-claim honesty, matched benchmark
a31f060 chore(paper): re-bind readiness gate to HEAD b8444ce after closure-index fix (ALL PASS, uncited=[])
```

The readiness report is re-generated from the current HEAD (24627d2315b7f2e53d63a812986f651273a305e6), which is a descendant of
051f30f in the lineage af601ac -> 051f30f -> 24627d2.

## 3. Paper artifact hashes (recomputed at gate time)

See `manifests/paper/paper_submission_readiness.json` for the full set. Key files:

```text
manuscript.tex      = 8bf3b5155030f87b794e2a32efd7c47b53fe94f9c2b1725faf49b15c75843f87
supplementary.tex   = 8811ba6d8726955b17542dc900dcd772a9a95cf629f4381211013d5b3e5980e5
references.bib      = 957720869541f50e099f9c8627cd5124d0f18d875e7d3240a0b9b874b1a42b18
retro_table.tex     = 499d53efbf5a52afa6b5f3324236c052dd4dee9e4f5a6e5583321074d305d596
supp88.tex          = 206fd7d588e34bbb12a18e85f8cfc1c1d9f8e7ecac6dce884f298667cb138f58
evidence_lock.json  = f89b75bb807656c4457619ce918c8dc4b0608b64343944063f3ce384abccb50f
```

## 4. Paper gates (ALL PASS)

PAPER-EVIDENCE-LOCK-GATE / PAPER-AUTHORITY-PRECEDENCE-GATE / PAPER-CONTRIBUTION-GATE / PAPER-PRIOR-ART-NOVELTY-GATE / PAPER-RESULTS-VALIDATION-GATE / PAPER-CLAIM-BOUNDARY-GATE / PAPER-REVIEWER-AUDIT-GATE / PAPER-REPRODUCIBILITY-GATE / PAPER-SEMANTIC-KILL-GATE / PAPER-SEMANTIC-ERROR-UNUSED-GATE / PAPER-SEMANTIC-DEFINITION-GATE.

Semantic lint (P0-7): TV-in-[0,1]=ALL PASS,
forged-witness/kill-tests=ALL PASS,
error-unused-honest=ALL PASS,
definition-drift=ALL PASS.

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

- P0 readiness report synced to HEAD 24627d2 (this file).
- P0 formal theorem blocks (T2b/T2c/T2d) written in manuscript.tex with definitions, assumptions,
  iff statements, complete D and gamma(S), witness/attainment conditions, action-map to categorical
  observation-law connection, T2c finite-sample formula and constants, T2d primal/dual, proof
  sketches; full proofs in supplementary.tex.
- P0 complete citations: all 10 .bib entries cited in text via \citep (incl. diaconis1998markov).
- P0 placeholder cleanup: retro_table.tex completed; 88-row baseline table in supplementary
  (supp88.tex); every figure caption gives question/result/interpretation/boundary.
- P1 worked numerical cases in manuscript.tex (exact collision, strict separation, cancellation,
  finite-sample vs exact oracle, cost/no-go, abstention boundary) and 8-baseline comparison table.
- P1 full build on 24627d2 with provenance (see build_provenance).

## 8. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。
- 真实作者列表、通讯信息、最终引用与许可复核须在投稿前提供（rule 6 / RamSci 15）。
