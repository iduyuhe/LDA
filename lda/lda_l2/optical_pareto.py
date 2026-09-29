# -*- coding: utf-8 -*-
"""光域 Pareto：MAC 吞吐 / 面积 / 光损耗 / 精度 的联合权衡（P6 · T6.1 · 系统级）。

口径 = **光域**。

🔴 诚实边界（禁止事后补票；与既有拒绝同源，本模块**不新增越界项**）：
  · **不判决能效**（`pJ/bit` / `TOPS/W` 中依赖电域 SerDes/TIA/DSP 的部分）。该量由电域主导，
    LDA 无电域锚 ⇒ 拿光域功率去比会让复现值低数个数量级、**恒过**（必假绿）。
    既有同源拒绝：`lda_design/cpo_engines.py:26` · `lda_l2/golden_product_benchmarks.py:941`
    · `lda_l2/innovation_market.py:1641` · `lda_harness/proposal_compiler.py:905`
    （并由 `run_system_types_smoke.py:108` 钉成判据）。本模块以 `assert_no_energy_metrics()`
    （**键名扫描**）把该边界机器化。
  · **吞吐是算术计数**（`K·N²` MACs/pass），**不是**实测吞吐，也不是「已实现的算力」。
  · **面积是版图 bbox 口径**（单排 1D），与 OIF/UCIe 的 **2D 凸点阵列**口径**不可直接比较**。
  · **损耗只含网格内路径 IL**（复用 U7 的 `il_db` 模型），**不含** demux/mux、光纤耦合、
    调制器与探测器损耗 ⇒ 是**下界**，不是链路预算。
  · **精度取自 U4 已签核后端**（`ring_weight_bank`），为**平台常数**，在本模块内**不随 N/K 变化**
    —— 本模块**拒绝发明**「精度 ↔ N」的映射（无锚可依）。

面积轴的**两种架构**（不可混为一谈；U1 = v0.9.122 实测 `area_ratio_vs_naive = 1/K`）：
  · `arch="shared"`（U1 共享网格 · 波长作并行维）：`K` 个波长**共享同一 N×N 网格**
    ⇒ 面积 ≈ 单面（**与 K 无关**），代价 = 波长复用必须**移出网格平面**（由 demux/mux 承担）。
  · `arch="tiled"`（块分解 · 每波长独立一平面，即 U1 之前的形态）：面积 = `K × 单面`
    ⇒ **面积 ∝ K**；收益 = 每面可独立布局/独立签核。
  ⇒ **两者的取舍是真实架构选择**，本模块两轴并列报告，不得只报有利的那一半。

复用对象（全部已在 CI core 内签核）：
  `lda_l2.loss_aware_compile`（U7 · v0.9.126）`il_db` / `rail_geometry` / 工艺常数
  `lda_layout.mesh_pnr`（主权 P&R）`build_mesh_pnr` / `dft_matrix`
  `lda_layout.wdm_shared_mesh_pnr`（U1 · v0.9.122）`build_wdm_shared_mesh_pnr`
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from lda_layout.mesh_pnr import build_mesh_pnr, dft_matrix
from lda_layout.wdm_shared_mesh_pnr import build_wdm_shared_mesh_pnr
from lda_l2.loss_aware_compile import (
    ALPHA_PROP_DEFAULT,
    ALPHA_TAP_DEFAULT,
    GAP_DEFAULT,
    RAIL_PITCH_DEFAULT,
    il_db,
    rail_geometry,
)

# ---------------------------------------------------------------------------
# 1) 诚实边界（机器可查）
# ---------------------------------------------------------------------------
OPTICAL_PARETO_DISCLOSURE: Dict[str, str] = {
    "scope": "只回答**光域**的量：MAC 吞吐（算术计数）/ 面积（版图 bbox）/ 网格内路径 IL / 平台精度。",
    "not_energy": "🔴 **不判决能效**（pJ/bit · TOPS/W 中依赖电域的部分）—— 电域主导，LDA 无电域锚，"
                  "复现值会低数个数量级导致恒过（必假绿）。本模块**零能效数字**。",
    "throughput_is_count": "吞吐 = K·N² MACs/pass，是**算术计数**，不是实测吞吐、不代表已实现算力。",
    "area_is_layout_bbox": "面积 = 版图实测 `footprint_um2`（单排 1D 海岸线口径），"
                           "与 OIF/UCIe 的 2D 凸点阵列口径不可直接比较（公开引用须标注口径）。",
    "area_two_architectures": "面积轴按**架构**分记：`shared`（U1 共享网格，面积≈单面、与 K 无关；"
                              "代价 = 波长复用移出网格平面）vs `tiled`（每波长独立面，面积 ∝ K）。"
                              "两者不可混为一谈，禁止只报有利的一半。",
    "loss_is_lower_bound": "损耗只含**网格内**路径 IL（U7 模型），不含 demux/mux、光纤耦合、调制器/探测器 "
                           "⇒ 是**下界**，不是链路预算。网格内 IL 在本模型下**与 K 无关**"
                           "（K 个波长走同构路径）；K 的真实代价在面积与 FSR 预算（见 T6.2）。",
    "precision_is_platform": "精度取 U4 已签核后端的平台常数，**不随 N/K 变化**；本模块拒绝发明"
                             "「精度 ↔ N」的映射（无锚）。",
    "pareto_semantics": "Pareto 支配：吞吐越大越好、面积/损耗越小越好。front 为**非支配**集；"
                        "若 front 退化为单点 ⇒ 该目标空间下**自由度 = 0**，须如实报告，不得包装成「有取舍」。",
    "reverse_guard": "反向护栏：人为放宽损耗上限 ⇒ Pareto 面**必须移动**（否则说明该约束不参与判决）。",
    "anchor_note": "本模块给出的表是**设计口径**的，不含任何实测回流；对外引用须同时引用本披露。",
}

ARCH_SHARED = "shared"
ARCH_TILED = "tiled"
ARCHS: Tuple[str, ...] = (ARCH_SHARED, ARCH_TILED)

# 能效/功耗相关令牌（键名扫描；**只扫键名不扫散文值** —— 否则合法披露文案必红）
# 🔴 **单一真值来源**：`lda_l2.eic_behavioral` 复用本表与 `assert_no_energy_metrics`
#    （U10 血案：同一准入条件不得两处各写一份 ⇒ 否则突变探针抓不住）。
#    2026-09-28 扩表：补 `power_*`（红线覆盖「能效 **与功耗**」，EIC 域尤其相关）。
FORBIDDEN_ENERGY_TOKENS: Tuple[str, ...] = (
    "pj_per_bit", "pJ/bit", "pJ_per_bit", "energy_per_bit", "energy_per_mac",
    "power_w", "power_dissipation", "power_mw",
    "tops_per_w", "TOPS/W", "tops", "fj_per_bit", "fJ/bit", "energy_efficiency",
)


class OpticalParetoError(Exception):
    """本模块的输入/不变量违规。"""


def assert_no_energy_metrics(payload: Any) -> None:
    """键名扫描守卫：payload 内**不得出现**能效类键名（递归）。

    只扫 **dict 键名**，不扫散文值（值里出现 "pJ/bit" 属**合法披露** —— 见 U8/U10 血案：
    「只扫键名、不扫散文值」是有意设计，必须写成判据而非注释）。
    可满足性：空载荷必过 · 纯散文载荷必过 · 含合法键载荷必过。
    """
    bad: List[str] = []

    def _walk(o: Any, path: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str):
                    for tok in FORBIDDEN_ENERGY_TOKENS:
                        if tok.lower() in k.lower():
                            bad.append("%s.%s" % (path, k))
                _walk(v, "%s.%s" % (path, k))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                _walk(v, "%s[%d]" % (path, i))

    _walk(payload, "$")
    if bad:
        raise OpticalParetoError(
            "载荷含能效类键名（越界）：%s —— 本模块零能效数字（见 OPTICAL_PARETO_DISCLOSURE['not_energy']）"
            % bad
        )


# ---------------------------------------------------------------------------
# 2) 单点配置的光域四量
# ---------------------------------------------------------------------------
def optical_metrics(N: int, K: int, arch: str = ARCH_SHARED,
                    rail_pitch: float = RAIL_PITCH_DEFAULT,
                    gap: float = GAP_DEFAULT,
                    alpha_prop: float = ALPHA_PROP_DEFAULT,
                    alpha_tap: float = ALPHA_TAP_DEFAULT,
                    precision_bits: Optional[float] = None,
                    build_cache: Optional[Dict[Any, dict]] = None) -> Dict[str, Any]:
    """单个 (N, K, arch) 配置的光域四量：吞吐 / 面积 / 损耗 / 精度。

    · 吞吐 = K·N² MACs/pass（算术计数）
    · 面积 = `shared` → U1 共享网格实测 `footprint_um2`；`tiled` → `K ×` 单面实测 `footprint_um2`
    · 损耗 = 网格内**最差路径** IL（`n_tap = deg_max`，U7 模型）⇒ 下界，且与 K 无关
    · 精度 = 平台常数（U4 已签核后端），**不随 N/K 变化**
    """
    if not isinstance(N, int) or N < 2:
        raise OpticalParetoError("N=%r 非法（须为 >=2 的 int）" % (N,))
    if not isinstance(K, int) or K < 1:
        raise OpticalParetoError("K=%r 非法（须为 >=1 的 int）" % (K,))
    if arch not in ARCHS:
        raise OpticalParetoError("arch=%r 非法（须 ∈ %s）" % (arch, list(ARCHS)))

    cache = build_cache if build_cache is not None else {}
    if ("plane", N) not in cache:
        # 🔴 必须与 U1（`wdm_shared_mesh_pnr`）同口径：**layout_mode="grid2d"**（压实布局）。
        #   默认布局的面积比 grid2d 大 7.1×（N=16 实测 254818.7 vs 35911.9 µm²）——
        #   本模块首版曾误用默认布局，被 `u1_area_crosscheck()` 当场抓出（rel_err=6.096）。
        cache[("plane", N)] = build_mesh_pnr(dft_matrix(N), rail_pitch=rail_pitch,
                                             layout_mode="grid2d")
    br = cache[("plane", N)]

    geom = rail_geometry(br)
    deg_max = int(geom["deg_max"])
    il = float(il_db(deg_max, float(geom["L_bus_um"]), alpha_prop, alpha_tap, rail_pitch, gap))
    # 🆕 D-126：本通道的损耗轴**本来就是每模最坏**（`deg_max`）—— 现登记到平台规范词汇
    #   （min/mean/max + basis 标签），并补上最好/均值的对照读数。
    #   ⇒ 与 `loss_aware_compile`（同端口模型）词汇统一；旧键 `il_worst_db` 一字未改。
    from lda_l2 import il_basis as _ILB
    ils = [float(il_db(d, float(geom["L_bus_um"]), alpha_prop, alpha_tap, rail_pitch, gap))
           for d in geom["deg"]]
    il_basis = _ILB.il_basis_from_values(
        ils, channel="pareto", n_modes=len(ils),
        per_element_db=float(alpha_prop * max(rail_pitch - gap, 0.0) / 1e4 + alpha_tap),
        per_element_kind="per_tap_db",
        basis_note="光域 Pareto 损耗轴 = 网格内**每模最坏**路径 IL（deg_max）；"
                   "il_worst_db ≡ il_basis_per_mode.il_max_db（同 `loss_aware_compile` 端口模型）。")
    # U1（v0.9.122）的面积结论是**纯算术**：共享 ⇒ fp_shared = fp_single；朴素 K 套 ⇒ fp_naive = K·fp_single
    #   （`wdm_shared_mesh_pnr.build_wdm_shared_mesh_pnr` 内部即 `fp_naive_lower = K*fp_single`）
    # ⇒ 此处直接算，并由 `u1_area_crosscheck()` 用 U1 真函数在 K=4 上交叉核验（不重复调用热路径）。
    plane_area = float(br["footprint_um2"])
    shared_area = plane_area
    naive_area = K * plane_area
    area = shared_area if arch == ARCH_SHARED else naive_area

    out = {
        "N": N,
        "K": K,
        "arch": arch,
        "macs_per_pass": K * N * N,
        "area_um2": area,
        "area_mm2": area / 1e6,
        "plane_area_mm2": plane_area / 1e6,
        "area_ratio_vs_naive": (shared_area / naive_area) if naive_area > 0 else None,
        "il_worst_db": il,
        "il_basis": "per_mode",
        "il_basis_per_mode": il_basis,
        "deg_max": deg_max,
        "L_bus_um": float(geom["L_bus_um"]),
        "n_cols": int(br["n_cols"]),
        "precision_bits": precision_bits,
        "precision_source": ("U4 ring_weight_bank 已签核后端（平台常数，不随 N/K 变化）"
                            if precision_bits is not None else None),
    }
    assert_no_energy_metrics(out)
    return out


def u1_area_crosscheck(N: int = 16, K: int = 4,
                       rail_pitch: float = RAIL_PITCH_DEFAULT) -> Dict[str, Any]:
    """用 U1 真函数交叉核验本模块的面积算术（防「自己算自己」的循环验证）。

    取 U1 `build_wdm_shared_mesh_pnr` 的实测 `footprint_um2` / `footprint_naive_lower_um2`
    与本模块的 `shared_area` / `tiled_area` 逐值比对。
    """
    if K < 1:
        raise OpticalParetoError("K=%r 非法" % (K,))
    wls = [1550.0 + 2.5 * i for i in range(K)]
    rep = build_wdm_shared_mesh_pnr(N=N, wavelengths_nm=wls, rail_pitch=rail_pitch)
    mine_shared = optical_metrics(N, K, ARCH_SHARED, rail_pitch=rail_pitch)["area_um2"]
    mine_tiled = optical_metrics(N, K, ARCH_TILED, rail_pitch=rail_pitch)["area_um2"]
    u1_shared = float(rep["footprint_um2"])
    u1_naive = float(rep["footprint_naive_lower_um2"])
    out = {
        "N": N, "K": K,
        "mine_shared_um2": mine_shared, "u1_shared_um2": u1_shared,
        "mine_tiled_um2": mine_tiled, "u1_naive_um2": u1_naive,
        "shared_rel_err": abs(mine_shared - u1_shared) / u1_shared,
        "tiled_rel_err": abs(mine_tiled - u1_naive) / u1_naive,
        "u1_area_ratio_vs_naive": float(rep["area_ratio_vs_naive"]),
        "consistent": (abs(mine_shared - u1_shared) / u1_shared < 1e-12
                       and abs(mine_tiled - u1_naive) / u1_naive < 1e-12),
    }
    assert_no_energy_metrics(out)
    return out


# ---------------------------------------------------------------------------
# 3) Pareto 支配与前沿
# ---------------------------------------------------------------------------
def _dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """a 支配 b：吞吐 >= 且 面积 <= 且 损耗 <=，且至少一项严格优。"""
    ge = a["macs_per_pass"] >= b["macs_per_pass"]
    le_a = a["area_um2"] <= b["area_um2"]
    le_l = a["il_worst_db"] <= b["il_worst_db"]
    strict = (a["macs_per_pass"] > b["macs_per_pass"]
              or a["area_um2"] < b["area_um2"]
              or a["il_worst_db"] < b["il_worst_db"])
    return bool(ge and le_a and le_l and strict)


def pareto_front(rows: Sequence[Dict[str, Any]],
                 il_max_db: Optional[float] = None,
                 area_max_um2: Optional[float] = None) -> List[Dict[str, Any]]:
    """非支配前沿。可选约束（越界者先被剔除，**并如实计数**，不静默丢弃）。"""
    pool = list(rows)
    if il_max_db is not None:
        pool = [r for r in pool if r["il_worst_db"] <= il_max_db]
    if area_max_um2 is not None:
        pool = [r for r in pool if r["area_um2"] <= area_max_um2]
    front = [r for r in pool if not any(_dominates(o, r) for o in pool if o is not r)]
    return sorted(front, key=lambda r: (r["arch"], r["N"], r["K"]))


def dominance_report(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """支配结构报告：是否存在**单点支配全部**（= 自由度 0）或 front 为空（= 全被约束剔除）。"""
    front = pareto_front(rows)
    out = {
        "n_configs": len(rows),
        "front_size": len(front),
        "front": [(r["arch"], r["N"], r["K"]) for r in front],
        "front_rows": front,
        "degenerate_single_point": len(front) == 1,
        "front_empty": len(front) == 0,
    }
    if len(front) == 1:
        out["freedom_note"] = ("Pareto 面退化为**单点** ⇒ 该目标空间下**自由度 = 0**"
                              "（存在一个配置在吞吐/面积/损耗三轴上同时不劣于所有其它配置）。"
                              "按 U7 先例：须如实报告，不得包装成「有取舍」。")
    elif len(front) > 1:
        archs = sorted({r["arch"] for r in front})
        out["freedom_note"] = ("Pareto 面含 %d 个非支配点（架构 %s）⇒ 目标空间内存在**真实取舍**。"
                              % (len(front), archs))
    else:
        out["freedom_note"] = "约束下 front 为空 ⇒ 约束不可行（须放宽或换目标域）。"
    return out


# ---------------------------------------------------------------------------
# 4) 表 + 反向护栏
# ---------------------------------------------------------------------------
DEFAULT_NS: Tuple[int, ...] = (2, 4, 8, 16)
DEFAULT_KS: Tuple[int, ...] = (1, 2, 4, 8, 16)


def optical_pareto_table(Ns: Sequence[int] = DEFAULT_NS,
                         Ks: Sequence[int] = DEFAULT_KS,
                         archs: Sequence[str] = ARCHS,
                         precision_bits: Optional[float] = None,
                         **kw: Any) -> Dict[str, Any]:
    """N × K × 架构 网格的光域四量表 + 非支配前沿。"""
    cache: Dict[Any, dict] = {}
    rows = [optical_metrics(int(N), int(K), arch=a, precision_bits=precision_bits,
                            build_cache=cache, **kw)
            for a in archs for N in Ns for K in Ks]
    rep = {
        "rows": rows,
        "Ns": list(Ns),
        "Ks": list(Ks),
        "archs": list(archs),
        "n_rows": len(rows),
        "disclosure_keys": sorted(OPTICAL_PARETO_DISCLOSURE.keys()),
        # 🆕 D-126：损耗轴口径登记（每模最坏）—— 与 `lda_l2.il_basis` 规范词汇统一
        "il_basis": "per_mode",
        "il_basis_note": ("损耗轴 = 网格内**每模最坏**路径 IL（`deg_max`）；每行另带 "
                          "`il_basis_per_mode`（min/mean/max + spread，见 `lda_l2.il_basis`）。"
                          "旧键 `il_worst_db` 语义不变，≡ `il_basis_per_mode.il_max_db`。"),
    }
    rep.update(dominance_report(rows))
    assert_no_energy_metrics(rep)
    return rep


def loss_relax_reverse_guard(Ns: Sequence[int] = DEFAULT_NS,
                             Ks: Sequence[int] = DEFAULT_KS,
                             archs: Sequence[str] = ARCHS,
                             tight_db: Optional[float] = None,
                             relaxed_db: Optional[float] = None,
                             precision_bits: Optional[float] = None,
                             **kw: Any) -> Dict[str, Any]:
    """反向护栏（T6.1 验收③）：**人为放宽损耗上限 ⇒ Pareto 面必须移动**。

    若放宽后 front 不变 ⇒ 说明损耗约束**未参与判决**（该护栏空转）：本函数把它判为失败。
    """
    cache: Dict[Any, dict] = {}
    rows = [optical_metrics(int(N), int(K), arch=a, precision_bits=precision_bits,
                            build_cache=cache, **kw)
            for a in archs for N in Ns for K in Ks]
    ils = sorted(r["il_worst_db"] for r in rows)
    if tight_db is None:
        tight_db = ils[len(ils) // 4]
    if relaxed_db is None:
        relaxed_db = ils[-1] + 1e-9
    f_tight = pareto_front(rows, il_max_db=tight_db)
    f_relax = pareto_front(rows, il_max_db=relaxed_db)
    tk = [(r["arch"], r["N"], r["K"]) for r in f_tight]
    rk = [(r["arch"], r["N"], r["K"]) for r in f_relax]
    out = {
        "tight_il_max_db": tight_db,
        "relaxed_il_max_db": relaxed_db,
        "front_tight": tk,
        "front_relaxed": rk,
        "moved": tk != rk,
        "n_kept_tight": len(tk),
        "n_kept_relaxed": len(rk),
    }
    assert_no_energy_metrics(out)
    return out


if __name__ == "__main__":  # 自测：打真实数字
    t = optical_pareto_table()
    print("=== 光域 Pareto 表（架构 × N × K）===")
    for r in t["rows"]:
        print("  %-7s N=%-3d K=%-3d  MAC=%5d  面积=%9.4f mm²  IL=%7.4f dB  deg_max=%2d"
              % (r["arch"], r["N"], r["K"], r["macs_per_pass"], r["area_mm2"],
                 r["il_worst_db"], r["deg_max"]))
    print("\nfront_size =", t["front_size"])
    print("front =", t["front"])
    print("退化单点 =", t["degenerate_single_point"])
    print("freedom_note:", t["freedom_note"])
    g = loss_relax_reverse_guard()
    print("\n=== 反向护栏（放宽损耗 ⇒ front 必须移动）===")
    print("  tight=%.6f dB → kept %d | relaxed=%.6f dB → kept %d | moved=%s"
          % (g["tight_il_max_db"], g["n_kept_tight"], g["relaxed_il_max_db"],
             g["n_kept_relaxed"], g["moved"]))
    print("\n=== 面积架构对照（U1 共享 vs 独立面）===")
    for N in DEFAULT_NS:
        for K in (1, 4, 16):
            a = [r for r in t["rows"] if r["N"] == N and r["K"] == K and r["arch"] == "shared"][0]
            b = [r for r in t["rows"] if r["N"] == N and r["K"] == K and r["arch"] == "tiled"][0]
            print("  N=%-3d K=%-3d shared=%8.4f mm²  tiled=%8.4f mm²  ratio=%.4f"
                  % (N, K, a["area_mm2"], b["area_mm2"], b["area_mm2"] / a["area_mm2"]))
    print("\n=== U1 面积交叉核验（防「自己算自己」）===")
    xc = u1_area_crosscheck(N=16, K=4)
    print("  mine shared=%.6f / u1=%.6f  rel_err=%.3e"
          % (xc["mine_shared_um2"], xc["u1_shared_um2"], xc["shared_rel_err"]))
    print("  mine tiled =%.6f / u1=%.6f  rel_err=%.3e"
          % (xc["mine_tiled_um2"], xc["u1_naive_um2"], xc["tiled_rel_err"]))
    print("  u1 area_ratio_vs_naive=%.6f | consistent=%s"
          % (xc["u1_area_ratio_vs_naive"], xc["consistent"]))
    print("\ndisclosure keys:", t["disclosure_keys"])
