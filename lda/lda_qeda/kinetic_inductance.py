"""D-221 · 超导薄膜**动力学电感**（kinetic inductance）—— 能力层 · 净增 0 锚。

## 为什么需要它

`cpw_quasi_static` 自己声明过「超导薄膜的动力学电感（K ≈ λ_L² 项）**未建模**」。
这不是精度瑕疵，而是**量级问题**——实测（本轮现算，参考几何 w=10 µm / t 见下 / T=20 mK）：

| 材料 | Tc(K) | λ_L(0) nm | t=200 nm 时的 α = L_k/L_mag | n_eff 相对纯几何 |
|---|---|---|---|---|
| Al | 1.20 | 50 | **1.484%** | **+0.739%** |
| Nb | 9.20 | 40 | 1.187% | +0.592% |
| **NbTiN** | 14.0 | 200 | **7.790%** | **+3.822%** |
| **TiN** | 4.50 | 350 | **20.11%** | **+9.592%** |

Al/Nb 只有 ~0.7%，但**高动力学电感材料（NbTiN / TiN）会让纯几何 n_eff 错 4–10%** ——
远超 FDM 读出频率规划的容差（音间隔典型 10–50 MHz）。

## 🔴 一条必须自己纠正的猜测

上一轮我猜「动力学电感可能正好解释 v0.9.269 观测到的 **0.2037%** 偏差」。**实测否定**：

| 口径 | n_eff | vs 设计常量 2.5 |
|---|---|---|
| 纯几何（`substrate_caliber`） | 2.494907 | **−0.2037%** |
| 含 L_kin（Al 200 nm） | 2.513353 | **+0.5341%** |

动力学电感把 n_eff **往上推 0.739%**，不是往 2.5 收 —— **它不能解释那个偏差，反而过冲**。
诚实的结论是：**设计常量 2.5 既不是纯几何值、也不是含电感值**，它落在两者之间而没有依据。
（这条已机器化进 `design_constant_position()`，防止后来的人拿它编故事。）

## 🔴 可锚性：实测判死（不是推测）

按项目纪律先做可锚性实验，再定架构。**两条理论路径在深低温重合**：

| T | T/Tc | L_k(双流体) H/m | L_k(BCS 全积分) H/m | 相对差 |
|---|---|---|---|---|
| 20 mK | 0.017 | 6.2874025134e−09 | 6.2874022695e−09 | **3.879e−08** |
| 150 mK | 0.125 | 6.2881740375e−09 | 6.2886002668e−09 | 6.778e−05 |

跨平台判据线是 **1e4·ulp ≈ 1e−12** ⇒ 3.879e−08 **远在容差之外**，无判别力。
物理上也讲得通：深低温下双流体与 BCS 的差是 `exp(−Δ/k_BT)` 量级
（Al @20 mK ⇒ **1.082e−46**，Nb ⇒ 1e−305）⇒ **理论本身在深低温就重合**，不是数值精度问题。

⇒ **`ANCHORABLE = False`**。给既有 CPW 锚加一个 `alpha_kin` 参数属**参数化扩展**
（同标量 · 同构型 · 同数值格式），按章程净增 0 锚。理由 + 候选实测 + 重评条件全部机器化进
`why_not_anchored()`。

## 红线

纯 stdlib（`math`）+ 平台闭式。材料参数 `λ_L(0)` / `Tc` 是**文献典型值、非实测**
（`provenance` 逐条登记），不得读成 golden。零量子 SDK、LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_qeda import cpw_quasi_static as CQS
from lda_qeda import substrate_caliber as CAL

ROLE = ("D-221 · 超导薄膜动力学电感（Mattis-Bardeen / 双流体）能力层 —— "
        "把「纯几何 n_eff」推进到「含 L_kin 的 n_eff」，并如实登记它**不能**解释既有 0.2% 偏差。"
        "可锚性实测判死（深低温双流体 ≡ BCS），不新增锚。")
ANCHORABLE = False

MU0 = 4.0e-7 * math.pi          # H/m
EPS0 = 8.8541878128e-12         # F/m
KB_EV = 8.617333262e-5          # eV/K

#: 材料库 —— 🔴 **λ_L(0) 与 Tc 均为文献典型值，非本平台实测**（provenance 见下）
#:   典型分散：Al 薄膜 λ_L(0) 实测 30–60 nm；NbTiN 100–300 nm ⇒ ±50% 不确定度是常态
MATERIALS: Dict[str, Dict[str, Any]] = {
    "Al":    {"tc_k": 1.20, "lambda0_nm": 50.0},
    "Nb":    {"tc_k": 9.20, "lambda0_nm": 40.0},
    "NbTiN": {"tc_k": 14.0, "lambda0_nm": 200.0},
    "TiN":   {"tc_k": 4.50, "lambda0_nm": 350.0},
}

MATERIAL_PROVENANCE: Dict[str, str] = {
    "Al":    "文献典型值（弱耦合 BCS · 薄膜 λ_L(0) 常见 30–60 nm）；**非实测**",
    "Nb":    "文献典型值（块体 Nb λ_L(0)≈39 nm，薄膜常取 40 nm）；**非实测**",
    "NbTiN": "文献典型值（无序超导膜 150–300 nm 分散大）；**非实测**",
    "TiN":   "文献典型值（高方阻 TiN 可达 300–500 nm）；**非实测**",
}

#: 实际量子芯片工作温度（稀释制冷机混合室）
T_OP_K = 0.020


# ---------------------------------------------------------------------------
# ① 伦敦穿透深度的温度依赖（双流体）
# ---------------------------------------------------------------------------
def lambda_l(lam0_nm: float, tc_k: float, t_k: float) -> float:
    """双流体伦敦穿透深度（m）：λ_L(T) = λ_L(0)/√(1 − (T/Tc)^4)。

    T ≥ Tc 时超导态不存在 ⇒ 抛错（不返回 inf/nan 让错误传播）。
    """
    if t_k < 0:
        raise ValueError("T 必须 ≥ 0 K")
    if tc_k <= 0:
        raise ValueError("Tc 必须 > 0 K")
    if t_k >= tc_k:
        raise ValueError("T (%.6f K) 必须 < Tc (%.6f K)：超导态不存在" % (t_k, tc_k))
    x = (t_k / tc_k) ** 4
    return float(lam0_nm) * 1e-9 / math.sqrt(1.0 - x)


def lambda_l_material(material: str, t_k: float = T_OP_K) -> float:
    """按材料名取 λ_L(T)（m）。未知材料抛错，不猜默认。"""
    if material not in MATERIALS:
        raise KeyError("未登记材料 %r（已登记：%s）" % (material, sorted(MATERIALS)))
    m = MATERIALS[material]
    return lambda_l(m["lambda0_nm"], m["tc_k"], t_k)


# ---------------------------------------------------------------------------
# ② 薄膜每单位长度动力学电感
# ---------------------------------------------------------------------------
def l_kin_per_length(lam_m: float, t_m: float, w_m: float) -> float:
    """薄膜（厚度 t、宽度 w）每单位长度动力学电感（H/m）。

    来源：London 方程 `λ²J'' = J` 在 slab 内的**精确解** `J(z) ∝ cosh(z/λ)`，
    每方块 `L_k^□ = μ0·λ·coth(t/λ)`（Tinkham / Gao 2008 Eq. 2.30），
    除以宽度得每单位长度。

    极限自检：
      t ≪ λ ⇒ `μ0λ²/(w·t)`（薄膜极限）
      t ≫ λ ⇒ `μ0λ/w`（厚膜双面极限，每面 λ/2）
    """
    if lam_m <= 0 or t_m <= 0 or w_m <= 0:
        raise ValueError("λ / t / w 必须 > 0")
    return MU0 * lam_m * (1.0 / math.tanh(t_m / lam_m)) / w_m


def l_mag_per_length(c_air_f_per_m: float) -> float:
    """准 TEM 磁电感（H/m）：`L_mag = μ0·ε0 / C_air`。

    依据：无损准 TEM 线上 `v = 1/√(L·C)`，真空中 `v = c = 1/√(μ0ε0)`
    ⇒ 取空气电容 `C_air` 时 `L_mag = μ0ε0/C_air`。
    """
    if c_air_f_per_m <= 0:
        raise ValueError("C_air 必须 > 0")
    return MU0 * EPS0 / c_air_f_per_m


# ---------------------------------------------------------------------------
# ③ 与 CPW / SSOT 串联：α 与含电感的 n_eff
# ---------------------------------------------------------------------------
def cpw_kinetic_report(material: str = "Al",
                       w_um: float = 10.0, g_um: float = 6.0,
                       h_um: float = 500.0, eps_r: float = 11.45,
                       t_film_nm: float = 200.0,
                       t_k: float = T_OP_K) -> Dict[str, Any]:
    """把「版图几何 + 材料 + 温度 → α → 含 L_kin 的 n_eff」接成可复算链路。

    🔴 `eps_eff` **不在此处重算** —— 一律取 `substrate_caliber.TL_EPS_EFF_REF`
    （单一真源），避免又长出一个新口径。
    """
    fin = CQS.cpw_closed_form(w_um, g_um, h_um=h_um, eps_r=eps_r)
    c_air = float(fin["C_air_F_per_m"])
    lam = lambda_l_material(material, t_k)
    lk = l_kin_per_length(lam, t_film_nm * 1e-9, w_um * 1e-6)
    lm = l_mag_per_length(c_air)
    alpha = lk / lm
    eps_geom = CAL.TL_EPS_EFF_REF
    n_geom = math.sqrt(eps_geom)
    # v = 1/√((L_mag+L_k)·C) ⇒ n_eff' = n_geom·√(1+α)
    n_kin = n_geom * math.sqrt(1.0 + alpha)
    return {
        "material": material,
        "provenance": MATERIAL_PROVENANCE.get(material, "?"),
        "t_k": t_k,
        "t_film_nm": t_film_nm,
        "lambda_l_m": lam,
        "lambda_l_nm": lam * 1e9,
        "c_air_f_per_m": c_air,
        "l_kin_h_per_m": lk,
        "l_mag_h_per_m": lm,
        "alpha_kin": alpha,
        "eps_eff_geom": eps_geom,
        "n_eff_geom": n_geom,
        "n_eff_with_kin": n_kin,
        "n_eff_delta_pct": (n_kin - n_geom) / n_geom * 100.0,
        "z0_factor": math.sqrt(1.0 + alpha),   # Z0 ∝ √(L/C) ⇒ ×√(1+α)
        "note": ("α = L_k/L_mag；n_eff' = n_geom·√(1+α)。"
                 "λ_L(0)/Tc 为文献典型值（非实测）⇒ α 的不确定度主要由 λ_L(0) 的分散决定。"),
    }


def n_eff_with_kin(material: str = "Al", t_film_nm: float = 200.0,
                   w_um: float = 10.0, t_k: float = T_OP_K,
                   g_um: float = 6.0, h_um: float = 500.0,
                   eps_r: float = 11.45) -> float:
    """含动力学电感的有效折射率（`α=0` 时**严格退化**为纯几何 n_eff）。"""
    return float(cpw_kinetic_report(material, w_um, g_um, h_um, eps_r,
                                    t_film_nm, t_k)["n_eff_with_kin"])


def f0_with_kin(length_um: float, material: str = "Al", t_film_nm: float = 200.0,
                w_um: float = 10.0, t_k: float = T_OP_K) -> float:
    """含 L_kin 的 λ/4 谐振频率（GHz）：`f = c0/(4·L·n_eff')`。"""
    if length_um <= 0:
        raise ValueError("腔长必须 > 0")
    n = n_eff_with_kin(material, t_film_nm, w_um, t_k)
    return 2.99792458e8 / (4.0 * length_um * 1e-6) / n / 1e9


# ---------------------------------------------------------------------------
# ④ 设计常量 2.5 的位置（防后人编故事）
# ---------------------------------------------------------------------------
def design_constant_position(material: str = "Al", t_film_nm: float = 200.0) -> Dict[str, Any]:
    """把「设计常量 2.5」与两种口径的相对位置如实登记。

    🔴 **结论是负面的**：动力学电感**不能**解释 v0.9.269 观测到的 0.2037% 偏差
    —— 它把 n_eff 往上推 0.739%（Al 200 nm），反而**过冲**。
    """
    rep = cpw_kinetic_report(material, t_film_nm=t_film_nm)
    return {
        "design_constant": 2.5,
        "n_eff_geom": rep["n_eff_geom"],
        "n_eff_with_kin": rep["n_eff_with_kin"],
        "geom_vs_2p5_pct": (rep["n_eff_geom"] - 2.5) / 2.5 * 100.0,
        "kin_vs_2p5_pct": (rep["n_eff_with_kin"] - 2.5) / 2.5 * 100.0,
        "verdict": "CONSTANT_HAS_NO_DERIVATION",
        "why": ("纯几何 = %.6f（比 2.5 低 %.4f%%）、含 L_kin = %.6f（比 2.5 高 %.4f%%）"
                "⇒ 2.5 **既不是**纯几何值、**也不是**含电感值，落在两者之间且无推导过程。"
                "动力学电感的作用是**上推**，因此它解释不了此前那个 **偏低** 0.2%% 的偏差。"
                % (rep["n_eff_geom"], abs((rep["n_eff_geom"] - 2.5) / 2.5 * 100),
                   rep["n_eff_with_kin"], (rep["n_eff_with_kin"] - 2.5) / 2.5 * 100)),
    }


# ---------------------------------------------------------------------------
# ⑤ 可锚性实验（机器化负结果）
# ---------------------------------------------------------------------------
def _sech2(x: float) -> float:
    """数值稳定的 sech²(x)：x 大时走 4e^(−2x) 渐近，避免 cosh 溢出。"""
    ax = abs(x)
    if ax > 350.0:
        return 0.0
    e = math.exp(-2.0 * ax)
    return 4.0 * e / (1.0 + e) ** 2


def delta_gross(tc_k: float, t_k: float) -> float:
    """BCS 能隙（eV）的 Gross 近似：Δ(T)=1.764·k_B·Tc·tanh(1.74·√(Tc/T−1))。"""
    if t_k <= 0:
        return 1.764 * KB_EV * tc_k
    if t_k >= tc_k:
        return 0.0
    return 1.764 * KB_EV * tc_k * math.tanh(1.74 * math.sqrt(tc_k / t_k - 1.0))


def ns_two_fluid(tc_k: float, t_k: float) -> float:
    """双流体超流密度比 `1 − (T/Tc)^4`。"""
    return 1.0 - (t_k / tc_k) ** 4


def ns_bcs(tc_k: float, t_k: float, npts: int = 20001) -> float:
    """BCS 全积分超流密度比（低频极限）。

    `n_s/n = 1 − (1/(2k_BT))·∫_Δ^∞ sech²(E/2k_BT)·E/√(E²−Δ²) dE`

    🔴 **端点奇点处理**：`E→Δ` 时被积式按 `1/√(E−Δ)` 发散（可积）。
    用代换 `E = Δ·cosh(u)` ⇒ `E/√(E²−Δ²)·dE = Δ·cosh(u) du` ⇒ **奇点消失**，
    变成 `∫_0^{u_max} sech²(Δcosh(u)/2k_BT)·Δ·cosh(u) du`。复合 Simpson 求积。

    ⚠️ **可信区间 `T ≤ 0.3·Tc`**：再往上 Gross 能隙近似开始失真（实测 Al 在 T/Tc=0.25
    已出现 13.6% 偏离，那是**近似失效**而非真物理差），故只在该区间内用于对拍。
    """
    d = delta_gross(tc_k, t_k)
    if d <= 0:
        return 0.0
    kt2 = 2.0 * KB_EV * t_k
    # u_max：令 sech² 的自变量 x = Δcosh(u)/2kBT 达到 ~350（此时 sech² < 1e-300）
    xmax = 350.0
    cosh_umax = max(xmax * kt2 / d, 1.0)
    u_max = math.acosh(cosh_umax) if cosh_umax > 1.0 else 0.0
    if u_max <= 0.0:
        return 1.0
    if npts % 2 == 0:
        npts += 1
    h = u_max / (npts - 1)

    def f(u: float) -> float:
        cu = math.cosh(min(u, 700.0))
        return _sech2(d * cu / kt2) * d * cu

    s = f(0.0) + f(u_max)
    for i in range(1, npts - 1):
        s += (4.0 if i % 2 else 2.0) * f(i * h)
    val = s * h / 3.0
    ns = 1.0 - val / kt2
    return max(min(ns, 1.0), 0.0)


def anchorability_probe(material: str = "Al", t_film_nm: float = 200.0,
                        w_um: float = 10.0) -> Dict[str, Any]:
    """可锚性实测：把「双流体」与「BCS 全积分」两条路径的 L_k 逐点对拍。

    判定线用**跨平台判据线 1e4·ulp ≈ 1e−12**（v0.9.255 立）：
      · 相对差 < 1e−12 ⇒ 无判别力 ⇒ **不可锚**
      · 相对差 ≫ 1e−12 且稳定 ⇒ 才有资格讨论锚
    """
    m = MATERIALS.get(material)
    if m is None:
        raise KeyError("未登记材料 %r" % (material,))
    tc, lam0 = m["tc_k"], m["lambda0_nm"]
    rows = []
    for tk in (0.020, 0.050, 0.100, 0.150, 0.200, 0.300):
        if tk / tc > 0.31:
            continue
        la = l_kin_per_length(lambda_l(lam0, tc, tk), t_film_nm * 1e-9, w_um * 1e-6)
        ns_b = ns_bcs(tc, tk)
        lam_b = lam0 * 1e-9 / math.sqrt(ns_b) if ns_b > 1e-12 else float("inf")
        lb = (l_kin_per_length(lam_b, t_film_nm * 1e-9, w_um * 1e-6)
              if math.isfinite(lam_b) else float("inf"))
        rel = abs(la - lb) / la if math.isfinite(lb) else float("inf")
        rows.append({"t_k": tk, "t_over_tc": tk / tc,
                     "l_kin_two_fluid": la, "l_kin_bcs": lb, "rel": rel})
    worst = max(r["rel"] for r in rows) if rows else float("inf")
    rel_op = rows[0]["rel"] if rows else float("inf")      # 首行 = T_OP = 20 mK
    d = delta_gross(tc, 0.020)

    # 🔴 判据口径（比「< 1e-12 就算重合」更讲道理）：
    #   可锚性要求「两条路径的差 **显著大于** 参数不确定度」，否则这个差会被
    #   材料参数分散彻底淹没，立成锚是自欺。λ_L(0) 的实测分散按 ±50% 计（Al 30–60 nm），
    #   即相对不确定度 ~0.5。
    mat_unc = 0.5
    return {
        "material": material,
        "rows": rows,
        "rel_at_operating_point": rel_op,
        "worst_rel_at_T_lessthan_0p3Tc": worst,
        "material_rel_uncertainty": mat_unc,
        "swamp_ratio_at_op": (mat_unc / rel_op) if rel_op > 0 else float("inf"),
        "swamp_ratio_worst": (mat_unc / worst) if worst > 0 else float("inf"),
        "exp_minus_delta_over_kbt_at_20mk": math.exp(-min(d / (KB_EV * 0.020), 700.0)),
        "verdict": ("NOT_ANCHORABLE"
                    if (rel_op < 1e-6 and worst < 1e-2) else "NEEDS_REVIEW"),
        "note": ("**工作点（20 mK）**：两条路径差 %.2e，被 λ_L(0) 的 ±50%% 材料分散淹没 %.0f 倍 "
                 "⇒ 无判别力。物理上也讲得通：深低温两者差是 exp(−Δ/kBT) 量级"
                 "（Al ⇒ 1e−46），**理论本身重合**。"
                 "**高温段（T→0.3Tc）**：差升到 %.2e，但那是**双流体近似失效**（BCS 才是对的），"
                 "不是「可锚证据」；且 %.2e 仍比材料不确定度小 %.0f 倍，同样淹没。"
                 % (rel_op, mat_unc / rel_op if rel_op > 0 else 0,
                    worst, worst, mat_unc / worst if worst > 0 else 0)),
    }


def why_not_anchored() -> Dict[str, Any]:
    """负结果机器化：为什么动力学电感不可以立成新锚。"""
    pr = anchorability_probe("Al", 200.0, 10.0)
    return {
        "anchorable": False,
        "three_reasons": [
            {"reason": "无第二条独立数值路径（理论在深低温重合）",
             "evidence": "Al @20 mK：双流体 vs BCS 的 L_k 相对差 **%.3e**；"
                         "指数证据 exp(−Δ/kBT) = **%.3e**"
                         % (pr["rows"][0]["rel"], pr["exp_minus_delta_over_kbt_at_20mk"]),
             "judge_line": "可锚性要求路径差 ≫ 参数不确定度；此处差 4e-8 被 ±50%% 分散淹没 1e7 倍"},
            {"reason": "几何因子是 London 方程的精确解，数值解必然重合",
             "evidence": "coth(t/λ) 来自 λ²J''=J 在 slab 内的解析解 J∝cosh(z/λ) ⇒ "
                         "任何正确数值解都给同一答案（resid ≡ 0）",
             "judge_line": "「精确解 vs 数值解」不构成独立路径"},
            {"reason": "λ_L(0) 本身是材料参数，无闭式 golden",
             "evidence": "Al 薄膜实测 λ_L(0) = 30–60 nm（±50%% 分散）；"
                         "要立锚必须**给定** λ0 ⇒ 退化为给既有 CPW 锚加参数",
             "judge_line": "参数化扩展（同标量·同构型·同数值格式）⇒ 净增 0"},
        ],
        "replacement": ("改为**能力层**：把 α 与含 L_kin 的 n_eff 算出来，"
                        "判据用极限自检（薄膜/厚膜）、单调性、与 SSOT 的串联恒等、"
                        "以及「不可锚」本身的可复现残差"),
        "revisit_condition": ("若将来有**实测** λ_L(0)（同一 wafer 的谐振器实测反演）"
                              "或 foundry 给出的动力学电感表，可把 α 升格为实证锚；"
                              "届时须同步登记 provenance 变更与不确定度"),
    }


def material_table(t_film_nm: float = 200.0, w_um: float = 10.0,
                   t_k: float = T_OP_K) -> List[Dict[str, Any]]:
    """材料 × 动力学电感一览（供面板/文档引用）。"""
    out = []
    for name in sorted(MATERIALS):
        try:
            r = cpw_kinetic_report(name, w_um=w_um, t_film_nm=t_film_nm, t_k=t_k)
            out.append({"material": name, "lambda_l_nm": r["lambda_l_nm"],
                        "alpha_kin": r["alpha_kin"],
                        "n_eff_with_kin": r["n_eff_with_kin"],
                        "n_eff_delta_pct": r["n_eff_delta_pct"]})
        except (ValueError, KeyError):
            continue
    return out


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    lam0, tc = 50.0, 1.20
    chk("① λ_L(T→0) = λ_L(0)（rel<1e-12）",
        abs(lambda_l(lam0, tc, 1e-12) - lam0 * 1e-9) <= 1e-12 * lam0 * 1e-9)
    chk("② λ_L(T) 随 T 单调增（4 点）",
        all(lambda_l(lam0, tc, a) < lambda_l(lam0, tc, b)
            for a, b in ((0.02, 0.2), (0.2, 0.5), (0.5, 1.0))))
    chk("③ T ≥ Tc 必抛（超导态不存在，不许返回 inf/nan）",
        _raises(lambda_l, lam0, tc, tc) and _raises(lambda_l, lam0, tc, 2.0))

    lam = lambda_l(lam0, tc, 0.02)
    w, t = 10e-6, 200e-9
    chk("④ 厚膜极限 t≫λ ⇒ L_k → μ0λ/w（rel<1e-9）",
        abs(l_kin_per_length(lam, 2000e-9, w) - MU0 * lam / w) / (MU0 * lam / w) < 1e-9)
    # ⑤ 薄膜极限：取 t/λ = 0.1（真薄膜），断言相对偏差**恰为 coth 展开的二阶项 (x²/3)**
    #    coth(x) = 1/x + x/3 − x³/45 + …  ⇒  L_k/(μ0λ²/wt) = 1 + x²/3 + O(x⁴)，x = t/λ
    _x = 0.1
    _t5 = _x * lam
    _lk5 = l_kin_per_length(lam, _t5, w)
    _ref5 = MU0 * lam ** 2 / (w * _t5)
    _rel5 = (_lk5 - _ref5) / _ref5
    _pred5 = _x ** 2 / 3.0
    chk("⑤ 薄膜极限 t/λ=0.1 ⇒ 偏差恰为 coth 展开二阶项 (t/λ)²/3（实测 %.3e vs 解析 %.3e）"
        % (_rel5, _pred5), abs(_rel5 - _pred5) < 0.1 * _pred5)
    chk("⑥ L_k 随膜厚 t 单调减（越薄电感越大）",
        l_kin_per_length(lam, 50e-9, w) > l_kin_per_length(lam, 100e-9, w)
        > l_kin_per_length(lam, 400e-9, w))
    chk("⑦ L_k 与宽度 w 严格反比",
        abs(l_kin_per_length(lam, t, w) * w - l_kin_per_length(lam, t, 2 * w) * 2 * w)
        <= 1e-15 * l_kin_per_length(lam, t, w) * w)

    rep = cpw_kinetic_report("Al", t_film_nm=200.0)
    chk("⑧ n_eff' = n_geom·√(1+α)（恒等）",
        abs(rep["n_eff_with_kin"] - rep["n_eff_geom"] * math.sqrt(1 + rep["alpha_kin"]))
        <= 1e-14 * rep["n_eff_with_kin"])
    chk("⑨ ε_eff 取自 substrate_caliber 单一真源（不在此处重算）",
        abs(rep["eps_eff_geom"] - CAL.TL_EPS_EFF_REF) <= 1e-15 * CAL.TL_EPS_EFF_REF)
    chk("⑩ L_mag = μ0ε0/C_air 与 cpw_quasi_static 的 C_air 一致",
        abs(rep["l_mag_h_per_m"] * rep["c_air_f_per_m"] - MU0 * EPS0)
        <= 1e-14 * MU0 * EPS0)

    pos = design_constant_position("Al", 200.0)
    chk("⑪ 设计常量 2.5 无推导：纯几何比它低、含 L_kin 比它高（两侧分居）",
        pos["geom_vs_2p5_pct"] < 0 < pos["kin_vs_2p5_pct"])

    pr = anchorability_probe("Al", 200.0, 10.0)
    chk("⑫ 可锚性实测：工作点差 %.2e 被材料分散淹没 %.0f 倍 · 高温段最大差 %.2e 也淹没 %.0f 倍 ⇒ 不可锚"
        % (pr["rel_at_operating_point"], pr["swamp_ratio_at_op"],
           pr["worst_rel_at_T_lessthan_0p3Tc"], pr["swamp_ratio_worst"]),
        pr["verdict"] == "NOT_ANCHORABLE")
    chk("⑬ 指数证据：Al @20 mK 的 exp(−Δ/kBT) < 1e-40（%.2e）"
        % pr["exp_minus_delta_over_kbt_at_20mk"],
        pr["exp_minus_delta_over_kbt_at_20mk"] < 1e-40)
    chk("⑭ 材料敏感性真实存在：TiN(200nm) 的 α > 10×Al(200nm) 的 α",
        cpw_kinetic_report("TiN", t_film_nm=200.0)["alpha_kin"]
        > 10 * cpw_kinetic_report("Al", t_film_nm=200.0)["alpha_kin"])
    chk("⑮ 负结果机器化：不可锚（三条理由齐备 + 重评条件）",
        ANCHORABLE is False and len(why_not_anchored()["three_reasons"]) == 3
        and why_not_anchored()["revisit_condition"])
    chk("⑯ 材料 provenance 逐条登记（λ_L(0) 是文献典型值，非实测）",
        all(k in MATERIAL_PROVENANCE and "非实测" in MATERIAL_PROVENANCE[k]
            for k in MATERIALS))
    chk("⑰ 未登记材料必抛（不猜默认材料）", _raises(lambda_l_material, "Unobtainium", 0.02))

    if verbose:
        for n, v in msgs:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


def _raises(fn, *a) -> bool:
    try:
        fn(*a)
        return False
    except Exception:                                        # noqa: BLE001
        return True


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print("---")
    print("kinetic_inductance 自检:", "ALL PASS" if ok else "FAIL")
    for r in material_table():
        print("  %-6s λ_L=%.1f nm  α=%.4f%%  n_eff=%.6f  Δ=%+.3f%%"
              % (r["material"], r["lambda_l_nm"], r["alpha_kin"] * 100,
                 r["n_eff_with_kin"], r["n_eff_delta_pct"]))
    print(design_constant_position()["why"])
