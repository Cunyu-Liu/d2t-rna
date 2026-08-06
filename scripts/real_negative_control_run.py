"""Fail-closed negative control runner (A3).

Emits a JSON certificate showing that the D2T-RNA executable *honestly refuses*
to certify separation on a real measured panel that cannot separate.  The panel
is drawn only from the measured-shared positions of the add riboswitch assay
(RMDB ADD71_STD_0001, Tian/Kladwang/Das, eLife 2018): identical binarized
apo/bound reactivity after the registered 1% readout floor.

Expected outcome
----------------
* T2b status ``IFF`` but ``gamma == 0`` with a non-trivial ``collision_witness``
  and no ``separation_witness``.
* ``enumeration_matches_lp == true`` and ``lp_strong_duality == true``.

This is the fail-closed evidence (contract 8.4 / 10.2): no input condition is
force-fit into a separation it cannot support.

Usage:
    PYTHONPATH=src python scripts/real_negative_control_run.py
"""
from __future__ import annotations

import json
import os
import time
from fractions import Fraction
from pathlib import Path

from d2t_rna.data.measured_add import (
    DOI,
    ACCESSION,
    PMID,
    registered_sequence,
)
from d2t_rna.data.measured_negative import (
    NEGATIVE_CONTROL_LABEL,
    NEGATIVE_CONTROL_ROLE,
    build_negative_control_model,
    certify_negative_control,
    strictly_non_separating_positions,
)

ARTIFACTS_ROOT = Path(os.environ.get("D2T_RNA_ARTIFACTS_ROOT", "/mnt/cunyuliu/d2t-rna/artifacts"))


def main() -> None:
    shared = strictly_non_separating_positions()
    cert = certify_negative_control(shared)
    model = build_negative_control_model(shared)

    out = {
        "name": "add_measured_shared_panel_negative_control",
        "role": NEGATIVE_CONTROL_ROLE,
        "label": NEGATIVE_CONTROL_LABEL,
        "accession": ACCESSION,
        "doi": DOI,
        "pmid": PMID,
        "length": len(registered_sequence()),
        "n_shared_panel_actions": len(model.actions),
        "shared_panel": shared,
        "observation_channel": "measured_1M7_SHAPE_reactivity (shared positions only)",
        "t2b": {
            "panel": [a.action_id for a in model.actions],
            "status": cert.status,
            "gamma": str(cert.gamma),
            "collision_witness": [str(x) for x in cert.collision_witness]
            if cert.collision_witness
            else None,
            "separation_witness": [str(x) for x in cert.separation_witness]
            if cert.separation_witness
            else None,
            "enumeration_matches_lp": cert.enumeration_matches_lp,
            "lp_strong_duality": cert.lp_strong_duality,
        },
        "verdict": (
            "FAIL_CLOSED"
            if (cert.gamma == 0 and cert.collision_witness is not None)
            else "SEPARATED (unexpected)"
        ),
    }

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"real-negative-control-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "certificate.json").write_bytes(
        json.dumps(out, indent=2, sort_keys=True).encode("utf-8")
    )

    print(
        json.dumps(
            {
                "accession": ACCESSION,
                "n_shared_panel_actions": out["n_shared_panel_actions"],
                "gamma": out["t2b"]["gamma"],
                "verdict": out["verdict"],
                "enumeration_matches_lp": out["t2b"]["enumeration_matches_lp"],
                "lp_strong_duality": out["t2b"]["lp_strong_duality"],
                "artifact": str(run_dir / "certificate.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()