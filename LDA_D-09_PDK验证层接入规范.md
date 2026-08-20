# LDA PDK 验证层接入规范（D-09）

> **版本**：v1.0 · 2026-08-20
> **定位**：阶段2 咽喉④ 的「技术落地契约」——定义晶圆厂 PDK 如何接入 LDA 验证层
> **对准**：《晶圆厂 PDK 对接首封话术与路线图》五步路线图 **第三步 · 验证层接入**
> **用途**：首封拿到 PDK 文档样例后，按本规范把它注册为 LDA 的「外部验证层」，
> 使主权求解器在真实工艺参数下接受检验，并沉淀公开基准（反向提升 PDK 信用）。

---

## 1. 接入对象与映射（PDK 三资产 → LDA 三 golden 源）

PDK 提供的三类资产，分别映射到 LDA 已有的 gold 来源结构（**不新造轮子，复用 D-06/D-04/D-05**）：

| PDK 资产 | 含义 | 映射为 LDA 结构 | 落地载体 |
|---|---|---|---|
| **层叠 Stack** | 材料折射率 / 膜厚 / 包层 | 几何真值（`geometry` 字典的 `n_si`/`n_clad`/`h_core_um` 等） | 求解器材料参数 + D-05 IR `param_bounds` |
| **设计规则 DRC** | 最小线宽 / 间距 / 曲率 | IR 参数边界（`lda_ir` 的 `param_bounds`） | D-05 L0 IR 设计空间约束 |
| **元件模型 Component Models** | 实测 S 参数 / 有效折射率 / 损耗 | `EmpiricalMeasurement`（D-06 corpus） | D-06 实证语料库 + `EmpiricalAnchor` |

> 红线（话术文档 §0）：PDK 是**制造侧资产**，LDA **借真值、不借代码**；PDK 内部 IP 不进入 LDA 求解器，
> 只作为外部 golden source 参与确定性比对。**不碰 GPL**。

---

## 2. 接入流程（对齐话术五步路线图第三步）

```
[话术第一步·首封] → [第二步·互信(脱敏PDK样例)] 
   → ★ 本规范起点：第三步·验证层接入 ★
   ① PDK 文档评估    平台给脱敏样例（层叠/规则/元件模型样例）
   ② 定义 PDK adapter   把 PDK 元件模型映射为 EmpiricalMeasurement / IR bounds
   ③ 注册 external golden   source="pdk-<fab>"，接入 EmpiricalAnchor / VerificationSpec
   ④ 跑验证层             LDA 求解器在该 PDK 真实工艺参数下接受检验
   ⑤ 沉淀公开基准        PDK 模型 vs LDA 仿真 的公开对比（脱敏）
   → [第四步·MPW小切口] → [第五步·意向闭环]
```

### ② 定义 PDK adapter（数据契约）

每个 PDK 元件模型条目，映射为一条 `EmpiricalMeasurement`：

```json
{
  "id": "P-NOEIC-DC-KAPPA",
  "device": "方向耦合器 gap=0.3um (NOEIC 220nm PDK)",
  "metric": "kappa_um",
  "measured_value": 0.035,
  "uncertainty_abs": 0.001,
  "fab_source": "NOEIC iSiPP220 PDK v2.1（脱敏样例）",
  "citation": "NOEIC PDK 元件模型文档 §3.2",
  "method": "cutback / 矢量网络分析",
  "geometry": {"w_core_um": 0.5, "h_core_um": 0.22, "gap_um": 0.3, "n_si": 3.48, "n_clad": 1.44, "wl_um": 1.55},
  "tags": ["pdk", "noeic", "coupler"]
}
```

- `id` 统一前缀 `P-<FAB>-<device>-<metric>`，与种子 corpus（`E-` 前缀）区分；
- `fab_source` / `citation` 必填且指向 PDK 文档版本（溯源，D-06 provenance 自动记录来源文件 + 贡献者）；
- 经 **D-06 批量导入工具**（`import_csv` / `import_json`）去重 + 溯源入库，或经 **D-10 CLI**（`empirical_submit.py --out bank`）单条补登。

### ③ 注册 external golden

复用 D-04 统一验证契约：把 PDK 条目注册为一个 `VerificationSpec`，其
`oracle_fn` 指向 `EmpiricalAnchor.resolve(mid)`，`source` 标记为 `pdk-<fab>`：

```python
from lda_harness.empirical_bank import EmpiricalAnchor, EmpiricalCorpus
from lda_harness.verification_spec import VerificationSpec, run_verification

corpus = EmpiricalCorpus.load("lda/lda_harness/pdk_corpus.json")  # 或并入 seed
anchor = EmpiricalAnchor(corpus)
spec = VerificationSpec(
    name="PDK-NOEIC-DC-kappa",
    oracle_fn=lambda c: anchor.resolve("P-NOEIC-DC-KAPPA"),
    compare_fn=cmp_abs, tol=anchor.resolve("P-NOEIC-DC-KAPPA")[2],  # 取 uncertainty 作 tol
    source="pdk-noeic",
)
outcome = run_verification(spec, candidate={"kappa": lda_solver_value})
```

比对仍是标量 `|candidate - measured| ≤ tol`（D-04 统一语义），**LLM 永不进判决路径**。

---

## 3. 首个 PDK 验证课题（对齐 D-01）

**方向耦合器 / 对称 Y 分支分束器（D-01 已验证锚）作为首个 PDK 课题**：

- D-01 已用 FDFD 超模法（κ/Lc）+ 对称性定理（50/50）建立主权验收锚（3/3 PASS）；
- 拿到某厂 PDK 的耦合器 / 分束器元件模型后，注册为 `pdk-<fab>` golden；
- 跑 D-01 闭环（`CouplerAgent`），验证 LDA 主权求解器在该厂真实工艺参数下的精度；
- 产出「PDK 模型 vs LDA 仿真」公开基准（脱敏：只暴露误差，不暴露 PDK 保密几何）。

这是话术文档第五步「签 PDK 合作意向」前最关键的**技术可信度证据**——证明 LDA 不是
另一套 AI 意见，而是能在真实 PDK 下被实测检验的主权求解器。

---

## 4. 与 D-06 / D-10 语料工具的联动

| 场景 | 工具 | 命令示例 |
|---|---|---|
| 晶圆厂批量提供元件模型表 | D-06 `import_csv` | `python run_d06_smoke.py` 同款 API：`corpus.import_csv("pdk_noec.csv", contributor="noeic")` |
| 专家单条补登实测 | D-10 CLI | `python empirical_submit.py submit --id P-X --device ... --metric ... --out bank --bank pdk_corpus.json` |
| 校验 PDK 语料合法性 | D-10 `validate` | `python empirical_submit.py validate --bank pdk_corpus.json` |

所有 PDK 条目统一经 D-06 去重 + provenance 溯源，与种子 corpus 同源管理，
可被 D-04 统一契约当作 golden 来源之一。

---

## 5. 脱敏与合规边界

- **公开基准只暴露「模型 vs 仿真误差」**，不暴露 PDK 内部工艺细节（膜厚绝对值、掺杂等保密项）；
- PDK 文档样例由晶圆厂提供「脱敏版」，LDA 侧不主动抓取或反向工程 PDK IP；
- 接入过程产生的 adapter / corpus 中，`fab_source` 标注 PDK 版本，满足可追溯但不泄密；
- 所有接入走开源仓库 PR（话术第三步「PDK 验证层 PR 进仓库」），公开可审计。

---

## 6. 接入完成判据（第三步成功标志）

- [ ] PDK 文档样例已评估，层叠/规则/元件模型三类资产已映射；
- [ ] PDK adapter 定义完成，元件模型注册为 `pdk-<fab>` golden（D-04 VerificationSpec）；
- [ ] 跑通首个 PDK 课题（D-01 耦合器/分束器），产出公开基准；
- [ ] PDK 验证层 PR 进仓库（话术第三步交付标志）。

---

*本文件与《LDA_晶圆厂PDK对接首封话术与路线图.md》《LDA_D-08_认证版技术边界论证.md》
《LDA_统一验证契约VerificationSpec说明.md》《LDA_L0_IR_v0.2_增补说明.md》及 D-06/D-10 工具配套。
起草可在首封前完成（无需 PDK 在手）；正式接入待杜先生触达拿到脱敏 PDK 样例后执行。*
