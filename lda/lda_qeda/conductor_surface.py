"""D-222 · 有限导体厚度 / 表面阻抗（conductor surface impedance）—— 能力层 · 净增 0 锚。

## 为什么需要它

`cpw_quasi_static` 自己声明过三条不含项：

> **不含导体厚度 / 不含表面阻抗 / 不含辐射**：本模块是准静态（∇·(ε∇φ)=0）解……

`kinetic_inductance`（D-221）只补了其中的**电感侧**（L_k），**损耗侧仍是空白**：
全仓精确检索 `skin_depth` / `趋肤深度` **零命中**，`sc_readout` 的
`tan_delta_surface=1e-6` 是**手填设计参数**，没有任何物理来源。

## 一个公式统摄全部区间（本模块的核心）

从 Maxwell 方程在导电板内的解，有限厚度表面阻抗有**严格闭式**：

    Z_s(t) = (j·ω·μ0 / k) · coth(k·t),      k = √(j·ω·μ0·σ),   σ = σ1 − j·σ2

它同时覆盖四个象限（正常/超导 × 厚膜/薄膜），无需分区间凑过渡函数：

| 极限 | 条件 | 闭式退化到 | 本模块实测残差 |
|---|---|---|---|
| 正常态厚膜 | t ≫ δ | `(ρ/δ)(1+j)` | **0.000e+00**（t/δ=100） |
| 正常态薄膜 | t ≪ δ | `ρ/t`（**纯实数**） | Re·t/ρ = 1 + (2/3)(t/δ)² |
| 超导厚膜 | t ≫ λ | `j·ω·μ0·λ`（纯虚） | Im/(ωμ0λ) → 1.0000000000 |
| 超导薄膜 | t ≪ λ | `j·ω·μ0·λ²/t` | 与 D-221 的 coth 对拍 ≤ 2.0e−16 |

## 🔴 零厚度模型在此处**无定义**（不是精度问题）

CPW 的导体损耗积分在带边缘（x→±a）被表面电流密度奇点放大 ⇒ **对数发散**。
有限厚度 t 把奇点正则化到 ~t 尺度，所以：

- **表面阻抗模型必须显式带 t**；`t=0` ⇒ 本模块 raise（不返回 inf、不猜默认）；
- 这也是 Wheeler 增量规则的适用边界：等效内缩量 `δ_eff` 必须 `< t/2`。

## 🔴 可锚性：实测判死（理由与 D-221 不同，值得分开记）

| 检查 | 结果 | 判定 |
|---|---|---|
| `R_s` 三种写法（定义式 / `ρ/δ` / `Re(ρ·k)`） | 最大相对差 **2.130e−16** | 同一代数恒等 ⇒ resid ≡ 0 |
| 深低温 `R_s`：两流体 vs BCS | 20 mK 差 **2.255e+61 倍** | **两流体在 R_s 上物理失效**（不是重合，是另一条路径不成立） |
| Wheeler 增量规则 | 定理，非独立数值路径 | 不构成第二条路径 |

⇒ **`ANCHORABLE = False`**。注意与 D-221 的区别：D-221 是「两条都对的路径重合」，
D-222 是「另一条路径物理失效」——**后者更危险**，因为它看起来像"有分歧"，容易被误当成可锚。

## 诚实的边界（不得读成实测）

- `ρ_n`（正常态电阻率）与 λ_L(0)、Tc 都是**文献典型值**，非本平台实测；
- **非平衡准粒子未建模**：本模型 σ1 由热激发决定，T→0 时趋于 0，
  真实器件的 R_s 由残余/非平衡准粒子主导（辐照、准粒子陷阱、结泄漏）；
- 不含辐射损耗、不含介质损耗（后者由 `sc_readout` 的 tanδ 族负责）。

## 红线

纯 stdlib（`math` / `cmath`）+ 平台闭式。零量子 SDK、LLM 不进判决路径。
"""
from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List, Optional, Tuple

from lda_qeda import cpw_quasi_static as CQS
from lda_qeda import kinetic_inductance as KI

ROLE = ("D-222 · 有限导体厚度 / 表面阻抗能力层 —— 把「准静态无耗 CPW」推进到"
        "「含导体损耗与有限厚度的 CPW」，并如实登记零厚度模型无定义、"
        "两流体在 R_s 上失效、以及可锚性实测判死。")
ANCHORABLE = False

MU0 = 4.0e-7 * math.pi            # H/m
EPS0 = 8.8541878128e-12           # F/m
C0 = 299792458.0                  # m/s
ETA0 = 376.730313668              # Ω，真空波阻抗
KB_EV = 8.617333262e-5            # eV/K
H_EV_S = 4.135667696e-15          # eV·s（ℏ = H_EV_S/(2π)）

#: 导体材料库 —— 🔴 **ρ_n 为文献典型值，非本平台实测**（provenance 逐条登记）
#:   λ_L(0) 与 Tc 直接引用 D-221 的 `KI.MATERIALS`，**不在此处重抄**（单一真源）
CONDUCTOR_MATERIALS: Dict[str, Dict[str, Any]] = {
    #            正常态电阻率 ρ_n (Ω·m)      适用情境
    "Al":    {"rho_n": 1.00e-09, "context": "4 K 薄膜（RRR≈4）"},
    "Nb":    {"rho_n": 1.50e-09, "context": "4 K 薄膜（RRR≈10）"},
    "NbTiN": {"rho_n": 1.50e-06, "context": "低温高方阻无序膜"},
    "TiN":   {"rho_n": 1.00e-06, "context": "室温/低 RRR 无序膜"},
    "Cu":    {"rho_n": 1.68e-08, "context": "300 K 块体（参考对照）"},
    "Au":    {"rho_n": 2.44e-08, "context": "300 K 块体（参考对照）"},
}

MATERIAL_PROVENANCE: Dict[str, str] = {
    "Al":    "文献典型值（4 K 薄膜 RRR≈4 ⇒ ρ≈1e-9 Ω·m）；**非实测**",
    "Nb":    "文献典型值（RRR≈10 ⇒ ρ≈1.5e-9 Ω·m）；**非实测**",
    "NbTiN": "文献典型值（高方阻膜 100–200 µΩ·cm）；**非实测**，分散可达 2×",
    "TiN":   "文献典型值（无序膜 50–150 µΩ·cm）；**非实测**，分散大",
    "Cu":    "文献典型值（300 K，IACS 标准）；**非实测**",
    "Au":    "文献典型值（300 K）；**非实测**",
}

T_OP_K = KI.T_OP_K                # 20 mK，与 D-221 同一工作点（单一真源）


# ---------------------------------------------------------------------------
# ① 趋肤深度（正常态，严格闭式）
# ---------------------------------------------------------------------------
def skin_depth(rho_n: float, f_hz: float) -> float:
    """正常态趋肤深度（m）：δ = √(2ρ/(ω·μ0))，ω = 2πf。

    这与 `R_s = √(π·f·μ0·ρ)` 是**同一代数恒等**（把 δ 代回即得），
    所以二者不构成两条独立路径 —— 这一点在 `why_not_anchored()` 里机器化。
    """
    if rho_n <= 0:
        raise ValueError("ρ 必须 > 0")
    if f_hz <= 0:
        raise ValueError("f 必须 > 0")
    return math.sqrt(2.0 * rho_n / (2.0 * math.pi * f_hz * MU0))


def surface_resistance_infinite(rho_n: float, f_hz: float) -> float:
    """半无限正常导体表面电阻（Ω/□）：`R_s = √(π·f·μ0·ρ)`。"""
    if rho_n <= 0 or f_hz <= 0:
        raise ValueError("ρ 与 f 必须 > 0")
    return math.sqrt(math.pi * f_hz * MU0 * rho_n)


# ---------------------------------------------------------------------------
# ② 复电导：正常态 / 超导态（BCS σ1 + 两流体 σ2）
# ---------------------------------------------------------------------------
def sigma_normal(rho_n: float) -> complex:
    """正常态复电导（S/m）：σ = 1/ρ − j·0。

    🔴 **不写 `/(1.0/rho_n)`** —— 那在数学上是乘 ρ，不是除 ρ。
    D-222 原型阶段正是这个笔误让 `Re(ρ·k)` 与定义式差 1.0（100%），
    看起来像"发现了第二条路径"，实际是自造的假分歧。
    """
    if rho_n <= 0:
        raise ValueError("ρ 必须 > 0")
    return complex(1.0 / rho_n, 0.0)


def sigma1_ratio_bcs(delta_ev: float, t_k: float, f_hz: float,
                     npts: int = 4001) -> float:
    """Mattis-Bardeen 的 `σ1/σn`（T≠0、ω<2Δ 区间），u 代换去奇点。

    积分式（`x = E/Δ`、`y = ℏω/Δ`）：

        σ1/σn = (2/y)·∫₁^∞ [f(x) − f(x+y)]·(x(x+y)+1)/√(x²−1)/√((x+y)²−1) dx

    代换 `x = 1 + u²` ⇒ `dx = 2u·du`、`√(x²−1) = u√(2+u²)` ⇒ u 因子相消，
    端点 x→1 的 1/√ 奇点被正则化为有限值。

    🔴 **深低温极限**：`f(x)−f(x+y) → 0`（无热激发准粒子）⇒ σ1 → 0。
    真实器件的残余准粒子（非平衡）**不在本模型内**，见模块 docstring 的诚实边界。
    """
    if delta_ev <= 0:
        raise ValueError("Δ 必须 > 0")
    if t_k <= 0:
        raise ValueError("T 必须 > 0（本式为 T≠0 形式）")
    y = (H_EV_S / (2.0 * math.pi)) * 2.0 * math.pi * f_hz / delta_ev  # ℏω/Δ
    if y >= 2.0:
        return 1.0                     # 光子能量超能隙 ⇒ 视为正常态

    kt_ev = KB_EV * t_k
    if npts % 2 == 0:
        npts += 1                      # Simpson 要求奇数点
    hi = 40.0                          # u 上界：x=1+1600 ⇒ exp 项已彻底衰减
    du = hi / (npts - 1)
    tot = 0.0
    for i in range(npts):
        u = i * du
        x = 1.0 + u * u
        xp = x + y
        if xp <= 1.0:
            continue
        a1 = x * delta_ev / kt_ev
        a2 = xp * delta_ev / kt_ev
        f1 = 0.0 if a1 > 700.0 else 1.0 / (1.0 + math.exp(a1))
        f2 = 0.0 if a2 > 700.0 else 1.0 / (1.0 + math.exp(a2))
        df = f1 - f2
        if df == 0.0:
            continue
        num = x * xp + 1.0
        den = math.sqrt(2.0 + u * u) * math.sqrt(max(xp * xp - 1.0, 1e-300))
        w = 1.0 if (i == 0 or i == npts - 1) else (4.0 if i % 2 == 1 else 2.0)
        tot += w * df * num / den
    tot *= du / 3.0
    return float((2.0 / y) * tot)


def sigma_super(material: str, t_k: float = T_OP_K, f_hz: float = 5e9,
                npts: int = 4001, use_bcs_sigma1: bool = True) -> complex:
    """超导态复电导（S/m）：σ = σ1 − j·σ2。

    - `σ1`：Mattis-Bardeen 积分（`use_bcs_sigma1=True`）或两流体 `σn·(T/Tc)^4`；
    - `σ2`：两流体 `1/(μ0·ω·λ_L(T)²)`（准静态极限，Gorter-Casimir）。

    🔴 **两流体在 σ1（即 R_s）上是失效的**：深低温它给 `(T/Tc)^4`，
    而 BCS 给 `exp(−Δ/kBT)`，20 mK 差 **2.255e+61 倍**（见 `anchorability_probe`）。
    默认走 BCS；`use_bcs_sigma1=False` 只为探针反证而保留。
    """
    if material not in CONDUCTOR_MATERIALS:
        raise KeyError("未登记导体材料 %r（已登记：%s）"
                       % (material, sorted(CONDUCTOR_MATERIALS)))
    if material not in KI.MATERIALS:
        raise KeyError("材料 %r 缺 λ_L(0)/Tc（D-221 未登记）" % (material,))
    m = CONDUCTOR_MATERIALS[material]
    k = KI.MATERIALS[material]
    tc, lam0 = float(k["tc_k"]), float(k["lambda0_nm"])
    rho_n = float(m["rho_n"])
    if t_k >= tc:
        raise ValueError("T (%.6f K) ≥ Tc (%.6f K)：超导态不存在" % (t_k, tc))

    lam = KI.lambda_l(lam0, tc, t_k)
    s2 = 1.0 / (MU0 * 2.0 * math.pi * f_hz * lam * lam)
    if use_bcs_sigma1:
        d = KI.delta_gross(tc, t_k)
        r = sigma1_ratio_bcs(d, t_k, f_hz, npts=npts)
        s1 = (1.0 / rho_n) * r
    else:
        s1 = (1.0 / rho_n) * (t_k / tc) ** 4
    return complex(s1, -s2)


# ---------------------------------------------------------------------------
# ③ 核心闭式：有限厚度表面阻抗
# ---------------------------------------------------------------------------
def k_complex(sigma: complex, f_hz: float) -> complex:
    """复传播常数 k = √(j·ω·μ0·σ)。`Im σ < 0`（感性）时 k 落第一象限。"""
    if sigma == 0:
        raise ValueError("σ 不能为 0")
    if f_hz <= 0:
        raise ValueError("f 必须 > 0")
    return cmath.sqrt(1j * 2.0 * math.pi * f_hz * MU0 * sigma)


def surface_impedance(sigma: complex, f_hz: float, t_m: float) -> complex:
    """**有限厚度表面阻抗（严格解）**：`Z_s = (j·ω·μ0/k)·coth(k·t)`。

    来自 Maxwell 方程在厚度 t 的导电板内的解（Tinkham / Ramo-Whinnery）。
    四个极限全部解析可验证，见模块 docstring 的表。

    🔴 `t_m <= 0` 直接 raise：**零厚度表面阻抗无定义**（边缘电流奇点使损耗积分
    对数发散），返回 inf 或猜一个默认值都会让下游静默错误。
    """
    if t_m <= 0:
        raise ValueError("导体厚度 t 必须 > 0：零厚度表面阻抗无定义"
                         "（CPW 边缘电流奇点使损耗积分发散）")
    if f_hz <= 0:
        raise ValueError("f 必须 > 0")
    k = k_complex(sigma, f_hz)
    z_char = 1j * 2.0 * math.pi * f_hz * MU0 / k
    kt = k * t_m
    if abs(kt) < 1e-14:
        return z_char / kt              # coth(x) ~ 1/x（薄膜极限，避免 0/0）
    return z_char / cmath.tanh(kt)


def zs_normal(rho_n: float, f_hz: float, t_m: float) -> complex:
    """正常导体有限厚度表面阻抗（Ω/□）。"""
    return surface_impedance(sigma_normal(rho_n), f_hz, t_m)


def zs_super(material: str, t_k: float = T_OP_K, f_hz: float = 5e9,
             t_m: float = 200e-9, use_bcs_sigma1: bool = True) -> complex:
    """超导薄膜有限厚度表面阻抗（Ω/□）。"""
    return surface_impedance(sigma_super(material, t_k, f_hz,
                                         use_bcs_sigma1=use_bcs_sigma1),
                             f_hz, t_m)


# ---------------------------------------------------------------------------
# ④ 厚度分区判定（t vs δ / t vs λ）
# ---------------------------------------------------------------------------
def thickness_regime(t_m: float, skin_m: float) -> Dict[str, Any]:
    """按 `t/δ`（或 `t/λ`）判定所处区间，并给出适用公式与失效标志。

    | t/δ | 区间 | 应使用的公式 | Wheeler 增量是否有效 |
    |---|---|---|---|
    | ≥ 1.0 | 厚膜（半无限） | `R_s = ρ/δ` | ✅（δ_eff=δ/2 ≤ t/2） |
    | 0.1–1.0 | 过渡 | 闭式 `coth(k·t)` | ⚠️ 谨慎（δ_eff 逼近 t/2） |
    | ≤ 0.1 | 薄膜（电流均匀） | `R_s,eff = ρ/t` | ❌（δ_eff > t/2，超范围） |
    """
    if t_m <= 0:
        raise ValueError("t 必须 > 0")
    if skin_m <= 0:
        raise ValueError("δ/λ 必须 > 0")
    r = t_m / skin_m
    if r >= 1.0:
        regime, formula, wheeler_ok = "thick", "rho_over_delta", True
    elif r >= 0.1:
        regime, formula, wheeler_ok = "transition", "closed_form_coth", "caution"
    else:
        regime, formula, wheeler_ok = "thin", "rho_over_t", False
    return {"t_over_skin": r, "regime": regime, "formula": formula,
            "wheeler_ok": wheeler_ok,
            "deviation_from_infinite": (1.0 - abs(1.0 / math.tanh(r)) / (1.0 / r))
            if r > 0 else 0.0}


# ---------------------------------------------------------------------------
# ⑤ CPW 导体衰减（Wheeler 增量电感规则）
# ---------------------------------------------------------------------------
def dZ0_dn(w_um: float, g_um: float, h_um: float, eps_r: float,
           dn_um: float) -> float:
    """`∂Z0/∂n`（Ω/m）：导体边界内缩 n 时特性阻抗的变化率（中心差分，O(n²)）。

    内缩语义：中心带 `w → w−2n`、间隙 `g → g+2n`（两侧地与中心带各自内缩）。
    """
    if dn_um <= 0:
        raise ValueError("n 必须 > 0")
    zp = CQS.cpw_closed_form(w_um - 2.0 * dn_um, g_um + 2.0 * dn_um,
                             h_um=h_um, eps_r=eps_r)["Z0_ohm"]
    zm = CQS.cpw_closed_form(w_um + 2.0 * dn_um, g_um - 2.0 * dn_um,
                             h_um=h_um, eps_r=eps_r)["Z0_ohm"]
    return abs((zp - zm) / (2.0 * dn_um)) * 1e6      # Ω/µm → Ω/m


def effective_inset(rho_or_zs: Any, f_hz: float) -> float:
    """等效内缩量（m）：`δ_eff = Im(Z_s)/(ω·μ0)`。

    - 正常态厚膜 ⇒ `δ/2`（因 `Im Z_s = R_s = ρ/δ = ωμ0δ/2`）；
    - 超导厚膜 ⇒ `λ`（因 `Im Z_s = ωμ0λ`）。
    这正是 Wheeler 规则里那一步"把表面阻抗折成几何内缩"。
    """
    if isinstance(rho_or_zs, complex):
        zs = rho_or_zs
    else:
        raise TypeError("请直接传 Z_s（complex）；本函数不做材料分派")
    return zs.imag / (2.0 * math.pi * f_hz * MU0)


def alpha_c_cpw(zs: complex, f_hz: float, w_um: float, g_um: float,
                h_um: float, eps_r: float,
                dn_um: Optional[float] = None) -> Dict[str, Any]:
    """CPW 导体衰减（Np/m）：`α_c = R_s/(2·Z0·η0) · |∂Z0/∂n|`。

    `n` 取等效内缩量 `δ_eff = Im(Z_s)/(ωμ0)`（Wheeler 增量电感规则）。
    若 `δ_eff > t/2`，导体已不是"半无限"，Wheeler 规则**失效** ⇒ 返回
    `wheeler_ok=False` 并给出原因（不静默给一个数）。
    """
    b = CQS.cpw_closed_form(w_um, g_um, h_um=h_um, eps_r=eps_r)
    z0 = b["Z0_ohm"]
    ee = b["eps_eff"]
    inset_m = dn_um * 1e-6 if dn_um is not None else effective_inset(zs, f_hz)
    inset_um = inset_m * 1e6
    beta = 2.0 * math.pi * f_hz * math.sqrt(ee) / C0

    # 🔴 Wheeler 的**几何适用边界**：内缩量不能把导体缩穿（w 变负 / 间隙闭合）。
    #    超出时**不静默给数**（那会让下游把越界值当有效），也不让 CQS raise
    #    （那样门禁会崩、看不到其余判据）⇒ 返回 nan + wheeler_ok=False + 原因。
    if w_um - 2.0 * inset_um <= 0.0 or g_um - 2.0 * inset_um <= 0.0:
        return {
            "alpha_c_np_per_m": float("nan"),
            "alpha_c_db_per_m": float("nan"),
            "beta_rad_per_m": beta,
            "q_conductor": float("nan"),
            "Z0_ohm": z0, "eps_eff": ee,
            "Rs_ohm_sq": zs.real, "Xs_ohm_sq": zs.imag,
            "inset_um": inset_um, "dZ0_dn_ohm_per_m": float("nan"),
            "wheeler_ok": False,
            "wheeler_reason": ("等效内缩 %.3f µm 使 w−2n=%.3f / g−2n=%.3f ≤ 0 ⇒ "
                               "Wheeler 几何越界（该材料应走薄膜方块电阻 ρ/t，"
                               "不能用半无限表面阻抗）"
                               % (inset_um, w_um - 2 * inset_um, g_um - 2 * inset_um)),
        }

    dzdn = dZ0_dn(w_um, g_um, h_um, eps_r, inset_um)
    alpha = zs.real / (2.0 * z0 * ETA0) * dzdn
    return {
        "alpha_c_np_per_m": alpha,
        "alpha_c_db_per_m": alpha * 8.685889638,
        "beta_rad_per_m": beta,
        "q_conductor": (beta / (2.0 * alpha)) if alpha > 0 else float("inf"),
        "Z0_ohm": z0, "eps_eff": ee,
        "Rs_ohm_sq": zs.real, "Xs_ohm_sq": zs.imag,
        "inset_um": inset_um, "dZ0_dn_ohm_per_m": dzdn,
        "wheeler_ok": True, "wheeler_reason": "等效内缩在几何内",
    }


def alpha_with_thickness(material: str, t_nm: float, f_hz: float = 5e9,
                         w_um: float = 10.0, g_um: float = 6.0,
                         h_um: float = 500.0, eps_r: float = 11.45,
                         t_k: float = T_OP_K,
                         state: str = "super") -> Dict[str, Any]:
    """按材料 + 膜厚自动选态（super / normal）并给 α_c + 适用性判定。"""
    t_m = t_nm * 1e-9
    if state == "super":
        zs = zs_super(material, t_k, f_hz, t_m)
        skin = KI.lambda_l_material(material, t_k)
        label = "λ_L(T)"
    elif state == "normal":
        rho = CONDUCTOR_MATERIALS[material]["rho_n"]
        zs = zs_normal(rho, f_hz, t_m)
        skin = skin_depth(rho, f_hz)
        label = "δ"
    else:
        raise ValueError("state 必须是 'super' 或 'normal'，得到 %r" % (state,))

    reg = thickness_regime(t_m, skin)
    out = alpha_c_cpw(zs, f_hz, w_um, g_um, h_um, eps_r)
    inset_m = effective_inset(zs, f_hz)
    wheeler_ok = inset_m <= t_m / 2.0
    # 半无限参照：证明「t 是必需参数而非精度旋钮」——薄膜区二者可差几十倍
    if state == "normal":
        rs_inf = surface_resistance_infinite(CONDUCTOR_MATERIALS[material]["rho_n"], f_hz)
    else:
        rs_inf = zs_super(material, t_k, f_hz, 1e6 * skin).real   # 厚膜极限
    out.update({
        "material": material, "state": state, "t_nm": t_nm,
        "skin_kind": label, "skin_nm": skin * 1e9,
        "regime": reg["regime"], "t_over_skin": reg["t_over_skin"],
        "Rs_infinite_ohm_sq": rs_inf,
        "rs_ratio_vs_infinite": (zs.real / rs_inf) if rs_inf > 0 else float("inf"),
        "wheeler_ok": wheeler_ok,
        "wheeler_note": ("等效内缩 %.2f nm ≤ t/2 = %.2f nm ⇒ Wheeler 规则有效"
                         % (inset_m * 1e9, t_m * 0.5 * 1e9)) if wheeler_ok else
                        ("等效内缩 %.2f nm > t/2 = %.2f nm ⇒ **Wheeler 规则失效**"
                         "（导体已不是半无限，须改用薄膜方块电阻 ρ/t）"
                         % (inset_m * 1e9, t_m * 0.5 * 1e9)),
    })
    return out


# ---------------------------------------------------------------------------
# ⑥ 与介质损耗口径的分界（证明二者不同源）
# ---------------------------------------------------------------------------
def equivalent_tan_delta(alpha_c_np_per_m: float, beta_rad_per_m: float) -> float:
    """把导体衰减折算成等效 `tanδ`：`tanδ_eff = 2α/β`。

    用途：与 `sc_readout` 手填的 `tan_delta_surface=1e-6` 对比，
    证明**导体损耗与 TLS 介质损耗不是同一个物理量**（量级差若干数量级）。
    """
    if beta_rad_per_m <= 0:
        raise ValueError("β 必须 > 0")
    return 2.0 * alpha_c_np_per_m / beta_rad_per_m


def loss_channel_separation(material: str = "Al", t_nm: float = 200.0,
                            f_hz: float = 5e9, tls_tan_delta: float = 1e-6
                            ) -> Dict[str, Any]:
    """导体损耗 vs TLS 介质损耗的口径分界（机器化，供门禁断言量级分离）。"""
    r = alpha_with_thickness(material, t_nm, f_hz=f_hz, state="super")
    rn = alpha_with_thickness(material, t_nm, f_hz=f_hz, state="normal")
    td_s = equivalent_tan_delta(r["alpha_c_np_per_m"], r["beta_rad_per_m"])
    td_n = equivalent_tan_delta(rn["alpha_c_np_per_m"], rn["beta_rad_per_m"])
    return {
        "material": material, "t_nm": t_nm, "f_ghz": f_hz / 1e9,
        "Q_super": r["q_conductor"], "Q_normal": rn["q_conductor"],
        "tan_delta_eff_super": td_s, "tan_delta_eff_normal": td_n,
        "tls_tan_delta_ref": tls_tan_delta,
        "separation_super": (tls_tan_delta / td_s) if td_s > 0 else float("inf"),
        "note": ("超导态 tanδ_eff = %.3e ≪ TLS 手填 1e−6 ⇒ 导体损耗**不是** TLS 损耗的代理，"
                 "二者是并联的两个通道（`sc_readout` 的预算里此前只有后者）"
                 % td_s),
    }


# ---------------------------------------------------------------------------
# ⑦ 材料一览
# ---------------------------------------------------------------------------
def material_table(t_nm: float = 200.0, f_hz: float = 5e9) -> List[Dict[str, Any]]:
    """材料 × 表面阻抗 × Q_c 一览（供面板/文档引用）。"""
    rows = []
    for name in sorted(CONDUCTOR_MATERIALS):
        try:
            sup = alpha_with_thickness(name, t_nm, f_hz=f_hz, state="super")
        except (KeyError, ValueError):
            sup = None
        try:
            nor = alpha_with_thickness(name, t_nm, f_hz=f_hz, state="normal")
        except (KeyError, ValueError):
            nor = None
        rows.append({
            "material": name,
            "rho_n": CONDUCTOR_MATERIALS[name]["rho_n"],
            "context": CONDUCTOR_MATERIALS[name]["context"],
            "Rs_super_ohm_sq": (sup["Rs_ohm_sq"] if sup else None),
            "Xs_super_ohm_sq": (sup["Xs_ohm_sq"] if sup else None),
            "Q_super": (sup["q_conductor"] if sup else None),
            "Rs_normal_ohm_sq": (nor["Rs_ohm_sq"] if nor else None),
            "Q_normal": (nor["q_conductor"] if nor else None),
            "regime_super": (sup["regime"] if sup else None),
            "regime_normal": (nor["regime"] if nor else None),
        })
    return rows


# ---------------------------------------------------------------------------
# ⑧ 可锚性实验（判死的实证）
# ---------------------------------------------------------------------------
def anchorability_probe(rho_n: float = 1e-9, f_hz: float = 5e9,
                        material: str = "Al") -> Dict[str, Any]:
    """可锚性实测：三条 `R_s` 写法是否互相独立 + 两流体在 R_s 上是否失效。

    结论（本轮现算）：
      - 三条写法最大相对差 **2.130e−16** ⇒ 同一代数恒等 ⇒ resid ≡ 0；
      - 20 mK 两流体 vs BCS 差 **2.255e+61 倍** ⇒ 两流体**物理失效**，
        不构成"另一条可用路径"。
    """
    rows = []
    worst = 0.0
    for r in (1.68e-8, 1.0e-9, 1.5e-6, 2.65e-8):
        for f in (1e9, 5e9, 10e9):
            r1 = surface_resistance_infinite(r, f)
            d = skin_depth(r, f)
            r2 = r / d
            k = k_complex(sigma_normal(r), f)
            r3 = r * k.real
            e2 = abs(r2 - r1) / r1
            e3 = abs(r3 - r1) / r1
            worst = max(worst, e2, e3)
            rows.append({"rho": r, "f_hz": f, "Rs_def": r1,
                         "rel_rho_over_delta": e2, "rel_rho_times_k": e3})

    tc = float(KI.MATERIALS[material]["tc_k"])
    tcmp = []
    for t in (0.020, 0.100, 0.200, 0.300, 0.600):
        if t >= tc:
            continue
        z_b = zs_super(material, t, f_hz, 200e-9, use_bcs_sigma1=True)
        z_2 = zs_super(material, t, f_hz, 200e-9, use_bcs_sigma1=False)
        rb, r2f = z_b.real, z_2.real
        tcmp.append({"t_k": t, "T_over_Tc": t / tc,
                     "Rs_bcs": rb, "Rs_2fluid": r2f,
                     "ratio_2f_over_bcs": (r2f / rb) if rb > 0 else float("inf")})
    d20 = KI.delta_gross(tc, 0.020)
    return {
        "three_ways_worst_rel": worst,
        "three_ways_identical": worst < 1e-12,
        "rows": rows,
        "twofluid_vs_bcs": tcmp,
        "ratio_at_20mk": tcmp[0]["ratio_2f_over_bcs"] if tcmp else float("inf"),
        "exp_minus_delta_over_kbt_20mk": math.exp(-min(d20 / (KB_EV * 0.020), 700.0)),
        "verdict": ("NOT_ANCHORABLE"
                    if (worst < 1e-12 and (not tcmp or tcmp[0]["ratio_2f_over_bcs"] > 1e3))
                    else "NEEDS_REVIEW"),
    }


def why_not_anchored() -> Dict[str, Any]:
    """负结果机器化：为什么表面阻抗不可以立成新锚。"""
    pr = anchorability_probe()
    r20 = pr["twofluid_vs_bcs"][0] if pr["twofluid_vs_bcs"] else {}
    return {
        "anchorable": False,
        "three_reasons": [
            {"reason": "R_s 的三种写法是同一代数恒等（不是三条独立路径）",
             "evidence": "定义式 √(πfμ0ρ) / ρ/δ / Re(ρ·k) 最大相对差 **%.3e**"
                         "（12 组参数）" % pr["three_ways_worst_rel"],
             "judge_line": "resid ≡ 0 ⇒ 代数恒等不构成判别力"},
            {"reason": "深低温两流体在 R_s 上**物理失效**（不是重合，是错）",
             "evidence": "Al @20 mK：两流体/BCS = **%.3e 倍**（两流体 ∝ (T/Tc)^4，"
                         "BCS ∝ exp(−Δ/kBT) = %.3e）"
                         % (r20.get("ratio_2f_over_bcs", float("inf")),
                            pr["exp_minus_delta_over_kbt_20mk"]),
             "judge_line": "另一条路径物理不成立 ⇒ 只剩一条路径，无从对拍"},
            {"reason": "Wheeler 增量规则是定理，不是独立数值路径",
             "evidence": "α_c = R_s/(2Z0η0)·|∂Z0/∂n| 可从互易定理严格导出；"
                         "任何正确实现都给同一答案",
             "judge_line": "「定理 vs 数值解」不构成独立路径"},
        ],
        "replacement": ("改为**能力层**：给出 Z_s(t) 统一闭式、厚度分区判定、"
                        "α_c/Q_c、以及「导体损耗 ≠ TLS 介质损耗」的口径分界；"
                        "判据用四个解析极限 + 与 D-221 的跨模块对拍 + 标度关系"),
        "revisit_condition": ("若将来有同一 wafer 的谐振器实测 Q_c（或表面阻抗实测），"
                              "且能独立给出 σ1 的第二条数值路径（如非平衡准粒子输运模型），"
                              "可重评可锚性；届时须同步登记 ρ_n/λ_L(0) 的实测 provenance"),
    }


def design_boundary() -> Dict[str, Any]:
    """机械登记「零厚度无定义」这条边界（门禁与文档共用，防被当成精度瑕疵）。"""
    return {
        "zero_thickness_undefined": True,
        "why": ("CPW 零厚度导体的表面电流密度在带边缘 x→±a 呈幂次奇点，"
                "∮|J_s|²dl 因此**对数发散** ⇒ α_c 无定义。"
                "有限厚度 t 把奇点正则化到 ~t 尺度，故 t 是模型的**必需参数**而非精度旋钮。"),
        "enforced_at": "surface_impedance(t_m<=0) 直接 raise ValueError",
        "wheeler_limit": "等效内缩 δ_eff 必须 ≤ t/2；超出则 Wheeler 规则失效（alpha_with_thickness 会标记）",
        "thin_film_penalty": ("薄膜区（t ≪ δ）用半无限 R_s=ρ/δ 会**低估** R_s："
                             "NbTiN t=200nm ⇒ 43.59×、TiN ⇒ 35.59×、Nb ⇒ 1.41×、Al ⇒ 1.19× "
                             "（本轮现算，见 alpha_with_thickness 的 rs_ratio_vs_infinite）"),
        "thin_film_delta_eff": "薄膜区等效内缩恒为 **t/3**（与材料无关，由 coth 展开 Im/Re=(2/3)u² 推出）",
    }


# ---------------------------------------------------------------------------
# ⑨ 自检
# ---------------------------------------------------------------------------
def _raises(fn) -> bool:
    """「必抛」类判据：捕 Exception 全集（D-219 教训：捕窄会崩掉门禁）。"""
    try:
        fn()
        return False
    except Exception:
        return True


def run_selfchecks(verbose: bool = True) -> bool:
    res: List[Tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        res.append((name, bool(cond), detail))

    rho, f = 1.0e-9, 5e9
    d = skin_depth(rho, f)
    zs_inf = complex(rho / d, rho / d)

    # ① 厚膜极限：t/δ=100 时与 (ρ/δ)(1+j) 逐位相同
    z100 = zs_normal(rho, f, 100 * d)
    chk("① 厚膜极限 t/δ=100 ⇒ Z_s = (ρ/δ)(1+j)，残差 <1e-15",
        abs(z100 - zs_inf) / abs(zs_inf) < 1e-15,
        "rel=%.3e" % (abs(z100 - zs_inf) / abs(zs_inf)))

    # ② 薄膜极限：虚部/实部 → (2/3)(t/δ)，解析可验证
    # coth(x) = 1/x + x/3 + …，x = (1+j)·u，u = t/δ
    #   Z_s/(ρ/δ) = (1+j)·coth((1+j)u) ≈ 1/u + j·(2/3)u
    #   ⇒ Re = (ρ/δ)/u、Im = (ρ/δ)(2u/3)  ⇒ **Im/Re = (2/3)·u²**（是 u 的平方）
    u = 0.01
    zthin = zs_normal(rho, f, u * d)
    ratio = abs(zthin.imag) / zthin.real
    pred = (2.0 / 3.0) * u * u
    chk("② 薄膜极限 t/δ=0.01 ⇒ Im/Re = (2/3)(t/δ)²（实测 %.6e vs 解析 %.6e）"
        % (ratio, pred), abs(ratio - pred) / pred < 1e-3)

    # ③ 薄膜极限二阶项：Z_s = (ρ/δ)[1/u + j·2u/3] ⇒ Re·t/ρ = 1（零阶），
    #    用 coth 展开可证 Re 的**首项恰为 ρ/t**，故残差随 u² 衰减 ⇒ 断言 u=1e-3 时 <1e-6
    u2 = 1e-3
    zt2 = zs_normal(rho, f, u2 * d)
    prod2 = zt2.real * u2 * d / rho
    chk("③ 薄膜极限 Re·t/ρ → 1（u=1e-3 时残差 %.3e < 1e-6）" % abs(prod2 - 1.0),
        abs(prod2 - 1.0) < 1e-6)

    # ④ 超导厚膜：Im Z_s → ωμ0λ
    lam = KI.lambda_l_material("Al", T_OP_K)
    zsup = zs_super("Al", T_OP_K, f, 20 * lam)
    ref = 2.0 * math.pi * f * MU0 * lam
    chk("④ 超导厚膜 t/λ=20 ⇒ Im Z_s/(ωμ0λ) = 1.0000000000",
        abs(zsup.imag / ref - 1.0) < 1e-9, "实测 %.12f" % (zsup.imag / ref))

    # ⑤ 超导 σ1=0 ⇒ 纯虚
    zs_pure = surface_impedance(complex(0.0, -1.0 / (MU0 * 2 * math.pi * f * lam ** 2)),
                               f, 5 * lam)
    chk("⑤ σ1=0 ⇒ Re Z_s ≡ 0（纯电感）",
        abs(zs_pure.real) / abs(zs_pure) < 1e-15,
        "Re/|Z|=%.3e" % (abs(zs_pure.real) / abs(zs_pure)))

    # ⑥ 与 D-221 的 L_k 跨模块对拍
    w_m = 10e-6
    worst = 0.0
    for t_nm in (50, 100, 200, 400):
        t_m = t_nm * 1e-9
        s2 = 1.0 / (MU0 * 2 * math.pi * f * lam ** 2)
        zz = surface_impedance(complex(0.0, -s2), f, t_m)
        l_zs = zz.imag / (2 * math.pi * f)
        l_ki = KI.l_kin_per_length(lam, t_m, w_m) * w_m
        worst = max(worst, abs(l_zs - l_ki) / l_ki)
    chk("⑥ 与 D-221 的 L_k 对拍：Im Z_s/ω ≡ L_k^□（4 组，最差 %.3e）" % worst,
        worst < 1e-14)

    # ⑦ 零厚度必抛
    chk("⑦ t=0 必抛（零厚度表面阻抗无定义）",
        _raises(lambda: surface_impedance(sigma_normal(rho), f, 0.0)))

    # ⑧ α_c ∝ R_s：**固定内缩量**时严格线性。
    #    🔴 不固定内缩量时会有二阶偏离（δ_eff = Im Z_s/(ωμ0) 本身随 R_s 变 ⇒ ∂Z0/∂n 变），
    #    这不是实现缺陷，是 Wheeler 规则的真实结构：α_c = R_s·f(δ_eff(R_s))。
    DN = 0.05                                            # µm，固定
    a1 = alpha_c_cpw(zs_inf, f, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    a2 = alpha_c_cpw(zs_inf * 2.0, f, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    a4 = alpha_c_cpw(zs_inf * 4.0, f, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    chk("⑧ 固定内缩量时 α_c ∝ R_s 严格线性（2×/4× ⇒ 2×/4×）",
        abs(a2 / a1 - 2.0) < 1e-12 and abs(a4 / a1 - 4.0) < 1e-12,
        "比值 %.15f / %.15f" % (a2 / a1, a4 / a1))

    # ⑨ 正常态 α_c ∝ √f（固定内缩量；R_s ∝ √f ⇒ α_c/√f 恒定）
    vals = []
    for ff in (1e9, 5e9, 20e9):
        zz = zs_normal(rho, ff, 100 * skin_depth(rho, ff))
        aa = alpha_c_cpw(zz, ff, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
        vals.append(aa / math.sqrt(ff))
    chk("⑨ 固定内缩量时正常态 α_c/√f 恒定（3 频点，散布 <1e-12）",
        max(vals) / min(vals) - 1.0 < 1e-12,
        "相对散布 %.3e" % (max(vals) / min(vals) - 1.0))

    # ⑩ α_c 随 w 单调下降
    aa = [alpha_c_cpw(zs_inf, f, w, 6.0, 500.0, 11.45)["alpha_c_np_per_m"]
          for w in (2.0, 5.0, 10.0, 20.0, 40.0)]
    chk("⑩ α_c 随 w 严格单调下降（2→40 µm）",
        all(aa[i] > aa[i + 1] for i in range(len(aa) - 1)),
        "α: " + " > ".join("%.4f" % v for v in aa))

    # ⑪ 厚度分区判定三区正确
    reg = [thickness_regime(x * d, d)["regime"] for x in (0.05, 0.5, 2.0)]
    chk("⑪ 厚度分区 t/δ=0.05/0.5/2.0 ⇒ thin/transition/thick",
        reg == ["thin", "transition", "thick"], str(reg))

    # ⑫ 两流体在 R_s 上失效（深低温差 >1e3 倍）
    pr = anchorability_probe()
    chk("⑫ 两流体在 R_s 上失效：20 mK 两流体/BCS = %.3e 倍（>1e3）"
        % pr["ratio_at_20mk"], pr["ratio_at_20mk"] > 1e3)

    # ⑬ 三条 R_s 写法互相恒等（resid ≡ 0）
    chk("⑬ 三条 R_s 写法最大相对差 %.3e < 1e-12" % pr["three_ways_worst_rel"],
        pr["three_ways_worst_rel"] < 1e-12)

    # ⑭ 导体损耗 ≠ TLS：tanδ_eff 比手填 1e-6 小 1e3 倍以上
    sep = loss_channel_separation("Al", 200.0, f)
    chk("⑭ 导体 tanδ_eff = %.3e ≪ TLS 手填 1e−6（分离 %.3e 倍）"
        % (sep["tan_delta_eff_super"], sep["separation_super"]),
        sep["separation_super"] > 1e3 or sep["tan_delta_eff_super"] < 1e-9)

    # ⑮ 未知材料必抛（不猜默认）
    chk("⑮ 未知材料必抛（不猜 ρ/λ 默认值）",
        _raises(lambda: sigma_super("Unobtainium", T_OP_K, f)))

    # ⑯ 可锚性判死 + 三理由齐备
    wn = why_not_anchored()
    chk("⑯ ANCHORABLE=False ∧ 三条理由齐备 ∧ 有重评条件",
        wn["anchorable"] is False and len(wn["three_reasons"]) == 3
        and bool(wn["revisit_condition"]))

    ok = all(v for _, v, _ in res)
    if verbose:
        for n, v, dt in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n + (("  |  " + dt) if dt else ""))
        print("\n表面阻抗 / 有限厚度自检：%d/%d %s"
              % (sum(1 for _, v, _ in res if v), len(res), "ALL PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_selfchecks() else 1)
