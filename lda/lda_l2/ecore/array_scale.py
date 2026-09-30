"""LDA ecore · E9 规模压力与诚实对标（千级阵列版图）（D-159）。

**为什么需要它（E9 逼出的平台接缝）**：
E6 的 `crossbar_array` 会**物化整阵列**（N²·7 + 2N 个几何对象），E7 的后仿用**稠密 MNA**
（未知量 ~2NM+N，矩阵 O((NM)²)）——两者都只到 **N≈32**。要做到**千级阵列**必须换算法：
  · 版图：**层次化**（cell + AREF）· 元素数 **O(N)**、不物化 N²；
  · 后仿：行线 IR drop 是**一维链**问题 ⇒ **三对角 O(N)** 求解，可直上 N=1024+。
E9 把「规模」这件事从「能画 8×8」推进到「**千级阵列的规模律与可及上界**」，并做**同族维度**诚实对标。

**本模块做什么**：
  1. **O(N) 行线 IR-drop 求解**（三对角 Thomas）：`V_{k-1} − (2+g·r)V_k + V_{k+1} = 0`，末端
     `V_{n-2} − (1+g·r)V_{n-1} = 0`；返回电压剖面 / 末端压降 / **平均相对误差**（= MVM 输出误差）；
  2. **规模律**：元素数 / 足迹 / 线长 / R / C / Elmore / IR drop / 失配 σ —— 逐规模闭式 + 实算；
  3. **层次化 GDS**：cell + **1 条 AREF** + O(N) 布线 ⇒ 千级阵列出图；压缩比 = flat/hier；
  4. **可及规模上界**：给定误差预算（如 5%）反解最大 N（二分）；
  5. **同族维度诚实对标**（沿用 E4 体例）：landmark 照录公开来源 · `LDA_CAPABILITIES` **不得含**
     TOPS/TOPS-W/fJ-op · `NON_CLAIMED` 明写「不同层级、不做数值超越比较」。

🔴 **诚实边界**：
  - 1D 行线模型**忽略列线电阻**（列线贡献为二阶项）——在校核规模内与 E7 的 2D 稠密 MNA 对拍一致，
    外推时须记住该省略（已写入披露）。
  - 工艺参数（ρ/金属厚度/ILD/失配系数）为**公开典型量级**，**非 Foundry PDK**。
  - landmark 为**公开来源照录（未在 LDA 上验证）**，只做**同族维度**（架构族 / 规模量级）对照。
  - 千级阵列是**设计期版图与规模律**，**非流片**；不报任何实测芯片指标。
  - 纯 numpy/标准库 · LLM 不进判决路径 · 零商业 EDA 依赖。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from lda_l2 import gds_export as G
from lda_l2.ecore import elayers as EL
from lda_l2.ecore import layout as LY
from lda_l2.ecore import mismatch as MM
from lda_l2.ecore import parasitic as PA
from lda_l2.ecore.mosfet import NmosParams

# ---------------------------------------------------------------------------
# 公开 landmark（同族维度：架构族 / 规模量级）· 照录 · 未验证
# ---------------------------------------------------------------------------
LANDMARKS = [
    {"name": "Mythic M1076", "family": "analog CIM / MVM 交叉阵列",
     "dimension": "architecture_family", "value": 76, "unit": "tiles",
     "source": "mythic.ai（公开资料照录）", "verified": False,
     "note": "模拟存内计算；**不在本模块做数值比较**（层级不同：流片芯片 vs 设计工具链）"},
    {"name": "模拟 CIM 阵列规模（文献通例）", "family": "analog CIM crossbar",
     "dimension": "array_scale_class", "value": 256, "unit": "rows×cols 量级",
     "source": "公开文献通行量级（照录·量级坐标）", "verified": False,
     "note": "仅作**规模量级**坐标；具体器件/工艺/指标因论文而异，不逐项比对"},
]

LDA_CAPABILITIES = [
    "从版图几何生成 N×N 1T 交叉阵列，**层次化 AREF GDS**（元素数 O(N)、不物化 N²）",
    "一维三对角 IR-drop 求解（O(N)）⇒ 千级阵列仍可算，给出电压剖面与输出相对误差",
    "三重规模律：IR drop 随 N **超线性**（近 N²）· 失配输出 σ ∝ **1/√N** · 版图面积 ∝ **N²**",
    "按误差预算反解**可及规模上界**（在公开典型工艺参数下，被动单端行线驱动的 IR-drop 天花板）",
]

NON_CLAIMED = [
    "不与商业模拟 CIM 芯片做 TOPS / TOPS-W / fJ/op 数值比较（LDA 是设计&验证工具链，非流片芯片）",
    "不与 landmark 在做不同层级（工具链 vs 芯片）的数值超越比较",
    "landmark 为公开来源**照录·未在 LDA 上验证**，仅作同族维度坐标",
]

SCALE_DISCLOSURE = {
    "role": "E9 = 千级阵列规模压力（层次化版图 + O(N) IR-drop 求解）+ 同族维度诚实对标",
    "algorithms": "版图：cell+AREF 层次化（O(N)）；后仿：一维三对角 Thomas（O(N)）",
    "omission": "1D 行线模型**忽略列线电阻**（二阶项）；在校核规模内与 E7 的 2D 稠密 MNA 对拍一致",
    "process": "工艺参数为**公开典型量级占位（非 Foundry PDK）**",
    "landmarks": "landmark 为**公开来源照录·未验证**，只作同族维度（架构族/规模量级）坐标",
    "honest": "千级阵列是**设计期版图与规模律**，非流片；不报任何实测芯片指标",
    "red_line": "纯 numpy/标准库 · LLM 不进判决路径 · 零商业 EDA 依赖",
}

_N_CELL_ELEMS = 7           # E6 的 1T 单元元素数（DIFF_D/DIFF_S/POLY/CONT×2/M1 焊垫/VIA1）


# ---------------------------------------------------------------------------
# ① 规模闭式：元素数 / 压缩比
# ---------------------------------------------------------------------------
def elements_flat(n: int, m: int) -> int:
    """**物化**整阵列的元素数（E6 `crossbar_array` 的规模）：n·m·7 + n + m。"""
    return n * m * _N_CELL_ELEMS + n + m


def elements_hierarchical(n: int, m: int) -> int:
    """**层次化** GDS 的元素记录数：cell(7) + 1 条 AREF + n 行线 + m 列线 = **O(N)**。"""
    return _N_CELL_ELEMS + 1 + n + m


def compression_ratio(n: int, m: int) -> float:
    """层次化压缩比 = flat / hier。

    🔴 **∝ N（不是 ∝ N²）**：flat = 7N²+2N、hier = 8+N+M ⇒ 比值 ≈ 7N/2 ⇒ **随 N 线性增**
    （N ×4 ⇒ 压缩比 ×4，渐近）。千级阵列实测 46×(16²) → 212×(64²) → 883×(256²) → 3571×(1024²)。
    """
    return elements_flat(n, m) / float(elements_hierarchical(n, m))


# ---------------------------------------------------------------------------
# ② 层次化 GDS（O(N) · 不物化 N²）
# ---------------------------------------------------------------------------
def hierarchical_gds(n: int, m: int,
                     params: Optional[Dict[str, float]] = None,
                     path: Optional[str] = None) -> Dict:
    """千级阵列的**层次化** GDS：cell + 1 条 AREF + O(N) 布线。**不物化 N² 单元。**"""
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    cell = LY.crosspoint_cell("row0", "col0", "wg_0_0", p)
    lines = LY.array_lines(n, m, p)
    top = [G.aref("XB_CELL", (0.0, 0.0), p["pitch_x_um"], p["pitch_y_um"], m, n,
                  layer=EL.L_DIFF)]
    for d in lines:
        top.append(G.path(d["layer"], d["width_um"], d["points_um"]))
    data = G.gds_library("LDA_ECORE_SCALE",
                         {"XB_CELL": [LY._desc_to_gds(d) for d in cell], "TOP": top})
    if path:
        G.write_gds(path, data)
    parsed = G.parse_gds(data)
    return {"gds_bytes": data, "n_bytes": len(data),
            "n_top_records": len(top), "n_cell_elements": len(cell),
            "n_lines": len(lines),
            "elements_hier": elements_hierarchical(n, m),
            "elements_flat": elements_flat(n, m),
            "compression": compression_ratio(n, m),
            "n_structures": parsed.get("n_structures"),
            "layers": sorted({d["layer"] for d in cell} | {d["layer"] for d in lines})}


def expanded_element_count(gds_bytes: bytes, max_expand: int = 64) -> Dict:
    """展开 AREF 后的元素数核算。

    N ≤ max_expand 时**真展开**（`parse_gds_polygons(expand_refs=True)`）逐元素核对；
    更大规模时用 **AREF 元数据**（colrow × cell 元素数 + top 记录）**结构性核算** ——
    🔴 展开 N² 个几何对象在 N≫64 时内存不可行（这正是要层次化的原因），故分级处理并**明示**。
    """
    parsed = G.parse_gds_polygons(gds_bytes, expand_refs=False)
    structs = parsed["structures"]
    top = parsed["top_structures"][0] if parsed["top_structures"] else None
    aref = [e for s in structs.values() for e in s if e.get("kind") == "aref"]
    n_cell = len(structs.get("XB_CELL", []))
    n_lines = len([e for e in structs.get(top, []) if e.get("kind") in ("path", "boundary")]) \
        if top else 0
    nx, ny = (aref[0].get("colrow") or (1, 1)) if aref else (1, 1)
    structural = int(nx) * int(ny) * n_cell + n_lines
    out = {"structural_count": structural, "n_aref": len(aref),
           "colrow": [int(nx), int(ny)], "n_cell_elements": n_cell,
           "n_lines_top": n_lines, "expanded": False}
    if max(nx, ny) <= int(max_expand):
        exp = G.parse_gds_polygons(gds_bytes, expand_refs=True)
        tot = sum(len(exp["structures"][s]) for s in exp["top_structures"])
        out.update({"expanded": True, "expanded_count": tot,
                    "match": tot == structural})
    return out


# ---------------------------------------------------------------------------
# ③ O(N) 行线 IR-drop（三对角）
# ---------------------------------------------------------------------------
def row_line_profile(n: int, r_seg: float, g: float, v_in: float = 1.0) -> Dict:
    """行线电压剖面（**O(N) 三对角 Thomas**）。

    节点 k=0..n−1：串联 r_seg、每个节点并联交叉点电导 g（列端理想虚地）。
      · 内部：`V_{k−1} − (2 + g·r)·V_k + V_{k+1} = 0`
      · 末端（末尾节点仍有 g、其后无节点）：`V_{n−2} − (1 + g·r)·V_{n−1} = 0`
      · 首端：`V_0 = v_in`
    返回 {voltages, far_end_v, far_drop_v, far_drop_rel, avg_rel_err, gr, alpha}。

    🔴 **两个口径别混**（E9 实测踩过）：
      · `far_drop_rel` = 1 − V_{n−1}/v_in —— **最坏列**（末端）压降，**对应 E7 的 `max_rel_err`**；
      · `avg_rel_err` = 1 − mean(V)/v_in —— **全列平均**，即 MVM 的平均输出误差。
    两者不相等（一维链上电压单调降 ⇒ 末端压降 ≥ 平均压降）。对拍 2D 必须用前者。
    """
    if n <= 0:
        raise ValueError("n 须 > 0")
    if g <= 0.0 or r_seg < 0.0:
        raise ValueError("g 须 > 0、r_seg 须 ≥ 0")
    v_in = float(v_in)
    if n == 1 or r_seg == 0.0:
        vs = np.full(n, v_in)
        return {"voltages": vs, "far_end_v": v_in, "far_drop_v": 0.0,
                "far_drop_rel": 0.0, "avg_rel_err": 0.0, "gr": g * r_seg, "alpha": 0.0}

    gr = g * float(r_seg)
    lower = np.zeros(n); diag = np.zeros(n); upper = np.zeros(n); rhs = np.zeros(n)
    diag[0], rhs[0] = 1.0, v_in
    for k in range(1, n - 1):
        lower[k], diag[k], upper[k] = 1.0, -(2.0 + gr), 1.0
    lower[n - 1], diag[n - 1] = 1.0, -(1.0 + gr)

    cp = np.zeros(n); dp = np.zeros(n)
    cp[0] = upper[0] / diag[0]; dp[0] = rhs[0] / diag[0]
    for k in range(1, n):
        m_ = diag[k] - lower[k] * cp[k - 1]
        cp[k] = upper[k] / m_
        dp[k] = (rhs[k] - lower[k] * dp[k - 1]) / m_
    x = np.zeros(n)
    x[-1] = dp[-1]
    for k in range(n - 2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k + 1]

    alpha = float(np.arccosh(1.0 + gr / 2.0)) if gr > 0 else 0.0
    return {"voltages": x, "far_end_v": float(x[-1]),
            "far_drop_v": v_in - float(x[-1]),
            "far_drop_rel": (v_in - float(x[-1])) / v_in if v_in else 0.0,
            "avg_rel_err": 1.0 - float(np.mean(x)) / v_in if v_in else 0.0,
            "gr": gr, "alpha": alpha}


def ir_drop_scaling(sizes: Sequence[int], r_seg: float, g: float,
                    v_in: float = 1.0) -> List[Dict]:
    """逐规模算 IR drop（O(N) 模型）。"""
    return [{"n": int(s), **{k: v for k, v in row_line_profile(int(s), r_seg, g, v_in).items()
                             if k != "voltages"}} for s in sizes]


def max_scale_for_budget(budget_rel_err: float, r_seg: float, g: float,
                         hi: int = 4096) -> int:
    """给定输出相对误差预算，二分反解**可及最大行数 N**（O(log hi) 次 O(N) 求解）。"""
    if row_line_profile(2, r_seg, g)["avg_rel_err"] > budget_rel_err:
        return 1
    lo, hi_i = 2, int(hi)
    if row_line_profile(hi_i, r_seg, g)["avg_rel_err"] <= budget_rel_err:
        return hi_i
    while lo < hi_i - 1:
        mid = (lo + hi_i) // 2
        if row_line_profile(mid, r_seg, g)["avg_rel_err"] <= budget_rel_err:
            lo = mid
        else:
            hi_i = mid
    return lo


# ---------------------------------------------------------------------------
# ④ 失配规模律（复用 E8 的 Pelgrom）
# ---------------------------------------------------------------------------
def sigma_cell_rel(w_um: float, l_um: float, vg: float,
                   params: Optional[NmosParams] = None,
                   process: Optional[Dict[str, float]] = None) -> float:
    """单元相对电导误差 σ_δ = √(σ_β² + (σ_ΔVth/(Vg−Vth0))²)（Pelgrom 闭式 · 单一真源 = E8）。"""
    p = params or NmosParams(w_over_l=float(w_um) / float(l_um))
    sig_vth = MM.pelgrom_sigma_vth_mv(w_um, l_um, process) / 1000.0
    sig_beta = MM.pelgrom_sigma_beta_rel(w_um, l_um, process)
    vov = float(vg) - p.vth0
    if vov <= 0:
        raise ValueError("须 Vg > Vth0")
    return float(np.hypot(sig_beta, sig_vth / vov))


def sigma_out_rel(n: int, w_um: float, l_um: float, vg: float,
                  params: Optional[NmosParams] = None,
                  process: Optional[Dict[str, float]] = None) -> float:
    """输出相对误差 σ = σ_δ/√n（E8 已 MC 验证的 **1/√N 求和平均律**）。"""
    return sigma_cell_rel(w_um, l_um, vg, params, process) / float(n) ** 0.5


# ---------------------------------------------------------------------------
# ⑤ 规模扫描
# ---------------------------------------------------------------------------
def array_scale_sweep(sizes: Sequence[int],
                      params: Optional[Dict[str, float]] = None,
                      vg: float = 2.5,
                      proc: Optional[Dict[str, float]] = None) -> List[Dict]:
    """逐规模的**三重规模律**：版图（元素/足迹/压缩比/GDS）+ 寄生（R/C/τ）+ IR drop + 失配。"""
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    out: List[Dict] = []
    for s in sizes:
        n = m = int(s)
        ap = PA.array_parasitics(n, m, p, proc)
        nmos = NmosParams(w_over_l=p["w_um"] / p["l_um"])
        k = nmos.kp * nmos.w_over_l
        g = k * (vg - nmos.vth0)
        ir = row_line_profile(n, ap["r_row_seg_ohm"], g)
        fw, fh = LY.array_footprint(n, m, p)
        out.append({
            "n": n, "m": m,
            "elements_flat": elements_flat(n, m),
            "elements_hier": elements_hierarchical(n, m),
            "compression": compression_ratio(n, m),
            "footprint_um": [fw, fh],
            "footprint_mm2": fw * fh * 1e-6,
            "row_len_um": fw, "col_len_um": fh,
            "r_row_seg_ohm": ap["r_row_seg_ohm"],
            "R_row_total_ohm": ap["R_row_total_ohm"],
            "tau_row_s": ap["tau_row_s"],
            "g_s": g, "gr": ir["gr"],
            "ir_far_drop_rel": ir["far_drop_rel"],
            "ir_avg_rel_err": ir["avg_rel_err"],
            "mismatch_sigma_rel": sigma_out_rel(n, p["w_um"], p["l_um"], vg, nmos, proc),
        })
    return out


# ---------------------------------------------------------------------------
# ⑥ 诚实对标
# ---------------------------------------------------------------------------
def honest_comparison() -> Dict:
    """同族维度诚实对标：只列**可比维度**，并把不可比维度显式声明。"""
    return {
        "comparable_dimensions": ["架构族（模拟 CIM / MVM 交叉阵列）",
                                  "规模量级（阵列行×列量级）"],
        "not_comparable": list(NON_CLAIMED),
        "landmarks": LANDMARKS,
        "lda_capabilities": LDA_CAPABILITIES,
    }


def honest_boundary_ok() -> bool:
    """护栏：`LDA_CAPABILITIES` **不得**含 TOPS / TOPS-W / fJ/op 等只有实测芯片才有的指标。"""
    blob = " ".join(LDA_CAPABILITIES).upper()
    banned = ("TOPS", "TOPS/W", "TOPS-W", "FJ/OP", "FJ/OP", "OP/S", "OPS/W")
    return not any(b in blob for b in banned)


# ---------------------------------------------------------------------------
# 自检（常驻断言）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    msgs: List[Tuple[str, bool]] = []

    def chk(name: str, cond, detail: str = "") -> bool:
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True

    # ① 元素数闭式 + 压缩比
    ok &= chk("① 元素数：flat=N²·7+2N · hier=7+1+2N（O(N)）",
              elements_flat(8, 8) == 64 * 7 + 16
              and elements_hierarchical(8, 8) == 7 + 1 + 16
              and elements_hierarchical(1024, 1024) == 7 + 1 + 2048)

    # ② 1D 三对角 ≡ E7 的 2D 稠密 MNA（列线电阻置零）
    # 🔴 必须比「最坏列压降 vs E7 的 max_rel_err」；拿 1D 的**平均**误差去比会差 ~35%
    #    （那是两个不同口径，不是模型错 —— E9 实测踩过并在此钉住）。
    vs = []
    for n in (4, 8, 16):
        nn = NmosParams(w_over_l=1.20 / 0.30)
        g = nn.kp * nn.w_over_l * (2.5 - nn.vth0)
        ap = PA.array_parasitics(n, n)
        r1 = row_line_profile(n, ap["r_row_seg_ohm"], g)["far_drop_rel"]
        r2 = PA.ir_drop_report(n, n, np.full((n, n), g), [1.0] * n,
                               ap["r_row_seg_ohm"], 0.0)["max_rel_err"]
        vs.append(abs(r1 - r2) / max(r2, 1e-12))
    ok &= chk("② 1D 三对角 ≡ E7 的 2D 稠密 MNA（列线 R=0 · **最坏列**口径）",
              max(vs) < 1e-9, f"最大相对差 {max(vs):.2e}")
    # ②b 两口径的相对关系：末端压降 ≥ 平均压降（一维链电压单调降）
    pr_ = row_line_profile(8, ap["r_row_seg_ohm"], g)
    ok &= chk("②b far_drop_rel ≥ avg_rel_err（末端 vs 全列平均，两口径不同）",
              pr_["far_drop_rel"] > pr_["avg_rel_err"] > 0.0,
              f"{pr_['far_drop_rel']:.6f} ≥ {pr_['avg_rel_err']:.6f}")

    # ③ 层次化 GDS：展开 ≡ flat（N ≤ 64 真展开）
    h = hierarchical_gds(16, 16)
    ex = expanded_element_count(h["gds_bytes"], max_expand=64)
    ok &= chk("③ AREF 展开元素数 ≡ flat 闭式（16×16 真展开核对）",
              ex["expanded"] and ex["match"]
              and ex["expanded_count"] == elements_flat(16, 16),
              f"展开 {ex.get('expanded_count')} vs flat {elements_flat(16, 16)}")
    h2 = hierarchical_gds(256, 256)
    ex2 = expanded_element_count(h2["gds_bytes"], max_expand=64)
    ok &= chk("④ 千级阵列（256²）结构性核算 = flat 闭式（不展开，O(N) 出图）",
              (not ex2["expanded"]) and ex2["structural_count"] == elements_flat(256, 256),
              f"结构 {ex2['structural_count']} vs flat {elements_flat(256, 256)}")

    # ⑤ IR drop 规模律：超线性（近 N²）
    ap = PA.array_parasitics(32, 32)
    nn = NmosParams(w_over_l=1.20 / 0.30)
    g = nn.kp * nn.w_over_l * (2.5 - nn.vth0)
    e8 = row_line_profile(8, ap["r_row_seg_ohm"], g)["avg_rel_err"]
    e16 = row_line_profile(16, ap["r_row_seg_ohm"], g)["avg_rel_err"]
    e32 = row_line_profile(32, ap["r_row_seg_ohm"], g)["avg_rel_err"]
    ok &= chk("⑤ IR drop 随 N 单调增且**超线性**（近 N²）",
              e8 < e16 < e32 and e16 / e8 >= 3.0 and e32 / e16 >= 3.0,
              f"{e8:.5f}→{e16:.5f}→{e32:.5f}")

    # ⑥ 足迹/线长 O(N²)
    f1 = LY.array_footprint(16, 16)
    f2 = LY.array_footprint(32, 32)
    ok &= chk("⑥ 阵列面积随 N 单调增（版图 O(N²)）",
              f2[0] > f1[0] and f2[1] > f1[1] and abs(f2[0] / f1[0] - 2) < 0.2)

    # ⑦ 可及规模上界（误差预算反解）
    n5 = max_scale_for_budget(0.05, ap["r_row_seg_ohm"], g)
    n1 = max_scale_for_budget(0.01, ap["r_row_seg_ohm"], g)
    ok &= chk("⑦ 可及规模上界：预算越紧 ⇒ 最大 N 越小",
              n1 < n5 and n5 > 1, f"5% 预算 → N≤{n5} · 1% 预算 → N≤{n1}")

    # ⑧ 失配 σ ∝ 1/√N（复用 E8）
    s16 = sigma_out_rel(16, 1.20, 0.30, 2.5)
    s64 = sigma_out_rel(64, 1.20, 0.30, 2.5)
    ok &= chk("⑧ 失配输出 σ ∝ 1/√N（N ×4 ⇒ σ 减半）", abs(s64 - s16 / 2.0) < 1e-15)

    # ⑨ 诚实护栏
    ok &= chk("⑨ 诚实护栏：LDA_CAPABILITIES 无 TOPS/TOPS-W/fJ-op", honest_boundary_ok())

    # ⑩ 千级阵列可出图（1024² 层次化 GDS 真生成）
    h3 = hierarchical_gds(1024, 1024)
    ok &= chk("⑩ 1024×1024 层次化 GDS 真生成（O(N) · 压缩比 ≫1）",
              h3["n_bytes"] > 0 and h3["compression"] > 1000,
              f"{h3['n_bytes']} B · 压缩比 {h3['compression']:.0f}×")

    if verbose:
        for nm, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {nm}")
    return bool(ok)
