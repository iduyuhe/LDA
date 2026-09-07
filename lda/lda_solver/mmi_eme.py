"""LDA · MMI 1×2 过量损耗求解核（2D-EIM 本征模展开 EME）· v0.9.56。

═══════════════════════════════════════════════════════════════════════
🔴 结论先行：**本求解核目前不足以判决 E5 实证锚（0.05 dB / tol 0.1 dB）**。
下面两节是实测证据，必须与任何引用本模块的结论一起读。
═══════════════════════════════════════════════════════════════════════

方法
────
2D 有效折射率（EIM）约化 + 一维横向本征模展开（EME）：
    ① 解接入波导（宽 w）基模 ψ_in；
    ② 解多模区（宽 W_mmi）全部导模 {φ_m, β_m}（n_eff > n_clad）；
    ③ 输入场在多模区导模上展开：c_m = ⟨φ_m|ψ_in⟩；
    ④ 各模按自身传播常数传播 L_mmi：c_m·exp(i·β_m·L)；
    ⑤ 输出场与两条输出臂基模重叠 ⇒ t₁、t₂；
    ⑥ excess_loss_dB = −10·log10(|t₁|²+|t₂|²)
       （输入输出波导同宽同材质 ⇒ 模式归一化常数在比值中精确抵消）。
纯代数（对称三对角本征分解 + 重叠积分），确定性可复现，无瞬态/吸收层/源注入。
LLM 不进判决路径；本模块只产出**死标量**。

为什么不是 2D FDTD（诚实边界）
────────────────────────────
本锚最初按「2D FDTD 全场时域」路线实施，实测**直波导控制实验都无法让导模沿线
保幅**（0.5 µm 直波导 ≈0.7 dB/µm 虚假衰减且非单调）——吸收层/源注入层面的数值
缺陷，不是 MMI 物理。按「全绿≠无失真」纪律，**不拿连直波导都测不准的求解器去
判决锚题**，该实现已删除（不入库，避免后人误用）。

为什么 EME 也判不了 E5（实测，2026-09-06）
────────────────────────────────────────
1. **自成像保真度自检不合格**。MMI 的定义性质是「L=3L_π/4 处出现单重自像」。
   本模型在 W=2.8 处该保真度只有 **0.827**（理论上限 p_in²≈0.9898），W=4.0
   →0.713，W=6.0→0.549。模数越少本应成像越差，但实测**越宽越差**，说明是
   色散偏离抛物线在长距离上累积，而非窄 MMI 的模数瓶颈。
2. **对拍长 L_π 病态敏感** ⇒ 结构性不可判。锚题 L=27 µm 落在模型自洽成像
   长度（(9/8)·L_π≈24.1 µm）的**侧翼**，此处 excess 对长度极敏感。实测
   L_π 相对误差 ε 的误差传播（等效长度 L/(1+ε)，L=27，y_split=W/4）：
       ε=±1%   ⇒ excess 摆动 **0.199 dB**（≈ 2× tol=0.1）
       ε=±2.5% ⇒ 摆动 **1.99 dB**（≈ 20× tol）
       ε=±5%   ⇒ 摆动 **2.82 dB**（≈ 28× tol）
   对 220 nm SOI 的 MMI，2D-EIM 的 L_π 误差远不止 1%（本模型 dl 从 0.04
   细化到 0.005，L_π 就从 21.05 漂到 21.48，即 2%）。
   ⇒ **tol=0.1 dB 的 E5 在原理上不可判**，这是 roadmap 已判 C2+C5 的**实测确认**。
3. 数值事实（dl=0.01）：L=27、y_split=W/4 下 excess=**4.33 dB**；即使放开
   (L, y_split) 全平面寻优，模型自身最优也只有 **0.44 dB**（T=0.90），
   仍是 golden 0.05 dB 的 9 倍、超出 tol 4.4 倍 ⇒ 换几何解释也救不回来。

用途
────
本模块作为**可复用的 MMI 物理求解能力**入库（设计扫描 / 教学 / 后续三维矢量化
的对照基线），并配 `run_mmi_eme_smoke.py` 锁死上述实测事实。**不挂 E5 的
candidate 字段**（挂上会让 CI 变红或迫使放宽容差，两者都违反诚实边界）。
"""
from __future__ import annotations

import math

import numpy as np

# ---- 有效折射率约化参数（220nm SOI 脊波导 TE0，标准 EIM 约化） ----
N_CORE_2D = 2.80   # slab 有效折射率（多模区与接入波导同厚度 ⇒ 同一约化 n）
N_CLAD_2D = 1.44   # 氧化硅包层

# MMI 1×2 设计几何（来自锚题 E-MMI-1X2-EL 器件：2.8×27 µm² footprint）
MMI_W_UM = 2.8
MMI_L_UM = 27.0

# 1×2 双像成像长度族（抛物线近似下）：L = (3/8 + 3m/4)·L_π
TWO_IMAGE_L_FACTORS = (0.375, 1.125, 1.875)


# ---------------------------------------------------------------------------
# 一维横向本征模
# ---------------------------------------------------------------------------
def slab_modes(eps_y: np.ndarray, dl: float, wl_um: float,
               n_clad: float = N_CLAD_2D):
    """1D 平板波导**导模**（n_eff > n_clad）→ (n_effs, modes)。

    解对称三对角本征问题  [d²/dy² + k0²·ε(y)]·φ = k0²·n_eff²·φ，
    取所有 n_eff > n_clad 的本征对，按 n_eff **降序**返回。

    返回 (n_effs (M,), modes (Ny, M))：modes 各列由 eigh 保证**正交归一**
    （欧氏内积），故 ⟨φ_m|φ_n⟩ = δ_mn，可直接用于功率归一化展开。
    """
    n = len(eps_y)
    k0 = 2.0 * math.pi / wl_um
    main = -2.0 / (dl * dl) + (k0 * k0) * eps_y
    A = np.diag(main)
    if n > 1:
        off = np.full(n - 1, 1.0 / (dl * dl))
        A = A + np.diag(off, 1) + np.diag(off, -1)
    vals, vecs = np.linalg.eigh(A)
    order = np.argsort(vals)[::-1]          # 降序：基模在前
    vals = vals[order]
    vecs = vecs[:, order]
    keep = vals > (k0 * k0) * (n_clad * n_clad)   # 仅导模
    neff = np.sqrt(np.maximum(vals[keep], 0.0)) / k0
    return neff, vecs[:, keep]


def slab_te_neff_analytic(n_core: float, n_clad: float, d_um: float,
                          wl_um: float, m: int = 0):
    """对称平板波导 TE_m 模 n_eff 的**解析**解（超越方程二分解）。

    独立校验用：与 `slab_modes` 的有限差分解互为交叉验证，两者方法完全不同
    （本征分解 vs 超越方程求根），一致性是本模块可信度的第一道闸门。

    偶模(m even)：w = u·tan(u)；奇模(m odd)：w = −u·cot(u)，
    u ∈ (mπ/2, (m+1)π/2)，u² + w² = V²，V = k0·(d/2)·√(n_core²−n_clad²)。
    返回 n_eff；若该阶不存在（u 会超过 V）返回 None。
    """
    k0 = 2.0 * math.pi / wl_um
    V = k0 * (d_um / 2.0) * math.sqrt(max(n_core ** 2 - n_clad ** 2, 0.0))
    lo, hi = m * math.pi / 2.0, (m + 1) * math.pi / 2.0
    if lo >= V:
        return None                      # 该阶截止，非导模

    def f(u: float) -> float:
        w = math.sqrt(max(V * V - u * u, 0.0))
        if m % 2 == 0:
            return u * math.tan(u) - w
        t = math.tan(u)
        if abs(t) < 1e-14:
            return -w
        return -u / t - w

    a, b = lo + 1e-12, min(hi - 1e-12, V - 1e-12)
    if b <= a or f(a) * f(b) > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (a + b)
        if f(a) * f(mid) <= 0:
            b = mid
        else:
            a = mid
    u = 0.5 * (a + b)
    beta2 = (k0 * n_core) ** 2 - (2.0 * u / d_um) ** 2
    if beta2 <= 0:
        return None
    return math.sqrt(beta2) / k0


def beat_length(neff: np.ndarray, wl_um: float) -> float:
    """拍长 L_π = π/(β₀−β₁)（µm）。"""
    if len(neff) < 2:
        raise ValueError("导模数 < 2，无法定义拍长")
    k0 = 2.0 * math.pi / wl_um
    return math.pi / (k0 * (neff[0] - neff[1]))


def _guide_eps(ys: np.ndarray, w_um: float, y_center: float,
               n_core: float, n_clad: float) -> np.ndarray:
    """以 y_center 为中心、宽 w_um 的单根波导的 ε 剖面。"""
    eps = np.full(len(ys), n_clad ** 2)
    eps[np.abs(ys - y_center) <= w_um / 2.0] = n_core ** 2
    return eps


def _fundamental(ys: np.ndarray, w_um: float, y_center: float, dl: float,
                 wl_um: float, n_core: float, n_clad: float) -> np.ndarray:
    """单根波导的基模（已正交归一；符号统一为峰值正）。"""
    eps = _guide_eps(ys, w_um, y_center, n_core, n_clad)
    _ne, modes = slab_modes(eps, dl, wl_um, n_clad)
    if modes.shape[1] == 0:
        raise ValueError("波导无导模（几何/折射率不支持束缚模）")
    m = np.asarray(modes[:, 0], dtype=float)
    if abs(float(m.min())) > abs(float(m.max())):
        m = -m
    return m


class MmiBasis:
    """多模区模式基 + 输入展开系数（只解一次，供长度/位置扫描复用）。"""

    def __init__(self, ys, psi_in, neff, phi, c):
        self.ys, self.psi_in, self.neff, self.phi, self.c = ys, psi_in, neff, phi, c

    def field(self, L_um: float, wl_um: float) -> np.ndarray:
        """传播 L_um 后的复场（多模区导模基下）。"""
        k0 = 2.0 * math.pi / wl_um
        return self.phi @ (self.c * np.exp(1j * k0 * self.neff * L_um))


def build_basis(w_um: float = 0.5, W_mmi: float = MMI_W_UM,
                wl_um: float = 1.55, n_core: float = N_CORE_2D,
                n_clad: float = N_CLAD_2D, dl: float = 0.01,
                y_pad_um: float = 3.0):
    """构建一次模式基（供 `mmi_excess_loss` 与扫描复用）。"""
    yhalf = W_mmi / 2.0 + y_pad_um
    Ny = int(round(2.0 * yhalf / dl)) | 1         # 奇数：网格关于 y=0 严格对称
    ys = (np.arange(Ny) - (Ny - 1) / 2.0) * dl
    psi_in = _fundamental(ys, w_um, 0.0, dl, wl_um, n_core, n_clad)
    neff, phi = slab_modes(_guide_eps(ys, W_mmi, 0.0, n_core, n_clad),
                           dl, wl_um, n_clad)
    if phi.shape[1] == 0:
        raise ValueError("MMI 多模区无导模")
    c = phi.T @ psi_in
    return MmiBasis(ys, psi_in, neff, phi, c)


# ---------------------------------------------------------------------------
# MMI 1×2 过量损耗
# ---------------------------------------------------------------------------
def mmi_excess_loss(w_um: float = 0.5, W_mmi: float = MMI_W_UM,
                    L_mmi: float = MMI_L_UM, out_gap: float = 0.9,
                    wl_um: float = 1.55, n_core: float = N_CORE_2D,
                    n_clad: float = N_CLAD_2D, dl: float = 0.01,
                    y_pad_um: float = 3.0, verbose: bool = False):
    """SOI MMI 1×2 过量损耗（dB），2D-EIM 本征模展开独立求解。

    `out_gap` = 两条输出臂的**边缘间距**（µm）；臂中心偏移
    y_split = out_gap/2 + w_um/2。标准 1×2 取 y_split = W/4 ⇒ out_gap = W/2 − w。

    返回 dict：{"value": excess_loss_dB, "T": 透射率, "t1"/"t2": 复振幅,
                "balance": 双输出不平衡度, "n_modes": 多模区导模数,
                "L_pi_um": 拍长, "power_in_mmi_modes": 输入功率落入导模的比例, ...}
    """
    B = build_basis(w_um, W_mmi, wl_um, n_core, n_clad, dl, y_pad_um)
    ys, psi_in, neff, phi, c = B.ys, B.psi_in, B.neff, B.phi, B.c
    y_split = out_gap / 2.0 + w_um / 2.0

    Eout = B.field(L_mmi, wl_um)
    psi1 = _fundamental(ys, w_um, +y_split, dl, wl_um, n_core, n_clad)
    psi2 = _fundamental(ys, w_um, -y_split, dl, wl_um, n_core, n_clad)
    t1 = complex(psi1 @ Eout)
    t2 = complex(psi2 @ Eout)

    T = abs(t1) ** 2 + abs(t2) ** 2
    excess_loss_dB = -10.0 * math.log10(max(T, 1e-300))

    L_pi = beat_length(neff, wl_um)
    if verbose:
        print(f"n_modes={phi.shape[1]} L_pi={L_pi:.2f}µm "
              f"|t1|={abs(t1):.4f} |t2|={abs(t2):.4f} T={T:.4f} "
              f"excess={excess_loss_dB:.4f} dB")

    return {
        "value": float(excess_loss_dB),
        "T": float(T), "t1": abs(t1), "t2": abs(t2),
        "balance": float(abs(abs(t1) ** 2 - abs(t2) ** 2) / max(T, 1e-300)),
        "n_modes": int(phi.shape[1]),
        "L_pi_um": float(L_pi),
        "power_in_mmi_modes": float(np.sum(np.abs(c) ** 2)),
        "energy_out": float(np.sum(np.abs(Eout) ** 2)),
        "n_eff_mmi": [float(x) for x in neff],
        "W_mmi": W_mmi, "L_mmi": L_mmi, "out_gap": out_gap,
        "y_split_um": y_split, "dl": dl, "Ny": int(len(ys)),
        "n_core_2d": n_core, "n_clad_2d": n_clad,
    }


# ---------------------------------------------------------------------------
# 模型自校验（🔴 这两个函数是「能不能拿去判锚」的闸门，不是装饰）
# ---------------------------------------------------------------------------
def self_image_fidelity(W_mmi: float = MMI_W_UM, w_um: float = 0.5,
                        wl_um: float = 1.55, n_core: float = N_CORE_2D,
                        n_clad: float = N_CLAD_2D, dl: float = 0.01,
                        span_um: float = 2.5, n_scan: int = 51):
    """MMI 定义性质自检：L=3L_π/4 处应出现**单重自像**。

    返回 dict：{"fidelity": max_L |⟨ψ_in|E(L)⟩|², "upper_bound": p_in²,
                "L_at_max", "L_theory"}。
    理想（抛物线色散）时 fidelity 应逼近 upper_bound=p_in²≈0.99；
    实测 W=2.8 只有 0.827 ⇒ 色散偏离抛物线，模型自证不足。
    """
    B = build_basis(w_um, W_mmi, wl_um, n_core, n_clad, dl)
    L_pi = beat_length(B.neff, wl_um)
    L_theory = 0.75 * L_pi
    p_in = float(np.sum(np.abs(B.c) ** 2))
    best = (-1.0, 0.0)
    for i in range(n_scan):
        L = L_theory + (i / (n_scan - 1) - 0.5) * 2.0 * span_um
        f = abs(complex(B.psi_in @ B.field(L, wl_um))) ** 2
        if f > best[0]:
            best = (f, L)
    return {"fidelity": float(best[0]), "upper_bound": float(p_in ** 2),
            "power_in_modes": p_in, "L_at_max": float(best[1]),
            "L_theory": float(L_theory), "L_pi_um": float(L_pi),
            "W_mmi": W_mmi}


def beat_length_error_propagation(L_mmi: float = MMI_L_UM, out_gap: float = 0.9,
                                  tol_db: float = 0.1,
                                  rel_errs=(-0.05, -0.025, -0.01, 0.0, 0.01,
                                            0.025, 0.05), **kw):
    """结构性可判性度量：**拍长 L_π 的相对误差 ε 会放大成多大的 dB 摆动**。

    成像相位 ∝ β·L ∝ L/L_π，故 L_π 的相对误差 ε 等价于以**等效长度
    L/(1+ε)** 传播。对每个 ε 重算 excess，取给定 ε 档位下 ± 两值的**极差**。

    🔴 用「±ε 档位极差」而不是局部导数 |dExcess/dL|：后者在 L=27 这种局部
    极值点会退化到 ≈0（实测 0.18 dB/µm），给出「很稳健」的**假象**——正是
    「标签≠行为」类陷阱。极差对操作点不敏感，是稳健度量。

    返回 dict：{"spread_1pct"/"spread_5pct": dB 极差, "spread_over_tol_1pct"...,
                "values": {ε: excess_dB}, "excess_db": 基准值, "L_pi_um"}
    """
    vals = {}
    for e in rel_errs:
        vals[float(e)] = mmi_excess_loss(L_mmi=L_mmi / (1.0 + e),
                                         out_gap=out_gap, **kw)["value"]

    def spread(mag: float) -> float:
        hi = vals.get(mag)
        lo = vals.get(-mag)
        if hi is None or lo is None:
            return float("nan")
        return abs(hi - lo)

    s1, s5 = spread(0.01), spread(0.05)
    base = vals.get(0.0, float("nan"))
    return {"spread_1pct_db": float(s1), "spread_5pct_db": float(s5),
            "spread_over_tol_1pct": float(s1 / tol_db),
            "spread_over_tol_5pct": float(s5 / tol_db),
            "values": {k: float(v) for k, v in vals.items()},
            "excess_db": float(base), "tol_db": float(tol_db),
            "L_mmi": float(L_mmi)}


def best_case_excess(W_mmi: float = MMI_W_UM, w_um: float = 0.5,
                     wl_um: float = 1.55, n_core: float = N_CORE_2D,
                     n_clad: float = N_CLAD_2D, dl: float = 0.02,
                     n_L: int = 25, n_s: int = 9):
    """放开 (L, y_split) 全平面寻优，返回模型**自身能达到的最好**过量损耗。

    🔴 这是模型的**能力上界**：若它都远超 tol，则任何几何解释的修正都救不回来。
    """
    B = build_basis(w_um, W_mmi, wl_um, n_core, n_clad, dl)
    L_pi = beat_length(B.neff, wl_um)
    psis = {}
    best = None
    for fac in TWO_IMAGE_L_FACTORS:
        for i in range(n_L):
            L = fac * L_pi + (i / (n_L - 1) - 0.5) * 3.0
            E = B.field(L, wl_um)
            for j in range(n_s):
                s = W_mmi / 4.0 + (j / (n_s - 1) - 0.5) * 0.8
                key = round(s, 4)
                if key not in psis:
                    psis[key] = _fundamental(B.ys, w_um, s, dl, wl_um,
                                             n_core, n_clad)
                T = 2.0 * abs(complex(psis[key] @ E)) ** 2
                ex = -10.0 * math.log10(max(T, 1e-300))
                if best is None or ex < best[0]:
                    best = (ex, L, s, T)
    return {"best_excess_db": float(best[0]), "L_um": float(best[1]),
            "L_over_Lpi": float(best[1] / L_pi),
            "y_split_um": float(best[2]), "y_split_over_W": float(best[2] / W_mmi),
            "T": float(best[3]), "L_pi_um": float(L_pi), "W_mmi": W_mmi}


def two_image_length(W_mmi: float = MMI_W_UM, wl_um: float = 1.55,
                     n_core: float = N_CORE_2D, n_clad: float = N_CLAD_2D,
                     dl: float = 0.01, order: int = 1) -> float:
    """1×2 双像成像长度族 L = (3/8 + 3m/4)·L_π（抛物线近似，模型自洽）。

    🔴 这是**模型自洽**的双像长度（由本模型解出的 β₀−β₁ 决定），与真实 3D
    器件的几何设计长度（锚题 27 µm）可能因 2D-EIM 近似而偏差；偏差属
    **模型几何失配**，不是器件损耗，须与结论一起披露。
    """
    yhalf = W_mmi / 2.0 + 3.0
    Ny = int(round(2.0 * yhalf / dl)) | 1
    ys = (np.arange(Ny) - (Ny - 1) / 2.0) * dl
    neff, _ = slab_modes(_guide_eps(ys, W_mmi, 0.0, n_core, n_clad),
                         dl, wl_um, n_clad)
    return TWO_IMAGE_L_FACTORS[order] * beat_length(neff, wl_um)


if __name__ == "__main__":
    import json
    print("== EME 自校验（W=2.8）==")
    print(json.dumps(self_image_fidelity(), indent=2))
    print("== 拍长误差传播（L=27）==")
    print(json.dumps(beat_length_error_propagation(), indent=2))
    print("== 模型能力上界 ==")
    print(json.dumps(best_case_excess(), indent=2))
    print("== 锚题几何（L=27, out_gap=0.9）==")
    r = mmi_excess_loss(verbose=True)
    print(json.dumps({k: v for k, v in r.items() if k != "n_eff_mmi"}, indent=2))
