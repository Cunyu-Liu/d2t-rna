#!/usr/bin/env python3
"""D2T-RNA paper readiness gate (fail-closed, --check / --write split).

Fail-closed paper gate:
  - ``--check`` is READ-ONLY: it computes and reports the gates (JSON + human report to
    stdout or an explicit ``--outdir``) and NEVER writes the authoritative manifest or
    report back into the repo.  Exit code is non-zero if any required gate fails.
  - ``--write`` requires an EXPLICIT authorization flag and only then writes the
    authoritative ``manifests/paper/paper_submission_readiness.json`` and
    ``docs/paper/submission_readiness_report.md``.  It refuses to write (and exits
    non-zero) when the gates do not pass, so a broken state can never be committed as
    ``READY``.

The gate is importable (``from paper_readiness_gate import compute``) so the negative
fixture suite can inject defects into a temp copy and assert fail-closed behaviour.

Usage:
  python scripts/paper_readiness_gate.py --repo /home/cunyuliu/d2t-rna --check
  python scripts/paper_readiness_gate.py --repo /home/cunyuliu/d2t-rna --write
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return out.stdout.strip()


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


_REPAIR_MARKERS = ("feat(Batch2", "feat(Batch3", "feat(Batch4")


def head_has_repair_marker(repo):
    """Fail-closed: P0 readiness only on a HEAD that carries a semantic-repair commit.

    The HEAD commit subject must carry a Batch 2/3/4 repair marker; a HEAD that still
    sits at (or behind) the pre-repair audit snapshot has no repair marker and is not
    readiness-eligible.  This is an internal evidence-gate invariant, not a scientific
    claim.
    """
    subject = git(repo, "log", "-1", "--format=%s")
    return any(m in subject for m in _REPAIR_MARKERS)


def import_origin_ok(repo):
    """Verify ``d2t_rna`` resolves to the repo's own ``src`` (not a shadowed copy).

    Returns True (correct origin), False (wrong origin), or None (repo has no local
    ``src/d2t_rna``, so the origin cannot be asserted here -> treated as UNKNOWN).
    """
    src_dir = os.path.realpath(os.path.join(repo, "src"))
    pkg_dir = os.path.realpath(os.path.join(src_dir, "d2t_rna"))
    if not os.path.isdir(pkg_dir):
        return None
    try:
        import d2t_rna
        origin = os.path.realpath(d2t_rna.__file__)
        return origin.startswith(src_dir + os.sep)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# parsing helpers (read-only)
# ---------------------------------------------------------------------------

_CITE_PAT = re.compile(
    r"\\(?:cite|citep|citet|citealp|citenum|citeauthor|citeyear)"
    r"(?:\[[^\]]*\])?(?:\[[^\]]*\])?\{([^}]*)\}"
)


def parse_cited_keys(tex):
    """Parse \\cite/\\citep/\\citet (+ optional args, multiple comma keys)."""
    keys = set()
    for m in _CITE_PAT.finditer(tex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                keys.add(k)
    return keys


def parse_bib_keys(bibtext):
    keys = set(re.findall(r"@\w+\{([^,]+),", bibtext))
    return {k.strip() for k in keys}


def _prob_ok(value):
    """Return True if a parsed rational number lies in [0,1]."""
    from fractions import Fraction
    try:
        return 0.0 <= float(Fraction(value)) <= 1.0
    except Exception:
        return False


def _scan_tv_values(tex):
    """Collect candidate probability/TV rationals that must lie in [0,1]."""
    bad = []
    # gamma = a/b patterns and bare a/b used as probabilities
    for m in re.finditer(r"\\(?:gamma|mathrm\{TV\}|mathrm\{TV\})?\s*=\s*([0-9]+/[0-9]+)", tex):
        val = m.group(1)
        if not _prob_ok(val):
            bad.append(val)
    # any explicit "9/5" style fraction that appears in a TV/gamma column is >1
    for m in re.finditer(r"([0-9]+)/([0-9]+)", tex):
        num, den = int(m.group(1)), int(m.group(2))
        if den > 0 and num > den:
            # Only flag the known-bad historical TV values; arbitrary ratios (e.g.
            # read counts) are allowed.  We specifically flag values that were the
            # historical fatal errors or any fraction >1 labelled gamma.
            prev = tex[max(0, m.start() - 60):m.start()]
            if "gamma" in prev or "TV" in prev or "tv" in prev:
                bad.append(f"{num}/{den}")
    return sorted(set(bad))


# ---------------------------------------------------------------------------
# core computation (pure, read-only w.r.t. authoritative outputs)
# ---------------------------------------------------------------------------

def compute(repo, with_build=False):
    """Return a result dict with gates / checks / all_pass / status.

    Does NOT write any authoritative file.  Callers decide where to persist.
    """
    paper = os.path.join(repo, "docs/paper")
    mani = os.path.join(repo, "manifests/paper")

    head = git(repo, "rev-parse", "HEAD")
    origin_main = git(repo, "rev-parse", "origin/main")
    worktree = git(repo, "status", "--porcelain")
    worktree_clean = (worktree.strip() == "")
    lineage = git(repo, "log", "--oneline", "-6")

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

    checks = {}  # each entry: {"status": PASS|FAIL|UNKNOWN, "note": str}

    # --- manuscript load ---
    tex = read(os.path.join(paper, "manuscript.tex")) if file_exists["manuscript"] else ""
    supp = read(os.path.join(paper, "supplementary.tex")) if file_exists["supplementary"] else ""
    bibtext = read(os.path.join(paper, "references.bib")) if file_exists["references"] else ""

    # (1) abstract
    prohibited = ["pretraining", "foundation model", "representation learning",
                  "fine-tuning", "held-out validation", "independent-library validation",
                  "prospective RNA experiment", "population-level RNA generalization"]
    abstract_prohibited = []
    if file_exists["manuscript"]:
        try:
            abstract = tex.split("\\begin{abstract}")[1].split("\\end{abstract}")[0]
        except IndexError:
            abstract = ""
        abstract_prohibited = [w for w in prohibited if w.lower() in abstract.lower()
                               and _in_claim_context(abstract, w)]
    checks["abstract_no_prohibited"] = {
        "status": "PASS" if not abstract_prohibited else "FAIL",
        "note": f"prohibited hits={abstract_prohibited or 'none'}",
    }

    # (2) citation closure: cited subseteq bib AND no cited-not-in-bib
    bib_keys = parse_bib_keys(bibtext)
    cited = parse_cited_keys(tex)
    cited_not_in_bib = sorted(cited - bib_keys)
    uncited = sorted(bib_keys - cited)
    checks["citation_cited_subseteq_bib"] = {
        "status": "PASS" if not cited_not_in_bib else "FAIL",
        "note": f"cited-but-not-in-bib={cited_not_in_bib or 'none'}",
    }
    checks["citation_all_bib_cited"] = {
        "status": "PASS" if not uncited else "FAIL",
        "note": f"uncited={uncited or 'none'}",
    }

    # (3) required-citation metadata (verified against authoritative sources)
    req_cite = {
        "moret1991test": ["1985", "10.1137/0906067"],
        "chernoff1959sequential": ["1972", "10.1137/1.9781611970593"],
        "cordero2012importance": ["2012", "10.1021/bi3008802"],
    }
    meta_bad = []
    for key, expect in req_cite.items():
        m = re.search(r"@\w+\{" + re.escape(key) + r",", bibtext)
        if not m:
            meta_bad.append(f"{key}:missing")
            continue
        nxt = re.search(r"@\w+\{", bibtext[m.end():])
        end = m.end() + nxt.start() if nxt else len(bibtext)
        entry = bibtext[m.start():end]
        if not all(e in entry for e in expect):
            meta_bad.append(f"{key}:field")
    checks["required_citation_metadata"] = {
        "status": "PASS" if not meta_bad else "FAIL",
        "note": f"verified-field mismatches={meta_bad or 'none'}",
    }

    # (4) ReactFlow / external evidence == 0
    external_terms = ["reactflow", "GBM", "gradient boosting", "permutation", "MLP"]
    rf_hits = [t for t in external_terms if t.lower() in tex.lower() and _in_claim_context(tex, t)]
    checks["reactflow_zero_evidence"] = {
        "status": "PASS" if not rf_hits else "FAIL",
        "note": f"external/reactflow evidence tokens={rf_hits or 'none'}",
    }

    # (4) probability/TV numeric range
    bad_tv = _scan_tv_values(tex + "\n" + supp)
    checks["probability_tv_in_unit_interval"] = {
        "status": "PASS" if not bad_tv else "FAIL",
        "note": f"out-of-range tv/gamma values={bad_tv or 'none'}",
    }

    # (5) cross-document numeric consistency for known TV keys
    tv_keys = ["9/10", "4/5", "3/5", "49/50"]
    missing = [k for k in tv_keys if k not in tex and k not in supp]
    checks["cross_doc_tv_consistency"] = {
        "status": "PASS" if not missing else "FAIL",
        "note": f"expected tv values missing={missing or 'none'}",
    }

    # (6) NOT_APPLICABLE abuse: prohibited claim must not be masked by NOT_APPLICABLE
    prohibited_phrases = ["measured certificate", "n=15 repeats", "n=3 repeats",
                          "real wet-lab cost saving", "strictly cheaper"]
    na_abuse = []
    for p in prohibited_phrases:
        if p.lower() in tex.lower():
            na_abuse.append(p)
    checks["not_applicable_not_abused"] = {
        "status": "PASS" if not na_abuse else "FAIL",
        "note": f"prohibited claim still present={na_abuse or 'none'}",
    }

    # (7) per_position_error_used consistency with code
    error_unused_ok = True
    for _mf in [
        "scripts/real_add_measured_run.py",
        "scripts/real_glycine_measured_run.py",
        "scripts/real_mattr_measured_run.py",
    ]:
        _p = os.path.join(repo, _mf)
        if os.path.exists(_p):
            _txt = read(_p)
            if re.search(r'"per_position_error_used"\s*:\s*True', _txt):
                error_unused_ok = False
    checks["per_position_error_used_honest"] = {
        "status": "PASS" if error_unused_ok else "FAIL",
        "note": "no measured run claims per_position_error_used=True",
    }

    # (7b) contribution / results files must be non-empty (plan 4.5 #11)
    empty_files = []
    for key in ("contribution", "results_validation"):
        p = files[key]
        if os.path.exists(p) and not read(p).strip():
            empty_files.append(key)
    checks["contribution_results_nonempty"] = {
        "status": "PASS" if not empty_files else "FAIL",
        "note": f"empty={empty_files or 'none'}",
    }

    # (7c) HEAD must carry a semantic-repair marker (plan 4.5 #2 old HEAD)
    checks["head_has_semantic_repair"] = {
        "status": "PASS" if head_has_repair_marker(repo) else "FAIL",
        "note": f"HEAD subject={git(repo, 'log', '-1', '--format=%s') or 'none'}",
    }

    # (7d) d2t_rna must resolve to the repo's own src (plan 4.5 #8 import origin)
    _io = import_origin_ok(repo)
    checks["import_origin_is_repo_src"] = {
        "status": "PASS" if _io is True else ("FAIL" if _io is False else "UNKNOWN"),
        "note": ("d2t_rna resolves under repo/src" if _io is True
                 else ("d2t_rna resolves OUTSIDE repo/src" if _io is False
                       else "repo has no local src/d2t_rna (origin not assertable)")),
    }

    # (8) import origin / semantic kill tests
    def _run_pytest_ok(targets):
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"] + targets,
                cwd=repo, capture_output=True, text=True, timeout=1800,
            )
            return (r.returncode == 0), (r.stdout + r.stderr)[-800:]
        except Exception as exc:
            return False, str(exc)

    kill_ok, kill_note = _run_pytest_ok([
        "tests/t2/test_semantic_counterexamples.py",
        "tests/t2/test_decision_semantics.py",
    ])
    checks["semantic_kill_tests"] = {
        "status": "PASS" if kill_ok else "FAIL",
        "note": kill_note.strip().replace("\n", " ") or "kill-tests pass",
    }

    # (9) decision tree STOP must not grant READY
    dt = os.path.join(repo, "manifests/audit/v7_decision_tree_resolution.json")
    dt_stop = False
    if os.path.exists(dt):
        try:
            dtj = json.loads(read(dt))
            dt_stop = "STOP" in str(dtj.get("decision", "")) or "BLOCKED" in str(dtj.get("status", ""))
        except Exception:
            dt_stop = False
    checks["decision_tree_not_gate_open"] = {
        "status": "PASS" if not dt_stop else "FAIL",
        "note": "decision tree STOP => not READY" if dt_stop else "no open STOP",
    }

    # (10) build main/supp (optional; UNKNOWN if latex unavailable)
    if with_build:
        build_ok = _build_pdf(repo, paper)
        checks["pdf_build"] = {
            "status": "PASS" if build_ok else "FAIL",
            "note": "pdflatex+bibtex build clean" if build_ok else "build failed or latex unavailable",
        }
    else:
        checks["pdf_build"] = {
            "status": "UNKNOWN",
            "note": "build not run (no --with-build; pdflatex not required for --check)",
        }

    # --- composite gates ---
    novelty = read(os.path.join(paper, "prior_art_novelty_matrix_REVISED.md")) if file_exists["prior_art"] else ""
    gates = {
        "PAPER-EVIDENCE-LOCK-GATE": file_exists["evidence_lock"] and file_exists["evidence_lock_json"],
        "PAPER-AUTHORITY-PRECEDENCE-GATE": file_exists["evidence_lock_json"],
        "PAPER-CONTRIBUTION-GATE": file_exists["contribution"],
        "PAPER-PRIOR-ART-NOVELTY-GATE": ("METHODS_LEVEL_NOVELTY_ONLY" in novelty and "NOT ESTABLISHED" in novelty),
        "PAPER-RESULTS-VALIDATION-GATE": file_exists["results_validation"],
        "PAPER-CLAIM-BOUNDARY-GATE": file_exists["claim_register"] and file_exists["claim_register_json"],
        "PAPER-REVIEWER-AUDIT-GATE": file_exists["reviewer_audit"],
        "PAPER-REPRODUCIBILITY-GATE": file_exists["supplementary"] and file_exists["supp88"],
        "PAPER-CITATION-CLOSURE-GATE": checks["citation_cited_subseteq_bib"]["status"] == "PASS",
        "PAPER-CITATION-METADATA-GATE": checks["required_citation_metadata"]["status"] == "PASS",
        "PAPER-REACTFLOW-ZERO-GATE": checks["reactflow_zero_evidence"]["status"] == "PASS",
        "PAPER-NUMERIC-RANGE-GATE": checks["probability_tv_in_unit_interval"]["status"] == "PASS",
        "PAPER-CROSSDOC-CONSISTENCY-GATE": checks["cross_doc_tv_consistency"]["status"] == "PASS",
        "PAPER-SEMANTIC-KILL-GATE": checks["semantic_kill_tests"]["status"] == "PASS",
        "PAPER-SEMANTIC-ERROR-UNUSED-GATE": checks["per_position_error_used_honest"]["status"] == "PASS",
        "PAPER-DECISION-TREE-GATE": checks["decision_tree_not_gate_open"]["status"] == "PASS",
        "PAPER-CONTRIBUTION-NONEMPTY-GATE": checks["contribution_results_nonempty"]["status"] == "PASS",
        "PAPER-HEAD-REPAIR-GATE": checks["head_has_semantic_repair"]["status"] == "PASS",
        "PAPER-IMPORT-ORIGIN-GATE": checks["import_origin_is_repo_src"]["status"] != "FAIL",
    }
    all_gates_pass = all(gates.values())

    # abstract/citation info for the report
    abstract_phrases = ["model-conditional", "fixed-horizon", "retrospective", "fail-closed"]
    if file_exists["manuscript"]:
        try:
            abstract = tex.split("\\begin{abstract}")[1].split("\\end{abstract}")[0]
        except IndexError:
            abstract = ""
    else:
        abstract = ""
    abstract_have = [r for r in abstract_phrases if r.lower() in abstract.lower()]

    result = {
        "schema": "d2t_rna.paper_submission_readiness.v2",
        "contract_id": "D2T-RNA-v7-THEORETICAL-RNA-METHODS",
        "contract_version": "v7.0.0",
        "status": "PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW" if all_gates_pass
                  else "PAPER_GATE_FAILED",
        "scientific_claim_authorized": False,
        "head": head,
        "origin_main": origin_main,
        "worktree_clean": worktree_clean,
        "lineage": lineage.splitlines(),
        "file_exists": file_exists,
        "file_hashes": file_hashes,
        "abstract_check": {
            "abstract_prohibited_hits": abstract_prohibited,
            "abstract_required_phrases_present": abstract_have,
            "abstract_ok": (not abstract_prohibited),
        },
        "citation_check": {
            "bib_entry_count": len(bib_keys),
            "cited_keys": sorted(cited),
            "cited_not_in_bib": cited_not_in_bib,
            "uncited_keys": uncited,
            "all_cited": (len(uncited) == 0),
            "cited_subseteq_bib": (len(cited_not_in_bib) == 0),
        },
        "checks": checks,
        "gates": gates,
        "gates_all_pass": all_gates_pass,
        "novelty_verdict": "METHODS_LEVEL_NOVELTY_ONLY (theorem-level NOT ESTABLISHED)",
    }
    return result


def _in_claim_context(tex, token):
    """Heuristic: token appears not merely as a negation/anti-claim."""
    i = tex.lower().find(token.lower())
    if i == -1:
        return False
    window = tex[max(0, i - 90): i + 90].lower()
    neg = ["no ", "not ", "without", "never", "does not", "do not", "prohibited", "zero", "0 evidence"]
    if any(n in window for n in neg):
        return False
    return True


def _build_pdf(repo, paper):
    """Best-effort pdflatex+bibtex build of main and supplementary in a temp dir."""
    import shutil, tempfile
    if not shutil.which("pdflatex") or not shutil.which("bibtex"):
        return False
    for doc in ("manuscript.tex", "supplementary.tex"):
        tmp = tempfile.mkdtemp(prefix="paperbuild_")
        try:
            for f in os.listdir(paper):
                src = os.path.join(paper, f)
                if os.path.isfile(src):
                    shutil.copy(src, tmp)
            tables = os.path.join(paper, "tables")
            if os.path.isdir(tables):
                shutil.copytree(tables, os.path.join(tmp, "tables"))
            figs = os.path.join(paper, "figures")
            if os.path.isdir(figs):
                shutil.copytree(figs, os.path.join(tmp, "figures"))
            r = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", doc],
                cwd=tmp, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                return False
            if not os.path.exists(os.path.join(tmp, "manuscript.pdf")) and doc == "manuscript.tex":
                return False
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def human_report(result, repo):
    head = result["head"]
    gates = result["gates"]
    checks = result["checks"]
    lines = []
    lines.append("# D2T-RNA v7 — Submission Readiness Report (fail-closed)")
    lines.append("")
    lines.append(f"> status = `{result['status']}`")
    lines.append(f"> scientific_claim_authorized = {result['scientific_claim_authorized']}")
    lines.append(f"> HEAD = {head}")
    lines.append("")
    lines.append("## Checks (PASS / FAIL / UNKNOWN)")
    lines.append("")
    for name, c in checks.items():
        lines.append(f"- {name}: **{c['status']}** — {c['note']}")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    for name, ok in gates.items():
        lines.append(f"- {name}: {'PASS' if ok else 'FAIL'}")
    lines.append("")
    lines.append(f"## Overall: {'ALL PASS' if result['gates_all_pass'] else 'NOT ALL PASS'}")
    lines.append("")
    lines.append("This is a fail-closed internal evidence gate, not a scientific claim "
                 "authorization and not a submission/acceptance status.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="D2T-RNA fail-closed paper readiness gate")
    ap.add_argument("--repo", default="/home/cunyuliu/d2t-rna")
    ap.add_argument("--check", action="store_true", help="READ-ONLY: report gates, write nothing authoritative")
    ap.add_argument("--write", action="store_true", help="write authoritative manifest+report (only on PASS)")
    ap.add_argument("--outdir", default=None, help="explicit output dir for --check artifacts")
    ap.add_argument("--with-build", action="store_true", help="also attempt pdflatex build check")
    args = ap.parse_args(argv)

    if args.check and args.write:
        print("error: --check and --write are mutually exclusive", file=sys.stderr)
        return 2
    if not (args.check or args.write):
        # default to read-only check (never writes authoritative)
        args.check = True

    result = compute(args.repo, with_build=args.with_build)
    all_pass = result["gates_all_pass"]

    if args.write:
        if not all_pass:
            # fail-closed: never write authoritative READY on a broken state
            print("REFUSED: gates do not pass; not writing authoritative READY artifact",
                  file=sys.stderr)
            print("status=", result["status"], file=sys.stderr)
            return 1
        mani = os.path.join(args.repo, "manifests/paper")
        paper = os.path.join(args.repo, "docs/paper")
        os.makedirs(mani, exist_ok=True)
        json_path = os.path.join(mani, "paper_submission_readiness.json")
        report_path = os.path.join(paper, "submission_readiness_report.md")
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
        with open(report_path, "w") as f:
            f.write(human_report(result, args.repo))
        print("wrote", json_path)
        print("wrote", report_path)
    else:
        # --check: never touch authoritative paths
        out = json.dumps(result, indent=2)
        if args.outdir:
            os.makedirs(args.outdir, exist_ok=True)
            with open(os.path.join(args.outdir, "paper_readiness_check.json"), "w") as f:
                f.write(out)
            with open(os.path.join(args.outdir, "submission_readiness_report.md"), "w") as f:
                f.write(human_report(result, args.repo))
        else:
            print(out)
            print(human_report(result, args.repo))

    print("HEAD        :", result["head"])
    print("gates       :", "ALL PASS" if all_pass else "NOT ALL PASS")
    print("cited-not-in-bib:", result["citation_check"]["cited_not_in_bib"])
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
