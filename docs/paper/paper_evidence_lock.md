# D2T-RNA v7 — Paper Evidence Lock (PAPER-0)

> **状态：`PAPER_EVIDENCE_LOCKED`**
> schema: `d2t_rna.paper_evidence_lock.v1`
> 本项目进入 **PAPER-0 (evidence lock)** 与 **PAPER-1 (manuscript build)** 阶段。
> 本文档是 paper-only 文件，不修改、不覆盖任何历史 acceptance manifest。

## 1. Repository state (preflight, read-only)

```text
repo            = /home/cunyuliu/d2t-rna
required_head   = f50e2510b473a4dcb9981790e7e060b2919dd1e6
required_origin = f50e2510b473a4dcb9981790e7e060b2919dd1e6
current_head    = f50e2510b473a4dcb9981790e7e060b2919dd1e6
origin_main     = f50e2510b473a4dcb9981790e7e060b2919dd1e6
worktree        = clean
```
preflight 通过：HEAD == origin/main == required，工作树干净，无未提交修改。

## 2. 封存输入（immutable evidence）

以下 acceptance manifest 与权威文档作为 paper evidence 封存输入，全部记录 SHA-256。
它们的状态与哈希已在本轮 preflight 中逐项核验，与 v7 contract authority 一致。

| 输入 | 角色 | SHA-256 (前 16) |
|---|---|---|
| manifests/m0/m0_v7_activation.json | 激活 | `ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS` |
| manifests/t2/t2_2_acceptance.json | T2b | `a1711025f9a748a2` |
| manifests/t2/t2_3_acceptance.json | T2c | `aad9a03504b78888` |
| manifests/t2/t2_4_acceptance.json | T2d | `6ac0d5b4a0202b49` |
| manifests/t2/t2_5_acceptance.json | T2-5 binding | `c84b7cbe5938390a` |
| manifests/t9/t9_matrix_acceptance.json | §9 矩阵 | `a0b56f5ac0609482` |
| manifests/t10/t10_validation_acceptance.json | §10 验证 | `0fc567f4453b18fa` |
| manifests/task6r/task6r_r1_acceptance.json | Task6-R R1 | `5e1b0ab895330780` |
| manifests/task6r/task6r_r2_acceptance.json | Task6-R R2 | `6928e7ca10666e0d` |
| manifests/s12/s12_3_submission_gate_acceptance.json | §12.3 门 | `4af1735cfbc6758b` |
| manifests/s14/s14_delivery_bundle_acceptance.json | §14 bundle | `e81ed5c2e6aae5e8` |
| docs/contracts/amendments/v7_amend_12_3_6_20260805.md | §12.3-6 修正案 | — |

完整 SHA-256 见 `manifests/paper/paper_evidence_lock.json` 的 `input_sha256` 字段。

## 3. Authority precedence

```text
1  active_v7_activation_and_approved_amendment
2  accepted_T2_manifests
3  accepted_T9_T10_manifests
4  accepted_Task6R_R1_R2_manifests
5  S12_submission_gate
6  S14_delivery_bundle
7  historical_t9_4_synthesis_record
8  legacy_project_contract_manifest
```

## 4. 历史记录 precedence（不修改原文件，仅在 crosswalk 中说明）

| 历史文件 | 状态 | 当前 authority | 原因 |
|---|---|---|---|
| docs/audit/t9_4_paper_scientific_units.md | `HISTORICAL_SYNTHESIS_RECORD` | false | 其 §9.4 时点 Task6-R 单元 4 记为"尚未完成"；此状态已被 S12 `COMPLETE_FAIL_CLOSED_ONLY_AUDIT` 与 R2 fail-closed 终态取代 |
| manifests/project_contract.json | `LEGACY_V6_1_PROJECT_CONTRACT_MANIFEST` | false | 保留 v6.1 的 T2 lemma-pending blocked 历史状态 |

两个文件保持原样，只在此 paper crosswalk 中说明其 precedence。

## 5. 科学解释（§1.1）

```text
T2b/T2c/T2d 是 model-conditional synthetic/theoretical certificates。
§9 是 model-conditional synthetic evaluation 与 executed baselines。
§10 是 contract assumptions、independence checker 与 claim boundaries 的 synthetic validation。
Task6-R 完成了 complete fail-closed audit，但无 qualified quantitative retrospective instance。
S12 submission readiness 是 internal evidence gate，不是 scientific claim authorization。
S14 是 delivery/replay bundle，不是 biological validation。
```

R2 三数据集终态为 fail-closed terminal outcomes，不是 established quantitative instances：
add=`NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL`，
sam-iii=`NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE`，
rorc=`NOT_APPLICABLE`。

## 6. S14 source commit 差异记录

S14 bundle 的 source commit 为 `728dec61...`，当前 HEAD 为 `f50e251...`。二者是不同
commit；差异已在本题 PAPER-0 中显式记录，不视为同一 commit。S14 引用的 §14 重放
source 是 `728dec61`，当前 paper build 基于 `f50e251`。

## 7. 授权边界

`paper_evidence_lock` 全部字段 `scientific_claim_authorized = false`。
本锁不授权任何 prospective / held-out / independent 验证主张。
