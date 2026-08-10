# D2T-RNA v7 — Data / Code / License Availability (Phase 6, synthetic route)

> Status: fail-closed `PAPER_MANUSCRIPT_DRAFT_READY_FOR_AUTHOR_REVIEW`
> (`SCIENTIFIC_SUBMISSION_BLOCKED_PENDING_AUTHOR_REVIEW`).  Owner/legal approval
> required before any submission claim.  `scientific_claim_authorized = false`.
> This statement is a packaging artifact, not a scientific or submission claim.

## Code

- Repository (frozen working copy): `/home/cunyuliu/d2t-rna` at frozen `HEAD`.
- All results in this bundle bind to the frozen `HEAD` recorded in
  `manifests/audit/v7_p6_submission_receipt.json`.
- Import origin verified: `d2t_rna` resolves under `repo/src/d2t_rna`
  (confirmed by the paper readiness gate `PAPER-IMPORT-ORIGIN-GATE`).
- Python environment: `editflow311`, Python 3.11 (project requires `>=3.11,<3.12`).
- No code is pushed (per execution policy; `HEAD != origin/main` until an
  authorized push).  The legacy `s14` delivery-bundle `source/runtime` check
  fails solely because of this no-push policy and is not a reproducibility
  failure.
- License: **Proprietary** (per `pyproject.toml`, `license.text = "Proprietary"`).

## Data

- **Synthetic benchmark only.** All evaluation is model-conditional and fully
  synthetic; no biological, population, transfer, or real-data claim is made.
- Immutable result artifacts (SHA-256 recorded in the Phase 6 receipt):
  - `/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/` — 80-cell grid, 12-cell
    ablation, baseline suite, scalability, Scheme-C scaling.
  - `/mnt/cunyuliu/d2t-rna/artifacts/phase4/p4_comparative.json` — sealed-family
    comparative (`COMPARATIVE_SYNTHETIC_RECORD`).
  - `/mnt/cunyuliu/d2t-rna/artifacts/phase5/p5_claim_register_v2.json` —
    claim register v2.
- **Real-data route is `TERMINATED_FOR_CURRENT_DATA`.**  The add riboswitch
  (PDB 1Y26), glycine riboswitch, and miniTTR cases are used only as
  `DESCRIPTIVE_ONLY` model-sensitivity illustrations on registered finite
  observation models.  No real gamma certificate, biological repeat count, or
  wet-lab cost claim is made.

## License

- Proprietary.  Distribution and reuse require owner authorization; the bundle
  does not grant any open-source rights.

## Reproducibility pointers

- Readiness gate: `scripts/paper_readiness_gate.py` → `ALL PASS` at frozen HEAD.
- Independent red team: `scripts/redteam_p0_review.py` → `all_pass = true`
  (7/7 checks), receipt recorded under the run directory referenced in the
  Phase 6 receipt.
- Citation verification: 100% (cited ⊆ bib and all bib cited).
- Claim–evidence bidirectional graph: `manifests/audit/v7_claim_evidence_graph_v2.json`.
- PDF QA: `docs/paper/manuscript.pdf` and `docs/paper/supplementary.pdf` build
  cleanly at frozen HEAD (cross-references resolve via `xr-hyper`).
