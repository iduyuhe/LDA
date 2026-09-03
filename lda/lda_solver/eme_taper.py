# -*- coding: utf-8 -*-
"""B8 · 绝热锥度传输效率 —— 独立候选求解器：本征模展开法（EME）。

为什么是 EME（而不是 BPM / FDTD）
---------------------------------
B8 的默认锥度 **L = 200 µm**（w1=0.2 → w2=0.5 µm），长宽比 400:1。

* **FDTD**：横向 ~6 µm / 纵向 200 µm，dx≈20 nm ⇒ 3e6 网格 × ~3.5e4 时间步，
  纯 numpy 需数小时——不可接受；
* **BPM（分步傅里叶）**：**已实测证否**（2026-09-03，`bpm_taper.py` 的失败记录）。
  根因是**旁轴近似在窄端失效**：w1=0.2 µm 的局部基模 n_eff≈1.90，远低于脊区
  n_core=2.44（更接近包层 1.44），旁轴展开参数 (n_core²−n_ref²)/n_ref² 达 **65%**。
  后果是伪辐射**随长度累积**：实测 T 随 L 增大反而**下降**（0.9936@25µm →
  0.9729@200µm），非绝热的 L=2 µm 反而 T=0.9967 —— **物理趋势完全反号**。
  且该误差**减小 dz 不收敛**（dz/2、dx/2 仍变 1.1e-2），因为它是模型误差
  （旁轴算子本征态 ≠ Helmholtz 本征态），不是离散误差。
* **EME**：每个 z 切片解**完整 Helmholtz 本征问题**（无旁轴假设），切片内传播
  精确、切片间用模式重叠矩阵投影。对**弱导模、强导模一律成立**；
  **功率守恒内建**（模式正交归一 ⇒ Σ|c|² ≤ 1 ⇒ T ≤ 1，与 B19 无源性同构）。

物理与数值模型
--------------
* 垂向已由 EIM 降维：横向问题中脊区折射率取 **n_eff**（默认 2.44），
  侧向包层取 **n_clad**（默认 1.44）；宽度沿 z **线性**变化
  w(z) = w1 + (w2−w1)·z/L（golden 只给 w1/w2/L，未指定廓形，取中性默认）。
* 切片离散：n_slices 个均匀片，片宽取中点 w(z_mid)；片内模态传播
  exp(−i β_m dz)；相邻片间重叠矩阵 O_{nm} = ∫ φ_n^{(j+1)} φ_m^{(j)} dx。
* 输入 = 首片基模，输出取末片基模的功率占比：

      T = |c_out,0|²,   c_out = O_{N−1}·diag(e^{−iβ dz})·…·O_0·e_0

自校锚（可标定，非自证）
------------------------
* **切片收敛**：n_slices 200→400 ⇒ T 变化 < 1e-4（可标定，非恒零）。
* **模式数收敛**：M 16→32 ⇒ T 变化 < 1e-4。
* **直波导恒等**：w1=w2 ⇒ T ≡ 1（任意 L）——算子正确性的硬守卫。
* **绝热单调性**：L↑ ⇒ T↑ 并趋于 1（绝热判据 ∝ L 的物理必然）。
* **反向**：非绝热（L=2 µm）⇒ T 明显 < 0.99（锚 tol=1e-2）。

诚实边界（写进 note，不得省略）
------------------------------
1. **EIM 降维**：垂向被压成常数 n_eff，故本候选**不含**垂向辐射与极化耦合；
   B8 的 golden 是「绝热极限」这一**物理上界**，二者在该语义下可比。
2. **单向近似**：EME 只算前向模式，忽略背向反射。绝热锥度的反射本就极小，
   且反射只会**降低** T ⇒ 本候选对 golden（上界 1.0）不会虚高。
3. **阶梯近似**：n_slices 有限 ⇒ 锥度被离散成台阶；收敛由上条自校锚钉住。
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import eigh_tridiagonal

__all__ = ["slab_modes", "taper_transmission", "abrupt_overlap",
           "te0_neff_analytic", "selfcheck",
           "DEFAULT_DZ", "DEFAULT_MMODES", "DEFAULT_DX",
           "DEFAULT_WINDOW_UM"]

# 生产档位（v0.9.26 实测标定，见 selfcheck 的收敛锚）
DEFAULT_DZ = 0.4           # z 向目标步长 um（n_slices 由 L/dz 推导，**不可固定**）
DEFAULT_MMODES = 32        # 每片保留模式数
DEFAULT_DX = 0.02          # 横向步长 um
DEFAULT_WINDOW_UM = 16.0   # 横向计算窗口 um

# 🔴 **为什么 n_slices 必须按 dz 推导而不是固定**（2026-09-03 血案）
# 固定 n_slices 时：①每片宽度步长 Δw=(w2−w1)/n_slices **与 L 无关** ⇒ 阶梯失配
# 损耗 L 无关；②L=200 时 dz=1 µm，辐射模失配相位 Δβ·dz 达 ~5 rad/片，**严重欠
# 采样** ⇒ 绝热相干抵消完全没发生。实测 T 在 dz 0.2/0.1/0.05 × M 16/32/64 全域
# 稳在 0.9956~0.9969，**L=2 与 L=200 同值** —— 判据零判别力。
# 改成按 dz 定片数后：Δw ∝ 1/L ⇒ 损耗 ∝ 1/L，物理趋势立刻恢复。
#
# 标定记录（win=16, M=32, L=200）：
#   dz 0.8 / 0.4 / 0.2 ⇒ 1−T = 9.73e-5 / 4.65e-5 / 2.34e-5（≈一阶收敛）
#   ⇒ 取 dz=0.4（2.7s），对 dz=0.2 的偏差 2.3e-5，仅占锚 tol 1e-2 的 0.23%。
MIN_NSLICES = 20


def _index_profile(x: np.ndarray, w: float, n_core: float,
                   n_clad: float) -> np.ndarray:
    """横向折射率剖面：|x| ≤ w/2 为脊区 n_core，其余 n_clad。

    🔴 **亚网格面积加权（不可改成硬判据）**：返回每格心的**等效折射率**
    sqrt(⟨n²⟩)，其中 ⟨n²⟩ 是 n² 在该格 [x−h/2, x+h/2] 上的**覆盖比例加权平均**
    ——核心区占比 f，包层占比 1−f。

    为什么必须这样：B8 的半宽只从 0.1 µm 走到 0.25 µm，dx=0.02 µm 时**只跨
    7.5 个网格**。若用 `|x| <= w/2` 硬判据，则无论 z 向切多少片，横向剖面**只有
    ~8 个可取值** ⇒ 锥度被离散成 8 次**突跳**，绝 adiabatic 性完全没被建模。
    实测后果（2026-09-03）：T 在 dz 0.2/0.1/0.05 × M 16/32/64 全域稳在
    0.9956~0.9969，**与 L 完全无关**（L=2 与 L=200 同值）——损耗是分辨率无关的
    ~0.4% 地板，判据零判别力。
    """
    h = float(x[1] - x[0])
    a = 0.5 * float(w)
    lo = x - 0.5 * h
    hi = x + 0.5 * h
    ov = np.clip(np.minimum(hi, a) - np.maximum(lo, -a), 0.0, None)
    f = ov / h
    n2 = f * (n_core ** 2) + (1.0 - f) * (n_clad ** 2)
    return np.sqrt(n2)


def slab_modes(x: np.ndarray, n_prof: np.ndarray, k0: float, m_modes: int):
    """一维横向 Helmholtz 本征问题：φ'' + k0²n²φ = β²φ（Dirichlet 外边界）。

    返回 (phis, betas)：phis 形状 (N, M)（列已按 ∫φ²dx=1 归一），
    betas 长度 M，**按降序**（第 0 个即基模）。
    """
    h = float(x[1] - x[0])
    N = len(x)
    d = -2.0 / h**2 + (k0**2) * n_prof**2      # 主对角
    e = np.full(N - 1, 1.0 / h**2)             # 次对角
    m = int(min(m_modes, N - 2))
    w_, v_ = eigh_tridiagonal(d, e, select="i", select_range=(N - m, N - 1))
    order = np.argsort(w_)[::-1]
    # 🔴 **复数 β，不得截断到 0**：本征值 β² 对**倏逝模为负**（β²<0 ⇒ β 纯虚）。
    # 若用 np.maximum(w_, 0) 把负本征值夹成 0，则 exp(−i·0·dz)=1 ⇒ 倏逝模被当成
    # **无衰减无相位的传播模**，既破坏场完备性又会把功率"锁"在不应存在的通道里。
    #   * 取复数 sqrt ⇒ 倏逝模 exp(−i·i|β|·dz)=exp(−|β|dz) 正确指数衰减。
    #   * 🔴 **分支必须取 Im(β)<0**：sqrt 主值给 **+i|β|** ⇒ exp(−i·(+i|β|)dz)
    #     = **exp(+|β|dz) 指数增长** —— 实测 L=5 µm 就溢出到 4e30、L=200 直接 inf。
    #     衰减分支是 **β=−i|β|**（虚部为负）。
    betas = np.sqrt(w_[order].astype(np.complex128))
    betas = np.where(betas.imag > 0.0, -betas, betas)
    phis = v_[:, order]
    phis = phis / np.sqrt(np.sum(phis**2, axis=0) * h)
    # 符号规整（重叠矩阵符号一致性）
    for j in range(phis.shape[1]):
        if phis[np.argmax(np.abs(phis[:, j])), j] < 0:
            phis[:, j] = -phis[:, j]
    return phis, betas


def _grid(window: float, dx: float):
    """横向均匀网格（格心偏置半个格，保证关于 x=0 对称）。"""
    N = int(round(window / dx))
    if N % 2:
        N += 1
    return (np.arange(N) - N // 2) * dx


def abrupt_overlap(w1: float, w2: float, wl: float, n_eff: float,
                   n_clad: float, dx: float = DEFAULT_DX,
                   window: float = DEFAULT_WINDOW_UM) -> float:
    """**突变结**极限的传输效率 |⟨φ₀(w2)|φ₀(w1)⟩|²（独立参照，非 EME）。

    物理意义：L→0 时锥度退化为**直接对接**，传输率就是两端基模的重叠积分。
    这是任何锥度 T(L) 的**下界参照**——渐变只能比突变好，不能更差。
    实测（w=0.2→0.5）：0.98525(dx=0.02) / 0.98535(dx=0.01)，窗口 8/16/32 全一致。
    """
    x = _grid(window, dx)
    k0 = 2.0 * np.pi / wl
    p1, _ = slab_modes(x, _index_profile(x, w1, n_eff, n_clad), k0, 4)
    p2, _ = slab_modes(x, _index_profile(x, w2, n_eff, n_clad), k0, 4)
    return float(np.sum(p2[:, 0] * p1[:, 0]) * dx) ** 2


def te0_neff_analytic(w: float, wl: float, n_core: float,
                      n_clad: float) -> float:
    """对称平板 **TE0 解析**有效折射率（brentq 解色散方程）。

        u·tan u = sqrt(V² − u²),  V = (w/2)·k0·sqrt(n_core² − n_clad²)
        n_eff²  = n_core² − (u / ((w/2)·k0))²

    🔴 用途：**非自证**地验证 `slab_modes` 的数值本征解。二者方法学完全独立
    （解析超越方程求根 vs 有限差分矩阵本征值），不构成循环论证。
    实测 w=0.2 ⇒ 1.8596、w=0.5 ⇒ 2.2199，与数值解吻合到 1e-4。
    """
    from scipy.optimize import brentq
    k0 = 2.0 * np.pi / wl
    V = 0.5 * w * k0 * np.sqrt(n_core**2 - n_clad**2)
    hi = min(V, 0.5 * np.pi) - 1e-9
    if hi <= 1e-9:
        raise ValueError(f"V={V:.4f} 过小，TE0 无解（低于截止）")
    f = lambda u: u * np.tan(u) - np.sqrt(max(V**2 - u**2, 0.0))
    u = brentq(f, 1e-12, hi, xtol=1e-14, rtol=1e-15)
    return float(np.sqrt(n_core**2 - (u / (0.5 * w * k0)) ** 2))


def taper_transmission(w1: float, w2: float, L: float, wl: float,
                       n_eff: float, n_clad: float,
                       m_modes: int = DEFAULT_MMODES,
                       dx: float = DEFAULT_DX,
                       window: float = DEFAULT_WINDOW_UM,
                       dz: float = DEFAULT_DZ,
                       n_slices: int | None = None,
                       n_core: float | None = None) -> float:
    """绝热锥度传输效率 T（0~1），EME 求解。

    参数
    ----
    w1, w2 : 输入端 / 输出端脊宽（um）；L : 锥度长度（um）；wl : 真空波长（um）
    n_eff  : 脊区（EIM 降维后）有效折射率；n_clad : 侧向包层折射率
    dz     : z 向目标步长（um）——**切片数由 L/dz 推导**；显式给 n_slices 则优先
    m_modes / dx / window : 数值档位（见模块自校锚）
    n_core : 兼容位（B8 参数里的材料折射率 3.48；横向 EIM 问题不用）
    """
    if L <= 0 or w1 <= 0 or w2 <= 0:
        raise ValueError("w1/w2/L 须为正")
    x = _grid(window, dx)
    k0 = 2.0 * np.pi / wl
    nsl = int(n_slices) if n_slices else max(MIN_NSLICES, int(round(L / dz)))
    dz_eff = L / nsl

    widths = w1 + (w2 - w1) * ((np.arange(nsl) + 0.5) / nsl)
    modes = [slab_modes(x, _index_profile(x, float(w), n_eff, n_clad), k0,
                        m_modes) for w in widths]

    # 初始激励：首片基模
    c = np.zeros(len(modes[0][1]), dtype=np.complex128)
    c[0] = 1.0
    for j, (phis, betas) in enumerate(modes):
        c = c * np.exp(-1j * betas * dz_eff)     # 片内精确模态传播
        if j + 1 < len(modes):
            phis_next = modes[j + 1][0]
            O = (phis_next.T @ phis) * dx        # 重叠矩阵 O[n,m]
            c = O @ c
    return float(abs(c[0]) ** 2)


# --------------------------- 自校锚（可标定） ---------------------------
def selfcheck(verbose: bool = True, quick: bool = False) -> bool:
    """EME 自校锚。`quick=True` 跳过三条耗时的收敛锚（③④⑤）。

    ⓪ 直波导恒等（算子硬守卫）  ① 模式解算器 vs 解析 TE0（**非自证**）
    ② 基线落在锚判据窗口内      ③ dz 收敛  ④ 模式数收敛  ⑤ 窗口收敛
    ⑥ 绝热单调性（**限定已收敛区** L≥5）  ⑦ 反向非绝热  ⑧ 突变结下界
    """
    P = dict(w1=0.2, w2=0.5, L=200.0, wl=1.55, n_eff=2.44, n_clad=1.44)
    ok = True

    def _chk(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")

    # ⓪ 直波导恒等（算子硬守卫）：w1=w2 ⇒ T≡1（任意 L，任意 dz）
    Ts = [taper_transmission(w1=0.5, w2=0.5, L=Lv, wl=1.55, n_eff=2.44,
                             n_clad=1.44) for Lv in (2.0, 50.0, 200.0)]
    _chk("⓪ 直波导恒等 w1=w2 ⇒ T≡1（算子守卫）",
         all(abs(t - 1.0) < 1e-6 for t in Ts),
         "T=" + "/".join(f"{t:.8f}" for t in Ts))

    # ① 模式解算器 vs 解析 TE0 色散（方法学独立：超越方程求根 vs 矩阵本征值）
    #    🔴 判据是「**收敛到解析值**」，不是单点阈值——解算器若写错，要么收敛到
    #    别的值、要么不收敛。实测 O(dx²)：w=0.2 时 dx 0.04/0.02/0.01/0.005 ⇒
    #    |Δn_eff| 5.33e-3 / 7.38e-4 / 1.84e-4 / 4.61e-5（比值 7.2 / 4.0 / 4.0）。
    def _dev(wv, dx):
        xg = _grid(DEFAULT_WINDOW_UM, dx)
        _, betas = slab_modes(xg, _index_profile(xg, wv, 2.44, 1.44),
                              2.0 * np.pi / 1.55, 4)
        num = float(betas[0].real) * 1.55 / (2.0 * np.pi)
        return abs(num - te0_neff_analytic(wv, 1.55, 2.44, 1.44))
    d_coarse = [_dev(wv, DEFAULT_DX) for wv in (0.2, 0.5, 1.0)]
    d_fine = [_dev(wv, 0.005) for wv in (0.2, 0.5, 1.0)]
    ratios = [a / b for a, b in zip(d_coarse, d_fine)]
    _chk("① 模式解算器 → 解析 TE0（O(dx²) 收敛，非自证）",
         max(d_fine) < 1e-4 and min(ratios) >= 8.0,
         "dx 0.02→0.005 |Δ|=" + "/".join(f"{a:.1e}→{b:.1e}" for a, b
                                         in zip(d_coarse, d_fine))
         + f"  降 " + "/".join(f"{r:.0f}×" for r in ratios))

    T0 = taper_transmission(**P)
    _chk("② 基线 T（L=200µm 深度绝热）", 0.99 <= T0 <= 1.0 + 1e-9,
         f"T={T0:.9f}  1−T={1-T0:.3e}")

    if not quick:
        # ③ dz 收敛（可标定，非恒零）：0.4 → 0.2
        T3 = taper_transmission(**P, dz=0.2)
        _chk("③ dz 收敛 0.4→0.2，ΔT < 1e-4", abs(T3 - T0) < 1e-4,
             f"|ΔT|={abs(T3-T0):.2e}")

        # ④ 模式数收敛 32 → 64
        T4 = taper_transmission(**P, m_modes=64)
        _chk("④ 模式数收敛 32→64，ΔT < 1e-4", abs(T4 - T0) < 1e-4,
             f"|ΔT|={abs(T4-T0):.2e}")

        # ⑤ 窗口收敛 16 → 32 µm
        T5 = taper_transmission(**P, window=32.0)
        _chk("⑤ 窗口收敛 16→32µm，ΔT < 1e-4", abs(T5 - T0) < 1e-4,
             f"|ΔT|={abs(T5-T0):.2e}")

    # ⑥ 绝热单调性 —— 🔴 **只取已收敛区 L≥5**
    #    L≤2 时窗口 8/16/32 的 T 相差达 4e-3（箱模谱在 Δβ·L≪1 时欠采样），
    #    未收敛 ⇒ 拿它做单调性断言会假 FAIL。已收敛区实测严格单调且
    #    (1−T) ∝ 1/L（1.38e-3@5 → 4.65e-5@200，长度 40×、损耗降 29.7×）。
    Ls = (5.0, 20.0, 50.0, 200.0)
    Tm = [taper_transmission(**{**P, "L": Lv}) for Lv in Ls]
    _chk("⑥ 绝热单调性 L↑ ⇒ T↑（已收敛区 L≥5µm）",
         all(b >= a - 1e-9 for a, b in zip(Tm, Tm[1:])),
         "T=" + "/".join(f"{t:.6f}" for t in Tm))

    # ⑦ 反向：非绝热 ⇒ 远跌破 0.99
    #    🔴 单扰 L 不行：0.2→0.5 这个几何的**损耗上限只有 ~1.5%**（突变结重叠
    #    0.9853），L 缩到 0.2µm 也只到 0.9933 —— 穿不透 tol=1e-2。
    #    故反向用例取 **w2=3.0 / L=1.0 µm**（同一参数空间内的"粗暴突变结"）。
    Trev = taper_transmission(w1=0.2, w2=3.0, L=1.0, wl=1.55,
                              n_eff=2.44, n_clad=1.44)
    _chk("⑦ 反向 非绝热（w2=3.0/L=1.0µm）⇒ T < 0.6", Trev < 0.6,
         f"T={Trev:.5f} vs 基线 {T0:.5f}")

    # ⑧ 突变结下界：渐变不可能比直接对接更差
    Tab = abrupt_overlap(0.2, 0.5, 1.55, 2.44, 1.44)
    _chk("⑧ 突变结下界 T_abrupt ≤ T(L) ≤ 1", Tab <= T0 <= 1.0 + 1e-9,
         f"T_abrupt={Tab:.6f} ≤ T={T0:.6f}")

    return bool(ok)


if __name__ == "__main__":
    print("B8 · EME 锥度求解器自校锚")
    print("PASS" if selfcheck(True) else "FAIL")
