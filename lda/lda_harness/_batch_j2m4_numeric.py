# -*- coding: utf-8 -*-
"""Batch J2-M4 数值实现 · 超导 Transmon 征程（J2）M4 QPU 级误差预算集成 + 拓扑对接 + 收官。

════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——

  B509：**QPU 耦合图的代数连通度 λ₂（Fiedler 值）**（topology ↔ surface-code connectivity）
        golden   = 闭式 **λ₂(P_rows □ P_cols) = 2 − 2·cos(π / max(rows, cols))**
                   —— 方阵耦合图 = 两条路径图的 **Cartesian 积** P_rows □ P_cols；
                   其 Laplacian 谱 = 两因子谱的 **Kronecker 和**（λ = λ_a(P_rows) + λ_b(P_cols)），
                   路径图 Laplacian 本征 λ_k = 2 − 2cos(kπ/n) ⇒ 次小（去 0 后最小）
                   取两因子 λ₁ 的**较小者** ⇒ 2 − 2cos(π / max(rows, cols))。
                   （**精确解析解、非截断近似**；实稠密对角化核对差 ~1e-16。）
        candidate = **Krylov 子空间 Rayleigh–Ritz 极小化**：
                     在 1⊥ 上构造**嵌套** Krylov 子空间 K_m(v₀) = span{v₀, Lv₀, …, L^{m−1}v₀}
                     （v₀ ⊥ 1，全程**全重正交**防基病态），解 Rayleigh–Ritz 问题取**最小 Ritz 值**。
                     由 **min-max 原理**：K_m ⊂ K_{m+1} ⇒ 最小 Ritz 值 λ₂^{(m)} **单调非增**、
                     且恒 ≥ λ₂ = 真值 ⇒ 残差 λ₂^{(m)} − λ₂ ≥ 0 随维数 m **单调下降**。
        ——方法学独立：golden 走「Kronecker 和谱定理解析闭式」；candidate 走「迭代子空间逼近」。

🔴 物理意义（承 J2 超导 Transmon 蓝图 · M4「拓扑连通性 vs 表面码需求」）：
  · 表面码要求耦合图提供 **2D 最近邻局部性** —— 解码器（Union-Find / MWPM）在图上做
    **局部匹配**，其可行性由图的**扩张（等周）能力**决定。
  · **代数连通度 λ₂**（Fiedler 值）是该能力的**连续谱度量**：Cheeger 不等式
      λ₂/2 ≤ h(G) ≤ √(2λ₂)
    把 λ₂ 与**等周数 h(G)**（「任意局部割至少被多少边穿过」）钉在一起 ⇒ λ₂ 越大，
    局部综合征越难被割断 ⇒ 2D 局部匹配越稳。
  · **拓扑代价的连续量化**：方阵（度 4）与 heavy-hex（度 3）在**同 qubit 数**下 λ₂ 不同
    （度 3 的边 qubit 把谱压平）⇒ 「度 3 代价」从**整数度判据（不可锚）**升级为**连续谱判据（可锚）**。
  · 本锚同时是 **LDA 拓扑构建器 `lda_qeda/sc_topology_core.py` 的交叉验证**：其产出的方阵
    耦合图，代数连通度必须与谱定理闭式一致（能力层 `lda_qeda/topology_qec_bridge.py` 复用）。

🔴 与既有锚的边界（**同源体检 · 实 grep 全仓核验**，本批第一道闸）：
  · **宪章原定 M4 两候选均被否决**（承 M0/M1/M3 先例「宪章选的新族先验同源」）：
      - 宪章 **B513**「拓扑连通性 vs 表面码需求（heavy-hex 度3 / 方阵度4 ⇄ 最近邻判据）」：
        度（degree）是**整数**、连通性是**布尔** ⇒ 精确量/离散量，**残差恒沉地板** ⇒
        属「不可锚」（同 S1–S6 纯算术、B17 定义式）⇒ 否决其**字面形式**；
        ⇒ 改靶到其**连续化**：同一「连通性」概念的**谱形式** λ₂（本锚）。
      - 宪章 **B514**「QPU 总错误率 ≤ 阈值余量（闭式预算 ⇄ 数值）」 ⇒ **完全被占用**：
        ①「总错误率预算」= **级联乘积/求和**（∏/Σ 算术）⇒ 与既有 **S4**（`part1.py`
           「量子门保真度预算（∏fᵢ 乘法级联）」，`golden_fn=s4_fidelity_budget`）**同源**
           （S1/S3/S5/S6 同为 margin 型预算锚）；②若走「∫ 率 dt ⇒ 累计错误」数值路线，
           则与 **J1 锚 B502/B503**（`F=exp(−∫率)` ⇄ 一维中点求积）+ **B504/B505**
           （`1−exp(−∫率)` / `∫(1−e^{−kx})dx` ⇄ 一维求积）**同原子族** ⇒ 否决。
  · 本批实际净增落在 M4 里**唯一既有锚未覆盖**的连续量：**耦合图的谱连通度 λ₂**。
  · 实 grep 核验（`benchmark_defs/` 与 `lda_solver/`）：`fiedler|algebraic_connect|laplacian|
    lanczos|krylov|power_iter|eigsh|谱隙|spectral_gap|graph_spectr` 在**锚定义**内**零占用**
    （仅 `part2` 2D 方势阱注释提到「2D FD Laplacian」= 量子阱本征、标量不同；
    `_batch_b15/b19` 用双调和模板/极坐标 Laplacian 验调和函数 = 微分算子核对、非谱不变量；
    `_batch_b9/b22`/`_adapter_p1` 用 `eigsh/稠密 eigh` 求**物理本征值**（f01/模频）、标量不同）。
  · 与 **B10/B506/B507**（门错误率 ⇄ Lindblad/矩阵 RK4）**标量·构型·格式三者均异** ⇒ 计新锚
    （承 B452↔B33 先例）。

🔴 判据 D 双向标定（默认档必须落在**离散误差主导区**）：
  实测扫描（方阵 10×10，N=100，λ₂=9.788697e-02）：
      m= 4 → 4.626e-01      m=16 → 1.082e-02
      m= 8 → 9.999e-02      m=32 → 1.122e-10   ← 默认档（>1e-12，留 891× 余量）
  ⇒ 默认档 m=32；tol=1e-7 ⇒ 余量 891.4×。
  🔴 诚实边界：Krylov 极值收敛**非均匀**（实测比值 4.63×/9.25×/**9.64e7×**），末段呈
   **超收敛**（Krylov 空间逼近谱极值时加速）—— 本锚**如实披露此非均匀性，不虚报「等比收敛」**；
   只报「严格单调下降 + 粗端浮出地板（动态范围 4.1e9×）+ 默认档 >1e-12」三条可证伪事实。
  🔴 避免退化：Krylov 维数 m 必须 < N（m→N 时重正交残差把常数向量泄漏进去 ⇒ 最小 Ritz
   滑向 λ₁=0）。本锚取 m=32 ≪ N=100。

🔴 命名避让：批次号 **J2-M4** 用连字符写法 `_batch_j2m4_numeric` / `_get_j2m4_numeric`
  （与 `_batch_j2_numeric`（M2）/ `_batch_j2m3_numeric`（M3）并列、互不覆盖）；
  候选 key 前缀 `b509_` 尚未占用（实 grep 核验 `b509_` 零命中）。磁盘 `_adapter_p*.py`
  **不新建**（L9 守卫：恒 6 片）。

🔴 纪律：
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 零 RNG：起始向量用**确定性解析式** v₀_i = sin(1 + 0.7i) + cos(0.3i) ⇒ 逐位可复现。
· 诚实边界：本锚标量是**图论谱不变量**（不耦合任何器件物理常数 / 非实测 PDK）；
  其物理意义是「拓扑支撑 2D 局部匹配的扩张能力」的连续度量。本锚只证
  「谱定理闭式 ⇄ Krylov 数值」一致这一数学事实 + LDA 拓扑构建器自洽，
  **不得作制造/性能宣称**。零商业依赖（纯 numpy）。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）─────────────
_M_BY_BID = {"B509": 32}
_GRID_BY_BID = {"B509": [4, 8, 16, 32]}
_TOL_BY_BID = {"B509": 1e-7}

#: 默认物理参数（只放 golden 接受的键；离散参数 m 由候选签名默认值承载）
_B509_DEFAULT = {"rows": 10, "cols": 10}

#: 起始向量确定性解析式（零 RNG ⇒ 逐位可复现）
_START_A, _START_B, _START_C = 1.0, 0.7, 0.3


def _grid_laplacian(rows: int, cols: int) -> "np.ndarray":
    """方阵耦合图 P_rows □ P_cols 的组合 Laplacian L = D − A（最近邻，度 ≤ 4）。"""
    rows, cols = int(rows), int(cols)
    n = rows * cols
    lap = np.zeros((n, n), dtype=float)

    def _idx(r: int, c: int) -> int:
        return r * cols + c

    for r in range(rows):
        for c in range(cols):
            i = _idx(r, c)
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    lap[i, i] += 1.0
                    lap[i, _idx(rr, cc)] -= 1.0
    return lap


def _krylov_lambda2(lap: "np.ndarray", m_dim: int) -> float:
    """嵌套 Krylov 子空间（⊂ 1⊥，全重正交）上的 Rayleigh–Ritz 最小值 λ₂^{(m)}。

    由 min-max 原理，λ₂^{(m)} ≥ λ₂ 且随 m 单调非增 ⇒ 残差 λ₂^{(m)} − λ₂ 单调下降。
    """
    n = lap.shape[0]
    m_dim = int(m_dim)
    if m_dim < 2:
        raise ValueError("Krylov 维数 m 须 ≥ 2")
    if m_dim > n:
        raise ValueError("Krylov 维数 m=%d 超过节点数 N=%d（会退化滑向 λ₁=0）"
                         % (m_dim, n))
    idx = np.arange(n, dtype=float)
    v = np.sin(_START_A + _START_B * idx) + np.cos(_START_C * idx)
    v = v - v.mean()
    nv = float(np.linalg.norm(v))
    if nv == 0.0:
        raise ZeroDivisionError("起始向量在 1⊥ 上为零")
    v = v / nv

    basis = [v]
    for _ in range(m_dim - 1):
        w = lap @ basis[-1]
        for q in basis:                     # 全重正交（防 Krylov 基条件数爆炸）
            w = w - float(q @ w) * q
        w = w - w.mean()                    # 保持 ⊂ 1⊥
        nw = float(np.linalg.norm(w))
        if nw < 1e-13:                      # Krylov 空间已饱和 ⇒ 提前停（维数实际不足）
            break
        basis.append(w / nw)
    q = np.column_stack(basis)
    ritz = np.linalg.eigvalsh(q.T @ lap @ q)
    return float(ritz[0])


def graph_algebraic_connectivity_golden(rows: int = 10, cols: int = 10) -> float:
    """B509 golden：方阵耦合图 P_rows □ P_cols 的代数连通度闭式（**精确**，Kronecker 和）。

        λ₂ = 2 − 2·cos(π / max(rows, cols))

    推导：Cartesian 积的 Laplacian 谱 = 因子谱之和；路径图 Laplacian 本征
        λ_k(P_n) = 2 − 2cos(kπ/n), k=0..n−1 ⇒ 次小 = min(λ₁(P_rows), λ₁(P_cols))
        = 2 − 2cos(π / max(rows, cols))。
    """
    rows, cols = int(rows), int(cols)
    if rows < 2 or cols < 2:
        raise ValueError("方阵图须 rows, cols ≥ 2（否则无 2D 最近邻结构）")
    return 2.0 - 2.0 * math.cos(math.pi / float(max(rows, cols)))


def graph_algebraic_connectivity_candidate(rows: int = 10, cols: int = 10,
                                           m: int = _M_BY_BID["B509"]) -> float:
    """B509 candidate：Krylov 子空间 Rayleigh–Ritz 极小化（与 golden 方法学独立）。"""
    lap = _grid_laplacian(int(rows), int(cols))
    return _krylov_lambda2(lap, int(m))


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b509(rows: int = 10, cols: int = 10) -> float:
    return graph_algebraic_connectivity_golden(rows, cols)


def cand_b509(rows: int = 10, cols: int = 10, m: int = _M_BY_BID["B509"]) -> float:
    return graph_algebraic_connectivity_candidate(rows, cols, m)


@functools.lru_cache(maxsize=None)
def _g509_c(rows: int, cols: int) -> float:
    return golden_b509(rows, cols)


@functools.lru_cache(maxsize=None)
def _c509_c(rows: int, cols: int, m: int) -> float:
    return cand_b509(rows, cols, m)


B509_DEFAULT_PARAMS = dict(_B509_DEFAULT)


#: 自检用例：bid, 物理参数（golden 键）
_CASES = (
    ("B509", _B509_DEFAULT),
)


def _measure_candidates():
    """现算：默认档 golden/cand/残差 + 判据 D 扫描链（粗→细）。"""
    out = {}
    for bid, params in _CASES:
        tol = _TOL_BY_BID[bid]
        grid = _GRID_BY_BID[bid]
        gold = golden_b509(**params)
        chain = []
        for m in grid:
            c = cand_b509(m=m, **params)
            chain.append((m, abs(c - gold)))
        resid = [r for _, r in chain]
        default_m = _M_BY_BID[bid]
        d_res = abs(cand_b509(m=default_m, **params) - gold)
        ratios = [resid[i] / resid[i + 1] for i in range(len(resid) - 1)
                  if resid[i + 1] > 0]
        out[bid] = {
            "golden": gold, "default_m": default_m, "tol": tol,
            "chain": chain, "resid": resid, "default_resid": d_res,
            "mono": all(resid[i] > resid[i + 1] for i in range(len(resid) - 1)),
            "ratios": ratios,
            "margin": tol / d_res if d_res > 0 else float("inf"),
            "gold_over_tol": abs(gold) / tol,
        }
    return out


if __name__ == "__main__":  # pragma: no cover —— 逐锚自检（判据 D 可标定 + 非代数恒等）
    print("=" * 72)
    print("Batch J2-M4 数值核自检（B509 · 耦合图代数连通度 λ₂ / Fiedler 值）")
    print("=" * 72)
    bad = 0
    for bid, m in _measure_candidates().items():
        print(f"\n[{bid}] golden={m['golden']:.12e}  tol={m['tol']:.1e}  "
              f"默认 m={m['default_m']}")
        print("  判据 D 残差链：" +
              "  ".join(f"m={n}→{r:.3e}" for n, r in m["chain"]))
        print("  实测比值：  " + "  ".join(f"{x:.2f}×" for x in m["ratios"]))
        print(f"  默认档残差={m['default_resid']:.3e}  余量={m['margin']:.1f}×  "
              f"|golden|/tol={m['gold_over_tol']:.3e}  MONO={m['mono']}")
        for name, cond in (
            ("默认档残差 > 1e-12（排除代数恒等）", m["default_resid"] > 1e-12),
            ("默认档残差 < tol", m["default_resid"] < m["tol"]),
            ("余量 ≥ 100×", m["margin"] >= 100.0),
            ("|golden|/tol ≥ 13.5", m["gold_over_tol"] >= 13.5),
            ("判据 D 严格单调（粗→细）", m["mono"]),
            ("粗端残差浮出地板（>1e-12）", m["resid"][0] > 1e-12),
            ("残差动态范围 ≥ 1e4×（排除「残差与离散参数无关」指纹）",
             m["resid"][0] / m["default_resid"] >= 1e4),
            ("每档比值 > 1（真下降）", all(x > 1.0 for x in m["ratios"])),
        ):
            ok = bool(cond)
            bad += 0 if ok else 1
            print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print("\n" + ("ALL PASS" if bad == 0 else f"{bad} FAIL"))
    raise SystemExit(0 if bad == 0 else 1)
