# Python 3.11 environment bootstrap audit

## Attempt 1 — preserved failure

```text
run_id: env-py311-20260729T2145p0800
target: /mnt/cunyuliu/d2t-rna/envs/py311
package_cache: /mnt/cunyuliu/d2t-rna/tmp/conda_pkgs
log: /mnt/cunyuliu/d2t-rna/logs/env-py311-20260729T2145p0800.log
command: /home/cunyuliu/miniconda3/bin/conda create --prefix /mnt/cunyuliu/d2t-rna/envs/py311 python=3.11 pip -y
```

Observed sequence:

1. Python 3.11.15 and base packages downloaded.
2. Conda entered its transaction against the NFS-backed `/mnt` prefix.
3. The process remained in `rpc_wait_bit_killable`.
4. The last observed file write was epoch `1785333682`.
5. After more than eight minutes without another write, the process met the registered no-progress stop rule.
6. PID 1369849 and its parent were revalidated by exact command, PPID, and run ID before `SIGTERM`.
7. The parent exited immediately; the child exited after the NFS RPC returned.

No partial file or log was deleted. This attempt is `FAILED_WITH_EVIDENCE`.

## Attempt 2 — successful recovery

```text
run_id: env-py311-home-20260729T2212p0800
target: /home/cunyuliu/d2t-rna/.venv
package_cache: /home/cunyuliu/d2t-rna/.conda-pkgs
log: /mnt/cunyuliu/d2t-rna/logs/env-py311-home-20260729T2212p0800.log
command: /home/cunyuliu/miniconda3/bin/conda create --prefix /home/cunyuliu/d2t-rna/.venv python=3.11 pip -y
```

Result:

```text
Python 3.11.15
pip 26.1.2
```

The `.venv`, `.conda-pkgs`, and `.pip-cache` paths are ignored by Git. They contain software runtime files only. Datasets, weights, checkpoints, logs, and generated scientific artifacts remain under `/mnt/cunyuliu/d2t-rna`.

## Project dependency installation

```text
run_id: deps-task1-20260729T2225p0800
log: /mnt/cunyuliu/d2t-rna/logs/deps-task1-20260729T2225p0800.log
command: /home/cunyuliu/d2t-rna/.venv/bin/python -m pip install -e ".[dev]"
```

Resolved versions:

```text
pydantic 2.13.4
pydantic-core 2.46.4
numpy 2.4.6
scipy 1.17.1
pytest 9.1.1
hypothesis 6.163.0
```

Final status: `PASS`.
