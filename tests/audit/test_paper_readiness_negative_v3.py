"""P0-5: ten fail-closed negative fixtures for the v3 paper readiness gate.

Each fixture injects a single defect into a golden (minimal-but-valid) repo copy and
asserts the gate FAILS (the corresponding ``negative_*`` check goes FAIL, and the CLI
returns non-zero).  A clean golden copy must pass (exit 0) and leave all ten
``negative_*`` checks PASS.

Evidence resolution is exercised through the single ``AuthorityV3`` resolver; invalid /
legacy / ReactFlow evidence refs must fail-closed.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
GATE_PATH = os.path.join(SCRIPTS, "paper_readiness_gate.py")

AUTHORITY_V3_SRC = os.path.join(
    REPO_ROOT, "src", "d2t_rna", "audit", "authority_v3.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("paper_readiness_gate", GATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load_gate()

BIB = """@article{moret1991test,
  author  = {Moret, Bernard M. E. and Shapiro, Henry D.},
  title   = {On Minimizing a Set of Tests},
  journal = {SIAM Journal on Scientific and Statistical Computing}, volume = {6},
  number  = {4}, pages = {983--1003}, year = {1985}, doi = {10.1137/0906067}
}
@book{chernoff1959sequential,
  author  = {Chernoff, Herman}, title = {Sequential Analysis and Optimal Design},
  publisher = {SIAM}, year = {1972}, doi = {10.1137/1.9781611970593}
}
@article{cordero2012importance,
  author  = {Cordero, Pablo and Kladwang, Wipapat and VanLang, Christopher C. and Das, Rhiju},
  title   = {Quantitative Dimethyl Sulfate Mapping for Automated RNA Secondary Structure Inference},
  journal = {Biochemistry}, volume = {51}, number = {36}, pages = {7037--7039},
  year = {2012}, doi = {10.1021/bi3008802}
}
"""

GOLDEN_MANUSCRIPT = r"""\begin{abstract}
We describe a model-conditional, fixed-horizon, retrospective, fail-closed design
method. \citep{moret1991test,chernoff1959sequential,cordero2012importance}.
The registered gamma values are $\gamma=9/10$, $\gamma=4/5$, $\gamma=3/5$, and
$\gamma=49/50$, all within the unit interval. No held-out validation is claimed.
\end{abstract}
\section{Body}
\citep{moret1991test}
"""

GOLDEN_SUPP = r"""\section{Supplementary}
gamma values: 9/10, 4/5, 3/5, 49/50.
"""

PRIOR_ART = "METHODS_LEVEL_NOVELTY_ONLY\nNOT ESTABLISHED\n"

INDEX = {
    "schema": "d2t_rna.v7_artifact_authority_index.v3",
    "payload": {
        "index": [
            {"artifact": "manifests/m0/m0_v7_activation.json", "role": "activation",
             "file_integrity": "ok", "scientific_interpretation": "ok",
             "paper_eligible": True, "terminal_status": "CURRENT_VALID",
             "schema": "d2t_rna.m0_activation.v7"},
            {"artifact": "manifests/t2/t2_2_acceptance.json", "role": "certificate",
             "file_integrity": "ok", "scientific_interpretation": "ok",
             "paper_eligible": True, "terminal_status": "CURRENT_VALID",
             "schema": "d2t_rna.t2_2_acceptance"},
        ],
    },
}

TERMINALIZATION = {
    "schema": "d2t_rna.v7_artifact_terminalization.v3",
    "payload": {"families": []},
}

EVIDENCE_LOCK = {
    "schema": "d2t_rna.paper_evidence_lock.v1",
    "active_manifest": "manifests/m0/m0_v7_activation.json",
    "status": "PAPER_EVIDENCE_LOCKED",
}

CLAIM_REGISTER = {
    "schema": "d2t_rna.paper_claim_register",
    "allowed_claims": {
        "C1": {"claim": "certificate", "authorized": True,
               "evidence": "manifests/t2/t2_2_acceptance.json",
               "strength": "within registered finite model"},
    },
}


def _write(root, rel, content):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


def _setup_src_pkg(repo):
    """Give the golden repo its own importable d2t_rna so the resolver + import-origin
    checks are exercised against this repo (copied from the real production module)."""
    dst = os.path.join(repo, "src", "d2t_rna", "audit")
    os.makedirs(dst, exist_ok=True)
    _write(repo, "src/d2t_rna/__init__.py", "")
    _write(repo, "src/d2t_rna/audit/__init__.py", "")
    if os.path.exists(AUTHORITY_V3_SRC):
        shutil.copy(AUTHORITY_V3_SRC, os.path.join(dst, "authority_v3.py"))


def _golden(tmp_path, mutate=None):
    """Build a minimal-but-valid repo; apply ``mutate(root)`` after."""
    repo = str(tmp_path / "repo")
    if os.path.exists(repo):
        shutil.rmtree(repo)
    paper = os.path.join(repo, "docs/paper")
    mani = os.path.join(repo, "manifests/paper")
    os.makedirs(paper, exist_ok=True)
    os.makedirs(mani, exist_ok=True)

    _write(repo, "docs/paper/manuscript.tex", GOLDEN_MANUSCRIPT)
    _write(repo, "docs/paper/supplementary.tex", GOLDEN_SUPP)
    _write(repo, "docs/paper/references.bib", BIB)
    _write(repo, "docs/paper/paper_evidence_lock.md", "# evidence lock\n")
    _write(repo, "docs/paper/confirmed_contribution.md", "# contribution\nnon-empty\n")
    _write(repo, "docs/paper/prior_art_novelty_matrix_REVISED.md", PRIOR_ART)
    _write(repo, "docs/paper/results_validation.md", "# results\n")
    _write(repo, "docs/paper/claim_register.md", "# claim register\n")
    _write(repo, "docs/paper/reviewer_audit.md", "# reviewer audit\n")
    _write(repo, "docs/paper/section_blueprint.md", "# blueprint\n")
    _write(repo, "docs/paper/limitation_register.md", "# limitation\n")
    _write(repo, "docs/paper/tables/supp88.tex", "% table\n")
    _write(repo, "docs/paper/tables/retro_table.tex", "% table\n")
    # PDFs (newer than sources) so the pdf-present check is clean
    _write(repo, "docs/paper/manuscript.pdf", "%PDF-1.4 golden\n")
    _write(repo, "docs/paper/supplementary.pdf", "%PDF-1.4 golden\n")
    # evidence chain
    _write(repo, "manifests/paper/paper_evidence_lock.json",
            json.dumps(EVIDENCE_LOCK))
    _write(repo, "manifests/paper/paper_claim_register.json",
            json.dumps(CLAIM_REGISTER))
    # authority manifests
    _write(repo, "manifests/audit/v7_artifact_authority_index_v3.json",
            json.dumps(INDEX))
    _write(repo, "manifests/audit/v7_artifact_terminalization_v3.json",
            json.dumps(TERMINALIZATION))
    _write(repo, "manifests/audit/v7_decision_tree_resolution.json",
            json.dumps({"decision": "GO", "status": "RESOLVED"}))
    # semantic kill-test stubs
    _write(repo, "tests/t2/test_semantic_counterexamples.py", "def test_ok():\n    assert True\n")
    _write(repo, "tests/t2/test_decision_semantics.py", "def test_ok():\n    assert True\n")
    # importable d2t_rna under repo/src
    _setup_src_pkg(repo)

    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "feat(Batch3): golden"], check=True)

    if mutate:
        mutate(repo)
    return repo


def _compute(repo, **kw):
    """Run the gate against ``repo``, clearing any cached d2t_rna so the import
    resolves to this repo's src (not a previously-built golden)."""
    sys.path.insert(0, os.path.join(repo, "src"))
    for m in [m for m in list(sys.modules)
              if m == "d2t_rna" or m.startswith("d2t_rna.")]:
        del sys.modules[m]
    return GATE.compute(repo, **kw)


NEGATIVE_CHECKS = [
    "negative_real_quantitative_claim",
    "negative_stale_head_binding",
    "negative_legacy_invalid_evidence",
    "negative_tex_evasion",
    "negative_citation_metadata",
    "negative_nested_decision_tree_stop",
    "negative_pdf_missing_build_unknown",
    "negative_orphan_quantitative_claim",
    "negative_reactflow_evidence",
    "negative_import_origin",
]


def test_clean_positive_exits_zero_and_all_negative_pass(tmp_path):
    """A clean golden copy must pass every negative check and exit 0."""
    repo = _golden(tmp_path)
    res = _compute(repo)
    assert res["gates_all_pass"] is True
    for c in NEGATIVE_CHECKS:
        assert res["checks"][c]["status"] == "PASS", c
    code = GATE.main(["--repo", repo, "--check"])
    assert code == 0


# ---- fixture 1: clamp-as-Bernoulli real quantitative claim ------------------
def test_fixture1_real_quantitative_claim_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        with open(p, "a") as f:
            f.write("\nclamp(normalized reactivity) provides a calibrated "
                    "Bernoulli likelihood for the measured assay.\n")
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_real_quantitative_claim"]["status"] == "FAIL"


# ---- fixture 2: stale HEAD/tree binding -------------------------------------
def test_fixture2_stale_head_binding_fails(tmp_path):
    def mut(repo):
        _write(repo, "manifests/paper/paper_submission_readiness.json",
               json.dumps({"head": "deadbeef00000000000000000000000000000000",
                           "status": "READY"}))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_stale_head_binding"]["status"] == "FAIL"


# ---- fixture 3: invalid / paper_eligible=false artifact ---------------------
def test_fixture3_legacy_invalid_evidence_fails(tmp_path):
    def mut(repo):
        cr = dict(CLAIM_REGISTER)
        cr["allowed_claims"] = dict(cr["allowed_claims"])
        cr["allowed_claims"]["C99"] = {
            "claim": "tombstoned", "authorized": True,
            "evidence": "manifests/legacy/tombstoned_phase5.json",
        }
        _write(repo, "manifests/paper/paper_claim_register.json", json.dumps(cr))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_legacy_invalid_evidence"]["status"] == "FAIL"


# ---- fixture 4: TeX linebreak / synonym / negate-then-affirm evasion --------
def test_fixture4_tex_evasion_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        with open(p, "a") as f:
            f.write("\nNo evidence of separation is claimed. However the method "
                    "achieves separation.\n")
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_tex_evasion"]["status"] == "FAIL"


# ---- fixture 5: citation metadata / context gap -----------------------------
def test_fixture5_citation_metadata_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/references.bib")
        s = open(p).read().replace("year = {1972}, doi", "year = {1959}, doi")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_citation_metadata"]["status"] == "FAIL"


# ---- fixture 6: nested decision-tree STOP/BLOCKED/UNKNOWN -------------------
def test_fixture6_nested_decision_tree_stop_fails(tmp_path):
    def mut(repo):
        _write(repo, "manifests/audit/v7_decision_tree_resolution.json",
               json.dumps({"decision": {"sub": {"status": "STOP"}}}))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_nested_decision_tree_stop"]["status"] == "FAIL"


# ---- fixture 7: PDF missing / build unknown / source mismatch ---------------
def test_fixture7_pdf_missing_fails(tmp_path):
    def mut(repo):
        os.remove(os.path.join(repo, "docs/paper/manuscript.pdf"))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_pdf_missing_build_unknown"]["status"] == "FAIL"


# ---- fixture 8: orphan quantitative claim -----------------------------------
def test_fixture8_orphan_quantitative_claim_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        with open(p, "a") as f:
            f.write("\nThe separation is registered as $\\gamma=1/2$.\n")
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_orphan_quantitative_claim"]["status"] == "FAIL"


# ---- fixture 9: ReactFlow evidence ------------------------------------------
def test_fixture9_reactflow_evidence_fails(tmp_path):
    def mut(repo):
        idx = json.loads(json.dumps(INDEX))
        idx["payload"]["index"].append(
            {"artifact": "manifests/reactflow_adapter.json", "role": "evidence",
             "file_integrity": "ok", "scientific_interpretation": "external",
             "paper_eligible": True, "terminal_status": "EXTERNAL_ONLY",
             "schema": "d2t_rna.reactflow"})
        _write(repo, "manifests/audit/v7_artifact_authority_index_v3.json",
               json.dumps(idx))
        cr = json.loads(json.dumps(CLAIM_REGISTER))
        cr["allowed_claims"]["C98"] = {
            "claim": "external", "authorized": True,
            "evidence": "manifests/reactflow_adapter.json",
        }
        _write(repo, "manifests/paper/paper_claim_register.json", json.dumps(cr))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_reactflow_evidence"]["status"] == "FAIL"


# ---- fixture 10: import / source provenance UNKNOWN -------------------------
def test_fixture10_import_origin_unknown_fails(tmp_path):
    def mut(repo):
        shutil.rmtree(os.path.join(repo, "src", "d2t_rna"))
    repo = _golden(tmp_path, mut)
    assert _compute(repo)["checks"]["negative_import_origin"]["status"] == "FAIL"


# ---- 10/10 CLI non-zero for each negative fixture ---------------------------
def _cli(repo, *args):
    """Run the gate CLI against ``repo`` with a deterministic d2t_rna import."""
    sys.path.insert(0, os.path.join(repo, "src"))
    for m in [m for m in list(sys.modules)
              if m == "d2t_rna" or m.startswith("d2t_rna.")]:
        del sys.modules[m]
    return GATE.main(["--repo", repo, "--check", *args])


def _append(root, rel, text):
    p = os.path.join(root, rel)
    with open(p, "a") as f:
        f.write(text)


def _mut_f1(repo):
    _append(repo, "docs/paper/manuscript.tex",
            "\nclamp(normalized reactivity) Bernoulli likelihood on measured assay.\n")


def _mut_f2(repo):
    _write(repo, "manifests/paper/paper_submission_readiness.json",
           json.dumps({"head": "deadbeef", "status": "READY"}))


def _mut_f3(repo):
    _write(repo, "manifests/paper/paper_claim_register.json",
           json.dumps({"allowed_claims": {"C": {"evidence": "manifests/legacy/x.json"}}}))


def _mut_f4(repo):
    _append(repo, "docs/paper/manuscript.tex",
            "\nNo evidence is claimed. However the method achieves it.\n")


def _mut_f5(repo):
    p = os.path.join(repo, "docs/paper/references.bib")
    s = open(p).read().replace("year = {1972}, doi", "year = {1959}, doi")
    open(p, "w").write(s)


def _mut_f6(repo):
    _write(repo, "manifests/audit/v7_decision_tree_resolution.json",
           json.dumps({"decision": {"s": {"status": "STOP"}}}))


def _mut_f7(repo):
    os.remove(os.path.join(repo, "docs/paper/manuscript.pdf"))


def _mut_f8(repo):
    _append(repo, "docs/paper/manuscript.tex", "\nThe value is $\\gamma=1/2$.\n")


def _mut_f9(repo):
    _write(repo, "manifests/paper/paper_claim_register.json",
           json.dumps({"allowed_claims": {
               "C": {"evidence": "manifests/reactflow_adapter.json"}}}))


def _mut_f10(repo):
    shutil.rmtree(os.path.join(repo, "src", "d2t_rna"))


def test_all_ten_negative_fixtures_cli_nonzero(tmp_path):
    """Build the ten defect states and assert each makes the CLI exit non-zero."""
    mutators = [_mut_f1, _mut_f2, _mut_f3, _mut_f4, _mut_f5, _mut_f6,
                _mut_f7, _mut_f8, _mut_f9, _mut_f10]
    assert len(mutators) == 10
    for i, mut in enumerate(mutators, start=1):
        repo = _golden(tmp_path, mut)
        code = _cli(repo)
        assert code != 0, f"fixture f{i} passed (should fail)"
