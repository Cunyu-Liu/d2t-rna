"""wrappers.toy_parity_runner -- run every faithful wrapper's toy case (P0-9).

The runner executes each registered wrapper's ``run_toy_parity()`` and records
PASS/FAIL/UNKNOWN against the *published* value, plus a ``headline_eligible``
flag.  A wrapper is headline-eligible ONLY if its original-paper toy case is
reproduced (status PASS against a verified published value).  Wrappers without
a verifiable published toy value are marked
``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and are NOT headline-eligible.
"""

from __future__ import annotations

import json

from .base import UNKNOWN

# registry of faithful wrappers (deterministic order)
_WRAPPERS = [
    ("controlled_sensing", "controlled_sensing"),
    ("fixed_horizon_ht", "fixed_horizon_ht"),
    ("bayesian_eig", "bayesian_eig"),
    ("test_cover", "test_cover"),
]


def registered_wrappers():
    """Yield instantiated wrappers in deterministic order."""
    from . import bayesian_eig, controlled_sensing, fixed_horizon_ht, test_cover

    mods = {
        "controlled_sensing": controlled_sensing,
        "fixed_horizon_ht": fixed_horizon_ht,
        "bayesian_eig": bayesian_eig,
        "test_cover": test_cover,
    }
    for wrapper_id, _mod in _WRAPPERS:
        yield mods[wrapper_id].wrapper()


def run_all_toy_parity() -> dict:
    """Run every wrapper's toy case; return an aggregated report."""
    results = [w.run_toy_parity() for w in registered_wrappers()]
    headline = [r for r in results if r.headline_eligible]
    n_unknown = sum(1 for r in results if r.status == UNKNOWN)
    return {
        "schema": "d2t_rna.wrappers.toy_parity.v3",
        "n_wrappers": len(results),
        "n_headline_eligible": len(headline),
        "n_unknown_full_text": n_unknown,
        "headline_eligible": [r.to_dict() for r in headline],
        "results": [r.to_dict() for r in results],
        "note": (
            "Wrappers without a verifiable published toy value are marked "
            "UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING and are NOT "
            "headline-eligible; no parity number is invented."
        ),
    }


def write_toy_parity_report(path: str) -> dict:
    import os
    import tempfile

    report = run_all_toy_parity()
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".toy_parity.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return report
