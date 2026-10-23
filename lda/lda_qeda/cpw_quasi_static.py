# -*- coding: utf-8 -*-
"""D-217 · CPW **准静态场解 + 版图反提**（净增 0 锚 · 能力层）。

═══════════════════════ 这一层补的是哪一处断点 ═══════════════════════
量子域全景审计（2026-10-23）判「版图 → 器件参数**不可反提**」为三处闭环断点之一：
`sc_layout` 只做**几何** DRC/LVS，`sc_readout` 的馈线参数靠**设计输入**，
而既有 CPW 锚（λ/4 读出谐振器基模 f0）把 `n_eff` 当作**给定常量 2.5** ——
也就是说「这个 2.5 是不是这块版图算出来的」在平台里**无法回答**。

本模块给出第一条可复算的链路：

    版图几何 (w, g, h, εr)  ──闭式保角映射──▶  (C_air, C_d, ε_eff, Z0, n_eff)
                              │
                              └──▶  λ/4 谐振 f0 = c0 / (4·L·n_eff)   ← 与既有锚同口径

于是「设计输入 n_eff=2.5」第一次可以被**版图几何**回答（实测 0.2% 差异，门禁 D 组）。

═══════════════════════════ 三条硬边界（必读）═══════════════════════════
① **半反提，不是全反提**：`w` 从版图 `path.width_um` **真回提**；
   `g` 在现有版图里**没有共面间隙字段**（Transmon 的地建在 y=±3 µm 的**上下方**，
   不是共面），故 `g` 只能来自设计参数或 `ground_gap` 的**等效假设** ——
   返回值里必带 `gap_source`，调用方不得把它当成实测。
   🔴 **由此登记一条新缺口**：`transmon_cell` 的「CPW 馈线 + 上下地平面框」几何
   与 CPW 物理模型（**共面**地）不匹配 ⇒ 版图→参数反提在这一处只能是等效级。
② **不含导体厚度 / 不含表面阻抗 / 不含辐射**：本模块是**准静态**（∇·(ε∇φ)=0）解，
   无限薄导体、准 TEM。超导薄膜的动力学电感（K ≈ λ_L² 项）**未建模**。
③ **不加锚**（可锚性三问已做，结论见 `ANCHORABLE` 与 `why_not_anchored()`）：
   闭式本身可作 golden，但**找不到廉价的独立数值候选** ——
   均匀网格 FDM 在间隙处欠分辨（实测 g=6 µm 时 dx≈2.7 µm ⇒ 间隙仅 2 格，
   相对误差 55% 且**随网格加密不单调**），非均匀网格/分层格林函数成本远高于收益。
   如实登记为「能力层、不可锚」，而不是凑一个 tol=2% 的假锚。

红线：纯 stdlib + numpy · 零第三方 · 零 LLM · 不报能效/规模宣称。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ROLE",
    "ANCHORABLE",
    "PHYSICAL_CONSTANTS",
    "ellip_k",
    "cpw_closed_form",
    "cpw_from_path_element",
    "cpw_from_layout",
    "resonator_f0_ghz",
    "layout_to_resonator_signoff",
    "why_not_anchored",
    "run_selfchecks",
]

ROLE = ("D-217 · CPW 准静态场解 + 版图反提（能力层）—— 把『版图几何 → (C, ε_eff, Z0, n_eff)』"
        "接起来，补『版图 → 器件参数不可反提』断点的第一段（半反提：w 真回提，g 为等效输入）")

#: 🔴 可锚性裁决（负结果机器化）：不做锚，理由见 `why_not_anchored()`
ANCHORABLE = False

PHYSICAL_CONSTANTS = {
    "EPS0": 8.8541878128e-12,      # F/m
    "MU0": 1.25663706212e-06,      # H/m
    "C0": 299792458.0,             # m/s
}

#: 默认衬底（Si · 高阻）—— 与既有 CPW 锚的 n_eff 口径同源（n_eff=2.5 ⇒ εr≈11.45）
DEFAULT_EPS_R = 11.45
#: 默认衬底厚度（µm）：500 µm 高阻 Si 对 10 µm 级 CPW 近似"无限厚"
DEFAULT_H_UM = 500.0


# ═══════════════════ 完全椭圆积分 K(k)（AGM · 纯 numpy）═══════════════════
def ellip_k(k: float) -> float:
    """第一类完全椭圆积分 K(k)（模数 k ∈ [0,1)），AGM 迭代至机器精度。

    门禁 A3 核对：K(0)=π/2、K(1/√2)=1.8540746773013719（已知闭式）。
    """
    if not (0.0 <= k < 1.0):
        raise ValueError("ellip_k 要求 0 ≤ k < 1（模数），实际 %r" % (k,))
    a, b = 1.0, math.sqrt(max(0.0, 1.0 - k * k))
    for _ in range(80):
        a, b = 0.5 * (a + b), math.sqrt(a * b)
        if abs(a - b) < 1e-17:
            break
    return math.pi / (2.0 * a)


# ═══════════════════════════ 闭式：CPW 准静态 ═══════════════════════════
def cpw_closed_form(w_um: float, g_um: float, *,
                    h_um: Optional[float] = DEFAULT_H_UM,
                    eps_r: float = DEFAULT_EPS_R) -> Dict[str, Any]:
    """CPW 准静态闭式（Ghione–Naldi 保角映射 + 有限衬底厚度修正）。

    几何（µm）：`w_um` 中心导体宽 · `g_um` 共面间隙 · `h_um` 衬底厚（None ⇒ 无限厚）
    材料：`eps_r` 衬底相对介电常数（上半空间为真空 ε=1）

    返回（全部 F/m、Ω、无量纲）：
      C_air     真空（εr=1 时）单位长度电容 —— 上半真空 + 下半也真空
      C_d       实际介质下的单位长度电容
      eps_eff   有效介电常数 = C_d / C_air
      Z0        特征阻抗（Ω）
      n_eff     有效折射率 = √eps_eff（与既有 CPW 锚的 n_eff 同口径）
      v_ph      相速度 m/s
      k, k1     保角映射模数（可追责）
    """
    if not (w_um > 0.0):
        raise ValueError("w_um 必须 > 0，实际 %r" % (w_um,))
    if not (g_um > 0.0):
        raise ValueError("g_um 必须 > 0，实际 %r" % (g_um,))
    if not (eps_r >= 1.0):
        raise ValueError("eps_r 必须 ≥ 1，实际 %r" % (eps_r,))
    if h_um is not None and not (h_um > 0.0):
        raise ValueError("h_um 必须 > 0 或 None，实际 %r" % (h_um,))

    EPS0 = PHYSICAL_CONSTANTS["EPS0"]
    C0 = PHYSICAL_CONSTANTS["C0"]

    k = w_um / (w_um + 2.0 * g_um)
    kp = math.sqrt(max(0.0, 1.0 - k * k))
    Kr = ellip_k(k)
    Krp = ellip_k(kp)

    # 真空电容（两侧半空间都是真空时）
    c_air = 4.0 * EPS0 * Kr / Krp

    if h_um is None:
        # 无限厚衬底 ⇒ 半空间填充因子 1/2（对称近似，q = 1）
        q = 1.0
        k1 = None
    else:
        # 有限厚衬底：上半空间真空 + 下半空间 εr、厚 h
        k1 = (math.sinh(math.pi * w_um / (4.0 * h_um))
              / math.sinh(math.pi * (w_um + 2.0 * g_um) / (4.0 * h_um)))
        k1p = math.sqrt(max(0.0, 1.0 - k1 * k1))
        q = (Krp / Kr) * (ellip_k(k1) / ellip_k(k1p))

    eps_eff = 1.0 + 0.5 * (eps_r - 1.0) * q
    c_d = c_air * eps_eff
    # Z0 用**定义式**（准 TEM：L = ε0μ0/C_air ⇒ Z0 = 1/(c0·√(C_air·C_d))），
    # 该式在 εr=1 时严格给出 Z0·C_air·c0 ≡ 1；
    # 工程手册常用的 30π/√εeff·K(k')/K(k) 是同一量的近似（差 ~7e-4），
    # 两者并列以供交叉校验（门禁 A2 断言二者相对差 < 1e-3）。
    z0 = 1.0 / (C0 * math.sqrt(c_air * c_d))
    z0_30pi = (30.0 * math.pi / math.sqrt(eps_eff)) * (Krp / Kr)
    n_eff = math.sqrt(eps_eff)

    return {
        "w_um": float(w_um), "g_um": float(g_um),
        "h_um": (None if h_um is None else float(h_um)),
        "eps_r": float(eps_r),
        "k": k, "k1": k1,
        "C_air_F_per_m": c_air,
        "C_d_F_per_m": c_d,
        "eps_eff": eps_eff,
        "Z0_ohm": z0,
        "Z0_air_ohm": 1.0 / (C0 * c_air),
        "Z0_30pi_ohm": z0_30pi,
        "n_eff": n_eff,
        "v_ph_m_per_s": C0 / n_eff,
        # 代数恒等（任意介质）：Z0·√(C_air·C_d)·c0 ≡ 1（准 TEM 定义式下精确）
        "zc_product": z0 * math.sqrt(c_air * c_d) * C0,
        "note": ("准静态闭式（保角映射）；不含导体厚度/动力学电感/辐射；"
                 "几何为无限薄导体 + 上半真空 + 下半 εr"),
    }


# ═══════════════════════════ 版图反提（半反提）═══════════════════════════
def cpw_from_path_element(element: Dict[str, Any], *,
                          gap_um: Optional[float] = None,
                          h_um: Optional[float] = DEFAULT_H_UM,
                          eps_r: float = DEFAULT_EPS_R) -> Dict[str, Any]:
    """从**单条版图 path** 回提 `w`，再按给定/等效间隙求 CPW 参数。

    `gap_um=None` ⇒ 该 path 上**没有共面间隙信息**，拒绝猜测（返回 `ok=False`
    并说明原因）—— 这是"不假装全反提"的硬约束。
    """
    if not isinstance(element, dict) or element.get("kind") != "path":
        raise ValueError("只接受 kind='path' 的版图元素")
    w = element.get("width_um")
    if w is None:
        raise ValueError("path 元素缺 width_um，无法回提导体宽")
    out = {
        "w_um": float(w),
        "w_source": "layout.path.width_um",
        "gap_um": (None if gap_um is None else float(gap_um)),
        "gap_source": ("caller" if gap_um is not None else "MISSING"),
        "ok": gap_um is not None,
    }
    if gap_um is None:
        out["reason"] = ("版图 path 不含共面间隙字段（Transmon 的地建在 y=±gj 的上下方，"
                         "非共面）⇒ 间隙必须由调用方显式给出，不在此处猜")
        return out
    out.update(cpw_closed_form(float(w), float(gap_um), h_um=h_um, eps_r=eps_r))
    out.update({"w_source": "layout.path.width_um", "gap_source": "caller"})
    return out


def cpw_from_layout(elements: List[Dict[str, Any]], *,
                    net: str = "qubit",
                    gap_um: Optional[float] = None,
                    ground_gap_um: Optional[float] = None,
                    h_um: Optional[float] = DEFAULT_H_UM,
                    eps_r: float = DEFAULT_EPS_R) -> Dict[str, Any]:
    """从**整份版图元素表**挑出该 net 的馈线 path，回提 `w` 并出 CPW 参数。

    `gap_um` 优先；否则用 `ground_gap_um` 作**等效共面间隙**（`gap_source="ground_gap_equiv"`，
    显式标注为等效假设）；两者皆无 ⇒ `ok=False`。

    选中规则：`kind="path"` ∧ `net` 匹配 ∧ `layer` 为超导薄膜层（取最宽的 path 作馈线，
    因为 Transmon 单元里两臂等宽；若不等宽则报 `multi_width` 让调用方定夺）。
    """
    from lda_qeda.sc_layout import FILM  # 单一真源（超导薄膜层号）

    paths = [e for e in (elements or [])
             if isinstance(e, dict) and e.get("kind") == "path"
             and e.get("net", net) == net and e.get("layer") == FILM]
    if not paths:
        return {"ok": False, "reason": "版图中没有 net=%r 的超导薄膜 path" % net,
                "n_paths": 0}

    widths = sorted({round(float(e.get("width_um", -1.0)), 6) for e in paths})
    if len(widths) > 1:
        return {"ok": False,
                "reason": "该 net 的 path 宽不唯一 %s ⇒ 需调用方指定馈线" % (widths,),
                "n_paths": len(paths), "widths_um": widths}

    w = widths[0]
    if gap_um is not None:
        g, src = float(gap_um), "caller"
    elif ground_gap_um is not None:
        g, src = float(ground_gap_um), "ground_gap_equiv"
    else:
        return {"ok": False, "w_um": w, "n_paths": len(paths),
                "reason": "版图无共面间隙字段，且未给 gap_um / ground_gap_um ⇒ 不猜"}

    out = cpw_closed_form(w, g, h_um=h_um, eps_r=eps_r)
    out.update({
        "ok": True,
        "n_paths": len(paths),
        "w_source": "layout.path.width_um",
        "gap_source": src,
        "caveat": ("w 为真回提；g 为 %s ⇒ **半反提**（非实测、非全反提）；"
                   "Transmon 版图的地是上下平面框，与共面 CPW 模型存在几何不匹配"
                   % ("调用方输入" if src == "caller" else "ground_gap 等效"))
    })
    return out


# ══════════════════ 与既有 CPW 锚同口径：λ/4 谐振频率 ══════════════════
def resonator_f0_ghz(L_um: float, n_eff: float) -> float:
    """λ/4 谐振器基模频率（GHz）：f0 = c0 / (4·L·n_eff)。

    🔴 与既有 CPW 锚**同口径**（同一传输线谐振式），本模块只提供"n_eff 从哪来"，
    **不复述**该锚，也不新增锚。
    """
    C0 = PHYSICAL_CONSTANTS["C0"]
    if not (L_um > 0.0):
        raise ValueError("L_um 必须 > 0，实际 %r" % (L_um,))
    if not (n_eff >= 1.0):
        raise ValueError("n_eff 必须 ≥ 1，实际 %r" % (n_eff,))
    return (C0 / (4.0 * (L_um * 1e-6) * n_eff)) / 1e9


def layout_to_resonator_signoff(w_um: float, g_um: float, L_um: float, *,
                                h_um: Optional[float] = DEFAULT_H_UM,
                                eps_r: float = DEFAULT_EPS_R,
                                n_eff_design: float = 2.5,
                                tol_frac: float = 0.02) -> Dict[str, Any]:
    """端到端：几何 → n_eff(反提) → f0，并与**设计输入 n_eff** 对账。

    `n_eff_design` 取既有 CPW 锚的默认设计值（2.5 = Si 衬底典型）；
    `tol_frac` 是"设计输入是否被版图几何支持"的验收容差（默认 2%）。
    """
    cf = cpw_closed_form(w_um, g_um, h_um=h_um, eps_r=eps_r)
    f0_layout = resonator_f0_ghz(L_um, cf["n_eff"])
    f0_design = resonator_f0_ghz(L_um, n_eff_design)
    rel = abs(cf["n_eff"] - n_eff_design) / n_eff_design
    return {
        "verdict": "CONSISTENT" if rel <= tol_frac else "DRIFT",
        "n_eff_layout": cf["n_eff"],
        "n_eff_design": float(n_eff_design),
        "n_eff_rel_diff": rel,
        "tol_frac": float(tol_frac),
        "f0_layout_ghz": f0_layout,
        "f0_design_ghz": f0_design,
        "f0_rel_diff": abs(f0_layout - f0_design) / f0_design,
        "Z0_ohm": cf["Z0_ohm"],
        "eps_eff": cf["eps_eff"],
        "disclosure": ("n_eff_layout 由保角映射闭式从 (w,g,h,εr) 算出；"
                       "n_eff_design 是既有设计输入常量。二者一致 ≠ 器件实测"),
    }


def why_not_anchored() -> Dict[str, Any]:
    """**负结果机器化**：为什么本模块不立锚（可锚性三问 + 候选体检实测记录）。"""
    return {
        "anchorable": ANCHORABLE,
        "q1_exact_combinatorial": False,
        "q2_closed_form_as_candidate": ("闭式只能作 golden；候选必须是**独立数值法**"
                                        "（准静态 ∇·(ε∇φ)=0 的离散解）"),
        "q3_threshold_or_mc": False,
        "candidate_probe": {
            "method": "均匀网格有限差分 + SOR + 能量法求 C（2026-10-23 原型实测）",
            "observed": ("w=10,g=6 µm（Si）时 C_FDM 与闭式 C_d 相对误差："
                         "dx=3.33 µm ⇒ 55%；dx=2.22 µm ⇒ 40%；dx=2.67 µm ⇒ 56%"
                         "（随加密**不单调**）"),
            "why_fails": ("CPW 电容集中在间隙处且导体边缘场奇异（1/√r），"
                          "均匀网格在 g=6 µm 下只有 2–3 个格 ⇒ 离散化误差主导，"
                          "且不随 h→0 单调收敛（域截断与分辨率两项互相抵消）"),
            "alternatives_cost": ("非均匀(拉伸)网格 / 分层介质格林函数的边界元或谱方法"
                                 "可做到 1e-3 量级，但实现与维护成本远高于本层收益 ⇒ "
                                 "**不做假锚**（不拿 tol=2% 凑数）"),
        },
        "decision": ("**能力层、不可锚**：把「版图→n_eff→f0」链路做出来并可机器复核，"
                     "但不新增账本条目"),
        "revisit_condition": ("若将来引入**分层介质格林函数 + 谱方法/Galerkin** 的独立候选"
                             "（目标残差 ≤1e-4），可重新评估把 ε_eff 或 C_air 立锚"),
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。全部为闭式/极限/代数恒等断言，无落盘、无子进程。"""
    res: List[Tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        res.append((name, bool(cond)))

    # ① 50 Ω 设计惯例（规格锚：Si 上 w=10/g=6 的工程典型）
    cf = cpw_closed_form(10.0, 6.0, h_um=None, eps_r=11.45)
    chk("① w=10/g=6/Si(无限厚) ⇒ Z0∈[50,52] Ω 且 εeff∈[6.2,6.25]",
        50.0 <= cf["Z0_ohm"] <= 52.0 and 6.2 <= cf["eps_eff"] <= 6.25)

    # ② 准 TEM 代数恒等（任意介质）+ 与 30π 工程形式的固有偏差
    fin = cpw_closed_form(10.0, 6.0, h_um=500.0, eps_r=11.45)
    dev30 = abs(fin["Z0_30pi_ohm"] - fin["Z0_ohm"]) / fin["Z0_ohm"]
    chk("② Z0·√(C_air·C_d)·c0 ≡ 1（两参数组残差 <1e-12）∧ 30π 形式偏差 ∈(1e-4,2e-3)",
        abs(cf["zc_product"] - 1.0) < 1e-12
        and abs(fin["zc_product"] - 1.0) < 1e-12
        and 1e-4 < dev30 < 2e-3)

    # ③ K 的两点闭式
    chk("③ K(0)=π/2 ∧ K(1/√2)=1.8540746773013719",
        abs(ellip_k(0.0) - math.pi / 2) < 1e-15
        and abs(ellip_k(1.0 / math.sqrt(2.0)) - 1.8540746773013719) < 1e-13)

    # ④ εr=1 ⇒ εeff=1、n_eff=1
    vac = cpw_closed_form(10.0, 6.0, h_um=None, eps_r=1.0)
    chk("④ εr=1 ⇒ εeff=1 且 n_eff=1（真空极限）",
        abs(vac["eps_eff"] - 1.0) < 1e-12 and abs(vac["n_eff"] - 1.0) < 1e-12)

    # ⑤ h→∞ 极限：有限厚公式趋近无限厚公式
    lim = cpw_closed_form(10.0, 6.0, h_um=1e7, eps_r=11.45)
    chk("⑤ h→∞ 时有限厚 εeff → 无限厚 (1+εr)/2（相对差 <1e-4）",
        abs(lim["eps_eff"] - 0.5 * (1.0 + 11.45)) / (0.5 * (1.0 + 11.45)) < 1e-4)

    # ⑥ 单调性：w↑ ⇒ Z0↓；εr↑ ⇒ εeff↑ 且 Z0↓
    z_lo = cpw_closed_form(6.0, 6.0, h_um=None)["Z0_ohm"]
    z_hi = cpw_closed_form(20.0, 6.0, h_um=None)["Z0_ohm"]
    e_lo = cpw_closed_form(10.0, 6.0, h_um=None, eps_r=4.0)
    e_hi = cpw_closed_form(10.0, 6.0, h_um=None, eps_r=11.45)
    chk("⑥ 单调性：w↑⇒Z0↓ ∧ εr↑⇒εeff↑ 且 Z0↓",
        z_hi < z_lo and e_hi["eps_eff"] > e_lo["eps_eff"] and e_hi["Z0_ohm"] < e_lo["Z0_ohm"])

    # ⑦ 版图反提：从 Transmon 版图真取到 w=0.5
    from lda_qeda.sc_layout import transmon_cell
    lay = cpw_from_layout(transmon_cell(), ground_gap_um=1.0)
    chk("⑦ 版图反提取到 w=0.5 µm 且 gap_source=ground_gap_equiv（半反提标注）",
        lay["ok"] is True and abs(lay["w_um"] - 0.5) < 1e-12
        and lay["gap_source"] == "ground_gap_equiv" and "半反提" in lay["caveat"])

    # ⑧ 不假装全反提：无 gap 时 ok=False 且给原因
    miss = cpw_from_layout(transmon_cell())
    chk("⑧ 无共面间隙输入 ⇒ ok=False（不猜）",
        miss["ok"] is False and "不猜" in miss["reason"])

    # ⑨ 端到端对账：反提 n_eff vs 设计 2.5（容差 2%）
    so = layout_to_resonator_signoff(10.0, 6.0, 4000.0, h_um=None)
    chk("⑨ 反提 n_eff 与设计输入 2.5 一致（相对差 <2%，判 CONSISTENT）",
        so["verdict"] == "CONSISTENT" and so["n_eff_rel_diff"] < 0.02)

    # ⑩ λ/4 同口径：f0 与 n_eff 成反比
    f1 = resonator_f0_ghz(4000.0, 2.5)
    f2 = resonator_f0_ghz(4000.0, 5.0)
    chk("⑩ f0 ∝ 1/n_eff 且 L=4000 µm·n=2.5 ⇒ f0≈7.5 GHz",
        abs(f2 - f1 / 2.0) < 1e-12 and 7.4 < f1 < 7.6)

    # ⑪ 负结果机器化：ANCHORABLE=False 且三问齐备 + 候选实测记录
    w = why_not_anchored()
    chk("⑪ 不可锚裁决齐备（anchorable=False + 三问 + 候选实测 + 重评条件）",
        w["anchorable"] is False and "candidate_probe" in w
        and "revisit_condition" in w and w["q1_exact_combinatorial"] is False)

    # ⑫ 护栏：非法输入四例
    guard = 0
    for bad in (lambda: cpw_closed_form(0.0, 6.0),
                lambda: cpw_closed_form(10.0, 0.0),
                lambda: cpw_closed_form(10.0, 6.0, eps_r=0.5),
                lambda: resonator_f0_ghz(0.0, 2.5),
                lambda: ellip_k(1.0)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑫ 护栏：五例非法输入均抛 ValueError", guard == 5)

    ok = all(v for _, v in res)
    if verbose:
        for n, v in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


if __name__ == "__main__":
    print("cpw_quasi_static 自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
