# §9.4 论文科学单元（Paper Scientific Units）

> 合同：D2T-RNA v7 `D2T-RNA-v7-THEORETICAL-RNA-METHODS`（v7.0.0）
> 状态：`SYNTHESIS_RECORD`（整理记录，非论文正文，非科学主张授权）
> `scientific_claim_authorized = false`

依据合同 §9.4，主结果固定为五项科学单元。本文档把每一项主结果与已验证的
artifact、验收 manifest、测试证据绑定，明确哪些已成立、哪些仍受依赖门控。
hash / schema / provenance / 运行 gate 一律归入方法或补充材料，不占据主结果
中心（§9.4 末段）。

---

## 单元 1 — T2 geometry（T2b collision-or-separation）

**内容**：对有限注册 RNA 模型，跨类差集 `D` 与 panel `S` 的鲁棒 action-image
分离 `gamma(S)=inf_{v∈D} max_{u∈S} ||B_u v||_1`；`gamma=0 ⇔` 存在碰撞见证，
`gamma>0 ⇔` 存在分离见证。精确有理 LP 提供 primal/dual 证书，并与穷举枚举
交叉核验。

**证据**：
- 定理：`src/d2t_rna/t2/theorem.py`（`collision_or_separation`、`build_gamma_lp`）。
- 见证/枚举/独立 verifier：`src/d2t_rna/t2/witness.py`、`src/d2t_rna/t2/verify.py`。
- 验收 manifest：`manifests/t2/t2_2_acceptance.json`（state `T2B_EXACT_COLLISION_OR_SEPARATION_ACCEPTED`）。
- 提交：`80bd16e`（T2b）。

**状态**：成立（IFF 方向，含必要/充分边界判定）。

---

## 单元 2 — finite-sample tightness（T2c）

**内容**：乘积律信息的 uniform lower/upper bound、弃权规则、预算后果、精确
TV/Hellinger/decision 枚举对照与 tightness 分析；`Decimal` 守序区间（guard
digits / `_enlarge`）保证严格闭区间。

**证据**：
- 实现：`src/d2t_rna/t2/info.py`、`src/d2t_rna/t2/bounds.py`、`src/d2t_rna/t2/decision.py`。
- 验收 manifest：`manifests/t2/t2_3_acceptance.json`（state `T2_SAMPLE_COMPLEXITY_BOUND_ACCEPTED`）。
  §9 微案例全部 `oracle_in_interval=true` 且交叉不变量成立（`correct_ge_lower`、
  `minimax_le_upper`、`tv_equals_1_minus_2err` 等全真）。
- 提交：`92f767c`（T2c）。

**状态**：成立（T2c 上/下界与精确 oracle 交叉核验一致）。

---

## 单元 3 — algorithm / scalability（§9 评测矩阵与 baseline execution）

**内容**：11 个合成微案例（2x2 alternating rectangle、无 cycle、zero-margin、
对称状态、重复 action、线性组合相消反例、三维/非分解 fixed-marginal、exact
collision、near-collision、strict positive separation、boundary），8 种
baseline 实际执行，报告 cost / risk / honest decision-probability / abstention /
runtime / memory / optimality gap / certified omitted mass / LP lower bound /
integer gap。

**证据**：
- 矩阵：`src/d2t_rna/evaluation/matrix.py`；run：`scripts/t9_matrix_run.py`。
- 运行报告：`/mnt/cunyuliu/d2t-rna/artifacts/runs/t9-matrix-20260805T131421+0800.json`。
- 验收 manifest：`manifests/t9/t9_matrix_acceptance.json`（state
  `T9_MATRIX_BASELINE_EXECUTION_ACCEPTED`）。
- 实测：11 个微案例全部 `oracle_in_interval=true`、交叉不变量全真；8 个 baseline
  （exhaustive oracle / full matrix / random / greedy-Test-Cover / EIG / Chernoff /
  LM²R-style / T2 integer design+LP）在全部微案例上 `verification_flag=EXECUTED`；
  budget=8，T2 integer design cost ∈ {1,4,8} 均不超预算，LP lower bound 为守恒有理数。
- 提交：`cb5f66c`（§9）。

**状态**：成立（baseline 实际执行，未形成 `NO_METHOD_SUPERIORITY_CLAIM` 之外的优越性结论）。

---

## 单元 4 — 三个分开的 retrospective cases（Task6-R）

**内容**：add/RMDB、SAM-III/GSE278422、RORC 三套数据各自的回顾证据资格审查，
不合并估计总体效应量。

**证据（当前 Task6-R 数据清单状态，用户的并行工作）**：
- `docs/audit/task-6-data-manifests.md`（accession 优先、scope 受 v6.1 治理）。
- `manifests/add/`（`ADDAPO_DCP_0000`）、`manifests/sam_iii/`（`GSE278422`/`6C27`/`RF01767`）、
  `manifests/rorc/`（`INELIGIBLE_UNRESOLVED_METADATA` fail-closed）。
- 角色：add=`COUNTERFACTUAL_RETROSPECTIVE_FULL_MATRIX_COMPRESSION`；
  sam_iii=`RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC`；
  rorc=`HISTORICALLY_EXPOSED_THIRD_STATE_MISSPECIFICATION_STRESS`（当前不满足资格）。

**状态**：**数据角色已建立（manifest 工程），回顾评测（R2）与完整资格审核待 Task6-R 阶段完成**。
RORC 在未解析官方 accession 前保持 fail-closed（`INELIGIBLE_UNRESOLVED_METADATA`），
不得以同名基因或无关测序数据替换。据此，单元 4 的完整科学结论**尚未成立**，不影响
单元 1/2/3/5 的纯理论主稿。

---

## 单元 5 — misspecification / abstention boundary（§10）

**内容**：假设破坏时的行为（abstain / `NOT_ESTABLISHED`）、注册 nuisance 耦合
（仅 `CARTESIAN`/`EQUAL_REALIZED_VALUE`）、claim lint、独立 checker 聚合。

**证据**：
- 模块：`src/d2t_rna/evaluation/validation.py`；run：`scripts/t10_validation_run.py`。
- 运行报告：`/mnt/cunyuliu/d2t-rna/artifacts/runs/t10-validation-20260805T133358+0800/`。
- 验收 manifest：`manifests/t10/t10_validation_acceptance.json`（state
  `VALIDATION_SCENARIOS_INDEPENDENT_REVIEW_ACCEPTED`）。
- 实测：assumption gate 1 valid→`PROCEED` + 6 破坏→`NOT_ESTABLISHED`；coupling
  pairwise 正确；claim lint 正确；独立 checker 2 个 collision 验证、5 个 separation
  验证、10 个 LP 对偶可行、10 个 budget/cost 一致、10 个乘积律 TV 一致。
- 提交：`11fa850`（§10）。

**状态**：成立（fail-closed 边界行为已验证）。

---

## 主结果中心与工程边界

五项主结果的 verifier、hash、schema、provenance、运行 gate 均作为工程证据进入
方法或补充材料（§9.4 末段），不占据主结果中心；不得以工程证据替代 theorem。
本记录不改变任何已验收 manifest 的 `scientific_claim_authorized` 状态。

- 合同 §14 重放顺序：authority/hash → source/runtime → statement → input manifest →
  solver → independent checker → microcase → larger finite → retrospective data role →
  claim audit。本记录中单元 4 的 retrospective data role 尚未完成，故不生成主文 claim。
- 硬门（§11）：单元 1/2/3/5 相关 gate 依各自 manifest 通过；单元 4 受
  `DATA-ROLE-GATE` / `DATA-ELIGIBILITY-GATE` 门控，当前未授予。