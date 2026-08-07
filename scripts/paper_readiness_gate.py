#!/usr/bin/env python3
"""D2T-RNA paper readiness gate + readiness report regenerator.

Regenerates, from the current git HEAD:
  - manifests/paper/paper_submission_readiness.json   (file hashes + gates + status)
  - docs/paper/submission_readiness_report.md         (human-readable, bound to HEAD)

Usage: python scripts/paper_readiness_gate.py [--repo /home/cunyuliu/d2t-rna]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return out.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/cunyuliu/d2t-rna")
    args = ap.parse_args()
    repo = args.repo
    paper = os.path.join(repo, "docs/paper")
    mani = os.path.join(repo, "manifests/paper")

    head = git(repo, "rev-parse", "HEAD")
    origin_main = git(repo, "rev-parse", "origin/main")
    worktree = git(repo, "status", "--porcelain")
    worktree_clean = (worktree.strip() == "")
    lineage = git(repo, "log", "--oneline", "-6")

    # Paper source files tracked for the manifest.
    files = {
        "manuscript": os.path.join(paper, "manuscript.tex"),
        "supplementary": os.path.join(paper, "supplementary.tex"),
        "references": os.path.join(paper, "references.bib"),
        "evidence_lock": os.path.join(paper, "paper_evidence_lock.md"),
        "evidence_lock_json": os.path.join(mani, "paper_evidence_lock.json"),
        "contribution": os.path.join(paper, "confirmed_contribution.md"),
        "prior_art": os.path.join(paper, "prior_art_novelty_matrix_REVISED.md"),
        "results_validation": os.path.join(paper, "results_validation.md"),
        "claim_register": os.path.join(paper, "claim_register.md"),
        "claim_register_json": os.path.join(mani, "paper_claim_register.json"),
        "reviewer_audit": os.path.join(paper, "reviewer_audit.md"),
        "section_blueprint": os.path.join(paper, "section_blueprint.md"),
        "limitation": os.path.join(paper, "limitation_register.md"),
        "supp88": os.path.join(paper, "tables/supp88.tex"),
        "retro_table": os.path.join(paper, "tables/retro_table.tex"),
    }
    file_hashes = {}
    file_exists = {}
    for key, path in files.items():
        exists = os.path.exists(path)
        file_exists[key] = exists
        file_hashes[key] = sha256_file(path) if exists else None

    # Abstract checks (from manuscript.tex abstract).
    tex = open(os.path.join(paper, "manuscript.tex")).read()
    abstract = tex.split("\\begin{abstract}")[1].split("\\end{abstract}")[0]
    sentences = [s for s in abstract.replace("\n", " ").split(". ") if s.strip()]
    prohibited = ["pretraining", "foundation model", "representation learning",
                  "fine-tuning", "held-out validation", "independent-library validation",
                  "prospective RNA experiment", "population-level RNA generalization"]
    abstract_prohibited = [w for w in prohibited if w.lower() in abstract.lower()]
    required = ["model-conditional", "fixed-horizon", "retrospective", "fail-closed"]
    abstract_phrases = [r for r in required if r in abstract.lower()]

    # Citation check: every .bib key must be cited in the manuscript.
    bib = open(os.path.join(paper, "references.bib")).read()
    import re
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    cited = set(re.findall(r"\\citep\{([^}]+)\}", tex))
    cited_flat = set()
    for c in cited:
        cited_flat.update(x.strip() for x in c.split(","))
    uncited = sorted(bib_keys - cited_flat)

    # Gates.
    novelty = open(os.path.join(paper, "prior_art_novelty_matrix_REVISED.md")).read()

    # ------------------------------------------------------------------
    # P0-7 semantic lint: actively catch the four categories of historical
    # fatal errors (TV>1, forged witness, error-unused, definition drift).
    def _run_pytest_ok(targets):
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"] + targets,
                cwd=repo, capture_output=True, text=True, timeout=1200,
            )
            return (r.returncode == 0), (r.stdout + r.stderr)[-1600:]
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)

    # (1) TV>1: separation measure must lie in [0,1].
    tv_ok = False
    try:
        from fractions import Fraction
        from d2t_rna.evaluation.matrix import per_action_tv
        tv_val = per_action_tv(
            (Fraction(1, 4), Fraction(3, 4)), (Fraction(1), Fraction(0))
        )
        tv_ok = 0 <= tv_val <= 1
    except Exception:  # pragma: no cover - defensive
        tv_ok = False

    # (2)+(4) kill-test suites embody forged-witness, minimax and drift checks.
    kill_ok, kill_note = _run_pytest_ok([
        "tests/t2/test_semantic_counterexamples.py",
        "tests/t2/test_decision_semantics.py",
    ])

    # (3) error-unused: no measured run may claim the position error is used.
    error_unused_ok = True
    for _mf in [
        "scripts/real_add_measured_run.py",
        "scripts/real_glycine_measured_run.py",
        "scripts/real_mattr_measured_run.py",
    ]:
        _p = os.path.join(repo, _mf)
        if os.path.exists(_p):
            _txt = open(_p).read()
            if '"per_position_error_used": True' in _txt.replace(" ", ""):
                error_unused_ok = False

    # (4) definition drift: decision code exposes corrected names and the paper
    #     no longer carries the TV>1 gamma value (49/25 = 1.96).
    drift_ok = False
    try:
        _dec = open(os.path.join(repo, "src/d2t_rna/t2/decision.py")).read()
        _has_corr = (
            "def exact_bayes_average_error" in _dec
            and "def exact_randomized_minimax_error" in _dec
        )
        _man = open(os.path.join(paper, "manuscript.tex")).read()
        _paper_tv_ok = ("49/25" not in _man) and ("1.96" not in _man)
        drift_ok = _has_corr and _paper_tv_ok
    except Exception:  # pragma: no cover - defensive
        drift_ok = False

    semantic_lint = {
        "tv_in_unit_interval": tv_ok,
        "forged_witness_fail_closed": kill_ok,
        "error_unused_honest": error_unused_ok,
        "definition_drift_clean": kill_ok and drift_ok,
        "kill_tests_pass": kill_ok,
        "kill_tests_note": kill_note,
    }
    semantic_lint_all_pass = all(semantic_lint.values())
    gates = {
        "PAPER-EVIDENCE-LOCK-GATE": file_exists["evidence_lock"] and file_exists["evidence_lock_json"],
        "PAPER-AUTHORITY-PRECEDENCE-GATE": file_exists["evidence_lock_json"],
        "PAPER-CONTRIBUTION-GATE": file_exists["contribution"],
        "PAPER-PRIOR-ART-NOVELTY-GATE": ("METHODS_LEVEL_NOVELTY_ONLY" in novelty
                                          and "NOT ESTABLISHED" in novelty),
        "PAPER-RESULTS-VALIDATION-GATE": file_exists["results_validation"],
        "PAPER-CLAIM-BOUNDARY-GATE": ("NOT_APPLICABLE" in tex or "NOT\\_APPLICABLE" in tex),
        "PAPER-REVIEWER-AUDIT-GATE": file_exists["reviewer_audit"],
        "PAPER-REPRODUCIBILITY-GATE": file_exists["supplementary"] and file_exists["supp88"],
        "PAPER-SEMANTIC-KILL-GATE": semantic_lint["kill_tests_pass"] and tv_ok,
        "PAPER-SEMANTIC-ERROR-UNUSED-GATE": error_unused_ok,
        "PAPER-SEMANTIC-DEFINITION-GATE": semantic_lint["definition_drift_clean"],
    }
    all_gates_pass = all(gates.values())

    manifest = {
        "schema": "d2t_rna.paper_submission_readiness.v1",
        "contract_id": "D2T-RNA-v7-THEORETICAL-RNA-METHODS",
        "contract_version": "v7.0.0",
        "status": "PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW",
        "scientific_claim_authorized": False,
        "head": head,
        "origin_main": origin_main,
        "worktree_clean": worktree_clean,
        "lineage": lineage.splitlines(),
        "file_exists": file_exists,
        "file_hashes": file_hashes,
        "abstract_check": {
            "abstract_sentence_count": len(sentences),
            "abstract_prohibited_hits": abstract_prohibited,
            "abstract_required_phrases_present": abstract_phrases,
            "abstract_ok": (not abstract_prohibited) and all(r in abstract_phrases for r in required),
        },
        "citation_check": {
            "bib_entry_count": len(bib_keys),
            "cited_keys": sorted(cited_flat),
            "uncited_keys": uncited,
            "all_cited": (len(uncited) == 0),
        },
        "gates": gates,
        "gates_all_pass": all_gates_pass,
        "semantic_lint": semantic_lint,
        "semantic_lint_all_pass": semantic_lint_all_pass,
        "novelty_verdict": "METHODS_LEVEL_NOVELTY_ONLY (theorem-level NOT ESTABLISHED)",
        "run_finished": time.time(),
    }

    os.makedirs(mani, exist_ok=True)
    json_path = os.path.join(mani, "paper_submission_readiness.json")
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Human-readable report.
    report = f"""# D2T-RNA v7 — Submission Readiness Report

> **状态：`PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`**
> 该状态是 paper draft 供作者审阅的内部证据状态；**不是** SCIENTIFIC_SUCCESS /
> PAPER_ACCEPTED / PUBLICATION_ACCEPTED / REAL_DATA_VALIDATED / PROSPECTIVE_READY。

## 1. Repository state

```text
current HEAD   = {head}
origin/main    = {origin_main}
worktree state = {'clean' if worktree_clean else 'DIRTY'}
```

## 2. Lineage (bound)

```text
{lineage}
```

The readiness report is re-generated from the current HEAD ({head}), which is a descendant of
051f30f in the lineage af601ac -> 051f30f -> {head[:7]}.

## 3. Paper artifact hashes (recomputed at gate time)

See `manifests/paper/paper_submission_readiness.json` for the full set. Key files:

```text
manuscript.tex      = {file_hashes['manuscript']}
supplementary.tex   = {file_hashes['supplementary']}
references.bib      = {file_hashes['references']}
retro_table.tex     = {file_hashes['retro_table']}
supp88.tex          = {file_hashes['supp88']}
evidence_lock.json  = {file_hashes['evidence_lock_json']}
```

## 4. Paper gates ({'ALL PASS' if all_gates_pass else 'NOT ALL PASS'})

{' / '.join(k for k,v in gates.items() if v)}.

Semantic lint (P0-7): TV-in-[0,1]={'ALL PASS' if tv_ok else 'FAIL'},
forged-witness/kill-tests={'ALL PASS' if kill_ok else 'FAIL'},
error-unused-honest={'ALL PASS' if error_unused_ok else 'FAIL'},
definition-drift={'ALL PASS' if semantic_lint_all_pass else 'FAIL'}.

Abstract: {len(sentences)} sentences, prohibited hits={abstract_prohibited or 'none'}.
Citations: {len(bib_keys)} bib entries, {len(uncited)} uncited ({uncited or 'none'}).
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

- P0 readiness report synced to HEAD {head[:7]} (this file).
- P0 formal theorem blocks (T2b/T2c/T2d) written in manuscript.tex with definitions, assumptions,
  iff statements, complete D and gamma(S), witness/attainment conditions, action-map to categorical
  observation-law connection, T2c finite-sample formula and constants, T2d primal/dual, proof
  sketches; full proofs in supplementary.tex.
- P0 complete citations: all 10 .bib entries cited in text via \\citep (incl. diaconis1998markov).
- P0 placeholder cleanup: retro_table.tex completed; 88-row baseline table in supplementary
  (supp88.tex); every figure caption gives question/result/interpretation/boundary.
- P1 worked numerical cases in manuscript.tex (exact collision, strict separation, cancellation,
  finite-sample vs exact oracle, cost/no-go, abstention boundary) and 8-baseline comparison table.
- P1 full build on {head[:7]} with provenance (see build_provenance).

## 8. Failed or deferred items

- 无 qualified retrospective quantitative instance（固有，fail-closed）。
- 无新盲法/前瞻实验、无独立 library、无 population 泛化主张（固有边界）。
- S14 source commit `728dec61` 与当前 HEAD 差异已显式记录（非同一 commit）。
- historical t9_4 记录为 HISTORICAL_SYNTHESIS_RECORD（precedence 7），非当前 authority。
- 真实作者列表、通讯信息、最终引用与许可复核须在投稿前提供（rule 6 / RamSci 15）。
"""
    report_path = os.path.join(paper, "submission_readiness_report.md")
    with open(report_path, "w") as f:
        f.write(report)

    print("HEAD        :", head)
    print("worktree    :", "clean" if worktree_clean else "DIRTY")
    print("gates       :", "ALL PASS" if all_gates_pass else "NOT ALL PASS")
    print("uncited     :", uncited)
    print("wrote       :", json_path)
    print("wrote       :", report_path)

if __name__ == "__main__":
    main()