# -*- coding: utf-8 -*-
"""E17 时序 / 时钟预算链（`lda/lda_l2/ecore/timing.py` · D-186）。

═══════════════════════════════════════════════════════════════════════════
定位：**时间维度上的 E15**
═══════════════════════════════════════════════════════════════════════════
E15 把 E1–E14 的**零散误差**合成一条精度预算链；本段把 E1–E14 的**零散时间量**
合成一条**节拍链**，回答「这颗阵列最快能跑多快」。

🔴 **只报「每样本耗时（ns）」与相对量；绝不报 TOPS / TOPS-W / fJ/op。**

═══════════════════════════════════════════════════════════════════════════
🔴🔴 第一原理：**误差要分类合成，时间要分拓扑相加**（与 E15 相对照）
═══════════════════════════════════════════════════════════════════════════
E15（`budget.combine`）：误差源按**相关结构**分三类 —— 系统 `Σ` · 随机 `RSS→kσ` · 有界 `Σ→√3`。
本模块（`combine_time`）：时间阶段按**拓扑**分 —— 串行链**必须代数相加**，流水线稳态取 **max**：

    serial_latency   = Σ t_i          （一条链走完）
    pipelined_period = max t_i        （稳态周期）
    pipelined_latency = Σ t_i         （首样本延迟，含填充）

⇒ **对时间用 RSS（√Σt²）是错的** —— 串行阶段的时间必然叠加，不满足「独立随机量」前提。
⇒ **E15 的合成律不可平移到 E17。**

═══════════════════════════════════════════════════════════════════════════
五个闭式 golden（全部可手算 · 方法学独立）
═══════════════════════════════════════════════════════════════════════════
G-1 一阶 RC 建立到相对残差 ε      : `t = τ·ln(1/ε)`        （`v=V(1−e^{−t/τ})` 反解）
G-2 建立到 k-bit 的 ½LSB          : `t = τ·(k+1)·ln2`      （G-1 令 ε=2^{−(k+1)}）
G-3 Elmore 延迟（R 梯）           : `τ = r·c·n(n+1)/2` → `R_tot·C_tot/2`
G-4 SAR 转换周期数                : `n_bits + 1`           （n_bits 次试判 + 1 次采样）
G-5 CDAC 底板建立 ⇒ 时钟          : `t_clk = settle_half_lsb(R_on·C_tot, k)`，`C_tot = C_u·2^n`

🔴 **全部复用**既有量、**不复制**：G-3 用 `parasitic.elmore_delay` / `array_parasitics`；
G-5 的 `R_on` 用 `converter.nmos_switch_ron_ohm`。

═══════════════════════════════════════════════════════════════════════════
五阶段（全部**复用**已有效量 · 无新物理）
═══════════════════════════════════════════════════════════════════════════
① 行线建立 `τ = E7 Elmore + R_oc·C_row_tot`（🔴 分布式 + 驱动源阻抗，**串联**）
② 列线建立 `τ = E7 Elmore_col`（TIA 虚地 ⇒ 无 Rf·C 项）
③ 采样保持 `τ = rs·cs`（E14 `CONV_PROCESS`）
④ SAR 转换 `t = (bits+1)·t_clk`（`t_clk` 由 G-5 推导，E14 `nmos_switch_ron_ohm`）
⑤ DAC 建立 `τ = r_unit·c_node`（`c_node` 为**显式占位** · E14 未建 R-2R 动态）

🔴 `R_oc = 0` ⇒ ①**退化为纯 Elmore**（泛化必须退化为特例 · 门禁 B7 守着）。

═══════════════════════════════════════════════════════════════════════════
保护性约束
═══════════════════════════════════════════════════════════════════════════
**只读消费** E7/E14 —— 不改任何既有默认值；**不给** `PERIPHERY_PROCESS` 加时间键
（E14 的行驱动**保持原样**，E17 的时间参数只进**自己的** `TIMING_PROCESS`）。
⇒ E15/E16 已发布数字**逐位不变**（门禁 B15/B16 守着）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple, Union

from . import parasitic as PA
from . import converter as CV
from . import periphery as PR

LN2 = math.log(2.0)

# ═══════════════════════════════════════════════════════════════════════════
# 工艺 / 默认参数（**公开典型量级占位 · 非 PDK**）
# ═══════════════════════════════════════════════════════════════════════════
TIMING_PROCESS: Dict[str, float] = {
    "bits": 8,                  # 默认有效位数（建立判据 = ½LSB @ bits）
    "r2r_node_cap_f": 0.5e-12,  # 🔴 R-2R 输出节点等效电容（**显式占位** · E14 未建 R-2R 动态）
}

TIMING_DISCLOSURE: Dict[str, str] = {
    "role": "E17 = 时序 / 时钟预算链 —— 把 E1–E14 的零散时间量合成一条节拍链",
    "metric": "🔴 **只报「每样本耗时（ns）」与相对量**；**不报 TOPS / TOPS-W / fJ/op** "
              "（那是吞吐×能效的联合指标 —— 本段既无功耗模型、也无实测硅）",
    "synthesis": "🔴 **时间按拓扑合成**（串行 Σ / 流水线 max），**不是**按类型做 RSS —— "
                 "与 E15 的误差分类合成律**不同**（串行阶段的时间必然叠加）",
    "model": "五阶段为**宏模型级**时间估算：行驱动仍是 **VCVS + 开环输出电阻宏模型**"
             "（无真实 GBW / 摆率）；比较器延时 / 时钟树 / 抖动**未建模**；"
             "R-2R 节点电容为**显式占位**（E14 未建 R-2R 动态）",
    "scope": "**只覆盖静态 + 一阶 RC 建立**：不含摆率限制 / 时钟偏斜与抖动 / 供电噪声 / "
             "温度梯度 / 老化 / 工艺角；🔴 **不做能量与功耗估算**",
    "params": "参数（C_u / R / rs / cs / c_node）为**公开典型量级占位 · 非 PDK · 无实测锚** "
              "⇒ **结论随参数变**，报告必须携带参数（DAC 阶段尤其参数敏感）",
    "coupling": "阵列 RC 沿用 E7/E9 一阶口径（**忽略列线电阻对行线的耦合**）",
    "red_line": "纯标准库（复用 E7/E14）· LLM 不进判决路径 · 零商业 EDA 依赖 · **非签核级 SPICE**",
}

__all__ = [
    "LN2", "TIMING_PROCESS", "TIMING_DISCLOSURE",
    # ① 时间合成律
    "normalize_stages", "serial_sum", "pipelined_period", "combine_time",
    # ② 闭式 golden
    "rc_settle_time", "settle_half_lsb", "sar_period",
    # ③ 五阶段
    "row_stage_time", "col_stage_time", "sample_hold_stage_time",
    "cdac_total_cap", "cdac_settle_tau", "cdac_clock_from_settle",
    "sar_stage_time", "dac_stage_time", "stage_times",
    # ④ 报告 / 反解 / 规模
    "per_sample_report", "clock_budget", "time_vs_n", "crossover_n_ps",
    # ⑤ 自检
    "timing_self_check",
]

_StageLike = Union[Dict, Sequence[Dict]]


# ═══════════════════════════════════════════════════════════════════════════
# ① 时间合成律（**按拓扑**，与 E15 的误差分类合成相对照）
# ═══════════════════════════════════════════════════════════════════════════
def normalize_stages(stages: _StageLike) -> List[Dict]:
    """把 `[{"name","t_s"}]` 或 `{"name": t_s}` 统一成阶段列表（保持给定顺序）。

    🔴 **保留原字典的其它键**（`tau_s` / `bits` / `source` / `param_sensitive` …）——
    否则 `combine_time` 返回的阶段表会丢掉来源信息，且 `per_sample_report` 的
    `dominant_share_pct` 会取到 `None`（share 是打在**复制后**那批字典上的）。
    """
    if isinstance(stages, dict):
        return [{"name": str(k), "t_s": float(v)} for k, v in stages.items()]
    out: List[Dict] = []
    for s in stages:
        if isinstance(s, dict):
            d = dict(s)                       # 浅复制：保留其余键
            d["name"] = str(d.get("name", "?"))
            d["t_s"] = float(d["t_s"])
            out.append(d)
        else:
            out.append({"name": "?", "t_s": float(s)})
    return out


def combine_time(stages: _StageLike, topology: str = "serial") -> Dict:
    """**按拓扑合成时间**。

    🔴 与 E15 `budget.combine`（按类型合成误差）**不同**：
      · `serial`    ⇒ `t = Σ t_i`（串行链必须代数相加）
      · `pipelined` ⇒ `t = max t_i`（稳态周期）；**首样本延迟仍 = Σ t_i**

    🔴 **对时间用 RSS（√Σt²）是错的** —— 串行阶段的时间必然叠加。
    """
    ss = normalize_stages(stages)
    total = sum(s["t_s"] for s in ss)
    slowest = max(ss, key=lambda s: s["t_s"]) if ss else None
    pip = float(slowest["t_s"]) if slowest else 0.0
    gain = ((total - pip) / total) if total > 0.0 else 0.0
    for s in ss:
        s["share_pct"] = (s["t_s"] / total * 100.0) if total > 0.0 else 0.0
    topo = str(topology).lower()
    if topo not in ("serial", "pipelined"):
        raise ValueError("topology 须为 'serial' 或 'pipelined'，得 %r" % (topology,))
    return {
        "topology": topo,
        "t_s": total if topo == "serial" else pip,
        "serial_s": total,
        "pipelined_period_s": pip,
        "pipelined_latency_s": total,
        "pipeline_gain_frac": gain,
        "n_stages": len(ss),
        "slowest_stage": (slowest or {}).get("name"),
        "stages": ss,
        "is_oracle": False,
    }


def serial_sum(stages: _StageLike) -> Dict:
    """串行链总时间 = `Σ t_i`（**必须代数相加**，不取 RSS）。"""
    return combine_time(stages, "serial")


def pipelined_period(stages: _StageLike) -> Dict:
    """流水线稳态周期 = `max t_i`；首样本延迟 = `Σ t_i`。"""
    return combine_time(stages, "pipelined")


# ═══════════════════════════════════════════════════════════════════════════
# ② 闭式 golden
# ═══════════════════════════════════════════════════════════════════════════
def rc_settle_time(tau_s: float, target_rel: float) -> float:
    """**G-1**：一阶 RC 建立到相对残差 `ε` 所需时间 `t = τ·ln(1/ε)`。

    反解自 `v(t) = V·(1 − e^{−t/τ})` ⇒ 残差 /V = `e^{−t/τ}` = ε。
    """
    e = float(target_rel)
    if not (0.0 < e < 1.0):
        raise ValueError("target_rel 须落在 (0, 1)，得 %r" % (target_rel,))
    return float(tau_s) * math.log(1.0 / e)


def settle_half_lsb(tau_s: float, bits: int) -> float:
    """**G-2**：建立到 `bits` 位的 **½LSB** ⇒ `t = τ·(bits+1)·ln2`（精确闭式）。

    = `rc_settle_time(τ, 2^{−(bits+1)})`。E14 的 `t_to_half_lsb_8bit_s`
    用的正是这一条（`−τ·ln(1 − (1 − 0.5/256))` = `τ·9·ln2`）。
    """
    b = int(bits)
    if b < 0:
        raise ValueError("bits 须 >= 0")
    return float(tau_s) * float(b + 1) * LN2


def sar_period(n_bits: int, t_clk_s: float) -> float:
    """**G-4**：SAR 转换周期 `= (n_bits + 1)·t_clk`（`n_bits` 次试判 + 1 次采样）。

    逐次逼近是**串行**的 ⇒ 时间**线性于位数**。与 `converter.sar_convert`
    的 `len(trace) == n_bits` 交叉核对（门禁 B8）。
    """
    n = int(n_bits)
    if n < 1:
        raise ValueError("n_bits 须 >= 1")
    if float(t_clk_s) <= 0.0:
        raise ValueError("t_clk 须 > 0")
    return float(n + 1) * float(t_clk_s)


# ═══════════════════════════════════════════════════════════════════════════
# ③ 五阶段
# ═══════════════════════════════════════════════════════════════════════════
def _bits(bits: Optional[int]) -> int:
    return int(TIMING_PROCESS["bits"] if bits is None else bits)


def _default_r_oc() -> float:
    """行驱动闭环输出电阻（**复用 E14**）：`R_ol/(1+A)`。"""
    return PR.buffer_closed_loop_rout(PR.PERIPHERY_PROCESS["r_out_open_ohm"],
                                      PR.PERIPHERY_PROCESS["a_gain"])


def row_stage_time(n: int, m: Optional[int] = None, bits: Optional[int] = None,
                   r_oc: Optional[float] = None,
                   cell_params: Optional[Dict[str, float]] = None,
                   proc: Optional[Dict[str, float]] = None) -> Dict:
    """① **行线建立**：`τ = Elmore(行线) + R_oc·C_row_tot`（分布式 + 驱动源阻抗，**串联**）。

    🔴 `r_oc = 0` ⇒ 退化为**纯 Elmore**（门禁 B7 守此退化）。
    """
    mm = int(n) if m is None else int(m)
    p = PA.array_parasitics(int(n), mm, cell_params, proc)
    tau_dist = float(p["tau_row_s"])
    roc = _default_r_oc() if r_oc is None else float(r_oc)
    if roc < 0.0:
        raise ValueError("r_oc 须 >= 0")
    tau_drv = roc * float(p["C_row_total_fF"]) * 1e-15      # Ω·fF = 1e-15 s
    tau = tau_dist + tau_drv
    b = _bits(bits)
    return {
        "name": "row_line", "t_s": settle_half_lsb(tau, b),
        "tau_s": tau, "tau_dist_s": tau_dist, "tau_drv_s": tau_drv,
        "r_oc_ohm": roc, "bits": b, "n": int(n), "m": mm,
        "source": "E7 parasitic.array_parasitics + E14 periphery.buffer_closed_loop_rout",
        "is_oracle": False,
    }


def col_stage_time(n: int, m: Optional[int] = None, bits: Optional[int] = None,
                   cell_params: Optional[Dict[str, float]] = None,
                   proc: Optional[Dict[str, float]] = None) -> Dict:
    """② **列线建立**：`τ = Elmore(列线)`（TIA 虚地 ⇒ 无 `Rf·C` 项）。"""
    mm = int(n) if m is None else int(m)
    p = PA.array_parasitics(int(n), mm, cell_params, proc)
    tau = float(p["tau_col_s"])
    b = _bits(bits)
    return {
        "name": "col_line", "t_s": settle_half_lsb(tau, b),
        "tau_s": tau, "bits": b, "n": int(n), "m": mm,
        "source": "E7 parasitic.array_parasitics",
        "is_oracle": False,
    }


def sample_hold_stage_time(bits: Optional[int] = None,
                           rs_ohm: Optional[float] = None,
                           cs_f: Optional[float] = None) -> Dict:
    """③ **采样保持**：`τ = rs·cs`（**复用 E14 `CONV_PROCESS`**）。"""
    rs = float(CV.CONV_PROCESS["rs_ohm"] if rs_ohm is None else rs_ohm)
    cs = float(CV.CONV_PROCESS["cs_f"] if cs_f is None else cs_f)
    tau = rs * cs
    b = _bits(bits)
    return {
        "name": "sample_hold", "t_s": settle_half_lsb(tau, b),
        "tau_s": tau, "bits": b, "rs_ohm": rs, "cs_f": cs,
        "source": "E14 converter.CONV_PROCESS",
        "is_oracle": False,
    }


def cdac_total_cap(bits: int, c_unit: Optional[float] = None) -> float:
    """CDAC 总电容 `C_tot = C_u·2^n`（解析闭式）。

    E14 `converter._cdac_c_unit` 是 `[C_u·2^k]_{k<n} + [C_u]` ⇒ 其和 = `C_u·(2^n−1) + C_u = C_u·2^n`
    （门禁 B9 逐值交叉核对 ⇒ **不复制、只等价**）。
    """
    cu = float(CV.CONV_PROCESS["c_unit_f"] if c_unit is None else c_unit)
    n = int(bits)
    if n < 1:
        raise ValueError("bits 须 >= 1")
    return cu * float(1 << n)


def cdac_settle_tau(bits: int, c_unit: Optional[float] = None,
                    r_on: Optional[float] = None) -> Dict:
    """**G-5**：CDAC 底板切换后的顶板建立时间常数 `τ_cdac = R_on·C_tot`。

    `R_on` 复用 E14 `nmos_switch_ron_ohm`（默认 6.4103 Ω）。
    """
    ro = float(CV.nmos_switch_ron_ohm(w_over_l=CV.CONV_PROCESS["dac_sw_wl"],
                                     v_gate=CV.CONV_PROCESS["sw_vgate_v"])
               if r_on is None else r_on)
    ctot = cdac_total_cap(bits, c_unit)
    return {"tau_s": ro * ctot, "r_on_ohm": ro, "c_total_f": ctot, "bits": int(bits),
            "source": "E14 converter.nmos_switch_ron_ohm", "is_oracle": False}


def cdac_clock_from_settle(bits: int, c_unit: Optional[float] = None,
                           r_on: Optional[float] = None) -> Dict:
    """**G-5**：由 CDAC 建立推出的 SAR 时钟周期 `t_clk = settle_half_lsb(τ_cdac, bits)`。"""
    d = cdac_settle_tau(bits, c_unit, r_on)
    b = int(bits)
    t_clk = settle_half_lsb(d["tau_s"], b)
    return {"t_clk_s": t_clk, "tau_cdac_s": d["tau_s"], "r_on_ohm": d["r_on_ohm"],
            "c_total_f": d["c_total_f"], "bits": b,
            "source": d["source"], "is_oracle": False}


def sar_stage_time(bits: Optional[int] = None, t_clk_s: Optional[float] = None,
                   c_unit: Optional[float] = None, r_on: Optional[float] = None) -> Dict:
    """④ **SAR 转换**：`t = (bits+1)·t_clk`；`t_clk` 缺省由 **G-5 推导**（可显式覆盖）。"""
    b = _bits(bits)
    if t_clk_s is None:
        g5 = cdac_clock_from_settle(b, c_unit, r_on)
        tclk = g5["t_clk_s"]
        src = g5["source"] + " ⇒ G-5 推导"
    else:
        tclk = float(t_clk_s)
        src = "显式覆盖"
    return {
        "name": "sar_convert", "t_s": sar_period(b, tclk),
        "t_clk_s": tclk, "n_clk": b + 1, "bits": b,
        "source": src, "is_oracle": False,
    }


def dac_stage_time(bits: Optional[int] = None, r_unit: Optional[float] = None,
                   c_node_f: Optional[float] = None) -> Dict:
    """⑤ **DAC 建立**：`τ = r_unit·c_node`。

    🔴 `c_node` 为**显式占位**（E14 未建 R-2R 动态）⇒ 本阶段**参数敏感**，报告须标注。
    """
    r = float(CV.CONV_PROCESS["r_unit_ohm"] if r_unit is None else r_unit)
    c = float(TIMING_PROCESS["r2r_node_cap_f"] if c_node_f is None else c_node_f)
    b = _bits(bits)
    tau = r * c
    return {
        "name": "dac_settle", "t_s": settle_half_lsb(tau, b),
        "tau_s": tau, "r_unit_ohm": r, "c_node_f": c, "bits": b,
        "param_sensitive": True,
        "source": "E14 converter.CONV_PROCESS + TIMING_PROCESS['r2r_node_cap_f']（**占位**）",
        "is_oracle": False,
    }


def stage_times(n: int = 8, m: Optional[int] = None, bits: Optional[int] = None,
                r_oc: Optional[float] = None,
                cell_params: Optional[Dict[str, float]] = None,
                proc: Optional[Dict[str, float]] = None,
                rs_ohm: Optional[float] = None, cs_f: Optional[float] = None,
                t_clk_s: Optional[float] = None, c_unit: Optional[float] = None,
                r_on: Optional[float] = None, r_unit: Optional[float] = None,
                c_node_f: Optional[float] = None) -> List[Dict]:
    """五阶段时间表（**顺序即物理串行序**：行 → 列 → 采样 → 转换 → DAC）。

    🔴 参数**显式列出**（不盲传 `**kw`）：各阶段接受的参数名不同，
    盲传会把 `r_oc` 之类的行线参数灌进采样保持 ⇒ `TypeError`。
    """
    return [
        row_stage_time(n, m, bits, r_oc=r_oc, cell_params=cell_params, proc=proc),
        col_stage_time(n, m, bits, cell_params=cell_params, proc=proc),
        sample_hold_stage_time(bits, rs_ohm=rs_ohm, cs_f=cs_f),
        sar_stage_time(bits, t_clk_s=t_clk_s, c_unit=c_unit, r_on=r_on),
        dac_stage_time(bits, r_unit=r_unit, c_node_f=c_node_f),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ④ 报告 / 反解 / 规模
# ═══════════════════════════════════════════════════════════════════════════
def per_sample_report(n: int = 8, m: Optional[int] = None, bits: Optional[int] = None,
                      **kw) -> Dict:
    """**每样本耗时报告**（🔴 只报耗时与相对量 · **不报 TOPS**）。

    输出：五阶段 + `serial` 总 + 流水线稳态周期 / 首样本延迟 + 主导项 + 最大采样率。
    """
    ss = stage_times(n, m, bits, **kw)
    cs = combine_time(ss, "serial")
    cp = combine_time(ss, "pipelined")
    ss = cs["stages"]                      # 🔴 用**打过 share_pct 的那批字典**（已保留 tau_s 等键）
    total = cs["serial_s"]
    dom = max(ss, key=lambda s: s["t_s"]) if ss else None
    return {
        "n": int(n), "m": (int(n) if m is None else int(m)), "bits": _bits(bits),
        "stages": cs["stages"],
        "serial_s": total, "serial_ns": total * 1e9,
        "pipelined_period_s": cp["pipelined_period_s"],
        "pipelined_period_ns": cp["pipelined_period_s"] * 1e9,
        "pipelined_latency_s": total,
        "pipeline_gain_frac": cp["pipeline_gain_frac"],
        "max_sample_rate_hz": (1.0 / total) if total > 0.0 else float("inf"),
        "dominant": dom,
        "dominant_name": (dom or {}).get("name"),
        "dominant_share_pct": (dom or {}).get("share_pct"),
        "row_tau_s": ss[0]["tau_s"], "col_tau_s": ss[1]["tau_s"],
        "is_oracle": False,
    }


def clock_budget(target_period_s: float, n_bits: int, n: int = 8,
                 m: Optional[int] = None) -> Dict:
    """**时钟预算反解**：给定目标每样本周期 ⇒ SAR 允许的最大 `t_clk`。

    扣除其余四阶段的固定开销后，把剩余预算分给 `(n_bits + 1)` 拍：
    `t_clk_max = (target − fixed) / (n_bits + 1)`。

    🔴 **代回验证**（门禁 B14）：`fixed + (n_bits+1)·t_clk_max == target`。
    """
    tgt = float(target_period_s)
    if tgt <= 0.0:
        raise ValueError("target_period_s 须 > 0")
    b = int(n_bits)
    # 固定开销 = 除 SAR 外的四阶段
    fixed = (row_stage_time(n, m, b)["t_s"]
             + col_stage_time(n, m, b)["t_s"]
             + sample_hold_stage_time(b)["t_s"]
             + dac_stage_time(b)["t_s"])
    slack = tgt - fixed
    feasible = slack > 0.0
    t_clk_max = (slack / float(b + 1)) if feasible else float("nan")
    back_calc = (fixed + sar_period(b, t_clk_max)) if feasible else float("nan")
    return {
        "target_period_s": tgt, "n_bits": b, "fixed_s": fixed,
        "slack_s": slack, "feasible": bool(feasible),
        "t_clk_max_s": t_clk_max,
        "t_clk_max_from_cdac_s": cdac_clock_from_settle(b)["t_clk_s"],
        "back_calc_s": back_calc,
        "residual_s": (abs(back_calc - tgt) if feasible else float("nan")),
        "is_oracle": False,
    }


def time_vs_n(sizes: Sequence[int], bits: Optional[int] = None, **kw) -> Dict:
    """**规模 × 时间**：阵列 RC 随 N 升，而**每样本耗时几乎不变**（外围主导）。"""
    rows = []
    for n in sizes:
        r = per_sample_report(int(n), int(n), bits, **kw)
        rows.append({
            "n": int(n),
            "row_tau_s": r["row_tau_s"], "col_tau_s": r["col_tau_s"],
            "serial_ns": r["serial_ns"],
            "row_stage_ns": r["stages"][0]["t_s"] * 1e9,
            "dominant": r["dominant_name"],
            "dominant_share_pct": r["dominant_share_pct"],
            "max_sample_rate_hz": r["max_sample_rate_hz"],
        })
    taus = [x["row_tau_s"] for x in rows]
    ser = [x["serial_ns"] for x in rows]
    span = (max(taus) / min(taus)) if taus and min(taus) > 0 else float("inf")
    span_t = (max(ser) / min(ser)) if ser and min(ser) > 0 else float("inf")
    return {
        "points": rows, "bits": _bits(bits),
        "tau_row_span_x": span, "serial_span_x": span_t,
        "conclusion": "阵列 τ_row 随 N 显著上升（∝N²），但每样本耗时几乎不变 —— **外围主导**",
        "is_oracle": False,
    }


def crossover_n_ps(tau_target_s: float = 1.0e-9, n_ref: int = 256,
                   lo: int = 4, hi: int = 1 << 20) -> Dict:
    """**解析交叉点**：阵列行线 τ 何时达到 `tau_target_s`（如 1 ns）。

    两条独立路径：
      · **解析外推** `N ≈ √(τ_target · n_ref² / τ_row(n_ref))`（利用 τ ∝ N²）；
      · **二分反解**（τ(N) 严格单调 ⇒ 二分合法）。
    """
    tgt = float(tau_target_s)
    if tgt <= 0.0:
        raise ValueError("tau_target_s 须 > 0")
    p_ref = PA.array_parasitics(int(n_ref), int(n_ref))
    tau_ref = float(p_ref["tau_row_s"])
    n_analytic = math.sqrt(tgt * float(int(n_ref)) ** 2 / tau_ref)
    a, b = int(lo), int(hi)
    while a < b:
        mid = (a + b) // 2
        if float(PA.array_parasitics(mid, mid)["tau_row_s"]) >= tgt:
            b = mid
        else:
            a = mid + 1
    return {
        "tau_target_s": tgt, "n_ref": int(n_ref), "tau_ref_s": tau_ref,
        "n_analytic": n_analytic, "n_bisect": int(a),
        "rel_diff_pct": abs(n_analytic - a) / a * 100.0,
        "tau_at_n_s": float(PA.array_parasitics(a, a)["tau_row_s"]),
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 自检（12 项）
# ═══════════════════════════════════════════════════════════════════════════
def timing_self_check(verbose: bool = True) -> bool:
    """模块自检 **12 项**（闭式 golden + 跨模块交叉 + 保护性约束）。"""
    res = True

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        nonlocal res
        if verbose:
            print(("PASS | " if cond else "FAIL | ") + name
                  + (("  :: " + detail) if detail else ""))
        res = res and bool(cond)
        return bool(cond)

    # ① G-1 闭式：反解验证
    tau, e = 3.7e-9, 1.0e-6
    t = rc_settle_time(tau, e)
    resid = math.exp(-t / tau)
    chk("① G-1 一阶 RC 建立闭式 t = τ·ln(1/ε)（反解 e^{−t/τ} == ε）",
        abs(resid - e) < 1e-18 and abs(t - tau * math.log(1.0 / e)) < 1e-24,
        "t=%.6e · 残差=%.3e" % (t, resid))

    # ② G-2 是 G-1 的特例（ε = 2^{−(k+1)}）
    ok2 = True
    for k in (4, 6, 8, 12):
        a = settle_half_lsb(1.0e-9, k)
        b = rc_settle_time(1.0e-9, 2.0 ** (-(k + 1)))
        c = 1.0e-9 * (k + 1) * LN2
        ok2 &= (abs(a - b) < 1e-24) and (abs(a - c) < 1e-24)
    chk("② G-2 建立到 k-bit ½LSB = τ·(k+1)·ln2 == G-1 令 ε=2^{−(k+1)}", ok2,
        "k=8 ⇒ %.6e s" % settle_half_lsb(1.0e-9, 8))

    # ③ G-2 ⟷ E14 实测（跨模块交叉核对 · 方法学独立：E14 走 MNA 瞬态）
    sh = CV.sample_hold_transient()
    mine = settle_half_lsb(sh["tau_s"], 8)
    chk("③ G-2 ⟷ **E14 实测** t_to_half_lsb_8bit_s（跨模块 · E14 走 MNA 瞬态）",
        abs(mine - sh["t_to_half_lsb_8bit_s"]) / sh["t_to_half_lsb_8bit_s"] < 1e-12,
        "闭式=%.6e ⟷ E14=%.6e" % (mine, sh["t_to_half_lsb_8bit_s"]))

    # ④ G-3 Elmore 规模律 τ ∝ N²（τ/N² 收敛 + 相邻比 → 4）
    taus = [PA.array_parasitics(n, n)["tau_row_s"] for n in (16, 32, 64, 128, 256)]
    per_n2 = [tt / float(n) ** 2 for tt, n in zip(taus, (16, 32, 64, 128, 256))]
    ratios = [taus[i + 1] / taus[i] for i in range(len(taus) - 1)]
    chk("④ G-3 Elmore 规模律 τ ∝ N²（τ/N² 收敛 · 相邻比 → 4）",
        all(ratios[i] > ratios[i + 1] - 1e-12 for i in range(len(ratios) - 1))
        and abs(ratios[-1] - 4.0) < 0.02
        and (max(per_n2) - min(per_n2)) / max(per_n2) < 0.15,
        "相邻比=%s · τ/N²=%.4e…%.4e" % (["%.3f" % r for r in ratios], min(per_n2), max(per_n2)))

    # ⑤ G-3b 退化：R_oc = 0 ⇒ 行线时间 == 纯 Elmore（逐位）
    p8 = PA.array_parasitics(8, 8)
    r0 = row_stage_time(8, 8, 8, r_oc=0.0)
    chk("⑤ G-3b **退化**：R_oc = 0 ⇒ 行线时间退化为**纯 Elmore**（逐位一致）",
        r0["tau_drv_s"] == 0.0 and r0["tau_s"] == p8["tau_row_s"]
        and r0["t_s"] == settle_half_lsb(p8["tau_row_s"], 8),
        "τ=%.6e ⟷ Elmore=%.6e" % (r0["tau_s"], p8["tau_row_s"]))

    # ⑥ G-4 SAR = (n_bits+1)·t_clk 线性 + 与 converter 逐位试判次数一致
    ok6 = True
    for nb in (6, 8, 10):
        ok6 &= abs(sar_period(nb, 1.0e-9) - (nb + 1) * 1.0e-9) < 1e-24
        ok6 &= (len(CV.sar_convert(0.37, n_bits=nb)["trace"]) == nb)
    chk("⑥ G-4 SAR 周期 = (n_bits+1)·t_clk 且与 E14 `len(trace)==n_bits` 一致", ok6,
        "8bit ⇒ %.4e s（9 拍）" % sar_period(8, 1e-9))

    # ⑦ G-5 CDAC 总电容 C_tot = C_u·2^n ⟷ E14 `_cdac_c_unit` 之和
    ok7 = True
    for nb in (6, 8, 10):
        ok7 &= abs(cdac_total_cap(nb, 1e-12) - sum(CV._cdac_c_unit(nb, 1e-12))) < 1e-24
    g5 = cdac_clock_from_settle(8)
    chk("⑦ G-5 C_tot = C_u·2^n ⟷ E14 `_cdac_c_unit` 之和（等价不复制）", ok7,
        "C_tot(8)=%.4e F · τ_cdac=%.4e s · t_clk=%.4e s"
        % (g5["c_total_f"], g5["tau_cdac_s"], g5["t_clk_s"]))

    # ⑧ 🔴 时间合成律（**非恒等样本**：各阶段互不相等且 ≥2 个）
    st = [{"name": "a", "t_s": 3.0e-9}, {"name": "b", "t_s": 7.0e-9},
          {"name": "c", "t_s": 11.0e-9}]
    ss, pp = serial_sum(st), pipelined_period(st)
    chk("⑧ 🔴 时间合成律：serial == Σ t_i · pipelined == max t_i（**非恒等样本**）",
        abs(ss["t_s"] - 21.0e-9) < 1e-24 and abs(pp["t_s"] - 11.0e-9) < 1e-24
        and ss["t_s"] != pp["t_s"],
        "Σ=%.3e · max=%.3e" % (ss["t_s"], pp["t_s"]))

    # ⑨ 🔴 流水线口径：首样本延迟 = Σ · 收益 = (Σ−max)/Σ
    chk("⑨ 🔴 流水线：首样本延迟 == Σ · 收益 =(Σ−max)/Σ · **对时间取 RSS 会给出不同值**",
        abs(pp["pipelined_latency_s"] - 21.0e-9) < 1e-24
        and abs(pp["pipeline_gain_frac"] - (21.0 - 11.0) / 21.0) < 1e-12
        and abs(math.sqrt(sum(s["t_s"] ** 2 for s in st)) - 21.0e-9) > 1e-9,
        "收益=%.4f" % pp["pipeline_gain_frac"])

    # ⑩ 五阶段单调：bits ↑ ⇒ 各阶段时间 ↑（更严的 LSB）
    lo = {s["name"]: s["t_s"] for s in stage_times(8, 8, 6)}
    hi = {s["name"]: s["t_s"] for s in stage_times(8, 8, 10)}
    chk("⑩ 五阶段单调：bits 6 → 10 ⇒ **每一阶段**时间都上升（更严的 ½LSB）",
        all(hi[k] > lo[k] for k in lo) and len(lo) == 5,
        "SAR 6bit=%.3e → 10bit=%.3e s" % (lo["sar_convert"], hi["sar_convert"]))

    # ⑪ 主导项识别 + share 合计 100%
    rep = per_sample_report(8, 8, 8)
    tot_share = sum(s["share_pct"] for s in rep["stages"])
    chk("⑪ 🔴 主导项识别：dominant == max 阶段 · share 合计 == 100%",
        abs(tot_share - 100.0) < 1e-9
        and rep["dominant"]["t_s"] == max(s["t_s"] for s in rep["stages"]),
        "主导=%s(%.1f%%) · 每样本=%.3f ns" % (rep["dominant_name"],
                                              rep["dominant_share_pct"], rep["serial_ns"]))

    # ⑫ 🔴 保护性约束 + 诚实披露
    p2 = PA.array_parasitics(8, 8)
    chk("⑫ 🔴 保护性：E7 默认 τ 逐位不变 · E14 `CONV_PROCESS` 未被改 · "
        "E17 不向 PERIPHERY_PROCESS 加时间键 · 披露含「不报 TOPS」",
        abs(p2["tau_row_s"] - 3.1186932940799992e-15) < 1e-27
        and abs(p2["tau_col_s"] - 2.07912886272e-15) < 1e-27
        and abs(p2["R_row_total_ohm"] - 3.5279999999999987) < 1e-12
        and set(PR.PERIPHERY_PROCESS.keys()) == {"a_gain", "r_out_open_ohm", "vfs_v", "vdd_v"}
        and CV.CONV_PROCESS["rs_ohm"] == 1.0e3
        and CV.CONV_PROCESS["cs_f"] == 1.0e-12
        and CV.CONV_PROCESS["t_step_s"] == 1.0e-9
        and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
        and ("不报 TOPS" in TIMING_DISCLOSURE["metric"])
        and ("非 PDK" in TIMING_DISCLOSURE["params"]),
        "τ_row(8×8)=%.6e" % p2["tau_row_s"])

    if verbose:
        print("\n" + ("ALL PASS" if res else "SOME FAILED") + " · timing_self_check")
    return res


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(0 if timing_self_check(verbose=True) else 1)
