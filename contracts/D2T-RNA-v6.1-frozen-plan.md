# D2T-RNA v6.1：最终冻结补丁与实现计划

## 1. 状态、架构与技术栈

科学合同冻结，不再修改中心问题。完成本计划前三项 schema/probability tests 后，状态更新为：

```text
GO_FINAL_SCIENTIFIC_FREEZE
GO_PROBABILITY_SPACE_AND_SCHEMA_FREEZE
GO_EXACT_SYNTHETIC_IMPLEMENTATION
GO_DATA_MANIFEST_BUILD
GO_EMPIRICAL_FINITE_DATASET_SUBSAMPLING_QA
GO_MODEL_CONDITIONAL_WITHIN_LIBRARY_RISK_WHEN_IDENTIFIABLE
GO_RORC_FAIL_CLOSED_STRESS

T2_LEMMA_PENDING_QUANTITATIVE_INTERVENTION_CONSEQUENCE
NO_GO_PROSPECTIVE_COVERAGE_CERTIFICATE
NO_GO_NEW_LIBRARY_CERTIFICATE
NO_GO_NATIVE_T4
NO_GO_POPULATION_GENERALIZATION
```

工作区当前无代码，初始化为 Python 3.11 项目：

```text
pyproject.toml
src/d2t_rna/
  contracts/
  probability/
  exact/
  evaluation/
  data/
tests/
manifests/
```

使用 Pydantic v2、NumPy/SciPy、pytest、Hypothesis；精确小体系使用 `fractions.Fraction` 或有认证误差的区间算术。所有合同对象：

```python
model_config = ConfigDict(extra="forbid", frozen=True)
```

并使用 canonical JSON 和 SHA-256。默认不 push、不创建外部 PR。

## 2. 四个强制概率与 schema patch

### Patch A：区分经验下采样与潜在 library 风险

新增 `ProbabilitySpaceSpec`：

```text
probability_scope:
  FINITE_OBSERVED_DATASET_SUBSAMPLING
  WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL
  NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL
  SYNTHETIC_KNOWN_CHANNEL

fixed_objects
random_objects
sampling_law_hash
parameter_space_hash
conditioning_sigma_field_hash
observation_model_hash
estimand
formal_scientific_risk_guarantee
```

#### `FINITE_OBSERVED_DATASET_SUBSAMPLING`

固定完整观察数据集 \(D_{\mathrm{obs}}\)，只有下采样索引 \(I\) 随机：

\[
P_{\mathrm{sub}}^{D_{\mathrm{obs}}}(E)
=
P_I\{E(D_{\mathrm{obs},I})\mid D_{\mathrm{obs}}\}.
\]

合同固定为：

```text
target: FULL_OBSERVED_DATASET_EMPIRICAL_FEATURE_DISTRIBUTION
formal_scientific_risk_guarantee: false
```

只允许产生：

- finite-population subsampling QA；
- read-depth degradation curve；
- confidence-set 软件 QA；
- empirical panel compression；
- retrospective yield-conditional curve。

不得输出 latent RNA ensemble、物理 library 或新 library 风险证书。

#### `WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL`

目标是注册 observation model 中的 latent ensemble parameter。必须声明：

- 同一 realized library 下的新有效分子抽样机制；
- 已条件化的 batch/library nuisance；
- duplicate/ESS 处理；
- observation weighting/sequencing law；
- split relation 及条件独立证明；
- 完整 uniform confidence-set proof。

只有这些对象齐全时，允许：

```text
MODEL_CONDITIONAL_WITHIN_LIBRARY_RISK_CERTIFICATE
```

该证书不外推到重新 folding、probing、RT、PCR、建库或新批次。

### Patch B：分离不重叠与统计独立

`SplitRelationSpec` 必须包含：

```text
split_relation:
  INDEPENDENT_LIBRARIES
  CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE
  RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET
  SHARED_BATCH_DEPENDENT
  UNKNOWN

dependency_unit_level
planning_partition_hash
certificate_partition_hash
conditioning_sigma_field_hash
selection_inference_independence_proof
overlap_counts
split_seed
```

验证规则：

- `INDEPENDENT_LIBRARIES`：允许普通独立 inference split。
- `CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE`：RiskCertificate 必须条件于该 nuisance，或对其统一最坏化。
- `RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET`：使用有限总体联合分布；不得引用 iid data-splitting 论证。
- `SHARED_BATCH_DEPENDENT`：需要显式联合模型或 selective-valid inference；v1 默认不发正式证书。
- `UNKNOWN`：只能 descriptive。

正式措辞统一为：

> dependency-unit separated with a registered split relation。

仅 read ID 不重叠不够；R1/R2、PCR family、UMI/molecule family 必须作为同一依赖单位。

### Patch C：RiskCertificate 加入 indifference 安全性

令：

\[
I=\{\omega:\tau_0<L(p,p^\star)<\epsilon\}.
\]

`RiskCertificate` 输出：

```text
h0_wrong_reject_bound
h1_wrong_certify_bound
indifference_decisive_output_bound
confidence_set_uniform_coverage
probability_scope
conditioning_sigma_field_hash
success_event_hash
failure_event_policy
conditional_bound
unconditional_bound
unconditional_derivation
```

在统一 95% confidence set 和所有失败分支均 abstain 时：

\[
\sup_{\omega\in I}P_\omega(C\cup R)\le0.05.
\]

条件风险转无条件风险只允许以下路径：

- `TOWER_UNIFORM_ALMOST_SURE`：条件风险界对注册 sigma-field 几乎处处成立。
- `ABSTAIN_OUTSIDE_VALIDITY_EVENT`：有效事件外强制 abstain，无条件界仍为 \(\delta\)。
- `GOOD_EVENT_UNION_BOUND`：有效事件外仍可能决策时：

\[
P(W)\le\delta+(1-\delta)\rho.
\]

- `NOT_AVAILABLE`：不能推出无条件界。

若证书条件于实际有效分子数 \(N\)，必须登记：

```text
conditional_on_effective_molecule_count: true
prospective_unconditional_bound: null
```

### Patch D：密封 TruthAsset 完整数值内容

Lock A–C 只允许：

```text
TruthAssetCommitment:
  truth_asset_id
  asset_hash
  sequence_identity_hash
  condition_spec_hash
  measurement_modality
  eligibility_status_without_direction
  numeric_payload_hash
  semantic_payload_hash
  visibility: HASH_ONLY
```

以下内容全部密封至 Lock D：

- population estimate 和 confidence region；
- directional evidence；
- state-preservation result；
- projected state proportions；
- H0/H1/core binding；
- action-effect labels。

Lock D 重新计算 numeric、semantic 和 binding payload hashes；任一不匹配则停止评分。`native_t4_eligible` 只能存在于 `DecisionTruthBindingReveal`。

## 3. Scenario、RORC 与 baseline 严格化

### 逐 scenario coverage proof

每个 scenario 必须有独立 `ScenarioProof`：

```text
scenario_id
law_hash
hypothesis_region
coverage_core_membership
conditioning_sigma_field_hash
risk_upper_bounds
coverage_lower_bounds
coverage_bound_method:
  EXACT_ENUMERATION
  VERIFIED_INTERVAL
  CERTIFIED_TRUNCATION
  MONTE_CARLO_ONLY
probability_mass_accounted
omitted_mass_bound
numerical_error_bound
proof_artifact_hash
```

只有前三种方法允许 `formal_guarantee: true`。`MONTE_CARLO_ONLY` 自动降级为 `RISK_CERTIFIED_COVERAGE_PREDICTED`。

有限 scenario 聚合只使用：

\[
\max_s\{\text{risk upper bound}\},
\qquad
\min_s\{\text{coverage lower bound}\}.
\]

同时记录 `per_scenario_proof_manifest`、`scenario_coverage_union_bound` 和 `scenario_probability_mass_accounted`。不得插值到连续 uncertainty set。

### RORC fail-closed

RORC 成功标准改为：

```text
decision: ABSTAIN
reason in:
  REGISTERED_MODEL_CLASS_REJECTED
  OUT_OF_SCOPE_STATE_DICTIONARY
  RIVAL_SUPPORT_INCOMPLETE
  ABSTAIN_INDETERMINATE
```

不要求算法猜中唯一生物学失配原因。主要指标为：

\[
P(\text{incorrect decisive output})
\]

以及遗漏第三状态后的 coverage 下降。允许返回多个稳定排序、去重后的 reason codes；不得根据 RORC 调优诊断器后再称其为 held-out stress test。

### Random baseline

对每个种子定义：

\[
\widetilde C_i=
\begin{cases}
C_i,&\text{feasible},\\
+\infty,&\text{completed but infeasible},\\
\mathrm{NA},&\text{timeout/error/unresolved}.
\end{cases}
\]

输出：

```text
feasibility_fraction
unresolved_fraction
extended_cost_median
feasible_cost_median
feasible_cost_iqr
```

规则：

- `+∞` 参与 extended median。
- `NA` 不参与排序，也不得与 infeasible 合并。
- 若 `unresolved_fraction>0`，primary `extended_cost_median=NA`，仅报告 resolved-only diagnostic。
- 若无 unresolved 且超过一半种子 infeasible，则中位成本为 \(+\infty\)。
- 固定 100 个 hash-derived seeds，禁止 best-of-100。
- 若所有竞争 baseline 不可行而本方法可行，报告 `FEASIBILITY_DOMINANCE`，不计算零成本比。

## 4. 实现任务与 TDD 顺序

### Task 1：项目骨架和不可变 schema

创建 `pyproject.toml`、`src/d2t_rna/contracts/` 和 schema tests。

先测试：

- 未注册字段被拒绝；
- canonical hash 跨进程一致；
- JSON 禁止裸 `Infinity/NaN`，使用 tagged `FINITE/POS_INF/NA`；
- Lock A–C 出现 truth numeric payload 立即失败；
- Lock A→B→C→D hash chain 不可逆。

验收后提交：

```text
feat(contracts): freeze probability and data-lock schemas
```

### Task 2：概率空间、split relation 和 RiskCertificate

实现 `probability/scopes.py`、`splits.py`、`risk.py`。

先测试：

- observed-dataset QA 拒绝 `formal_scientific_risk_guarantee=true`；
- model-conditional scope 缺 observation model 或 independence proof 时强制 abstain；
- random finite partition 不能序列化为 independent split；
- 条件风险通过 tower property 得到无条件界；
- failure 时 abstain 与继续决策分别得到 \(\delta\) 和 \(\delta+(1-\delta)\rho\)；
- indifference truth 的 decisive probability 不超过 0.05；
- QC、GOF、solver、yield failure 均只能 abstain。

提交：

```text
feat(probability): separate empirical QA from model-conditional risk
```

### Task 3：Truth commitment、语义盲法和 Lock D

实现 `contracts/truth.py`、`locks.py` 和 planning-package sanitizer。

先测试：

- Lock A–C 只能读取 hash-only stub；
- 文件名、headers、metadata 中的 ON/OFF/rescue 标签被检测；
- Lock D 前揭示 population region 使评测失效；
- reveal payload 与 commitment 不一致时停止评分；
- 当前 add、SAM-III、RORC 标记为 `HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE`。

提交：

```text
feat(data-lock): seal truth payloads until post-certificate audit
```

### Task 4：Exact enumeration 和 coverage engine

实现 `exact/support.py`、`enumerate.py`、`confidence.py`、`coverage.py`。

范围保持：

- \(K\le3\)；
- 动作不超过 3；
- alphabet 不超过 4；
- \(N_{\mathrm{total}}\le40\)；
- 单动作可到 80；
- 联合支持数上限 \(10^7\)。

先计算：

\[
\prod_u
\binom{N_u+m_u-1}{m_u-1}.
\]

超过上限必须在创建迭代器或分配内存前抛出 `EnumerationTooLarge`。验证精确概率和误差不超过 \(10^{-12}\)。

新增两项强制测试：

- **Indifference test**：所有注册 \(\omega\in I\) 满足 \(P(C\cup R)\le0.05\)。
- **Outer-approximation monotonicity**：

  \[
  \mathcal C_{\mathrm{exact}}\subseteq
  \mathcal C_{\mathrm{outer}}
  \]

  时，outer set 不得产生 exact set 未产生的确定性结论。

提交：

```text
feat(exact): add exhaustive risk and coverage verification
```

### Task 5：Scenario proof、planner failure 与 baselines

实现 proof manifest、独立 MILP checker、三层失败语义和 baseline wrapper。

必须区分：

```text
NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER
NO_CERTIFICATE_WITHIN_AVAILABLE_CONTROL_LIBRARY
NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS
PLANNER_UNRESOLVED
```

所有 baseline 使用同一 RiskCertificate、CoverageFeasibilityAssessment、yield scope、成本表和扩展顺序。Monte Carlo scenario proof 不得冒充 formal coverage。

提交：

```text
feat(evaluation): unify proof manifests and baseline feasibility
```

### Task 6：Data manifest build

为 add、SAM-III、RORC 构建 accession-first manifests，先只录入官方 metadata、construct identity、assay、replicate、dependency graph、exposure status 和 EvidenceRole。

输出分离为：

- public planning stub；
- sealed truth commitment；
- private provenance manifest；
- sanitized action package；
- RORC stress eligibility record。

不在本阶段下载或解释 FASTQ outcome，不生成 native truth label。

提交：

```text
data(manifest): add audited RNA parent manifests
```

## 5. Release tests 与最终边界

进入 large finite stress 前必须全部通过：

- exact micro-case 与独立 naive oracle 完全一致；
- \(m=16,N=80\) 在枚举前被拒绝；
- observed-dataset QA 永不产生 latent ensemble risk claim；
- split relation 与 conditioning sigma-field 一致；
- indifference 不进入 H0/H1 错误分母且 decisive bound 正确；
- outer approximation 只能减少确定性输出；
- scenario 每一点均有形式 proof manifest；
- random `+∞/NA` 语义无混用；
- RORC 对全部注册路径均 abstain，但不要求唯一 reason；
- Lock D 前无法访问任何数值或方向 truth；
- 所有证书、计划、manifest 和 proof artifacts 均可由 hash 复现。

最终公开口径固定为：

> exact synthetic risk–coverage proof；真实 RNA 数据上的经验有限数据集下采样 QA 和 coverage prediction；仅在注册 observation model、split relation 与条件化对象均可辩护时输出 model-conditional within-library risk certificate。不存在 prospective coverage、new-library risk、native T4 或 RNA population-level 保证。