# Experiment runbook

No training or GPU validation has been launched for D2T-RNA.

Before any run:

1. create a unique run ID;
2. record the code commit, contract hash, resolved config, data and split hashes, seed, CUDA requirement, GPU index and UUID, exact command, and all absolute evidence paths;
3. recheck process ownership, GPU memory/utilization, CUDA availability, CPU/RAM/swap, and disk;
4. start only if CPU fallback is impossible and all outputs are writable;
5. persist the main log, tail-friendly local metrics, system metrics, checkpoints, manifest, and failure bundle under `/mnt/cunyuliu/d2t-rna`;
6. monitor at low frequency and preserve all success, failure, and early-stop evidence.

Each completed run adds `docs/experiments/<run_id>.md` with objective, changes, command, evidence paths, results, failures, diagnosis, repair, validation, next preflight, and final status.
