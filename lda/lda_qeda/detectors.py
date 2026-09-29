"""D-115 · SNSPD 探测物理（G_Q1 探测部分）——on/off POVM / PNR 二项衰减 / 死时间饱和 / HOM 探测。

LDA-Q3b（M3 物理深度第二步 · 探测侧）：给 LOQC 处理器补上**真实探测器**这一环。

光量子芯片的读出靠单光子探测器（SNSPD）。真实探测器是**阈值(on/off)探测器**——它只回答
「这个时间窗内有/无光子」，**不分辨光子数**；且带有限探测效率 η、暗计数、死时间。
本模块把这些物理补上，并给出与芯片无关的可复用闭式锚。

════════════════════════════════════════════════════════════════════════════
物理定律锚（闭式 · 公共品科学原理 · 可作 golden）
════════════════════════════════════════════════════════════════════════════
1. **on/off 探测器 POVM**（阈值探测，η 探测效率，p_d 暗计数）：
      Π_off = (1−p_d)·Σₙ (1−η)ⁿ |n⟩⟨n| ,   Π_on = I − Π_off
      ⇒ 响应概率闭式 **P(click | n) = 1 − (1−p_d)(1−η)ⁿ**（n=0 且 p_d=0 时恒为 0）
2. **PNR 探测器（光子数分辨）**：输入 |n⟩、效率 η ⇒ 探测到 k 个光子服从**二项分布**
      P(k | n) = C(n,k)·ηᵏ·(1−η)^{n−k}   （k>n 时为 0）
   —— 这与「衰减率为 η 的损耗通道」是同一物理（见第 5 条）。
3. **死时间饱和**（SNSPD 恢复时间 τ 限制计数率）：
      · 非瘫痪模型：R_meas = R_in / (1 + R_in·τ)      （上限 1/τ）
      · 瘫痪模型  ：R_meas = R_in · e^{−R_in·τ}
4. **HOM 的 on/off 探测**：两个 on/off 探测器对输出模做符合计数，
      P(coin) = Σ_{n,m} P(n,m)·P(click|n)·P(click|m)
   理想不可区分双光子 ⇒ 联合分布只落在 (2,0)/(0,2) ⇒ 符合概率 0（**与 η 无关**）。
5. **探测效率 ≡ 损耗透射率**（探测器物理 ↔ 开放系统的桥）：
      效率 η 的探测器  ≡  透射率 η 的损耗通道 + 理想(η=1)探测器
      ⇒ ⟨0|Φ_η(ρ)|0⟩ = Σₙ ρ_nn (1−η)ⁿ（两条构造必须一致）

以上均为量子光学/探测物理**闭式物理律**（教科书级、非拟合）⇒ 可作 golden。

════════════════════════════════════════════════════════════════════════════
方法学独立（交叉验证 · 反自证桩）
════════════════════════════════════════════════════════════════════════════
PNR 二项分布用两条结构完全不同的路径独立算：
  (a) **闭式** 组合计数 C(n,k)ηᵏ(1−η)^{n−k}；
  (b) **玻色振幅法**（复用 D-113 loqc_states）：把「探测效率」建成**光束分束器 + 真空环境模**
      （Stinespring 膨胀）⟨k,n−k| B(η) |n,0⟩，用 permanent 组合计数算振幅模方。
组合计数（闭式）vs 玻色子振幅（permanent/Stinespring）结构迥异 ⇒ 一致即非复制粘贴。

════════════════════════════════════════════════════════════════════════════
红线纪律（与 LDA 一致）
════════════════════════════════════════════════════════════════════════════
· C 级自主：纯 numpy，零量子 SDK。· LLM 不进判决路径（闭式死标量比对）。
· 物理边界（诚实）：理想探测量子效率模型（无时间抖动/无后脉冲/无热噪声）；PNR 仅在
  截断 Fock 空间；死时间用标准两模型，未含多光子/恢复动力学。截断残差如实上报。

运行自检：python -c "from lda.lda_qeda.detectors import run_selfchecks; run_selfchecks(verbose=True)"
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

# ── 统一命名空间导入（防「同一文件双实例」陷阱）─────────────────────────────
# 把包根 lda/ 放入 path，一律用 `lda_qeda.*` 导入兄弟模块；否则同一文件可能被
# 同时实例化为 top-level `loqc_states` 与包内 `lda_qeda.loqc_states` 两份对象
# （功能虽等价，但 monkeypatch / 身份比较会打空 ⇒ 门禁假绿）。
import os as _os
import sys as _sys

_LDA_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # = …/lda
if _LDA_DIR not in _sys.path:
    _sys.path.insert(0, _LDA_DIR)

try:
    from lda_qeda import loqc_states as LS        # 统一形式（lda/ 已在 path）
except ImportError:                               # 极端兜底（直跑且包根不可达）
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import loqc_states as LS                      # noqa: E402

__all__ = [
    "onoff_povm",
    "click_prob",
    "click_prob_from_populations",
    "click_prob_closed_form",
    "pnr_prob_closed_form",
    "pnr_prob_stinespring",
    "half_resolving_probs",
    "dead_time_nonparalyzable",
    "dead_time_paralyzable",
    "coincidence_prob_onoff",
    "hom_output_joint",
    "hom_coincidence_onoff",
    "hom_visibility_onoff",
    "loss_then_ideal_no_click",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]

RED_LINE_DISCLOSURE = (
    "D-115 SNSPD 探测物理：纯 numpy 自研（C 级自主），零量子 SDK；闭式物理律（on/off 响应、PNR 二项、"
    "死时间饱和）作 golden；两条结构不同路径（闭式组合计数 × 玻色振幅/Stinespring）交叉验证。"
    "LLM 不进判决路径。诚实边界：理想探测量子效率模型（无抖动/后脉冲），截断残差如实上报。"
)

_DEFAULT_TRUNC = 40


# ════════════════════════════════════════════════════════════════════════════
# 1. on/off 探测器 POVM
# ════════════════════════════════════════════════════════════════════════════
def onoff_povm(eta: float, n_max: int = _DEFAULT_TRUNC, dark: float = 0.0):
    """on/off 探测器 POVM (Π_off, Π_on)（截断 Fock 空间 d=n_max+1）。

    Π_off = (1−p_d)·diag((1−η)ⁿ)，Π_on = I − Π_off。返回 (d×d, d×d)。
    """
    if not (0.0 <= eta <= 1.0):
        raise ValueError(f"探测效率 η 必须在 [0,1]（当前 {eta}）")
    if not (0.0 <= dark <= 1.0):
        raise ValueError(f"暗计数概率 p_d 必须在 [0,1]（当前 {dark}）")
    d = int(n_max) + 1
    diag = np.array([(1.0 - dark) * (1.0 - eta) ** n for n in range(d)], dtype=complex)
    Pi_off = np.diag(diag)
    Pi_on = np.eye(d, dtype=complex) - Pi_off
    return Pi_off, Pi_on


def click_prob(rho: np.ndarray, eta: float, dark: float = 0.0) -> float:
    """响应概率（数值 · 走 POVM）：Tr[Π_on ρ]。"""
    n_max = rho.shape[0] - 1
    _, Pi_on = onoff_povm(eta, n_max, dark)
    return float(np.real(np.trace(Pi_on @ rho)))


def click_prob_from_populations(pops, eta: float, dark: float = 0.0) -> float:
    """响应概率（走光子数布居）：Σₙ pₙ·[1 − (1−p_d)(1−η)ⁿ]。"""
    return sum(float(p) * click_prob_closed_form(eta, n, dark) for n, p in enumerate(pops))


def click_prob_closed_form(eta: float, n: int, dark: float = 0.0) -> float:
    """P(click | n) 闭式 = 1 − (1−p_d)(1−η)ⁿ。"""
    return 1.0 - (1.0 - dark) * (1.0 - eta) ** n


# ════════════════════════════════════════════════════════════════════════════
# 2. PNR 探测器（光子数分辨）——两条独立路径
# ════════════════════════════════════════════════════════════════════════════
def pnr_prob_closed_form(n: int, k: int, eta: float) -> float:
    """PNR 闭式：P(k|n) = C(n,k)·ηᵏ·(1−η)^{n−k}（二项分布；k>n ⇒ 0）。"""
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * eta ** k * (1.0 - eta) ** (n - k)


def pnr_prob_stinespring(n: int, k: int, eta: float) -> float:
    """PNR 独立路径（玻色振幅）：⟨k,n−k| B(η) |n,0⟩ 的模方，B = bs_unitary(θ)，cosθ=√η。

    把探测器效率建成「信号模 × 真空环境模」的分束器（Stinespring 膨胀），用 D-113 的
    permanent 组合计数算玻色振幅 —— 与闭式二项分布算法结构完全不同。
    """
    if k < 0 or k > n:
        return 0.0
    th = math.acos(math.sqrt(eta))
    B = LS.bs_unitary(th)
    out = tuple([k, n - k])
    amp = LS.linear_optics_amplitude(B, (n, 0), out)
    return float(abs(amp) ** 2)


def half_resolving_probs(n: int, eta: float):
    """半分辨探测器：(P(0), P(1), P(≥2))，由二项分布求和。"""
    p0 = pnr_prob_closed_form(n, 0, eta)
    p1 = pnr_prob_closed_form(n, 1, eta)
    pge2 = 1.0 - p0 - p1
    return p0, p1, pge2


# ════════════════════════════════════════════════════════════════════════════
# 3. 死时间饱和
# ════════════════════════════════════════════════════════════════════════════
def dead_time_nonparalyzable(r_in: float, tau: float) -> float:
    """非瘫痪死时间模型 R_meas = R_in/(1+R_in·τ)（上限 1/τ）。"""
    if r_in < 0.0 or tau < 0.0:
        raise ValueError("R_in 与 τ 必须 ≥ 0")
    return r_in / (1.0 + r_in * tau)


def dead_time_paralyzable(r_in: float, tau: float) -> float:
    """瘫痪死时间模型 R_meas = R_in·e^{−R_in·τ}（高计数率下回落，峰值 1/(e·τ)）。"""
    if r_in < 0.0 or tau < 0.0:
        raise ValueError("R_in 与 τ 必须 ≥ 0")
    return r_in * math.exp(-r_in * tau)


# ════════════════════════════════════════════════════════════════════════════
# 4. 符合计数 / HOM 的 on/off 探测
# ════════════════════════════════════════════════════════════════════════════
def coincidence_prob_onoff(joint_probs: dict, eta: float, dark: float = 0.0) -> float:
    """符合概率 P(coin) = Σ_{n,m} P(n,m)·P(click|n)·P(click|m)（两 on/off 探测器）。

    joint_probs: {(n, m): P}（两输出模的光子数联合分布）。
    """
    tot = 0.0
    for (n, m), p in joint_probs.items():
        tot += float(p) * click_prob_closed_form(eta, n, dark) * click_prob_closed_form(eta, m, dark)
    return tot


def hom_output_joint(theta: float, indist: bool = True) -> dict:
    """HOM 分束器（bs_unitary(θ)）两输出的光子数联合分布。

    indist=True ：不可区分双光子 ⇒ 真实量子分布（D-113 permanent，含干涉）；
    indist=False：可区分光子     ⇒ 经典多项分布（两光子独立，无干涉）。
    """
    B = LS.bs_unitary(theta)
    if indist:
        return {tuple(o): float(p) for o, p in LS.output_distribution(B, (1, 1)).items()}
    c2 = math.cos(theta) ** 2      # 单光子留在模 0 的概率
    s2 = math.sin(theta) ** 2      # 单光子到模 1 的概率
    return {(2, 0): c2 * c2, (1, 1): 2.0 * c2 * s2, (0, 2): s2 * s2}


def hom_coincidence_onoff(theta: float, eta: float, indist: bool = True,
                          dark: float = 0.0) -> float:
    """HOM 符合概率（on/off 探测）= Σ P(n,m)·click(n)·click(m)。"""
    return coincidence_prob_onoff(hom_output_joint(theta, indist), eta, dark)


def hom_visibility_onoff(theta: float, eta: float, dark: float = 0.0) -> float:
    """HOM 可见度 V=(P_dist−P_indist)/(P_dist+P_indist)（on/off 探测）。

    理想情形：不可区分 ⇒ 符合 0（聚束到同一输出），可区分 ⇒ η²·P(1,1)。
    """
    p_d = hom_coincidence_onoff(theta, eta, indist=False, dark=dark)
    p_i = hom_coincidence_onoff(theta, eta, indist=True, dark=dark)
    denom = p_d + p_i
    if denom <= 0.0:
        return float("nan")
    return (p_d - p_i) / denom


# ════════════════════════════════════════════════════════════════════════════
# 5. 探测效率 ≡ 损耗透射率（探测器 ↔ 开放系统的桥）
# ════════════════════════════════════════════════════════════════════════════
def loss_then_ideal_no_click(n: int, eta: float) -> float:
    """「透射率 η 的损耗通道 + 理想探测器」的**不响应**概率 ⟨0|Φ_η(|n⟩⟨n|)|0⟩。

    独立构造（Stinespring）：|⟨0,n| B(η) |n,0⟩|²（信号模 n 光子**全漏进**环境模 →
    信号模残留真空），用永久式玻色振幅算。单个光子的「全漏」振幅 = i·sinθ（cosθ=√η）
     ⇒ 结果为 sin²ⁿθ = (1−η)ⁿ，且等于 on/off POVM 的 Π_off 对角元。
    🔴 输出模必须取 (0, n)（光子数守恒 Σin=Σout）；写 (0,0) 会因光子数不守恒恒得 0。
    """
    th = math.acos(math.sqrt(eta))
    B = LS.bs_unitary(th)
    amp = LS.linear_optics_amplitude(B, (n, 0), (0, n))
    return float(abs(amp) ** 2)


# ════════════════════════════════════════════════════════════════════════════
# 6. 自检锚
# ════════════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块内自检：on/off 三路 / PNR 双路 / 半分辨 / 死时间 / POVM / 标度 / HOM / 桥 / 护栏。"""
    res = OrderedDict()

    def rec(name, ok, detail=""):
        res[name] = bool(ok)
        if verbose:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' | ' + detail) if detail else ''}")

    eta = 0.85
    dark = 1e-6
    n_max = 40

    # ① P(click|n) 三路一致：POVM 数值（对角态）× 布居闭式 × Stinespring 不响应
    max_d = 0.0
    for n in range(0, 9):
        rho = np.zeros((n_max + 1, n_max + 1), dtype=complex)
        rho[n, n] = 1.0
        p_povm = click_prob(rho, eta, dark)
        p_close = click_prob_closed_form(eta, n, dark)
        p_stine = 1.0 - (1.0 - dark) * loss_then_ideal_no_click(n, eta)
        max_d = max(max_d, abs(p_povm - p_close), abs(p_stine - p_close))
    rec("on/off 响应 P(click|n)=1−(1−p_d)(1−η)ⁿ：POVM × 布居闭式 × Stinespring 三路一致",
        max_d < 1e-12, f"max|Δ|={max_d:.3e}（η={eta} p_d={dark}）")

    # ② 暗计数闭式：p_d>0 下 n=0 也响应（暗计数真实存在）
    p0_dark = click_prob_closed_form(eta, 0, dark=1e-3)
    rec("暗计数闭式：P(click|n=0)=p_d（无光子也可响应）",
        abs(p0_dark - 1e-3) < 1e-15, f"P(click|0)={p0_dark:.6e}")

    # ③ PNR 双路独立：闭式二项 × 玻色振幅(Stinespring/permanent)
    max_dp = 0.0
    for n in range(0, 7):
        for k in range(0, n + 1):
            max_dp = max(max_dp, abs(pnr_prob_closed_form(n, k, eta)
                                     - pnr_prob_stinespring(n, k, eta)))
    rec("PNR 双路独立：闭式二项 C(n,k)ηᵏ(1−η)^{n−k} × 玻色振幅(permanent·Stinespring)",
        max_dp < 1e-12, f"max|Δ|={max_dp:.3e}（覆盖 n≤6 全 k）")

    # ④ PNR 概率守恒 Σ_k P(k|n) = 1（对全 k 求和，含数值截断 n_max≥n）
    max_sum = 0.0
    for n in range(0, 12):
        s = sum(pnr_prob_closed_form(n, k, eta) for k in range(0, n + 1))
        max_sum = max(max_sum, abs(s - 1.0))
    rec("PNR 归一 Σ_k P(k|n)=1（全 k）", max_sum < 1e-12, f"max|Σ−1|={max_sum:.3e}")

    # ⑤ 半分辨：P0+P1+P≥2 = 1 且与二项一致
    p0, p1, pge2 = half_resolving_probs(5, eta)
    rec("半分辨探测 P(0)+P(1)+P(≥2)=1",
        abs(p0 + p1 + pge2 - 1.0) < 1e-12 and abs(pge2 - (1 - p0 - p1)) < 1e-15,
        f"P0={p0:.6f} P1={p1:.6f} P≥2={pge2:.6e}")

    # ⑥ 死时间：非瘫痪单调上界 1/τ；瘫痪峰后回落；低率下两者 → R_in（相对误差 < R·τ）
    tau = 10e-9
    r_hi = 1e9
    rnp = dead_time_nonparalyzable(r_hi, tau)
    rpl = dead_time_paralyzable(r_hi, tau)
    r_low = dead_time_nonparalyzable(1e3, 1e-9)          # R·τ=1e-6 ⇒ 相对误差 ~1e-6
    r_low_pl = dead_time_paralyzable(1e3, 1e-9)
    rel_low = max(abs(r_low - 1e3) / 1e3, abs(r_low_pl - 1e3) / 1e3)
    ok_dt = (rnp < 1.0 / tau) and (rpl < rnp) and (rel_low < 1e-4)
    rec("死时间饱和：非瘫痪 R/(1+Rτ)<1/τ · 瘫痪高率回落 · 低率→R_in",
        ok_dt, f"R_np={rnp:.4e} R_pl={rpl:.4e} 上限1/τ={1.0 / tau:.1e} 低率相对误差={rel_low:.2e}")

    # ⑦ POVM 完备 Π_off+Π_on=I 且 Π_on 本征值 ∈[0,1]
    Pi_off, Pi_on = onoff_povm(eta, n_max, dark)
    comp = float(np.max(np.abs(Pi_off + Pi_on - np.eye(n_max + 1))))
    ev = np.linalg.eigvalsh(Pi_on)
    rec("on/off POVM：完备 Π_off+Π_on=I 且 Π_on 半正定 ≤ I",
        comp < 1e-15 and ev.min() > -1e-15 and ev.max() < 1.0 + 1e-15,
        f"max|Π_off+Π_on−I|={comp:.2e} 本征=[{ev.min():.3f},{ev.max():.3f}]")

    # ⑧ 标度律：单路响应 ∝ η（弱光），符合(双路) ∝ η²
    e_small = 1e-4
    p1 = click_prob_closed_form(e_small, 1, 0.0)                      # ≈ η
    p_coin = coincidence_prob_onoff({(1, 1): 1.0}, e_small, 0.0)      # ≈ η²
    rec("标度律：单路 P(click|1)≈η · 符合(1,1)≈η²（探测器效率的平方衰减）",
        abs(p1 - e_small) < 1e-12 and abs(p_coin - e_small ** 2) < 1e-15,
        f"P1={p1:.3e} Pcoin={p_coin:.3e} η²={e_small ** 2:.3e}")

    # ⑨ HOM 的 on/off 探测：理想不可区分 ⇒ 符合 0，可见度 V=1（与 η 无关）
    vis_list = [hom_visibility_onoff(math.pi / 4.0, e) for e in (0.3, 0.6, 0.9, 1.0)]
    coin_i = hom_coincidence_onoff(math.pi / 4.0, 0.9, indist=True)
    rec("HOM on/off 探测：不可区分符合=0 · 可见度 V=1（理想，与 η 无关）",
        max(abs(v - 1.0) for v in vis_list) < 1e-12 and coin_i < 1e-15,
        f"V(η=0.3..1.0)={['%.6f' % v for v in vis_list]} 符合(η=0.9)={coin_i:.2e}")

    # ⑩ 桥：探测效率 ≡ 损耗透射率 ⟨0|Φ_η(|n⟩⟨n|)|0⟩ = (1−η)ⁿ = Π_off 对角元
    max_bridge = 0.0
    for n in range(0, 9):
        left = loss_then_ideal_no_click(n, eta)
        max_bridge = max(max_bridge, abs(left - (1.0 - eta) ** n))
    rec("桥：探测器 η ≡ 损耗通道 η + 理想探测器（Φ_η 残留真空 =(1−η)ⁿ）",
        max_bridge < 1e-12, f"max|Δ|={max_bridge:.3e}")

    # ⑪ 护栏：η∉[0,1] / p_d∉[0,1] 抛错；n=0 且无暗计数 ⇒ 响应 0
    guard_ok = True
    for bad in (-0.1, 1.1):
        try:
            onoff_povm(bad)
            guard_ok = False
        except ValueError:
            pass
    p0_clean = click_prob_closed_form(eta, 0, dark=0.0)
    rec("护栏：η∉[0,1] 抛 ValueError · 无光子无暗计数 ⇒ P(click|0)=0",
        guard_ok and abs(p0_clean) < 1e-15, f"P(click|0,p_d=0)={p0_clean:.2e}")

    ok = all(res.values())
    if verbose:
        n_fail = sum(1 for v in res.values() if not v)
        print(f"\ndetectors 自检：{len(res) - n_fail}/{len(res)} PASS")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selfchecks(verbose=True) else 1)
