# LDA · 统一验证契约 VerificationSpec（D-04）

> 文档编号：LDA-VER-001
> 版本：v1.0
> 编制日期：2026-08-20
> 对应任务：开发规划 D-04 三套裁判范式统一
> 密级：内部

---

## 0. 为什么需要统一契约

项目内有**四套裁判**各自运行、各自定义目标/容差/报告格式，对外协作时"验证是怎么做的"缺乏单一入口与单一语义：

| 裁判 | 目标描述 | ORACLE | 容差语义 | 报告 |
|---|---|---|---|---|
| harness（B1-B11） | spec dict | golden（physical-law） | abs | BenchmarkResult |
| waveguide_loop | WaveguideTarget | FDFD 本征 neff | abs | WaveguideOutcome |
| coupler_loop | CouplerTarget | FDFD 超模 κ / 对称性 | rel / balance | CouplerOutcome |
| solver_writer | SolverSpec+TestCase | tmm 解析 | max_abs_err | LoopReport |

D-04 定义**统一验证契约 VerificationSpec**，让四套共用同一套 ORACLE 接入、容差语义、报告格式，为外部协作（Issue/PR 提验证题）和 PDK 接入（D-09）铺路。

## 1. 契约定义（`lda/lda_harness/verification_spec.py`）

```python
@dataclass
class VerificationSpec:
    spec_id: str          # 唯一标识：B1 / WG-500x220 / DC-gap0.3 / YB-1x2 / SW-1D-FDTD-T
    metric: str           # 指标名：neff / kappa / transmission / power_frac / ...
    oracle_kind: str      # physical_law | fdfd_eigen | fdfd_supermode
                          # | symmetry_theorem | tmm_analytic
    oracle_fn: Callable   # oracle_fn(params) -> 真值（确定性物理锚）
    compare_fn: Callable  # compare_fn(candidate, oracle) -> err
    tol: float
    tol_mode: str         # 'abs' | 'rel' | 'abs_balance'
    target_desc: str      # 人类可读目标描述
    params: dict          # 目标几何/参数
    source: str           # 黄金参考事实来源
    candidate_desc: str   # 候选求解器描述
```

统一执行器 `run_verification(spec, candidate_fn)` → 统一结果 `VerificationOutcome`（PASS/FAIL + candidate/oracle/err/tol + `to_dict()` 统一 JSON 格式）。

**红线**：oracle_fn 全为确定性物理定律锚，LLM 不进判决路径；candidate_fn 独立实现。

## 2. 适配器（`lda/lda_harness/verification_adapters.py`）

四套裁判到契约的适配（**不重构四套内部实现**，只统一对外语义）：

| build_* | 覆盖 | 说明 |
|---|---|---|
| build_harness_specs | B1-B11 | golden_with_source → oracle；cmp_abs；参考候选=golden；另提供 harness_perturbed_candidate(rel) 演示 fail 检测 |
| build_waveguide_specs | 3 例 neff | fdfd_mode_field → oracle；FDTD 模态源 → candidate；cmp_abs（tol=0.15） |
| build_coupler_specs | DC×2 + YB×1 | 超模法 κ / 对称性 0.5 → oracle；超模投影递推 / 能流功率 → candidate；cmp_rel / cmp_abs_balance |
| build_solver_writer_specs | 1.4 闭环 | tmm 用例真值 → oracle；沙箱执行候选代码 → candidate；cmp_max_abs_err |

## 3. 统一回归入口（`lda/lda_harness/run_all_specs.py`）

```bash
# 全量（waveguide 纯 numpy 慢 ~15min）
python run_all_specs.py --json reports/unified_verification_report.json

# 跳慢项 / 只跑某组
python run_all_specs.py --skip waveguide
python run_all_specs.py --skip harness coupler solver_writer   # 只 waveguide

# 演示 fail 检测（harness 扰动候选，golden·1.1 → 预期 FAIL）
python run_all_specs.py --perturb 0.1 --skip waveguide coupler solver_writer
```

输出统一 JSON 报告 + 控制台摘要。**验收基线：harness 11/11 + waveguide 3/3 + coupler 3/3 + solver_writer 1/1 = 18/18 PASS。**

## 4. 本机实测（2026-08-20）

| 组 | 结果 | 备注 |
|---|---|---|
| harness B1-B11（参考候选） | 11/11 PASS | err=0（参考候选=golden） |
| solver_writer（v1 候选） | 1/1 PASS | max_abs_err=0.0326 ≤ 0.05 |
| coupler（DC×2 + YB） | 3/3 PASS | κ rel 1.4%/2.5%、YB 平衡度 0.0006（torch GPU） |
| waveguide（3 例 neff） | 3/3 PASS | FDTD vs FDFD，tol=0.15 |

> waveguide 组为纯 numpy 标量 3D FDTD（f=24），单例 ~5min，全组 ~15min；coupler 依赖 torch GPU（CI 无 GPU 时跳过）。

## 5. 后续

- D-09 PDK 接入规范可直接引用 VerificationSpec 作为"PDK 验证层接入"的统一接口。
- 外部贡献者经 Issue 提验证题时，可映射为一个 VerificationSpec（oracle/容差/来源）。
- 统一报告格式将用于 WebUI 验收页（D-07）渲染。

---

*与《LDA_阶段总结与下一步开发工作规划.md》D-04、《LDA_阶段性总结与剩余工作.md》配套。*
