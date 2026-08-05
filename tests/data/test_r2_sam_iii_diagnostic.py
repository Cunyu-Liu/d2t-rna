"""Tests for the D2T-RNA v7 §8.5 SAM-III R2 modality-transfer diagnostic.

The diagnostic is fail-closed: DMS reactivity is a continuous per-nucleotide
measure and is not a registered categorical observation channel over latent
structural states, so the action semantics are never comparable by the
registered action space (contract 8.5).  This file pins the empirical
reactivity statistics extraction and the fail-closed verdict logic.
"""

from __future__ import annotations

import json
import math

from d2t_rna.data.r2_sam_iii_diagnostic import (
    DIAGNOSTIC,
    NOT_COMPARABLE,
    NOT_ESTABLISHED,
    SamIIIModalityDiagnostic,
    sam_iii_modality_diagnostic,
)


def _condition(construct="native", condition="SAM", n=6, rows=None):
    """Build one canonical condition dict (row = [count, raw, count, raw, bg])."""
    if rows is None:
        rows = [
            [float("nan"), float("nan"), 0.0, 0.0, 0.0],
            [-0.03, 0.0025, -0.06, 0.0018, 0.0037],
            [0.06, 0.0113, 0.13, 0.0134, 0.0094],
            [0.14, 0.0060, 0.27, 0.0099, 0.0015],
            [-0.02, 0.0010, -0.04, 0.0008, 0.0009],
            [0.20, 0.0180, 0.31, 0.0150, 0.0020],
        ]
    return {
        "construct": construct,
        "condition": condition,
        "positions": list(range(1, n + 1)),
        "sequence": ["A"] * n,
        "rows": rows,
    }


def _canonical(conditions):
    return {
        "accession": "GSE278422",
        "role": "RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC",
        "construct_sequences": {},
        "conditions": conditions,
    }


def test_default_flags_are_fail_closed_and_not_comparable() -> None:
    diag = sam_iii_modality_diagnostic.__wrapped__ if hasattr(
        sam_iii_modality_diagnostic, "__wrapped__"
    ) else sam_iii_modality_diagnostic
    # Use a real file to exercise the json load path.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "canonical.json"
        p.write_text(json.dumps(_canonical([_condition()])))
        d = diag(p)
    assert d.verdict == NOT_COMPARABLE
    assert d.action_semantics_comparable is False
    assert d.observation_model_registered is False
    assert d.label == DIAGNOSTIC
    assert any("not comparable" in rc for rc in d.reason_codes)


def test_reactivity_statistics_extracted() -> None:
    """Coverage, mean/min/max are computed from the raw modified-channel rate."""
    canonical = _canonical([_condition(n=6)])
    with tempfile_path(canonical) as p:
        d = sam_iii_modality_diagnostic(p)
    cond = d.conditions[0]
    assert cond.covered == 5          # 5 numeric rows, 1 nan row
    assert cond.n_positions == 6
    assert cond.coverage == 5 / 6
    # reactive values: 0.0025, 0.0113, 0.0060, 0.0010, 0.0180
    assert math.isclose(cond.mean_reactivity, (0.0025 + 0.0113 + 0.0060 + 0.0010 + 0.0180) / 5)
    assert math.isclose(cond.min_reactivity, 0.0010)
    assert math.isclose(cond.max_reactivity, 0.0180)


def test_1component_rows_use_raw_as_reactive_rate() -> None:
    """Rows are [nReact, Raw, Background] for 1-component tables; raw=row[1]."""
    rows_1comp = [
        [float("nan"), float("nan"), float("nan")],
        [-0.0296, 0.0019, 0.0029],
        [0.2060, 0.0136, 0.0065],
        [0.2874, 0.0113, 0.0014],
    ]
    canonical = _canonical([_condition(condition="noSAM", rows=rows_1comp)])
    with tempfile_path(canonical) as p:
        d = sam_iii_modality_diagnostic(p)
    cond = d.conditions[0]
    assert cond.covered == 3
    assert math.isclose(cond.min_reactivity, 0.0019)
    assert math.isclose(cond.max_reactivity, 0.0136)


def test_never_upgrades_even_when_all_flags_true() -> None:
    """Fail-closed: even with registered semantics + independence, no upgrade."""
    canonical = _canonical([_condition()])
    with tempfile_path(canonical) as p:
        d = sam_iii_modality_diagnostic(
            p,
            action_semantics_registered=True,
            dependency_unit_known=True,
            reads_independent=True,
        )
    # Action semantics IS comparable now, but the module never upgrades a
    # diagnostic to a certificate (contract 8.4/8.5).
    assert d.action_semantics_comparable is True
    assert d.verdict == NOT_ESTABLISHED


def test_as_dict_roundtrip() -> None:
    canonical = _canonical([_condition()])
    with tempfile_path(canonical) as p:
        d = sam_iii_modality_diagnostic(p)
    out = d.as_dict()
    assert out["dataset_id"] == "sam-iii"
    assert out["verdict"] == NOT_COMPARABLE
    assert out["label"] == DIAGNOSTIC
    json.dumps(out)


def test_condition_react_as_dict_serializable() -> None:
    from d2t_rna.data.r2_sam_iii_diagnostic import SamIIIConditionReact

    c = SamIIIConditionReact(
        construct="native",
        condition="SAM",
        n_positions=6,
        covered=5,
        coverage=5 / 6,
        mean_reactivity=0.01,
        min_reactivity=0.001,
        max_reactivity=0.018,
        raw=(0.01, 0.02),
    )
    d = c.as_dict()
    assert d["coverage"] == round(5 / 6, 6)
    assert d["mean_reactivity"] == 0.01
    json.dumps(d)


from contextlib import contextmanager  # noqa: E402


@contextmanager
def tempfile_path(obj):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "canonical.json"
        p.write_text(json.dumps(obj))
        yield p