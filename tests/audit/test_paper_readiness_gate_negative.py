"""Negative fixtures for the fail-closed paper readiness gate (Batch 4.5).

Each fixture injects a single defect into a golden (minimal-but-valid) repo copy and
asserts that ``paper_readiness_gate.compute`` reports the corresponding FAIL (or that
the CLI returns non-zero / refuses to write), never a false PASS.

The real repository is never modified: every fixture builds into a pytest tmp_path.
"""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
GATE_PATH = os.path.join(SCRIPTS, "paper_readiness_gate.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("paper_readiness_gate", GATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load_gate()

BIB = """@article{diaconis1998markov,
  author  = {Diaconis, Persi and Sturmfels, Bernd},
  title   = {Algebraic Algorithms for Sampling from Conditional Distributions},
  journal = {The Annals of Statistics}, volume = {26}, number = {1},
  pages   = {363--397}, year = {1998}
}
@article{moret1991test,
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
method. \citep{diaconis1998markov,moret1991test,chernoff1959sequential,cordero2012importance}.
The registered gamma values are $\gamma=9/10$, $\gamma=4/5$, $\gamma=3/5$, and
$\gamma=49/50$, all within the unit interval. No held-out validation is claimed.
\end{abstract}
\section{Body}
\citep{diaconis1998markov}
"""

GOLDEN_SUPP = r"""\section{Supplementary}
gamma values: 9/10, 4/5, 3/5, 49/50.
"""

PRIOR_ART = "METHODS_LEVEL_NOVELTY_ONLY\nNOT ESTABLISHED\n"


def _write(root, rel, content):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


def _golden(tmp_path, mutate=None):
    """Build a minimal repo that the gate can read; apply ``mutate(root)`` after."""
    repo = str(tmp_path / "repo")
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
    _write(repo, "manifests/paper/paper_evidence_lock.json",
            json.dumps({"current_head": "abc", "status": "PAPER_EVIDENCE_LOCKED"}))
    _write(repo, "manifests/paper/paper_claim_register.json",
            json.dumps({"prohibited_present_in_manuscript": False, "status": "PASS"}))
    _write(repo, "manifests/audit/v7_decision_tree_resolution.json",
            json.dumps({"decision": "GO", "status": "RESOLVED"}))
    # the gate runs the semantic kill-tests; provide passing stubs so a golden passes
    _write(repo, "tests/t2/test_semantic_counterexamples.py", "def test_ok():\n    assert True\n")
    _write(repo, "tests/t2/test_decision_semantics.py", "def test_ok():\n    assert True\n")
    # a git repo so git() calls succeed
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "feat(Batch3): golden"], check=True)

    if mutate:
        mutate(repo)
    return repo


def _check_status(repo, name):
    return GATE.compute(repo)["checks"][name]["status"]


# ---------------------------------------------------------------------------
# Fixtures (plan 4.5)
# ---------------------------------------------------------------------------

def test_tv_out_of_range_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read().replace("$\\gamma=9/10$", "$\\gamma=9/5$")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "probability_tv_in_unit_interval") == "FAIL"


def test_missing_evidence_lock_fails(tmp_path):
    def mut(repo):
        os.remove(os.path.join(repo, "docs/paper/paper_evidence_lock.md"))
    repo = _golden(tmp_path, mut)
    assert GATE.compute(repo)["gates"]["PAPER-EVIDENCE-LOCK-GATE"] is False


def test_wrong_cite_key_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read().replace("\\citep{diaconis1998markov}", "\\citep{wrongkey}")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "citation_cited_subseteq_bib") == "FAIL"


def test_bib_field_error_fails(tmp_path):
    """Bibliography field error: chernoff must be 1972, not 1959."""
    def mut(repo):
        p = os.path.join(repo, "docs/paper/references.bib")
        s = open(p).read().replace("year = {1972}, doi", "year = {1959}, doi")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "required_citation_metadata") == "FAIL"


def test_prohibited_claim_synonym_fails(tmp_path):
    """Paraphrase (not exact banned word) of a real-data overclaim must fail."""
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read() + "\nA measured certificate on the assay is reported.\n"
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "not_applicable_not_abused") == "FAIL"


def test_decision_tree_stop_fails(tmp_path):
    def mut(repo):
        _write(repo, "manifests/audit/v7_decision_tree_resolution.json",
               json.dumps({"decision": "STOP", "status": "BLOCKED"}))
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "decision_tree_not_gate_open") == "FAIL"


def test_reactflow_evidence_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read() + "\nA ReactFlow adapter produces the evidence.\n"
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "reactflow_zero_evidence") == "FAIL"


def test_undefined_citet_key_fails(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read() + "\n\\citet{missing_key}.\n"
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "citation_cited_subseteq_bib") == "FAIL"


def test_gate_false_cli_returns_nonzero(tmp_path):
    repo = _golden(tmp_path, lambda r: os.remove(
        os.path.join(r, "docs/paper/paper_evidence_lock.md")))
    code = GATE.main(["--repo", repo, "--check"])
    assert code != 0


def test_check_does_not_write_authoritative(tmp_path):
    outdir = str(tmp_path / "out")
    repo = _golden(tmp_path)
    code = GATE.main(["--repo", repo, "--check", "--outdir", outdir])
    assert code == 0
    # authoritative paths must NOT be created by --check
    assert not os.path.exists(os.path.join(repo, "manifests/paper/paper_submission_readiness.json"))
    assert not os.path.exists(os.path.join(repo, "docs/paper/submission_readiness_report.md"))
    # outputs went only to --outdir
    assert os.path.exists(os.path.join(outdir, "paper_readiness_check.json"))


def test_write_refuses_on_failure(tmp_path):
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read().replace("\\citep{diaconis1998markov}", "\\citep{wrong}")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    code = GATE.main(["--repo", repo, "--write"])
    assert code != 0
    assert not os.path.exists(os.path.join(repo, "manifests/paper/paper_submission_readiness.json"))


def test_write_succeeds_on_pass(tmp_path):
    repo = _golden(tmp_path)
    code = GATE.main(["--repo", repo, "--write"])
    assert code == 0
    assert os.path.exists(os.path.join(repo, "manifests/paper/paper_submission_readiness.json"))


def test_old_head_fails(tmp_path):
    """Plan 4.5 #2: a HEAD without a semantic-repair marker (old/pre-repair) must fail."""
    def mut(repo):
        _write(repo, "old_marker.txt", "x")
        subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
        subprocess.run(["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "old unmarked state"], check=True)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "head_has_semantic_repair") == "FAIL"


def test_per_position_error_used_flag_fails(tmp_path):
    """Plan 4.5 #7: a measured run that claims per_position_error_used=True must fail."""
    def mut(repo):
        _write(repo, "scripts/real_add_measured_run.py",
               'x = {"per_position_error_used": True}\n')
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "per_position_error_used_honest") == "FAIL"


def test_wrong_import_origin_fails(tmp_path):
    """Plan 4.5 #8: repo declares a local d2t_rna but the import resolves elsewhere -> fail."""
    def mut(repo):
        _write(repo, "src/d2t_rna/__init__.py", "# shadowed package\n")
        _write(repo, "src/d2t_rna/py.typed", "")
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "import_origin_is_repo_src") == "FAIL"


def test_empty_contribution_fails(tmp_path):
    """Plan 4.5 #11: empty contribution / results files must fail."""
    def mut(repo):
        _write(repo, "docs/paper/confirmed_contribution.md", "")
        _write(repo, "docs/paper/results_validation.md", "")
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "contribution_results_nonempty") == "FAIL"


def test_prohibited_claim_with_na_elsewhere_fails(tmp_path):
    """Plan 4.5 #12: a prohibited claim retained in the body, masked by NOT_APPLICABLE
    elsewhere, must still fail."""
    def mut(repo):
        p = os.path.join(repo, "docs/paper/manuscript.tex")
        s = open(p).read() + ("\nA measured certificate on the assay is reported here, "
                              "and it is NOT_APPLICABLE in the scope table.\n")
        open(p, "w").write(s)
    repo = _golden(tmp_path, mut)
    assert _check_status(repo, "not_applicable_not_abused") == "FAIL"
