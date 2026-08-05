# Task 6 accession-first data manifest build

## Scope

This record is governed only by
`contracts/D2T-RNA-v6.1-frozen-plan.md` at SHA-256
`87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`.
The stage records official metadata, construct identity, assay, replicate,
dependency graph, exposure status, and `EvidenceRole`. It does not download
or interpret FASTQ outcomes and does not generate native truth labels.

## Registered sources

- `add`: RMDB accession `ADDAPO_DCP_0000`.
- `sam-iii`: NCBI GEO `GSE278422`, RCSB PDB `6C27`, and Rfam `RF01767`.
- `rorc`: no primary official RNA accession was resolved from the project
  record or the bounded official-source search. The manifest records this as
  `INELIGIBLE_UNRESOLVED_METADATA`; it is not replaced with a same-name gene
  or unrelated sequencing accession.

All public planning facts retain source IDs and retrieval date
`2026-08-01`. Construct identity and truth payloads remain hash-only.

## Stop-line and acceptance interpretation

All five output classes are separate schemas and cross-file hash-bound:

- public planning stub;
- sealed truth commitment;
- private provenance manifest;
- sanitized action package;
- RORC stress eligibility record.

`PASS_WITH_FAIL_CLOSED_RORC` means the manifest engineering checks pass while
RORC remains ineligible. It does not issue a truth label, a risk certificate,
a held-out claim, or a prospective/new-library conclusion.
