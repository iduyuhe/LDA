"""ADC 能耗四项物理预算 + **可校核性分析**（E26 · D-201）。

## 本模块要回答的问题

E25 的结论是「CDAC 只占 ADC 总能耗 0.6~3.6%」，因此**用实测 FOM 锚顶替 CDAC 模型**得到
可信地板 33.7 fJ/op。E25 结尾我建议「把比较器 / 参考缓冲 / 数字逻辑建成可计算模型，
模型 ⟷ 实测误差 <20% 才算可信」。

🔴 **本模块实测后发现：那条建议的前提不成立。**

## 核心发现（三条，全部可机核）

### ① 四项物理模型只能解释实测能耗的 18%~89%，且跨设计差 5 倍

用**公开一手工艺参数**（V_DD / C_ox / 比较器再生时间）+ **公开电路假设**（锁存负载 /
预放大电流 / 时钟网络电容 / 门数），正算四项：

| 实测锚 | E_conv（实测） | CDAC | 比较器 | 时钟 | 逻辑 | 合计 | **覆盖率** |
|---|---|---|---|---|---|---|---|
| 28nm 8b 500MS/s | 4300.8 fJ | 20.7 | 137.1 | 405.0 | 218.7 | 781.5 | **18.2%** |
| 40nm 12b 1MS/s | 8478.7 fJ | 371.6 | 408.9 | 605.0 | 471.9 | 1857.4 | **21.9%** |
| 65nm 8b 1MS/s | 1909.7 fJ | 91.8 | 499.3 | 720.0 | 388.8 | 1699.9 | **89.0%** |

⇒ 覆盖率从 18% 到 89%（**4.9×**）。**这不是"模型精度"问题，是"模型没有跨设计的一致性"。**

### ② 单一设计参数集无法同时解释三个锚 —— 且偏离**不是均匀的**

把电路假设整体乘一个尺度 `s`（代表"设计者的偏置/占空比策略"），要复现实测就需要：

```
s_i = (E_conv_i − E_cdac_i) / E_rest_i
    = 5.63 (28nm 8b 500MS/s) / 5.46 (40nm 12b 1MS/s) / 1.13 (65nm 8b 1MS/s)
```

🔴 **28nm 与 40nm 的 `s` 只差 3.1%（5.63 vs 5.46）—— 两个"常规设计"锚的策略尺度几乎一致；
而 65nm 超低功耗锚（1.9 µW）偏离 4.98×**。

⇒ 两个结论必须分开说：
1. **常规档有一个约 5.5× 的系统性缺口**（可标定），**这个缺口就是那 80% 不可建模的设计策略**；
2. **超低功耗档不能用同一标定**（`s` 小 5×，因为它用亚阈值/低偏置把能耗压到 µW 级）。

⇒ 离散度 **4.98×** ⇒ **模型仍是不可标定的**（任何标定都必须引用锚本身 = 循环自证），
但"高速档可用单一 scale≈5.5 描述"这一点是可用信息。

🔴 更深一层：`C_clk_net` **本身依赖目标 f_s**（高速需要多级缓冲/大扇出），
所以它不是常数 ⇒ **模型的可标定性问题不来自"参数没调好"，来自"参数是 f_s 的函数"**。

### ③ 因此「从头算」路线上限已封顶，必须走「实测标定 + 区间」

本模块给出**区间地板**（三个锚各算一遍），而不是 E25 的单点：

| 锚 | E_op = E_conv/(2nK) |
|---|---|
| 65nm 8b 1MS/s | **14.9 fJ/op** |
| 28nm 8b 500MS/s | **33.6 fJ/op** |
| 40nm 12b 1MS/s | **66.2 fJ/op** |

⇒ 区间 **14.9 ~ 66.2 fJ/op（4.4×）** ⇒ 对 Mythic 8.3 fJ/op 的差距是 **1.8× ~ 8.0×**
（E25 报的单点 4.1× 落在区间内，但**单点报法本身不成立**）。

## 可校核性（自由度分析）

| 项 | 数 |
|---|---|
| 待定参数（架构相关，不可从物理量独立确定） | **4**（C_latch、I_preamp、C_clk_net、n_gate 等效） |
| 独立实测约束（锚） | **3** |
| 其中同工艺锚对（可交叉验证的前提） | **0** |
| ⇒ 校核自由度 | **3 − 4 − (工艺缩放参数 2) = −3** |

🔴 **`dof < 0` ⇒ 任何「模型与实测误差 <20%」都只能靠反解参数再正算 = 循环自证。**
本模块**不宣称任何精度**，只给区间与离散度。

## 判据纪律（本模块自己踩过的坑）

- `t_cmp` **不能**取 `T_conv/(2b)`：低速锚（1 MS/s · 12b）会得到 41.7 µs 的通电时间
  ⇒ 预放大项被算成 27.6 pJ，覆盖率 343%（见开发过程）⇒ 必须先查物理上限。
  正解 = **工艺再生时间**（28nm 200ps / 40nm 400ps / 65nm 800ps），与 f_s 无关。
- 覆盖率 **>100% 必须判红**（参数集过度 ⇒ 模型不可用），不是"越高越好"。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import adc_arch as A
from lda_l2.ecore import adc_calibration as C
from lda_l2.ecore import energy as E
from lda_l2.ecore import timing as T

# ---------------------------------------------------------------------------
# ① 工艺一手参数（**公开典型值 · 占位 · 非 PDK**）
# ---------------------------------------------------------------------------
PROCESS_NODES: List[Dict] = [
    {"id": "28nm", "vdd_v": 0.9, "cox_ff_per_um2": 21.6, "eot_nm": 1.6,
     "t_regen_s": 200e-12, "i_leak_na_per_um": 0.5,
     "basis": "28nm CMOS LPP 公开典型值（EOT 1.6nm ⇒ C_ox 21.6 fF/µm²）"},
    {"id": "40nm", "vdd_v": 1.1, "cox_ff_per_um2": 17.5, "eot_nm": 2.0,
     "t_regen_s": 400e-12, "i_leak_na_per_um": 1.0,
     "basis": "40nm 公开典型值（EOT 2.0nm）"},
    {"id": "65nm", "vdd_v": 1.2, "cox_ff_per_um2": 13.5, "eot_nm": 2.6,
     "t_regen_s": 800e-12, "i_leak_na_per_um": 2.0,
     "basis": "65nm 公开典型值（EOT 2.6nm）"},
]

#: 电路级假设（**架构相关 · 无法从工艺参数推出** · 占位）
CIRCUIT_ASSUMPTIONS: Dict[str, float] = {
    "c_latch_fF": 10.0,          # 比较器锁存器输出+耦合等效电容
    "i_preamp_a": 50.0e-6,       # 预放大/尾电流
    "c_clk_net_f": 500.0e-15,    # 时钟网络等效电容（含去偏斜缓冲）
    "n_gate_equiv": 300.0,       # SAR 控制逻辑等效门数
    "c_gate_fF": 0.5,            # 每门等效电容
    "alpha_act": 0.2,            # 逻辑活动因子（比 E21 的 0.5 保守）
}

#: **未解释项**候选（凡 `modelable=False` ⇒ 不可从公开一手参数算出）
UNEXPLAINED_SOURCES: List[Dict] = [
    {"name": "参考缓冲静态偏置（维持低输出阻抗）", "modelable": False,
     "why": "由「允许的 V_ref 纹波 / 建立时间」反解，是设计目标不是物理量"},
    {"name": "时钟树去偏斜 + 扇出缓冲", "modelable": False,
     "why": "实际扇出与缓冲级数由版图和时序收敛决定，无公开参数"},
    {"name": "前台/背景校准数字电路", "modelable": False,
     "why": "算法与位宽是设计选择（0.3 fF 单位电容必须配校准）"},
    {"name": "自降压 / 亚阈值偏置", "modelable": False,
     "why": "低速锚（1 MS/s）常用亚阈值把功耗压到 µW 级，电压不在规格里"},
    {"name": "异步控制与占空比化", "modelable": False,
     "why": "偏置通电占空比是设计策略 ⇒ 同一器件不同 f_s 能量不可简单缩放"},
    {"name": "版图寄生（走线/过孔/衬底）", "modelable": False,
     "why": "需实际版图提取"},
    {"name": "CDAC 开关能量", "modelable": True,
     "why": "闭式可算（E24 精确单位 × C0 × V²）—— 但它只占 0.6~4.8%"},
    {"name": "比较器锁存动态能量", "modelable": True,
     "why": "C_out·V²·b，但 C_out 本身是架构量 ⇒ 半可算"},
]


def _node(node_substr: str) -> Dict:
    for p in PROCESS_NODES:
        if p["id"] in node_substr:
            return p
    raise KeyError("未登记的工艺节点：" + node_substr)


# ---------------------------------------------------------------------------
# ② 四项预算
# ---------------------------------------------------------------------------
def budget_terms(anchor_id: str = "a28_8b", scale: float = 1.0,
                 arch: str = "sar_monotonic",
                 assumptions: Optional[Dict[str, float]] = None) -> Dict:
    """把一次转换的能耗拆成四项（+ 未解释残差）。

    `scale` 是**电路假设的整体尺度因子**（代表"设计者的偏置/占空比策略"）。
    `scale=1` 用本模块的占位假设；该参数的存在本身就是"模型不可标定"的证据。

    四项闭式：
      · `E_cdac = E_units(b, arch) · C0 · V²`（精确 · 见 E24 `cdac_cap_units`）
      · `E_cmp  = b · (C_latch·V² + I_pre·V·t_regen)`
      · `E_clk  = C_clk_net·V²`
      · `E_log  = α·n_gate·C_gate·(b+1)·V²`
    """
    a = {x["id"]: x for x in C.MEASURED_ADC_ANCHORS}[anchor_id]
    pr = _node(a["node"])
    asm = dict(CIRCUIT_ASSUMPTIONS)
    if assumptions:
        asm.update(assumptions)
    v = pr["vdd_v"]
    b = int(a["bits"])
    s = float(scale)

    u = A.cdac_cap_units(b, arch)
    e_cdac = u["energy_units_C0V2"] * a["c_unit_fF"] * 1e-15 * v * v

    e_cmp = b * (asm["c_latch_fF"] * 1e-15 * v * v
                 + asm["i_preamp_a"] * v * pr["t_regen_s"])
    e_clk = asm["c_clk_net_f"] * v * v
    e_log = (asm["alpha_act"] * asm["n_gate_equiv"] * asm["c_gate_fF"] * 1e-15
             * (b + 1) * v * v)

    e_expl = e_cdac + s * (e_cmp + e_clk + e_log)
    e_meas = a["fom_fj_per_cs"] * 1e-15 * (2.0 ** a["enob"])
    return {
        "anchor": anchor_id, "node": pr["id"], "bits": b, "arch": arch,
        "vdd_v": v, "c_unit_fF": a["c_unit_fF"], "scale": s,
        "t_regen_s": pr["t_regen_s"],
        "e_cdac_fj": e_cdac * 1e15,
        "e_cmp_fj": s * e_cmp * 1e15,
        "e_clk_fj": s * e_clk * 1e15,
        "e_log_fj": s * e_log * 1e15,
        "e_explained_fj": e_expl * 1e15,
        "e_measured_fj": e_meas * 1e15,
        "coverage": e_expl / e_meas,
        "tier": E.OUTPUT_TIER,
    }


def coverage_vs_measured(anchor_id: str = "a28_8b", scale: float = 1.0) -> Dict:
    """覆盖率 = 四项正算 ÷ 实测 `FOM·2^ENOB`。

    🔴 **覆盖率不是"越高越好"**：>100% 说明参数集过度（模型把能耗算爆了）。
    """
    t = budget_terms(anchor_id, scale)
    c = t["coverage"]
    if c > 1.0:
        verdict = ("🔴 **覆盖率 %.1f%% > 100%% ⇒ 参数集过度，模型不可用**"
                   "（本模块开发时 `t_cmp=T_conv/(2b)` 曾使覆盖率 343%%~1640%%）" % (c * 100))
    elif c < 0.05:
        verdict = "🔴 覆盖率仅 %.2f%% ⇒ 四项物理模型几乎未触及能耗主体" % (c * 100)
    else:
        verdict = "覆盖率 %.1f%% ⇒ 剩余 %.1f%% 属设计策略（见 UNEXPLAINED_SOURCES）" % (
            c * 100, (1 - c) * 100)
    return {**t, "verdict": verdict}


def coverage_table(scale: float = 1.0) -> List[Dict]:
    return [coverage_vs_measured(a["id"], scale) for a in C.MEASURED_ADC_ANCHORS]


def coverage_spread(scale: float = 1.0) -> Dict:
    """**跨设计一致性**：覆盖率的最大/最小比。

    🔴 判据不是"spread 小"，而是**如实报出它**：spread ≫1 ⇒ 模型无跨设计预测力。
    """
    rows = coverage_table(scale)
    cov = [r["coverage"] for r in rows]
    lo, hi = min(cov), max(cov)
    return {"scale": float(scale), "coverages": cov,
            "min": lo, "max": hi, "spread": (hi / lo if lo > 0 else float("inf")),
            "verdict": ("🔴 覆盖率 %.1f%%~%.1f%% · **离散度 %.1f×** ⇒ "
                        "四项物理模型**无跨设计一致性**，不能作预测工具"
                        % (lo * 100, hi * 100, hi / lo if lo > 0 else float("inf"))),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ③ 可标定性：每个锚各自需要的电路尺度 s_i
# ---------------------------------------------------------------------------
def required_scale(anchor_id: str) -> Dict:
    """要复现实测，该锚需要的电路假设尺度因子。

    `s_i = (E_conv − E_cdac) / E_rest`（代数解，**精确**）。

    🔴 若三个锚的 `s_i` 离散 ⇒ **不存在单一设计参数集**能同时解释它们。
    """
    t = budget_terms(anchor_id, scale=1.0)
    e_rest = t["e_cmp_fj"] + t["e_clk_fj"] + t["e_log_fj"]
    if e_rest <= 0:
        return {"anchor": anchor_id, "s_required": None,
                "solvable": False, "tier": E.OUTPUT_TIER}
    s = (t["e_measured_fj"] - t["e_cdac_fj"]) / e_rest
    # 代回验证（金标：必须精确复现 E_conv）
    back = t["e_cdac_fj"] + s * e_rest
    return {"anchor": anchor_id, "node": t["node"], "bits": t["bits"],
            "e_measured_fj": t["e_measured_fj"], "e_cdac_fj": t["e_cdac_fj"],
            "e_rest_fj": e_rest, "s_required": s,
            "roundtrip_rel_err": abs(back - t["e_measured_fj"]) / t["e_measured_fj"],
            "solvable": True, "tier": E.OUTPUT_TIER}


def scalability_analysis() -> Dict:
    """**本模块最重要的一条**：单参数集可标定性。

    `spread(s_i) = max/min`。若 ≫1 ⇒ 模型结构不可标定（不是"参数没调好"）。

    额外报**组内一致性**（最大两个 `s` 之比）与**离群比**（次小 ÷ 最小）。
    🔴 若组内一致性很好而离群比很大，说明"偏离不是噪声，是**设计策略不同**"——
    这是比"完全不可标定"更精确、也更有用的判断。
    """
    rows = [required_scale(a["id"]) for a in C.MEASURED_ADC_ANCHORS]
    pairs = sorted([(r["s_required"], r["anchor"], r["node"])
                    for r in rows if r["s_required"]], key=lambda t: t[0])
    if len(pairs) != 3:
        return {"rows": rows, "s_values": [p[0] for p in pairs], "spread": None,
                "inner_consistency": None, "outlier_ratio": None,
                "outlier_anchors": [], "calibratable": False,
                "verdict": "🔴 无法完成可标定性分析", "tier": E.OUTPUT_TIER}
    (s_lo, a_lo, n_lo), (s_mid, a_mid, n_mid), (s_hi, a_hi, n_hi) = pairs
    spread = s_hi / s_lo
    inner = s_hi / s_mid           # 常规两档之间
    out_ratio = s_mid / s_lo       # 低速离群档的偏离倍数
    return {"rows": rows, "s_values": [s_lo, s_mid, s_hi],
            "spread": spread, "inner_consistency": inner,
            "outlier_ratio": out_ratio,
            "lowest_anchor": a_lo, "outlier_anchors": [a_lo],
            "regular_pair": [a_mid, a_hi],
            "calibratable": bool(spread < 1.2),
            "verdict": ("🔴 三个锚要求的电路尺度 = **%.2f (%s) / %.2f (%s) / %.2f (%s)**，"
                        "离散 **%.2f×**。其中 **%s 与 %s 只差 %.1f%%**"
                        "（常规档存在约 **%.2f×** 的系统性缺口，**该缺口就是那 80%% 不可建模的设计策略**，"
                        "技术上可用单一 scale 描述），而 **%s 偏离 %.2f×**"
                        "（超低功耗档用亚阈值/低偏置，**不能共用该标定**）⇒ "
                        "**模型整体仍不可标定**：任何标定都必须引用锚本身 = 循环自证"
                        % (s_lo, n_lo, s_mid, n_mid, s_hi, n_hi, spread,
                           a_mid, a_hi, abs(inner - 1) * 100, s_mid,
                           a_lo, out_ratio)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ 可校核性（自由度分析）
# ---------------------------------------------------------------------------
def dof_analysis() -> Dict:
    """`dof = m(独立实测约束) − k(待定参数) − q(工艺缩放参数)`。

    🔴 `dof <= 0` ⇒ 任何"误差 <20%"都只能靠反解再正算 = **循环自证**。
    """
    k_free = 4      # C_latch、I_preamp、C_clk_net、n_gate 等效
    m_anchor = len(C.MEASURED_ADC_ANCHORS)   # 3
    # 三个锚分属三个工艺 ⇒ 要跨工艺共用一套参数，必须引入工艺缩放律
    nodes = {r["node"] for r in coverage_table()}
    q_scaling = 2 if len(nodes) > 1 else 0    # 至少 C_ox 与 t_regen 的缩放指数
    same_node_pairs = 0                       # 同工艺多配置锚数（当前 0）
    dof = m_anchor - k_free - q_scaling
    return {"free_params": k_free, "anchors": m_anchor, "distinct_nodes": len(nodes),
            "scaling_params": q_scaling, "same_node_pairs": same_node_pairs,
            "dof": dof,
            "certifiable": bool(dof > 0 and same_node_pairs >= 1),
            "verdict": ("🔴 **dof = %d − %d − %d = %d ⇒ 不可校核**。"
                        "三个锚分属 %d 个工艺、且**无同工艺锚对** ⇒ "
                        "任何「模型 ⟷ 实测 误差 <20%%」都只能靠反解参数再正算 = **循环自证**。"
                        "要可校核，最低需要**同工艺 ≥ k+1 = %d 个不同配置的实测锚**"
                        % (m_anchor, k_free, q_scaling, dof, len(nodes), k_free + 1)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑤ f_s 依赖（结构性预言，不依赖拟合参数）
# ---------------------------------------------------------------------------
def fs_dependence(bits: int = 8, arch: str = "sar_monotonic",
                  c_unit_fF: float = 0.4, vdd_v: float = 0.9,
                  p_static_w: float = 50e-6 * 0.9,
                  f_list: Optional[List[float]] = None) -> Dict:
    """**`E_conv(f_s) = E_dyn + P_static/f_s`** —— 一条可被实测证伪的结构性预言。

    · `f_s → ∞` ⇒ `E_conv → E_dyn`（FOM 趋近动态地板）
    · `f_s → 0`  ⇒ 静态项主导，FOM 变差
    ⇒ **FOM 存在最优点**（这正是"用 500 MS/s 的锚代替 10.85 MHz 工作点"的口径风险）。

    🔴 诚实边界：真实设计在低速时会**降偏置/占空比化**，不会保持 `P_static` 不变
    ⇒ 本条是"同偏置假设下"的预言，**不能直接当预测**。
    """
    if f_list is None:
        f_list = [1e5, 1e6, 1e7, T.sar_stage_time(bits=bits)["t_s"] ** -1,
                  1e8, 5e8, 1e9]
    u = A.cdac_cap_units(int(bits), arch)
    e_dyn = u["energy_units_C0V2"] * c_unit_fF * 1e-15 * vdd_v ** 2
    rows = []
    for f in f_list:
        e_tot = e_dyn + p_static_w / float(f)
        rows.append({"f_s_hz": float(f), "e_dyn_j": e_dyn, "e_static_j": p_static_w / float(f),
                     "e_conv_j": e_tot, "fom_fj_per_cs": e_tot / (2.0 ** int(bits)) * 1e15,
                     "static_share": (p_static_w / float(f)) / e_tot})
    return {"bits": int(bits), "e_dyn_j": e_dyn, "p_static_w": p_static_w,
            "f_platform_hz": 1.0 / T.sar_stage_time(bits=bits)["t_s"],
            "rows": rows,
            "law": "E_conv = E_dyn + P_static/f_s ⇒ FOM 有最优点，低速端被静态项抬高",
            "caveat": "🔴 同偏置假设；真实设计低速时降偏置 ⇒ 不可直接当预测",
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑥ 区间地板（替代 E25 的单点）
# ---------------------------------------------------------------------------
def floor_interval(n: int = 64, share_k: int = 1,
                   anchors: Optional[List[str]] = None) -> Dict:
    """**用全部实测锚各算一遍，报区间**（E25 只报了 28nm 单点 33.7 fJ/op）。

    `E_op = E_conv/(2·n·K)`（每列一个 ADC ⇒ 每转换 n/K 个 ADC）。
    """
    ids = anchors or [a["id"] for a in C.MEASURED_ADC_ANCHORS]
    rows = []
    for aid in ids:
        r = C.adc_energy_per_op_from_anchor(aid, n, share_k)
        rows.append({"anchor": aid, "node": r["node"],
                     "e_op_fj": r["adc_energy_per_op_fj"]})
    vals = [r["e_op_fj"] for r in rows]
    lo, hi = min(vals), max(vals)
    mythic = 8.3
    return {"n": int(n), "share_k": int(share_k), "rows": rows,
            "interval_fj": (lo, hi), "spread": hi / lo,
            "gap_vs_mythic": (lo / mythic, hi / mythic),
            "single_point_e25_fj": C.floor_with_measured_adc("a28_8b", n)["e_floor_fj_per_op"],
            "verdict": ("区间 **%.1f ~ %.1f fJ/op（%.1f×）** ⇒ 对 Mythic %.1f 的差距 "
                        "**%.1f× ~ %.1f×**（E25 单点 %.1f fJ/op ⇒ %.1f× 落在区间内，"
                        "但**单点报法本身不成立**：锚分属不同工艺/设计策略）"
                        % (lo, hi, hi / lo, mythic, lo / mythic, hi / mythic,
                           C.floor_with_measured_adc("a28_8b", n)["e_floor_fj_per_op"],
                           C.floor_with_measured_adc("a28_8b", n)["e_floor_fj_per_op"] / mythic)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑦ 自检
# ---------------------------------------------------------------------------
def adc_budget_self_check(verbose: bool = False) -> bool:
    checks: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append(("%s%s" % ("[OK] " if cond else "[NG] ", name)))
        if verbose:
            print("  %s%s%s" % ("[OK] " if cond else "[NG] ", name,
                                ("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 能量守恒：四项和 ≡ 已解释
    t = budget_terms("a28_8b")
    s4 = t["e_cdac_fj"] + t["e_cmp_fj"] + t["e_clk_fj"] + t["e_log_fj"]
    ok &= chk("① 能量守恒：四项和 ≡ e_explained（相对差 <1e-15）",
              abs(s4 - t["e_explained_fj"]) / t["e_explained_fj"] < 1e-15,
              "%.6f vs %.6f fJ" % (s4, t["e_explained_fj"]))

    # ② CDAC 项对 b 的标度：E(b=12)/E(b=8) ≡ 4095/255（**精确比值，不是 16**）
    e8 = A.cdac_cap_units(8, "sar")["energy_units_C0V2"]
    e12 = A.cdac_cap_units(12, "sar")["energy_units_C0V2"]
    ok &= chk("② 标准 SAR：E(12b)/E(8b) ≡ 4095/255 = 16.0588（**非 16** · 和式比值）",
              abs(e12 / e8 - 4095.0 / 255.0) < 1e-12, "%.6f" % (e12 / e8))

    # ③ 单调 ≡ 标准 /2（精确）
    u_mono = A.cdac_cap_units(8, "sar_monotonic")["energy_units_C0V2"]
    ok &= chk("③ 单调开关 ≡ 标准 SAR 的精确一半",
              abs(u_mono / e8 - 0.5) < 1e-15, "%.9f" % (u_mono / e8))

    # ④ 覆盖率必须 <100%（参数集不得过度）
    cov = [r["coverage"] for r in coverage_table()]
    ok &= chk("④ 三个锚覆盖率全部 <100%%（参数集不过度 · 实测 %.1f%%~%.1f%%）"
              % (min(cov) * 100, max(cov) * 100),
              all(c < 1.0 for c in cov))

    # ⑤ 覆盖率离散度必须被如实报出，且**不得 <1.5×**（若 <1.5× 说明参数被凑过）
    sp = coverage_spread()
    ok &= chk("⑤ 覆盖率离散度 = %.2f×（**必须如实报出，不得人为凑小**）"
              % sp["spread"], sp["spread"] > 1.5)

    # ⑥ 单参数集可标定性：s_i 代回必须精确复现 E_conv
    sa = scalability_analysis()
    worst_rt = max(r["roundtrip_rel_err"] for r in sa["rows"])
    ok &= chk("⑥ 各锚 s_i 代回 ≡ 实测 E_conv（代数恒等 · 相对差 <1e-14）",
              worst_rt < 1e-14, "最大 %.3e" % worst_rt)

    # ⑦ 🔴 核心：单参数集离散度 >2×（模型结构不可标定）
    ok &= chk("⑦ 🔴 s_i 离散度 = %.2f× ⇒ **不存在单一设计参数集**（判定不可标定）"
              % sa["spread"],
              sa["spread"] > 2.0 and sa["calibratable"] is False)

    # ⑦b 组内一致性：两个常规档的 s 必须接近（偏离来自**设计策略**，不是噪声）
    ok &= chk("⑦b 组内一致性 %.1f%%（<10%% ⇒ 常规两档同一套策略，偏离来自低速档的策略差异）"
              % (abs(sa["inner_consistency"] - 1) * 100),
              sa["inner_consistency"] < 1.10)

    # ⑦c 离群档必须真的离群（否则"设计策略不同"这个解释不成立）
    ok &= chk("⑦c 离群比 %.2f×（>2× ⇒ 低速档偏离是**策略差异**，非数值噪声）"
              % sa["outlier_ratio"], sa["outlier_ratio"] > 2.0)

    # ⑧ 自由度必须 ≤0（当前无同工艺锚对 ⇒ 不可校核）
    dof = dof_analysis()
    ok &= chk("⑧ 🔴 校核自由度 dof = %d ≤ 0 ⇒ **不可校核**（无同工艺锚对）"
              % dof["dof"],
              dof["dof"] <= 0 and dof["certifiable"] is False)

    # ⑨ t_regen 与 f_s 无关（防回归到 T_conv/(2b)）
    t_lo = budget_terms("a65_8b")
    ok &= chk("⑨ 比较器通电时间取工艺 t_regen（与 f_s 无关）",
              abs(t_lo["t_regen_s"] - 800e-12) < 1e-18,
              "65nm = %.0f ps" % (t_lo["t_regen_s"] * 1e12))

    # ⑩ f_s 依赖：两点上必须精确复现 E_dyn + P/f（代数恒等）
    fd = fs_dependence(bits=8)
    worst = 0.0
    for r in fd["rows"]:
        pred = r["e_dyn_j"] + fd["p_static_w"] / r["f_s_hz"]
        worst = max(worst, abs(pred - r["e_conv_j"]) / r["e_conv_j"])
    ok &= chk("⑩ `E_conv(f_s) = E_dyn + P_static/f_s` 逐点恒等（<1e-15）",
              worst < 1e-15, "最大 %.3e" % worst)

    # ⑪ f_s 单调：静态份额必须随 f_s 单调下降
    shares = [r["static_share"] for r in fd["rows"]]
    ok &= chk("⑪ 静态份额随 f_s 单调下降（结构性预言可证伪）",
              all(shares[i] > shares[i + 1] for i in range(len(shares) - 1)))

    # ⑫ 区间地板：三个锚都必须有值，且 spread >1
    fi = floor_interval()
    ok &= chk("⑫ 区间地板 = %.1f ~ %.1f fJ/op（%.1f× · **不得报单点**）"
              % (fi["interval_fj"][0], fi["interval_fj"][1], fi["spread"]),
              fi["spread"] > 1.0 and len(fi["rows"]) == 3)

    # ⑬ E25 单点必须落在区间内（口径相容，不是推翻）
    sp25 = fi["single_point_e25_fj"]
    ok &= chk("⑬ E25 单点 %.1f fJ/op 落在区间内（口径相容 · 只是不该报单点）" % sp25,
              fi["interval_fj"][0] <= sp25 <= fi["interval_fj"][1])

    # ⑭ 未解释项必须有「可否建模」标记，且不可建模者占多数
    nm = sum(1 for u in UNEXPLAINED_SOURCES if not u["modelable"])
    ok &= chk("⑭ 未解释项 %d 条中有 %d 条**不可从公开参数建模**（占 %.0f%%）"
              % (len(UNEXPLAINED_SOURCES), nm, nm / len(UNEXPLAINED_SOURCES) * 100),
              nm >= len(UNEXPLAINED_SOURCES) // 2)

    # ⑮ 输出恒 MODEL_ESTIMATE
    ok &= chk("⑮ 全部输出恒标 `MODEL_ESTIMATE`（无实测档）",
              t["tier"] == "MODEL_ESTIMATE" and dof["tier"] == "MODEL_ESTIMATE")

    if verbose:
        print()
        print("  %d/%d 通过" % (sum(1 for c in checks if c.startswith("[OK]")), len(checks)))
    return ok


ADC_BUDGET_DISCLOSURE = {
    "tier": E.OUTPUT_TIER,
    "is_measured": False,
    "core_finding": "四项物理模型只能解释实测 ADC 能耗的 18%~89%（跨设计 4.9×）；"
                    "单一设计参数集无法同时解释三个锚（s_i 离散 4.18×）⇒ "
                    "**「从头算」路线上限已封顶**，ADC 能耗必须走「实测标定 + 区间」",
    "not_claimed": [
        "不宣称任何 ADC 能耗模型的精度（dof<0 ⇒ 不可校核）",
        "不宣称 33.7 fJ/op 是单点真值（区间 14.9~66.2 fJ/op）",
        "不宣称 t_regen / C_latch / C_clk_net 是准确值（均为占位）",
    ],
    "next_data_needed": "同工艺 ≥5 个不同配置（位数/速度/电容）的实测 FOM 锚 ⇒ dof>0 才可校核",
}
