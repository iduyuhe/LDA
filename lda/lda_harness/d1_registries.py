# -*- coding: utf-8 -*-
"""蓝图 v2 · **D1 光-量异质集成** —— 里程碑裁决与「不可锚」登记（**非门禁模块**）。

🔴 为什么单独放这里（与 `bl_registries.py` 同一条纪律）
------------------------------------------------------------
K4 的 L2 覆盖是「文本 ∪ manifest」。若把锚号字面量写进**门禁源码**，K4 的文本
代理就会把「评论里提了一句」算成「有专属判据」⇒ L2 虚增、盲区虚假缩水。故：
- **锚号只出现在本模块**（非 CORE 门禁，不被 K4 扫描）；
- 门禁 `run_v2d1_smoke.py` 只 `import` 并写「见 `D1_M1_ADJUDICATION`」。

本模块同时承担「**负结果机器化**」：判「不可锚」不是写一段话就完事，而是把
**哨兵指标名**登记下来，让门禁去扫 `BENCHMARK_DEFS`；日后有人把同一个物理量
换个名字重新立锚，CI 必红。
"""

# ── M1 裁决：**不立新锚**（v0.9.259 同源体检实测） ──────────────────────────
#
# 章程原定 M1 两条：
#   ① `interface_fresnel_loss(n1, n2, theta)`  —— Fresnel 反射损耗
#   ② `interface_absorption_loss(alpha_db_cm, length_um)` —— Beer–Lambert 吸收
#
# 同源体检（全账本 539 锚现扫）结论：**两条均已被既有锚 100% 覆盖，且连候选
# 方法都对得上** ⇒ 再立即「参数化扩展」，属重复计数（R1 红线）。
D1_M1_ADJUDICATION = {
    "milestone": "M1",
    "title": "异质界面损耗（Fresnel 反射 + 界面吸收）",
    "verdict": "NOT_ANCHORABLE",
    "verdict_zh": "不立新锚（复用既有覆盖锚）",
    "as_chartered": [
        "interface_fresnel_loss(n1, n2, theta)",
        "interface_absorption_loss(alpha_db_cm, length_um)",
    ],
    # 🔴 覆盖锚：只在此处出现锚号
    "covering_anchors": {
        "B413": {
            "metric": "normal_incidence_reflectance",
            "role": "垂直入射反射率 R0=((n1−n2)/(n1+n2))² · golden 闭式",
            "candidate_method": "1D FD Helmholtz 总场解",
            # 🔴 断言用「golden 的**解析闭式形态**」而非名称：该条 oracle 文本里没有
            #   「Fresnel」字样（名字在 title 里），写成名称会假红（首轮实测）。
            "oracle_must_contain": "analytical(R0=",
            "candidate_must_contain": "FD Helmholtz",
        },
        "B493": {
            "metric": "qs_pump_transmission",
            "role": "Beer–Lambert 透过率 T(L)=T₀·exp(−n·σ_abs·L) · golden 闭式指数",
            "candidate_method": "RK4 空间推进",
            "oracle_must_contain": "Beer",
            "candidate_must_contain": "RK4",
        },
    },
    # 理由须 ≥3 条、每条 ≥12 字（门禁 H3 逐条现算）
    "reasons": [
        "被测标量与既有覆盖锚完全同一（反射率 R0 / 透过率 T(L)），再立即同一物理量重复计数。",
        "golden 闭式（Fresnel 反射系数 / Beer–Lambert 指数）与既有覆盖锚逐项相同，独立性不成立。",
        "候选方法学亦相同（1D FD Helmholtz 总场解 / RK4 空间推进），连「不同源」这一条也站不住。",
        "同族 Fresnel 已有 13 条（R0/Rs/Rp/Ts/Tp/Runpol/ΔR/TsTp/θB/|t_s|/TIR/β/能量守恒）⇒ 族内已饱和。",
    ],
    # 🔴 哨兵：日后偷登记这些指标名 ⇒ 门禁 H2 必红
    "sentinel_metrics": [
        "fresnel_interface_loss",
        "interface_fresnel_loss",
        "interface_absorption_loss",
        "hetero_interface_loss",
        "interface_loss_db",
    ],
}


def d1_covering_anchor_ids():
    """覆盖锚号（升序）—— 供门禁动态取用，避免门禁源码出现锚号字面量。"""
    return sorted(D1_M1_ADJUDICATION["covering_anchors"])


def d1_m1_sentinel_metrics():
    """M1「不可锚」哨兵指标名。"""
    return list(D1_M1_ADJUDICATION["sentinel_metrics"])


# ── M2 裁决：**不立新锚**（v0.9.261 可锚性数值体检实测） ──────────────────
#
# 章程原定 M2：`fiber_array_offset_tolerance(w1, w2, eta_budget)` ·
#              `angular_misalignment_loss(w, theta, lam)`（封装级阵列对准容差/良率）
#
# 体检结论：**良率是既有单通道耦合律的「统计包装」，不是新物理面**；
# 且两条候选路线各有一处硬伤（见 `empirical` 实测数字）。
D1_M2_ADJUDICATION = {
    "milestone": "M2",
    "title": "封装级光耦合（光纤阵列对准容差：横向偏移 / 角度失配）",
    "verdict": "NOT_ANCHORABLE",
    "verdict_zh": "不立新锚（既有耦合律的统计包装 · 派生量）",
    "as_chartered": [
        "fiber_array_offset_tolerance(w1, w2, eta_budget)",
        "angular_misalignment_loss(w, theta, lam)",
    ],
    "reasons": [
        "良率 Y=P(η(d)≥η_min) 只是既有单通道耦合律 η(d)=exp(−d²/2w²) 的统计重写："
        "η≥η_min ⟺ |d|≤d_max ⇒ 不引入任何新物理量，属派生量而非新物理面。",
        "其闭式 Y=erf(d_max/(√2σ)) 与 M0 的 γ̄ 同属 erf 族；若候选取「限窗复合 Simpson」，"
        "则数值格式也与 M0 同族 ⇒ 三处比对中两处同族，只剩「被测标量是概率」一条分歧。",
        "MC 候选实测（8 个固定种子取最坏）N=1e5 误差 1.6e-3、N=1e6 仍 3.7e-4（相对 4e-4），"
        "达不到「残差 ≤ tol/100」的判据口径所需余量，且统计误差跨种子不可复现。",
        "角度失配已被 part5 的 note 明确记为「复振荡被积函数 ⇒ 谱精度 ⇒ 假独立」⇒ 章程不再重复尝试。",
    ],
    # 🔴 实测证据（机器可读 · 门禁 K3 只断言「在册且 ≥2 条」，不复算）
    "empirical": {
        "yield_closed_form": "Y = erf(d_max/(√2σ))，d_max = w·sqrt(2·ln(1/η_min))",
        "design_point": {"w_um": 5.0, "sigma_um": 2.0, "eta_min_db": -1.0, "Y": 0.910215412391},
        "mc_worst_of_8_seeds": {"N_1e5": 1.615e-03, "N_1e6": 3.736e-04},
        "density_simpson_chain": {"n256_resid": 6.695e-12, "ratios": "12.75/15.25/15.82/15.96/16.02"},
        "conclusion": "MC 余量不足 + 跨种子不可复现；Simpson 与 M0「数值格式 + 特殊函数」双重同族。",
    },
    "sentinel_metrics": [
        "fiber_array_offset_tolerance",
        "angular_misalignment_loss",
        "array_alignment_yield",
        "packaging_coupling_yield",
    ],
}


def d1_m2_sentinel_metrics():
    """M2「不可锚」哨兵指标名。"""
    return list(D1_M2_ADJUDICATION["sentinel_metrics"])


def d1_m2_selfcheck():
    """M2 裁决面自检（纯结构 · 不读账本）。"""
    a = D1_M2_ADJUDICATION
    ch = {}
    ch["verdict_is_not_anchorable"] = a.get("verdict") == "NOT_ANCHORABLE"
    ch["reasons_at_least_4"] = len(a.get("reasons") or []) >= 4
    ch["reasons_each_long_enough"] = all(len(r.strip()) >= 12 for r in a.get("reasons") or [])
    ch["sentinels_at_least_4"] = len(a.get("sentinel_metrics") or []) >= 4
    emp = a.get("empirical") or {}
    # 证据面：闭式 / 设计点 / MC / Simpson 四条在册
    ch["evidence_has_closed_form"] = bool(emp.get("yield_closed_form"))
    ch["evidence_has_design_point"] = bool(emp.get("design_point"))
    ch["evidence_has_mc"] = len(emp.get("mc_worst_of_8_seeds") or {}) >= 2
    ch["evidence_has_simpson"] = bool(emp.get("density_simpson_chain"))
    ch["as_chartered_recorded"] = len(a.get("as_chartered") or []) >= 2
    return ch


def d1_selfcheck():
    """登记面自检（纯结构，不读账本）⇒ 返回 {检查名: bool}。"""
    a = D1_M1_ADJUDICATION
    ch = {}
    ch["verdict_is_not_anchorable"] = a.get("verdict") == "NOT_ANCHORABLE"
    ch["reasons_at_least_3"] = len(a.get("reasons") or []) >= 3
    ch["reasons_each_long_enough"] = all(len(r.strip()) >= 12 for r in a.get("reasons") or [])
    ch["covering_anchors_at_least_2"] = len(a.get("covering_anchors") or {}) >= 2
    ch["covering_have_method_spec"] = all(
        all(k in v for k in ("metric", "candidate_method",
                             "oracle_must_contain", "candidate_must_contain"))
        for v in (a.get("covering_anchors") or {}).values())
    ch["sentinels_non_empty"] = len(a.get("sentinel_metrics") or []) >= 3
    ch["as_chartered_recorded"] = len(a.get("as_chartered") or []) >= 2
    return ch
