# -*- coding: utf-8 -*-
"""BENCHMARK_DEFS 分片 6/6（F-08 拆分 · v0.9.209）。

覆盖 key：B469 … B472（共 4 条，Batch B-38 光子传感器新征程 PS-M8 衍生：几何灵敏度半 + Q 增强 LOD 缩放）。
分类（诚实）：**B469/B470/B471 = 严格独立**（`candidate` 指向 `_adapter_p4` 注册的 FV-FD 候选）；
**B472 = 自证桩**（无 `candidate` 键 —— 其原候选与 golden **代数恒等**，经反自证桩护栏实测判为自证桩，如实降级，见其 note）。

🔴 增锚必同登两处契约：`BENCHMARK_DEFS`（本片）+ `benchmarks.py::BENCHMARK_ORDER`（手工维护遍历序）。
🔴 三分类自动跟随：有 `candidate` 键（且函数在 `BENCHMARK_CANDIDATES` 登记）⇒ `_vmm_classify` 自动判 `strict_independent`；
   无 `candidate` 键 ⇒ `self_certified`。但四处硬编码数字陈述（README 当前账本 + 验证三分类、CONTRIBUTING 顶块、
   `run_webui_verification_ledger_smoke.py` docstring）须手动同步（见 Task #49）。
🔴 scipy 隔离：本片仅 `from .._batch_b38_numeric import ...` 顶层别名（模块顶层 scipy-free）；golden 函数体惰性 import scipy，
   闭式门禁（count_consistency / three_class）只导入本片结构、不执行 golden/cand。
"""
from .._batch_b38_numeric import (  # Batch B-38 光子传感器新征程 PS-M8 衍生（几何灵敏度半：薄线/狭缝/悬浮高灵敏几何 + Q 增强 LOD 缩放）
    golden_b469,
    golden_b470,
    golden_b471,
    golden_b472,
)
DEFS = {
    "B469": {
        "title": "薄线（thin-wire）波导折射率灵敏度 S=dn_eff/dn_a（一阶本征值微扰闭式 golden vs FV-FD 候选）",
        "metric": "geometry_refractive_index_sensitivity",
        "oracle": "closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w，非对称算子; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check",
        "tol": 5e-3,
        "default_params": {},
        "golden_fn": golden_b469,
        "candidate": "b469_thinwire_sensitivity_cand",
        "candidate_desc": "FV-FD 有限差分：perturb n_a ±δ → 重解 n_eff → 中心差商（δ=1e-4，避开双精度抵消地板，又不引入 O(δ²) 截断主导）；选模口径与 golden 严格一致（conf_min=0.0 + TE 主导 + 受限）",
        "note": "golden = 一阶本征值微扰（Rayleigh 商 + **左本征矢**）：`build_operator` 返回的算子**非对称**（‖A−Aᵀ‖/‖A‖≈18.6%，staggered 离散），一阶微扰必须用左本征矢 w（Aᵀ 在 γ0=(k0·n_eff)² 的右本征矢）⇒ dγ/dn_a=⟨w|δÂ|h⟩/⟨w|h⟩，δÂ 仅来自 analyte 区 ε 改变（δε=2·N_A·δ）；右本征矢 RQ 系统性错（strip 0.815 vs 真值 0.495）。S=dγ/dn_a/(2·k0²·n_eff)。candidate=FV-FD 重解后中心差商，方法学独立（golden=线性化微扰不重解，cand=重解差商）。实测默认档 |Δ|=8.714e-07（tol=5e-3 的 5734× 余量）；几何为 SOI 220nm @1550nm 设计示例（thinwire w=0.22 / h=0.22 / substrate，water n_a=1.33）。🔴 **同源体检（实 grep 全仓，如实登记不掩盖）**：`thin.wire|thinwire|窄条|几何灵敏度|geometry.*sensitivity` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **高灵敏几何族零锚占用（本族首锚）**；与 PS-M0~M7（B459~B468）被测标量完全不同 ⇒ **非重复计数**。⚠️ **诚实边界**：设计示例，结论只可用于数值方法与量级，不得作制造/性能宣称。零商业依赖（numpy + scipy 标准数值库）。",
    },
    "B470": {
        "title": "狭缝（slot）波导折射率灵敏度 S=dn_eff/dn_a（一阶本征值微扰闭式 golden vs FV-FD 候选）",
        "metric": "geometry_refractive_index_sensitivity",
        "oracle": "closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check",
        "tol": 5e-3,
        "default_params": {},
        "golden_fn": golden_b470,
        "candidate": "b470_slot_sensitivity_cand",
        "candidate_desc": "FV-FD 有限差分：perturb n_a ±δ → 重解 n_eff → 中心差商（δ=1e-4）；选模口径与 golden 严格一致（conf_min=0.0 + TE 主导 + 受限）",
        "note": "同 B469 口径（slot 几何：rail=0.22 / gap=0.05 / substrate，water 填缝）。golden=左本征矢 RQ 微扰，candidate=FV-FD 重解差商，方法学独立。实测默认档 |Δ|=3.962e-08（tol=5e-3 的 126200× 余量）。🔴 **诚实梯度（实测）**：SOI 220nm 下 substrate 受限的薄条/狭缝灵敏度 ≈ strip 基线或略低（strip≈0.495 / thinwire(0.22)≈0.447 / slot≈0.446）；唯一戏剧杠杆是**去衬底** suspended→1.171（2.4×）。判据梯度断言 = 「suspended ≫ strip ≈ thinwire ≈ slot」，**不要求 slot>thinwire>strip**（该梯度在物理上错）。🔴 **同源体检**：`slot|狭缝|slot.*waveguide` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **slot 族零锚占用**。⚠️ **诚实边界**：设计示例，不得作制造/性能宣称。零商业依赖。",
    },
    "B471": {
        "title": "悬浮（suspended）波导折射率灵敏度 S=dn_eff/dn_a（一阶本征值微扰闭式 golden vs FV-FD 候选 · 去衬底 2.4× 增强杠杆）",
        "metric": "geometry_refractive_index_sensitivity",
        "oracle": "closed_form(Rayleigh 商一阶本征值微扰 + 左本征矢 w; S=dγ/dn_a/(2 k0² n_eff)) + FV-FD 有限差分独立_cross_check",
        "tol": 5e-3,
        "default_params": {},
        "golden_fn": golden_b471,
        "candidate": "b471_suspended_sensitivity_cand",
        "candidate_desc": "FV-FD 有限差分：perturb n_a ±δ → 重解 n_eff → 中心差商（δ=1e-4）；suspended 时去掉 substrate（原 SiO2 区改 water）；选模口径与 golden 严格一致",
        "note": "同 B469 口径（suspended 几何：w=0.45 / h=0.22 / **无 substrate**，原 SiO2 区改 water）；去衬底 ⇒ analyte 包围度提高，灵敏度唯一大幅增强杠杆（2.4×）。golden=左本征矢 RQ 微扰，candidate=FV-FD 重解差商。实测默认档 |Δ|=1.291e-05（tol=5e-3 的 387× 余量）。🔴 **同源体检**：`suspended|悬浮` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **suspended 族零锚占用**。⚠️ **诚实边界**：设计示例，不得作制造/性能宣称。零商业依赖。",
    },
    "B472": {
        "title": "Q 增强 LOD 缩放闭式（LOD_real(Q)=√((LOD_elec_ref·Q0/Q)²+LOD_temp_ref²) · 自证桩 · 电学受限区间）",
        "metric": "q_scaling_lod",
        "oracle": "closed_form(LOD_real(Q)=√((LOD_elec_ref·Q0/Q)² + LOD_temp_ref²), Q↑⇒LOD↓∝1/Q) · 自证桩（无方法学独立候选）",
        "tol": 1e-9,
        "default_params": {},
        "golden_fn": golden_b472,
        "note": "🔴 **本锚为「自证桩」（VMM Tier-1 · 诚实降级，v0.9.209 定谳）**：原设计曾登记 candidate=`b472_q_scaling_lod_cand`（PS-M2 `lod_real(Q)` 逐分量合成）并自称为「方法学独立」，但经 `run_benchmark_falsifiability_smoke`（反自证桩护栏）实测**判定为自证桩**——该候选与 golden **代数恒等**：`resonance_slope_max=depth·(3√3/4)/FWHM`、`FWHM=λ/Q` ⇒ slope 严格 ∝Q ⇒ `lod_elec` 严格 ∝1/Q ⇒ golden 的缩放闭式**精确重现** `lod_real(Q)`，实测 |Δ|=0.0（**精确 0，非 1e-16**，代数恒等的签名）。属 **B28 同型「同式异写 ⇒ 虚报」**（判据 D 亦判其无离散参数、非真数值方法）。故**如实撤下 candidate 登记**、降为自证桩（保留锚位 + 升级路径），不越级谎报。golden 本身=由 PS-M2 模型导出的闭式：FWHM=λ/Q ⇒ 边缘斜率 ∝Q ⇒ LOD_elec ∝1/Q；LOD_temp 与 Q **解耦**（热漂由温控决定）⇒ LOD_real(Q)=√((LOD_elec_ref·Q0/Q)² + LOD_temp_ref²)，ref=Q0=1e4 处模型实算值。🔴 **诚实纪律（测试区间）**：默认噪声（5 mK / 无 referencing / CMR=1）下 LOD_temp≈9.3e-7 ≫ LOD_elec≈1.8e-10 ⇒ LOD_real 被热漂地板主导、**与 Q 无关**（缩放退化、单调性失效），故**不作锚测试区间**；锚默认噪声取 B472_NOISE（CMR=1e4 压低热漂到 LOD_temp≈9.3e-11），Q 缩放清晰可见且单调。物理洞察：Q 增强 LOD **仅当**热漂被 referencing 抑制才成立（真实传感器多热漂受限），此洞察本身就是 B472 要交付的诚实结论。🔴 **同源体检**：`Q.*增强|Q.*scaling|LOD.*Q` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **Q-scaling 族零锚占用**。**升级路径**：接独立 ORACLE（外部 Q-LOD 实测数据集 / 独立光-热耦合全波求解器）后升 Tier-3。⚠️ **诚实边界**：噪声为设计示例，结论只可用于数值方法与量级，不得作性能宣称。零商业依赖（纯 numpy，lod_real 无 scipy）。",
    },
}
