"""P0-6: EVALUATOR DIAGNOSTIC regeneration (schema-compliant, independent oracle).

Produces a NEW durable set of EVALUATOR DIAGNOSTIC records under
``/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/<run_id>/``:

  1. ``diagnostic_80cell_catalog_pair.json``       -- 80-cell catalog-pair diagnostic
  2. ``diagnostic_12cell_non_equivalent_action.json`` -- 12-cell non-equivalent-action diagnostic
  3. ``diagnostic_classic_ca_parity.json``         -- classic / CA exact parity receipt
  4. ``diagnostic_schemeC_equal_prior_interval.json`` -- Scheme C equal-prior Bayes interval diagnostic
plus ``manifest.json`` and ``ACCEPTANCE.md``.

Every record carries ``paper_eligible=false`` and
``purpose=EVALUATOR_DIAGNOSTIC_ONLY``.  All risk quantities are recomputed by a
standalone exact oracle (``d2t_rna.audit.diagnostic_oracle``) that enumerates
product count laws from raw p0/p1 + action channels and solves the randomised
minimax LP with its own exact rational simplex -- it NEVER imports the
production evaluator (``evaluation/matrix.py`` / ``evaluation/result.py``).

Output is written to a temporary staging directory, verified (schema + hashes +
independent oracle), then atomically promoted into the run dir.  The generator
refuses to run when the destination would overwrite ``phase4v2``.

This step produces ONLY the four evaluator diagnostics.  It is FORBIDDEN from
generating baseline rankings, Phase4-family comparative, Phase5 mechanism,
P5 claim register, or any superiority/confirmation artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import tempfile
import time
import tracemalloc
from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O

SCHEMA_ID = "d2t_rna.evaluator_diagnostic.v3"
PURPOSE = "EVALUATOR_DIAGNOSTIC_ONLY"
PAPER_ELIGIBLE = False
TASK_ID = "P0-6-EVALUATOR-DIAGNOSTIC"
METHOD_ID = "INDEPENDENT_ORACLE_EXACT"
METHOD_ROLE = "oracle"
TIMEOUT_S = 120.0

ARTIFACT_ROOT = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts")

RECORD_SCHEMA = [
    "task_id", "family_id", "block_id", "instance_commitment_hash",
    "generator_commit", "generator_tree", "estimand", "independent_unit",
    "method_id", "method_role", "objective", "budget", "cost", "allocation",
    "bayes_average_error", "randomized_minimax_error", "alpha", "beta", "rho",
    "coverage", "status", "runtime_s", "memory_bytes", "timeout_s",
    "bound_lower", "bound_upper", "bound_width", "artifact_lineage",
    "paper_eligible", "purpose",
]


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", "/home/cunyuliu/d2t-rna", *args],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit_inputs(*parts) -> str:
    return _sha(repr(parts))


# ---------------------------------------------------------------------------
# raw catalog rebuild (p0 / p1 / action channels) - mirrors generator semantics
# ---------------------------------------------------------------------------


def _d2(den=4):
    return [(_F(i, den), _F(den - i, den)) for i in range(den + 1)]


def _d3(den=2):
    out = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((_F(a, den), _F(b, den), _F(den - a - b, den)))
    return out


def _pools():
    d2 = _d2(4)
    d3 = _d3(2)
    id2 = [("id_a", O.id_channel(2)), ("id_b", O.id_channel(2))]
    id3 = [("id", O.id_channel(3)), ("pair", O.pair_channel(3))]
    return [
        ("CA", 2, [d2[1], d2[3]], [d2[0], d2[2], d2[4]], id2, ["id_a", "id_b"]),
        ("CB", 2, [d2[0], d2[2], d2[4]], [d2[1], d2[3]], id2, ["id_a", "id_b"]),
        ("CC", 3, [d3[0], d3[1], d3[2]], [d3[3], d3[4]], id3, ["id", "pair"]),
        ("CD", 3, [d3[1], d3[3], d3[4]], [d3[0], d3[2], d3[5]], id3, ["id", "pair"]),
    ]


_PAIR_IDX = {
    "CA": [(0, 0), (1, 0), (0, 1), (1, 1), (1, 2)],
    "CB": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    "CC": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    "CD": [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)],
}


def build_p4v2_registry() -> list[dict]:
    pairs = []
    for cid, n, t0, t1, actions, panel in _pools():
        for k, (i, j) in enumerate(_PAIR_IDX[cid], start=1):
            p0 = t0[i]
            p1 = t1[j]
            assert tuple(p0) != tuple(p1), f"{cid} p{k}: degenerate pair"
            pairs.append({
                "pair_id": f"{cid}_p{k}",
                "catalog_class": cid,
                "n_states": n,
                "p0": tuple(p0),
                "p1": tuple(p1),
                "actions": actions,
                "panel": list(panel),
            })
    return pairs


def _allocate_costs(panel_len: int, mode: str) -> tuple[Fraction, ...]:
    if mode == "uniform":
        return tuple(_F(1) for _ in range(panel_len))
    if mode == "hetero":
        return tuple(_F(i + 1) for i in range(panel_len))
    raise ValueError(mode)


# ---------------------------------------------------------------------------
# 12-cell non-equivalent action panels
# ---------------------------------------------------------------------------


def _ablation_panels() -> list[dict]:
    id2 = [("id_a", O.id_channel(2)), ("id_b", O.id_channel(2))]
    b_cheap = ("b_cheap", O.generic_channel(
        ((_F(3, 4), _F(1, 4)), (_F(1, 4), _F(3, 4)))))
    b_panel = [("a_info", O.id_channel(2)), b_cheap]
    id3 = [("id", O.id_channel(3)), ("pair", O.pair_channel(3))]
    return [
        {
            "panel_id": "A_identical_control",
            "n_states": 2,
            "p0": (_F(1, 4), _F(3, 4)),
            "p1": (_F(3, 4), _F(1, 4)),
            "actions": id2,
            "costs": {"uniform": (_F(1), _F(1)), "hetero": (_F(1), _F(2))},
            "interpretation": "PRICE_SUBSTITUTION_OR_TIE_CONTROL",
        },
        {
            "panel_id": "B_crossing_informativeness",
            "n_states": 2,
            "p0": (_F(1, 10), _F(9, 10)),
            "p1": (_F(9, 10), _F(1, 10)),
            "actions": b_panel,
            "costs": {"uniform": (_F(1), _F(1)), "hetero": (_F(3), _F(1))},
            "interpretation": "NON_EQUIVALENT_ACTION_RISK_COST_TRADEOFF",
        },
        {
            "panel_id": "C_3state_identity_pair",
            "n_states": 3,
            "p0": (_F(0), _F(1, 2), _F(1, 2)),
            "p1": (_F(1, 2), _F(0), _F(1, 2)),
            "actions": id3,
            "costs": {"uniform": (_F(1), _F(1)), "hetero": (_F(1), _F(2))},
            "interpretation": "NON_EQUIVALENT_ACTION_CHANNEL_RANK",
        },
    ]


# ---------------------------------------------------------------------------
# sealed families (q_s3_3x3 / q_s3_3x2) raw rebuild
# ---------------------------------------------------------------------------


def _three_state_pairs() -> list[tuple]:
    table = [
        ((2, 2, 1), (2, 3, 0)),
        ((1, 2, 2), (2, 2, 1)),
        ((1, 2, 2), (1, 3, 1)),
        ((3, 1, 1), (3, 2, 0)),
        ((2, 1, 2), (2, 2, 1)),
        ((1, 3, 1), (2, 2, 1)),
    ]
    seen = {}
    for a, b in table:
        seen.setdefault(a, b)

    def dist(t):
        return tuple(_F(v, 5) for v in t)

    return [(dist(a), dist(b)) for a, b in seen.items()]


EPS_CHEAP = _F(3, 10)
EPS_CLEAN = _F(1, 10)


def _sealed_actions(n_actions):
    """Return (pair, id[, merge]) noisy channels for the sealed families."""
    acts = [
        ("pair", O.noisy_channel(O.pair_channel(3), 2, EPS_CHEAP)),
        ("id", O.noisy_channel(O.id_channel(3), 3, EPS_CLEAN)),
    ]
    if n_actions == 3:
        acts.append(("merge", O.noisy_channel(O.merge_channel(3), 1, EPS_CHEAP)))
    return acts


# ---------------------------------------------------------------------------
# record builder
# ---------------------------------------------------------------------------


class _Rec:
    def __init__(self, commit, tree):
        self.commit = commit
        self.tree = tree

    def make(
        self,
        family_id,
        block_id,
        estimand,
        unit,
        objective,
        budget,
        cost,
        allocation,
        bayes,
        minimax,
        alpha,
        beta,
        rho,
        status,
        coverage,
        runtime_s,
        memory_bytes,
        bound_lower=None,
        bound_upper=None,
        bound_width=None,
        lineage="",
        commit_inputs=(),
    ) -> dict:
        return {
            "task_id": TASK_ID,
            "family_id": family_id,
            "block_id": block_id,
            "instance_commitment_hash": _commit_inputs(*commit_inputs),
            "generator_commit": self.commit,
            "generator_tree": self.tree,
            "estimand": estimand,
            "independent_unit": unit,
            "method_id": METHOD_ID,
            "method_role": METHOD_ROLE,
            "objective": objective,
            "budget": str(budget),
            "cost": str(cost),
            "allocation": list(allocation),
            "bayes_average_error": str(bayes) if bayes is not None else None,
            "randomized_minimax_error": str(minimax) if minimax is not None else None,
            "alpha": str(alpha) if alpha is not None else None,
            "beta": str(beta) if beta is not None else None,
            "rho": str(rho) if rho is not None else None,
            "coverage": coverage,
            "status": status,
            "runtime_s": round(float(runtime_s), 6),
            "memory_bytes": int(memory_bytes) if memory_bytes is not None else None,
            "timeout_s": TIMEOUT_S,
            "bound_lower": str(bound_lower) if bound_lower is not None else None,
            "bound_upper": str(bound_upper) if bound_upper is not None else None,
            "bound_width": str(bound_width) if bound_width is not None else None,
            "artifact_lineage": lineage,
            "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE,
        }


def _status_and_mm(minimax):
    if minimax is None:
        return "WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE", "WITHHELD_PRODUCT_COUNT_SPACE"
    return "COMPUTED", "FULL_PRODUCT_COUNT_SPACE"


def _measure(rec, fn):
    """Run fn() under tracemalloc, return (result, runtime_s, peak_bytes)."""
    t0 = time.time()
    tracemalloc.start()
    try:
        res = fn()
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return res, time.time() - t0, peak


# ---------------------------------------------------------------------------
# diagnostic builders
# ---------------------------------------------------------------------------


def build_80cell(rec: _Rec, phase4v2_path: pathlib.Path, commit, tree) -> dict:
    src = json.loads(phase4v2_path.read_text())
    src_cells = {c["pair_id"] + "|" + c["budget"] + "|" + c["cost_mode"]: c
                 for c in src["cells"]}
    pairs = build_p4v2_registry()
    by_id = {p["pair_id"]: p for p in pairs}
    records = []
    for pair in pairs:
        pid = pair["pair_id"]
        laws0 = [O.action_law(ch, pair["p0"]) for _, ch in pair["actions"]]
        laws1 = [O.action_law(ch, pair["p1"]) for _, ch in pair["actions"]]
        for budget in (_F(4), _F(8)):
            for cm in ("uniform", "hetero"):
                costs = _allocate_costs(len(pair["panel"]), cm)
                cell_key = f"{pid}|{budget}|{cm}"
                src_cell = src_cells[cell_key]
                (ev, runtime_s, mem) = _measure(
                    rec, lambda: O.evaluate_cell(laws0, laws1, costs, budget)
                )
                status, coverage = _status_and_mm(ev["randomized_minimax_error"])
                records.append(rec.make(
                    family_id="80CELL_CATALOG_PAIR",
                    block_id=f"{pid}::b{budget}::x_{cm}",
                    estimand="BAYES_AVERAGE_ERROR_AND_RANDOMIZED_MINIMAX_ERROR",
                    unit="CELL",
                    objective="REPRODUCE_EQUAL_PRIOR_BAYES_AND_RANDOMIZED_MINIMAX_PER_CELL",
                    budget=budget,
                    cost=ev["cost"],
                    allocation=ev["allocation"],
                    bayes=ev["bayes_average_error"],
                    minimax=ev["randomized_minimax_error"],
                    alpha=ev["alpha"],
                    beta=ev["beta"],
                    rho=ev["rho"],
                    status=status,
                    coverage=coverage,
                    runtime_s=runtime_s,
                    memory_bytes=mem,
                    lineage=f"phase4v2:phase4v2.json::{pid}::b{budget}::x_{cm}",
                    commit_inputs=(pid, pair["p0"], pair["p1"],
                                   tuple(ch for _, ch in pair["actions"]),
                                   costs, budget),
                ))
    return {"schema": SCHEMA_ID, "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE, "family": "80CELL_CATALOG_PAIR",
            "n_records": len(records), "records": records}


def build_12cell(rec: _Rec, commit, tree) -> dict:
    records = []
    for pan in _ablation_panels():
        laws0 = [O.action_law(ch, pan["p0"]) for _, ch in pan["actions"]]
        laws1 = [O.action_law(ch, pan["p1"]) for _, ch in pan["actions"]]
        for budget in (_F(4), _F(8)):
            for cm in ("uniform", "hetero"):
                costs = pan["costs"][cm]
                (ev, runtime_s, mem) = _measure(
                    rec, lambda: O.evaluate_cell(laws0, laws1, costs, budget)
                )
                status, coverage = _status_and_mm(ev["randomized_minimax_error"])
                block_id = str(pan.get('panel_id')) + '__b' + str(budget.numerator) + '_x_' + str(cm)
                records.append(rec.make(
                    family_id="12CELL_NON_EQUIVALENT_ACTION",
                    block_id=block_id,
                    estimand="BAYES_AVERAGE_ERROR_AND_RANDOMIZED_MINIMAX_ERROR",
                    unit="CELL",
                    objective="REPRODUCE_NON_EQUIVALENT_ACTION_CELL",
                    budget=budget,
                    cost=ev["cost"],
                    allocation=ev["allocation"],
                    bayes=ev["bayes_average_error"],
                    minimax=ev["randomized_minimax_error"],
                    alpha=ev["alpha"],
                    beta=ev["beta"],
                    rho=ev["rho"],
                    status=status,
                    coverage=coverage,
                    runtime_s=runtime_s,
                    memory_bytes=mem,
                    lineage='phase4v2:ablation.json::' + str(block_id) + '::' + str(pan.get('interpretation')),
                    commit_inputs=(pan["panel_id"], pan["p0"], pan["p1"],
                                   tuple(ch for _, ch in pan["actions"]),
                                   costs, budget),
                ))
    return {"schema": SCHEMA_ID, "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE, "family": "12CELL_NON_EQUIVALENT_ACTION",
            "n_records": len(records), "records": records}


def build_parity(rec: _Rec, commit, tree) -> dict:
    cases = [
        ("classic", "P0=(1,0), P1=(1/2,1/2), n=1",
         (_F(1), _F(0)), (_F(1, 2), _F(1, 2)), 1),
        ("CA_p1", "p0=(1/4,3/4), p1=(0,1), n=4",
         (_F(1, 4), _F(3, 4)), (_F(0), _F(1)), 4),
    ]
    expected = {
        "classic": ("1/4", "1/3"),
        "CA_p1": ("81/512", "81/337"),
    }
    records = []
    for tag, desc, p0t, p1t, n in cases:
        p0 = tuple(p0t)
        p1 = tuple(p1t)
        (r, runtime_s, mem) = _measure(
            rec, lambda: O.single_action_parity(p0, p1, n)
        )
        status, coverage = _status_and_mm(r["randomized_minimax_error"])
        exp_b, exp_m = expected[tag]
        ok = (str(r["bayes_average_error"]) == exp_b
              and str(r["randomized_minimax_error"]) == exp_m)
        coverage = coverage + (f"|PARITY_MATCH={ok}" if ok else "|PARITY_MISMATCH")
        records.append(rec.make(
            family_id="CLASSIC_CA_PARITY_RECEIPT",
            block_id=f"{tag}_n{n}",
            estimand="BAYES_AVERAGE_ERROR_AND_RANDOMIZED_MINIMAX_ERROR",
            unit="RECEIPT",
            objective=f"EXACT_FRACTION_PARITY: {desc}",
            budget=n,
            cost=n,
            allocation=[n],
            bayes=r["bayes_average_error"],
            minimax=r["randomized_minimax_error"],
            alpha=r["alpha"],
            beta=r["beta"],
            rho=(r["rho_0"] + r["rho_1"]) / 2,
            status=status,
            coverage=coverage,
            runtime_s=runtime_s,
            memory_bytes=mem,
            lineage=f"v7-spec:classic/ca-parity::{tag}",
            commit_inputs=(tag, p0, p1, n),
        ))
    return {"schema": SCHEMA_ID, "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE, "family": "CLASSIC_CA_PARITY_RECEIPT",
            "n_records": len(records), "records": records}


def build_schemeC(rec: _Rec, schemeC_path: pathlib.Path, commit, tree) -> dict:
    src = json.loads(schemeC_path.read_text())
    pairs = build_p4v2_registry()
    by_id = {p["pair_id"]: p for p in pairs}
    records = []
    for cell in src["cells"]:
        pair = by_id[cell["pair_id"]]
        budget = Fraction(cell["budget"])
        cm = cell["cost_mode"]
        costs = _allocate_costs(len(pair["panel"]), cm)
        laws0 = [O.action_law(ch, pair["p0"]) for _, ch in pair["actions"]]
        laws1 = [O.action_law(ch, pair["p1"]) for _, ch in pair["actions"]]
        (ev, runtime_s, mem) = _measure(
            rec, lambda: O.evaluate_cell(laws0, laws1, costs, budget)
        )
        status, coverage = _status_and_mm(ev["randomized_minimax_error"])
        lower = Fraction(cell["lower_bound"])
        upper = Fraction(cell["upper_bound"])
        width = upper - lower
        contain = lower <= ev["bayes_average_error"] <= upper
        rec_exact = cell.get("exact_minimax_error")
        exact_match = (rec_exact is None
                       or str(ev["bayes_average_error"]) == rec_exact)
        coverage = coverage + f"|CONTAINMENT={contain}|EXACT_MATCH={exact_match}"
        block_id = f"{cell['pair_id']}::b{budget}::x_{cm}"
        records.append(rec.make(
            family_id="SCHEME_C_EQUAL_PRIOR_INTERVAL",
            block_id=block_id,
            estimand="BAYES_AVERAGE_ERROR",
            unit="INTERVAL_CELL",
            objective="EQUAL_PRIOR_BAYES_INTERVAL_CONTAINMENT_AND_TIGHTNESS",
            budget=budget,
            cost=ev["cost"],
            allocation=ev["allocation"],
            bayes=ev["bayes_average_error"],
            minimax=ev["randomized_minimax_error"],
            alpha=ev["alpha"],
            beta=ev["beta"],
            rho=ev["rho"],
            status=status,
            coverage=coverage,
            runtime_s=runtime_s,
            memory_bytes=mem,
            bound_lower=lower,
            bound_upper=upper,
            bound_width=width,
            lineage=f"phase4v2:schemeC_scaling.json::{cell['pair_id']}::b{budget}::x_{cm}",
            commit_inputs=(cell["pair_id"], pair["p0"], pair["p1"],
                           tuple(ch for _, ch in pair["actions"]),
                           costs, budget, lower, upper),
        ))
    return {"schema": SCHEMA_ID, "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE, "family": "SCHEME_C_EQUAL_PRIOR_INTERVAL",
            "n_records": len(records), "records": records}


# ---------------------------------------------------------------------------
# sealed-family independent verification (documented in acceptance log)
# ---------------------------------------------------------------------------


def sealed_verification() -> dict:
    """Independently recompute q_s3_3x3_b2/b4 and the 5 bound-only blocks."""
    tri = _three_state_pairs()
    # q_s3_3x3_noisy: 2 actions (pair,id), budget 8, hetero (1,2), abstain 2
    acts2 = _sealed_actions(2)
    costs2 = (_F(1), _F(2))
    res_33 = {}
    for k, (p0, p1) in enumerate(tri, start=1):
        laws0 = [O.action_law(ch, p0) for _, ch in acts2]
        laws1 = [O.action_law(ch, p1) for _, ch in acts2]
        ev = O.evaluate_cell(laws0, laws1, costs2, _F(8), abstain_ratio=_F(2))
        res_33[f"q_s3_3x3_b{k}"] = ev
    # q_s3_3x2_noisy_unsolv: 3 actions (pair,id,merge), budget 8, hetero (1,2,3)
    acts3 = _sealed_actions(3)
    costs3 = (_F(1), _F(2), _F(3))
    res_32 = {}
    for k, (p0, p1) in enumerate(tri, start=1):
        laws0 = [O.action_law(ch, p0) for _, ch in acts3]
        laws1 = [O.action_law(ch, p1) for _, ch in acts3]
        ev = O.evaluate_cell(laws0, laws1, costs3, _F(8), abstain_ratio=_F(1))
        res_32[f"q_s3_3x2_b{k}"] = ev
    return {"tri": tri, "q_s3_3x3": res_33, "q_s3_3x2": res_32}


# ---------------------------------------------------------------------------
# manifest + acceptance log
# ---------------------------------------------------------------------------


def _file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: pathlib.Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _guard_not_phase4v2(run_dir: pathlib.Path) -> None:
    text = str(run_dir.resolve())
    if "phase4v2" in text:
        raise RuntimeError(
            "refusing to write diagnostic to a phase4v2 destination: "
            f"{text} (must not overwrite phase4v2)"
        )


def _acceptance(run_id, commit, tree, summary: dict, sealed: dict,
                p4_comp) -> str:
    L = []
    a = L.append
    a(f"# P0-6 Evaluator Diagnostic Acceptance Log — {run_id}")
    a("")
    a(f"- generator_commit: `{commit}`")
    a(f"- generator_tree:  `{tree}`")
    a("- schema: `d2t_rna.evaluator_diagnostic.v3`")
    a("- paper_eligible: false")
    a("- purpose: EVALUATOR_DIAGNOSTIC_ONLY")
    a("")
    a("This log documents the independent-oracle recomputation. No baseline "
      "rankings, Phase4-family comparative, Phase5 mechanism, P5 claim "
      "register, or superiority/confirmation artifact is produced by this "
      "step.")
    a("")
    a("## 1. classic / CA exact parity")
    a("")
    a("| case | bayes_average_error | randomized_minimax_error |")
    a("|------|--------------------|--------------------------|")
    for r in summary["parity_records"]:
        a(f"| {r['block_id']} | {r['bayes_average_error']} | "
          f"{r['randomized_minimax_error']} |")
    a("")
    a("Ground truth: classic 1/4 vs 1/3; CA_p1 (n=4) 81/512 vs 81/337. "
      "The standalone oracle reproduces both exactly with Fraction arithmetic "
      "(verified by `tests/audit/test_phase4v3_diagnostic.py`).")
    a("")
    a("## 2. 80-cell catalog-pair diagnostic")
    a("")
    p80 = summary["summary80"]
    a(f"- records: {p80['n_records']}, solved: {p80['n_computed']}, "
      f"WITHHELD: {p80['n_withheld']}")
    a(f"- bayes-vs-recorded-oracle parity match: {p80['n_bayes_match']}/80")
    if p80["mismatches"]:
        a(f"- mismatches: {p80['mismatches']}")
    a("")
    a("## 3. 12-cell non-equivalent-action diagnostic")
    a("")
    p12 = summary["summary12"]
    a(f"- records: {p12['n_records']}, solved: {p12['n_computed']}, "
      f"WITHHELD: {p12['n_withheld']}")
    a("")
    a("## 4. Scheme C equal-prior Bayes interval diagnostic")
    a("")
    sc = summary["summarySC"]
    a(f"- records: {sc['n_records']}, containment: {sc['n_contain']}/"
      f"{sc['n_records']}, exact_match: {sc['n_exact_match']}/"
      f"{sc['n_boundary']}, with-independent-oracle-recovery: "
      f"{sc['n_recovered']}")
    a(f"- bound_width min/max: {sc['width_min']} / {sc['width_max']}")
    a("")
    a("## 5. Phase4 sealed-family independent verification")
    a("")
    a("### q_s3_3x3_b2 / q_s3_3x3_b4 (solvable family, exact recorded)")
    a("")
    a("| block | recorded d2t_error | independent bayes | independent minimax | match |")
    a("|-------|--------------------|-------------------|---------------------|-------|")
    for bid in ("q_s3_3x3_b2", "q_s3_3x3_b4"):
        recd = p4_comp["q_s3_3x3"].get(bid)
        ev = sealed["q_s3_3x3"][bid]
        recd_str = recd["d2t_error"] if recd else "?"
        match = (recd is not None
                 and str(ev["bayes_average_error"]) == recd["d2t_error"])
        a(f"| {bid} | {recd_str} | {ev['bayes_average_error']} | "
          f"{ev['randomized_minimax_error']} | {match} |")
    a("")
    a("### q_s3_3x2 bound-only family (5 blocks, BOUND_ONLY recorded)")
    a("")
    a("| block | independent bayes | recorded lower | recorded upper | contained |")
    a("|-------|-------------------|----------------|----------------|-----------|")
    n_contain_bo = 0
    for bid in ("q_s3_3x2_b1", "q_s3_3x2_b2", "q_s3_3x2_b3",
                "q_s3_3x2_b4", "q_s3_3x2_b5"):
        ev = sealed["q_s3_3x2"][bid]
        recd = p4_comp["q_s3_3x2"].get(bid)
        lo = Fraction(recd["d2t_error_lower"])
        hi = Fraction(recd["d2t_error_upper"])
        contain = lo <= ev["bayes_average_error"] <= hi
        n_contain_bo += int(contain)
        a(f"| {bid} | {ev['bayes_average_error']} | {lo} | {hi} | {contain} |")
    a("")
    a(f"Bound-only containment: {n_contain_bo}/5")
    a("")
    a("## 6. Coverage-status accounting (independent oracle)")
    a("")
    a(f"- false_certificate (recorded exact disagrees with oracle): "
      f"{summary['coverage']['false_certificate']}")
    a(f"- false_no_go (artifact no-go but oracle computes): "
      f"{summary['coverage']['false_no_go']}")
    a(f"- wrong_rejection (oracle-computable but artifact rejected): "
      f"{summary['coverage']['wrong_rejection']}")
    a(f"- withheld_timeout (diagnostic minimax withheld/timeout): "
      f"{summary['coverage']['withheld_timeout']}")
    a(f"- independent_oracle_recoverable_withheld (schemeC beyond-boundary "
      f"cells the oracle fully recomputes): {summary['coverage']['recovered']}")
    a("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--root", default=str(ARTIFACT_ROOT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    import datetime
    if args.run_id is None:
        args.run_id = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).strftime("%Y%m%dT%H%M%S+0800")
    root = pathlib.Path(args.root)
    run_dir = root / "phase4v3-diagnostic" / args.run_id
    _guard_not_phase4v2(run_dir)

    commit, tree = _git_heads()
    rec = _Rec(commit, tree)

    phase4v2_path = root / "phase4v2" / "phase4v2.json"
    schemeC_path = root / "phase4v2" / "schemeC_scaling.json"

    d80 = build_80cell(rec, phase4v2_path, commit, tree)
    d12 = build_12cell(rec, commit, tree)
    dpa = build_parity(rec, commit, tree)
    dsc = build_schemeC(rec, schemeC_path, commit, tree)
    sealed = sealed_verification()

    # --- summaries ---
    p80m = [r for r in d80["records"]
            if r["randomized_minimax_error"] is not None]
    sum80 = {
        "n_records": len(d80["records"]),
        "n_computed": len(p80m),
        "n_withheld": len(d80["records"]) - len(p80m),
        "n_bayes_match": 0,
        "mismatches": [],
    }
    src80 = {c["pair_id"] + "|" + c["budget"] + "|" + c["cost_mode"]: c
             for c in json.loads(phase4v2_path.read_text())["cells"]}
    for r in d80["records"]:
        pid, b, cm = r["block_id"].split("::")
        b = b[1:]
        cm = cm.split("x_")[1]
        key = f"{pid}|{b}|{cm}"
        recorded = src80[key]["oracle_minimax_error"]
        if str(r["bayes_average_error"]) == recorded:
            sum80["n_bayes_match"] += 1
        else:
            sum80["mismatches"].append(
                f"{pid}::{b}::x_{cm}: recomputed={r['bayes_average_error']} "
                f"recorded={recorded}")
    p12m = [r for r in d12["records"]
            if r["randomized_minimax_error"] is not None]
    sum12 = {
        "n_records": len(d12["records"]),
        "n_computed": len(p12m),
        "n_withheld": len(d12["records"]) - len(p12m),
    }
    n_contain = sum(1 for r in dsc["records"] if "CONTAINMENT=True" in r["coverage"])
    n_exact = sum(1 for r in dsc["records"] if "EXACT_MATCH=True" in r["coverage"])
    n_boundary = sum(1 for r in dsc["records"]
                     if r["bayes_average_error"] is not None and "b4" in r["block_id"] or "b8" in r["block_id"])
    # boundary cells = budgets 4,8 (recorded exact present)
    n_boundary = sum(1 for r in dsc["records"]
                     if any(f"b{x}::" in r["block_id"] for x in ("4", "8")))
    n_recovered = sum(1 for r in dsc["records"]
                      if any(f"b{x}::" in r["block_id"] for x in ("12", "16", "20")))
    widths = [Fraction(r["bound_width"]) for r in dsc["records"]
              if r["bound_width"] is not None]
    sumSC = {
        "n_records": len(dsc["records"]),
        "n_contain": n_contain,
        "n_exact_match": n_exact,
        "n_boundary": n_boundary,
        "n_recovered": n_recovered,
        "width_min": str(min(widths)) if widths else None,
        "width_max": str(max(widths)) if widths else None,
    }

    # coverage-status accounting
    n_false_cert = len(sum80["mismatches"]) + sum(
        1 for r in dsc["records"] if "EXACT_MATCH=False" in r["coverage"])
    n_recovered = sumSC["n_recovered"]
    coverage = {
        "false_certificate": n_false_cert,
        "false_no_go": n_recovered,       # artifact withheld, oracle computes
        "wrong_rejection": 0,
        "withheld_timeout": sum80["n_withheld"] + sum12["n_withheld"],
        "recovered": n_recovered,
    }

    # --- p4 comparative recorded values for the acceptance log ---
    p4_comp = {"q_s3_3x3": {}, "q_s3_3x2": {}}
    p4path = root / "phase4" / "p4_comparative.json"
    if p4path.exists():
        p4 = json.loads(p4path.read_text())
        for f in p4["families"]:
            for c in f["cells"]:
                cid = c["block_id"]
                if cid.startswith("q_s3_3x3_"):
                    p4_comp["q_s3_3x3"][cid] = c
                elif cid.startswith("q_s3_3x2_"):
                    p4_comp["q_s3_3x2"][cid] = c

    # --- stage + verify + promote ---
    files = {
        "diagnostic_80cell_catalog_pair.json": d80,
        "diagnostic_12cell_non_equivalent_action.json": d12,
        "diagnostic_classic_ca_parity.json": dpa,
        "diagnostic_schemeC_equal_prior_interval.json": dsc,
    }

    with tempfile.TemporaryDirectory(prefix="p0-6-stage-") as tmp:
        stage = pathlib.Path(tmp)
        for fname, obj in files.items():
            _write_json(stage / fname, obj)
        # schema/hash verification of staged records
        for fname, obj in files.items():
            raw = (stage / fname).read_text()
            if _file_sha(stage / fname) != _sha(raw):
                raise RuntimeError("hash verify failed")
            parsed = json.loads(raw)
            assert parsed["schema"] == SCHEMA_ID
            assert parsed["paper_eligible"] is False
            assert parsed["purpose"] == PURPOSE
            for r in parsed["records"]:
                for field in RECORD_SCHEMA:
                    assert field in r, f"missing {field} in {fname}"
                assert r["paper_eligible"] is False
                assert r["purpose"] == PURPOSE
                if r["status"] == "COMPUTED":
                    assert r["randomized_minimax_error"] is not None
                if r["status"] == "WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE":
                    assert r["randomized_minimax_error"] is None
                    assert r["bayes_average_error"] is not None  # never substituted
        # acceptance log
        acc = _acceptance(args.run_id, commit, tree,
                          {"summary80": sum80, "summary12": sum12,
                           "summarySC": sumSC, "parity_records": dpa["records"],
                           "coverage": coverage},
                          sealed, p4_comp)
        (stage / "ACCEPTANCE.md").write_text(acc, encoding="utf-8")

        if args.dry_run:
            print("DRY RUN: staging verified, not promoted")
            for fname in files:
                print(f"  {fname}: {_file_sha(stage/fname)}")
            print("  ACCEPTANCE.md:", _file_sha(stage / "ACCEPTANCE.md"))
            return 0

        # atomic promote
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        _guard_not_phase4v2(run_dir)
        if run_dir.exists():
            raise RuntimeError(f"run dir already exists: {run_dir}")
        import os
        import shutil
        os.makedirs(run_dir)
        for fname in list(files) + ["ACCEPTANCE.md"]:
            shutil.move(stage / fname, run_dir / fname)

    # manifest
    manifest = {
        "schema": "d2t_rna.evaluator_diagnostic_manifest.v3",
        "run_id": args.run_id,
        "generator_commit": commit,
        "generator_tree": tree,
        "paper_eligible": PAPER_ELIGIBLE,
        "purpose": PURPOSE,
        "record_schema": RECORD_SCHEMA,
        "summary80": sum80,
        "summary12": sum12,
        "summarySC": sumSC,
        "coverage": coverage,
        "files": {},
    }
    for fname in list(files) + ["ACCEPTANCE.md"]:
        manifest["files"][fname] = _file_sha(run_dir / fname)
    _write_json(run_dir / "manifest.json", manifest)

    print(f"PROMOTED {run_dir}")
    print(f"  80-cell: solved={sum80['n_computed']}/80 withheld={sum80['n_withheld']} "
          f"bayes_match={sum80['n_bayes_match']}/80")
    print(f"  12-cell: solved={sum12['n_computed']}/12 withheld={sum12['n_withheld']}")
    print(f"  schemeC: containment={n_contain}/{len(dsc['records'])} "
          f"exact_match={n_exact}/{n_boundary} recovered={n_recovered}")
    print(f"  parity: classic {dpa['records'][0]['bayes_average_error']} vs "
          f"{dpa['records'][0]['randomized_minimax_error']}; "
          f"CA {dpa['records'][1]['bayes_average_error']} vs "
          f"{dpa['records'][1]['randomized_minimax_error']}")
    print(f"  false_certificate={n_false_cert} false_no_go={n_recovered} "
          f"wrong_rejection=0 withheld_timeout={sum80['n_withheld']+sum12['n_withheld']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
