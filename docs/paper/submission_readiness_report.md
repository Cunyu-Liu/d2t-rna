# D2T-RNA v7 — Submission Readiness Report (fail-closed)

> status = `PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`
> scientific_claim_authorized = False
> HEAD = ddc3eb9b416841d37092891686cc23b95c0fd60a

## Checks (PASS / FAIL / UNKNOWN)

- abstract_no_prohibited: **PASS** — prohibited hits=none
- citation_cited_subseteq_bib: **PASS** — cited-but-not-in-bib=none
- citation_all_bib_cited: **PASS** — uncited=none
- required_citation_metadata: **PASS** — verified-field mismatches=none
- reactflow_zero_evidence: **PASS** — external/reactflow evidence tokens=none
- probability_tv_in_unit_interval: **PASS** — out-of-range tv/gamma values=none
- cross_doc_tv_consistency: **PASS** — expected tv values missing=none
- not_applicable_not_abused: **PASS** — prohibited claim still present=none
- per_position_error_used_honest: **PASS** — no measured run claims per_position_error_used=True
- contribution_results_nonempty: **PASS** — empty=none
- head_has_semantic_repair: **PASS** — HEAD subject=docs(P6): finalize manuscript+supplementary for Phase4-v2 synthetic benchmark; xr-hyper cross-refs; TERMINATED real-data disclosure
- import_origin_is_repo_src: **PASS** — d2t_rna resolves under repo/src
- semantic_kill_tests: **PASS** — ................................                                         [100%] =============================== warnings summary =============================== ../miniconda3/envs/editflow311/lib/python3.11/site-packages/_pytest/config/__init__.py:1434   /home/cunyuliu/miniconda3/envs/editflow311/lib/python3.11/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: timeout        self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html 32 passed, 1 warning in 0.38s
- decision_tree_not_gate_open: **PASS** — no open STOP
- pdf_build: **FAIL** — build failed or latex unavailable

## Gates

- PAPER-EVIDENCE-LOCK-GATE: PASS
- PAPER-AUTHORITY-PRECEDENCE-GATE: PASS
- PAPER-CONTRIBUTION-GATE: PASS
- PAPER-PRIOR-ART-NOVELTY-GATE: PASS
- PAPER-RESULTS-VALIDATION-GATE: PASS
- PAPER-CLAIM-BOUNDARY-GATE: PASS
- PAPER-REVIEWER-AUDIT-GATE: PASS
- PAPER-REPRODUCIBILITY-GATE: PASS
- PAPER-CITATION-CLOSURE-GATE: PASS
- PAPER-CITATION-METADATA-GATE: PASS
- PAPER-REACTFLOW-ZERO-GATE: PASS
- PAPER-NUMERIC-RANGE-GATE: PASS
- PAPER-CROSSDOC-CONSISTENCY-GATE: PASS
- PAPER-SEMANTIC-KILL-GATE: PASS
- PAPER-SEMANTIC-ERROR-UNUSED-GATE: PASS
- PAPER-DECISION-TREE-GATE: PASS
- PAPER-CONTRIBUTION-NONEMPTY-GATE: PASS
- PAPER-HEAD-REPAIR-GATE: PASS
- PAPER-IMPORT-ORIGIN-GATE: PASS

## Overall: ALL PASS

This is a fail-closed internal evidence gate, not a scientific claim authorization and not a submission/acceptance status.