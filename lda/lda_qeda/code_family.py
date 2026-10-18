# -*- coding: utf-8 -*-
"""量子纠错**码族参数律**（CF 征程 · **CF-M0** · 能力层 · 🔴 **不计锚**）。

本模块是 CF 征程第一档的交付物：把「多码族的参数律」做成**可复核的能力层**，
并**用机器锁把「本族不可锚」这个负结果固定下来**（防后人把它当锚登记 ⇒ 虚报）。

================================================================================
🔴 结论：码族参数**整族不可锚**（三条现算证据，2026-10-18 实测）
================================================================================
本仓锚的判据范式是「**闭式 golden vs 数值候选 + |Δ| < tol + 残差随离散参数单调收敛**」。
码族参数律三条都过不去：

**证据 1 · C3（指标须连续且对数值参数扰动有响应）不成立**
    `n(d)` / `k(d)` / `n(L)` 全是**整数**，对 `d`（或 `L`）分段常值 ⇒ 在非跳点处
    `∂n/∂d ≡ 0`，任何连续小扰动都不产生响应。扰动一档就跳变 ⇒ 残差不是"变小"而是"跳"，无收敛可言。

**证据 2 · 判据 D（残差须浮出双精度地板并单调收敛）不成立**
    任何**正确**的独立构造给出的都是精确整数，与闭式**逐位相等** ⇒ 残差恒 `0.0`。
    本仓铁律明写：残差恒 ~1e-16 ⇒ **代数恒等，判假独立，不计入独立候选数**；
    而 `0.0` 比 `1e-16` 更极端 —— 与自证桩 `|Δ|≡0` **完全不可区分**。
    **实测（本模块自检 A4/B1）**：环面码 L=2…6，`|n_enum − 2L²| ≡ 0` 且 `|k_enum − 2| ≡ 0`。

**证据 3 · 渐近律同样精确**
    同 `d` 下 `n_color/n_toric = (3d²+1)/(8d²) = 3/8 + 1/(8d²)`，对 `1/d²` **线性** ⇒
    两点 Richardson 外推**代数精确**。实测 `Richardson(d=5,10) = 0.37500000000000000`，
    与外推残差 `0.000e+00`。⇒ 连"用外推制造离散误差"这条路也堵死。

**先例（本仓已裁决同型问题）**：P6·T6.1 的三个量全为精确量 ⇒ **T6.1 无锚**（2026-09-28）。
本档与该先例同型，故**如实登记净增 0**，不硬凑（CF 章程 §3 总纪律 / §5 R1 头号红线）。

================================================================================
交付内容（能力层，可被门禁与对外物料复用）
================================================================================
1. **闭式参数律**：三角色码 / 环面码 / 旋转表面码 / 平面表面码 / 编码率 / 资源比 / 渐近极限
2. **独立图枚举**（环面码族）：显式构造「顶点-边-面」复形，用 GF(2) **边界算子秩** 求 `k`，
   与闭式**逐位对照** —— 这是真独立路径（秩计算 vs 公式），但**因为精确所以不可锚**。
3. **自检**：`selfcheck_code_family()`（18 项）+ CLI 自跑。

诚实边界
--------
- 三角色码 `n(d)=(3d²+1)/4` 仅有**闭式 + 独立小表对照**（d=3…11）；**未做**三角色码的
  独立格点构造（该构造需 6.6.6 三角贴片，本档未实现）⇒ 其"独立性"弱于环面码族。
- 环面码 `d = L` 是**公式口径**，**未做**独立最短路/同调枚举（最短非收缩环）。
- 本模块**不含**迭代解码（BP+OSD 属 CF-M2），也**不含**任何阈值/误码率（那需蒙特卡洛 ⇒
  仿真值 ⛔ 非 golden）。
- **零第三方 QEC SDK**：纯标准库，未 `import numpy`/`scipy`/`ldpc`/`stim`/`pymatching`。

设计与工程：杜玉河 · 致谢 LDA 工程团队。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

__all__ = [
    "ANCHORABLE", "NOT_ANCHORABLE_REASONS",
    "color_code_n", "color_code_rate", "toric_params", "rotated_surface_params",
    "planar_surface_params", "resource_ratio_color_toric",
    "RATIO_ASYMPTOTIC", "ratio_deviation",
    "toric_params_enumerated", "selfcheck_code_family",
]

# ===========================================================================
# 🔴 不可锚声明（由门禁 `run_cf_code_family_smoke` 的 B 组机器守）
# ===========================================================================
ANCHORABLE = False

NOT_ANCHORABLE_REASONS: Tuple[str, ...] = (
    "C3 不成立：n/k 为整数、对 d（L）分段常值 ⇒ 非跳点处 ∂n/∂d ≡ 0，连续扰动无响应",
    "判据 D 不成立：正确独立构造给出精确整数 ⇒ 残差恒 0.0，与自证桩 |Δ|≡0 不可区分",
    "渐近律亦精确：比值对 1/d² 线性 ⇒ 两点 Richardson 外推代数精确（实测残差 0.000e+00）",
)

# ===========================================================================
# 一、闭式参数律
# ===========================================================================
def color_code_n(d: int) -> int:
    """三角色码（triangular color code）比特数 `n(d) = (3d²+1)/4`，`d` 为奇 ≥3。

    自检锚点：d=3 ⇒ 7（Steane 七比特码）· d=5 ⇒ 19 · d=7 ⇒ 37 · d=9 ⇒ 61 · d=11 ⇒ 91。
    """
    if d < 3 or d % 2 == 0:
        raise ValueError("三角色码距离 d 必须为奇且 ≥3（d=%r）" % (d,))
    if (3 * d * d + 1) % 4 != 0:
        raise ValueError("(3d²+1) 非 4 的倍数 —— d=%r 不该出现" % (d,))
    return (3 * d * d + 1) // 4


def color_code_rate(d: int) -> float:
    """三角色码编码率 `k/n = 1/n = 4/(3d²+1)`（`k=1`）。"""
    return 1.0 / float(color_code_n(d))


def toric_params(L: int) -> Dict[str, float]:
    """环面码（toric code）参数：`n = 2L²` · `k = 2` · `d = L`。

    ⚠️ `d = L` 是**公式口径**（最短非收缩环），本档未做独立同调枚举。
    """
    if L < 2:
        raise ValueError("环面码尺寸 L 必须 ≥2（L=%r）" % (L,))
    return {"n": 2 * L * L, "k": 2, "d": L}


def rotated_surface_params(d: int) -> Dict[str, float]:
    """旋转表面码（rotated surface code）：`n = d²` · `k = 1` · `d = d`。"""
    if d < 3 or d % 2 == 0:
        raise ValueError("旋转表面码距离 d 必须为奇且 ≥3（d=%r）" % (d,))
    return {"n": d * d, "k": 1, "d": d}


def planar_surface_params(d: int) -> Dict[str, float]:
    """非旋转（unrotated）平面表面码：`n = 2d² − 1` · `k = 1`。

    🔴 与 J1 已用的 `2d²−1`（lattice surgery 资源）**同式但不同量**：
    此处是**码块比特数**，J1 是**手术补丁面积**。本模块只作能力层，不计锚 ⇒ 不构成同源冲突。
    """
    if d < 3 or d % 2 == 0:
        raise ValueError("平面表面码距离 d 必须为奇且 ≥3（d=%r）" % (d,))
    return {"n": 2 * d * d - 1, "k": 1, "d": d}


RATIO_ASYMPTOTIC = 0.375  # = 3/8


def resource_ratio_color_toric(d: int) -> float:
    """同 `d`（取 `L=d`）下 色码/环面码 比特数之比：`(3d²+1)/(8d²) = 3/8 + 1/(8d²)`。"""
    nc = float(color_code_n(d))
    nt = float(toric_params(d)["n"])
    return nc / nt


def ratio_deviation(d: int) -> float:
    """比值与渐近极限 `3/8` 的**精确**差：`1/(8d²)`。

    🔴 走**整数恒等式**而非浮点相减：`8·n_color − 3·n_toric ≡ 2`（对一切奇 d 成立），
    故 `|n_color/n_toric − 3/8| = 2/(8·n_toric) = 1/(8d²)` 精确。
    浮点 `(nc/nt) − 0.375` 会带 ~1e-17 舍入，不能用作精确断言（本档自检初版即因此误红）。
    """
    if d < 3:
        raise ValueError("d 必须 ≥3（d=%r）" % (d,))
    nc = color_code_n(d)
    nt = toric_params(d)["n"]
    lhs = 8 * nc - 3 * nt
    if lhs != 2:                                  # 恒等式守卫：破了说明闭式被改
        raise ValueError("整数恒等式 8·n_color−3·n_toric ≡ 2 不成立（得 %d）" % (lhs,))
    return float(lhs) / float(8 * nt)


# ===========================================================================
# 二、独立图枚举（环面码族）—— 真独立路径，但**精确 ⇒ 不可锚**
# ===========================================================================
def _build_toric_complex(L: int) -> Tuple[Dict[Tuple[int, int], int],
                                          List[Tuple[Tuple[int, int], Tuple[int, int]]],
                                          List[List[int]]]:
    """显式构造 L×L 环面码的「顶点-边-面」复形（**不读任何参数公式**）。

    边编号：先水平 `h[r][c]`（`(r,c)→(r,c+1)`）共 L² 条，再竖直 `v[r][c]`
    （`(r,c)→(r+1,c)`）共 L² 条 ⇒ 总数天然 = 2L²（这是**数出来的**，不是套公式）。
    面 `(r,c)` 的 4 条边与 `lda_qeda.decoder.ToricCode.syndrome_x` 同约定。
    """
    if L < 2:
        raise ValueError("环面码尺寸 L 必须 ≥2（L=%r）" % (L,))
    verts = [(r, c) for r in range(L) for c in range(L)]
    vid = {v: i for i, v in enumerate(verts)}
    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    eh: Dict[Tuple[int, int], int] = {}
    ev: Dict[Tuple[int, int], int] = {}
    for r in range(L):
        for c in range(L):
            eh[(r, c)] = len(edges)
            edges.append(((r, c), (r, (c + 1) % L)))
    for r in range(L):
        for c in range(L):
            ev[(r, c)] = len(edges)
            edges.append(((r, c), ((r + 1) % L, c)))
    faces: List[List[int]] = []
    for r in range(L):
        for c in range(L):
            faces.append([eh[(r, c)], eh[((r + 1) % L, c)],
                          ev[(r, c)], ev[(r, (c + 1) % L)]])
    return vid, edges, faces


def _gf2_rank(rows: List[int]) -> int:
    """GF(2) 秩。行以 `int` 位掩码表示，按最高位主元消元（纯标准库，无 numpy）。"""
    basis: Dict[int, int] = {}
    rk = 0
    for x in rows:
        cur = x
        while cur:
            h = cur.bit_length() - 1
            if h in basis:
                cur ^= basis[h]
            else:
                basis[h] = cur
                rk += 1
                break
    return rk


def toric_params_enumerated(L: int) -> Dict[str, int]:
    """**图枚举**环面码参数（独立于闭式）：

    - `n = |E|`（边数，数出来的）
    - `k = (|E| − rank ∂₁) − rank ∂₂` —— 同调维数定义，`∂₂` 面→边、`∂₁` 边→顶点
    - `rank_d1` / `rank_d2` 一并给出（用于与理论值 `L²−1` 对照）
    """
    vid, edges, faces = _build_toric_complex(L)
    d2 = []
    for f in faces:
        m = 0
        for e in f:
            m |= (1 << e)
        d2.append(m)
    r2 = _gf2_rank(d2)
    d1 = [(1 << vid[u]) | (1 << vid[v]) for (u, v) in edges]
    r1 = _gf2_rank(d1)
    n = len(edges)
    return {"n": n, "k": (n - r1) - r2, "rank_d1": r1, "rank_d2": r2}


# ===========================================================================
# 三、自检
# ===========================================================================
def selfcheck_code_family() -> Dict[str, bool]:
    """能力层自检（18 项）。全部 `True` 才 `ACCEPT`。"""
    ok: Dict[str, bool] = {}

    # ── 三角色码：闭式 vs **独立硬编码小表**（防公式抄错） ──────────────
    _REF = {3: 7, 5: 19, 7: 37, 9: 61, 11: 91}
    ok["color_d3_7_steane"] = color_code_n(3) == 7
    ok["color_d5_19"] = color_code_n(5) == 19
    ok["color_d7_37"] = color_code_n(7) == 37
    ok["color_d9_61"] = color_code_n(9) == 61
    ok["color_d11_91"] = color_code_n(11) == 91
    ok["color_small_table_match"] = all(color_code_n(d) == n for d, n in _REF.items())
    ok["color_rate_4_over_3d2p1"] = abs(color_code_rate(7) - 4.0 / 148.0) < 1e-18
    ok["color_n_integer_for_all_odd"] = all((3 * d * d + 1) % 4 == 0
                                            for d in range(3, 200, 2))

    # ── 参数契约（值域在算术之前判） ──────────────────────────────────
    def _raises(fn, *a) -> bool:
        try:
            fn(*a)
        except ValueError:
            return True
        except Exception:            # noqa: BLE001 —— 非契约异常也算失败
            return False
        return False

    ok["color_even_d_ValueError"] = _raises(color_code_n, 4)
    ok["color_d1_ValueError"] = _raises(color_code_n, 1)
    ok["toric_L1_ValueError"] = _raises(toric_params, 1)

    # ── 环面码：图枚举 vs 闭式（**逐位相等** ⇒ 不可锚的核心证据） ──────
    _ENUM = {L: toric_params_enumerated(L) for L in range(2, 7)}
    ok["toric_enum_n_eq_2L2"] = all(_ENUM[L]["n"] == 2 * L * L for L in _ENUM)
    ok["toric_enum_k_eq_2"] = all(_ENUM[L]["k"] == 2 for L in _ENUM)
    ok["toric_rank_d2_eq_L2m1"] = all(_ENUM[L]["rank_d2"] == L * L - 1 for L in _ENUM)
    ok["toric_rank_d1_eq_L2m1"] = all(_ENUM[L]["rank_d1"] == L * L - 1 for L in _ENUM)
    ok["toric_enum_residual_identically_zero"] = all(
        abs(_ENUM[L]["n"] - toric_params(L)["n"]) == 0
        and abs(_ENUM[L]["k"] - toric_params(L)["k"]) == 0 for L in _ENUM)

    # ── 其余族 ────────────────────────────────────────────────────────
    ok["rotated_d5_25_1"] = (rotated_surface_params(5)["n"] == 25
                             and rotated_surface_params(5)["k"] == 1)
    ok["planar_d5_49_1"] = (planar_surface_params(5)["n"] == 49
                            and planar_surface_params(5)["k"] == 1)

    # ── 渐近律：单调趋近 3/8，且偏差恰 = 1/(8d²) ──────────────────────
    _ds = [3, 5, 7, 9, 11, 21, 51, 101]
    _dev = [abs(resource_ratio_color_toric(d) - RATIO_ASYMPTOTIC) for d in _ds]
    ok["ratio_monotone_to_3_8"] = all(_dev[i] > _dev[i + 1] for i in range(len(_dev) - 1))
    ok["ratio_deviation_is_1_over_8d2"] = all(
        abs(_dev[i] - ratio_deviation(d)) <= 1e-15 * max(1.0, _dev[i])
        for i, d in enumerate(_ds))

    # ── 不可锚声明的自洽 ──────────────────────────────────────────────
    ok["not_anchorable_declared"] = (ANCHORABLE is False
                                    and len(NOT_ANCHORABLE_REASONS) >= 3)
    return ok


def main() -> int:
    chk = selfcheck_code_family()
    bad = [k for k, v in chk.items() if not v]
    for k in chk:
        print("  [%s] %s" % ("PASS" if chk[k] else "FAIL", k))
    print("-" * 78)
    print("CF-M0 码族参数律（能力层）：%d 项 · FAIL=%d · ANCHORABLE=%s"
          % (len(chk), len(bad), ANCHORABLE))
    print("🔴 净增 0 锚（精确量不可锚 · 见模块 docstring 三条证据）")
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
