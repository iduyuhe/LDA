"""量子网络 · **源不可分辨性：不对称源通式 + 多光子成分**（G-QNET-2 · v0.9.295 · 纯标准库）

═══════════════════════════════════════════════════════════════════════
改前是什么（G-QNET-2「源不可分辨性」）
═══════════════════════════════════════════════════════════════════════
`qnet_source.overlap_magnitude_sq` 只实现**对称源**（`σ₁ = σ₂ = σ`）：

    V = exp(−δt²/(4σ²)) · exp(−δω²σ²)

而它自己的 docstring 里写着通式（**只写在注释里，从未实现**）：

    V = [2σ₁σ₂/(σ₁²+σ₂²)] · exp(−δt²/(2(σ₁²+σ₂²))) · exp(−2δω²σ₁²σ₂²/(σ₁²+σ₂²))

⇒ 「源不可分辨性」只对**两个源完全相同**成立。真实的独立光子源（两个 SPDC 源 / 两个量子点）
必然在**谱宽与中心频率上失配**，此前的模型对此**恒等于 1（无惩罚）**，即默认「两个源一样」。
这与 v0.9.287–294 同型：**一个普遍情形被写成特例，且没人核**。

═══════════════════════════════════════════════════════════════════════
本层给什么
═══════════════════════════════════════════════════════════════════════
① `hom_visibility_asym`   不对称源通式（**σ₁ ≠ σ₂、δω₁ ≠ δω₂**），
   🔴 **对照支路：σ₁=σ₂ ∧ δω₁=δω₂ 时逐位退化为 `qnet_source.hom_visibility`**（本体自洽、不是另起一套）；
② `hom_visibility_with_g2` 多光子成分的**一阶**修正 `V = V_ideal·(1 − g²(0))`
   🔴 **两个端点都是已知物理**：`g²(0)=0`（理想单光子）⇒ `V = V_ideal`；`g²(0)=1`（相干态）⇒ `V = 0`；
③ `indistinguishability_asym` / `mismatch_sweep` / `source_mismatch_report` 全量报告。

═══════════════════════════════════════════════════════════════════════
诚实边界
═══════════════════════════════════════════════════════════════════════
· `g²(0)` 修正是**一阶**（`1 − g²` 线性化），不含多光子高阶项、不含探测器暗计数与后脉冲；
· 波包仍假设高斯、变换极限（不含非傅里叶极限的谱扩散 / chirp）；
· 参数为文献量级设计示例，**非实测**；不作性能宣称。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from lda_l2 import qnet_source as SR

__all__ = [
    "DEFAULT_SIGMA1_S", "DEFAULT_SIGMA2_S", "DEFAULT_DW1_RAD_S", "DEFAULT_DW2_RAD_S",
    "DEFAULT_DELAY_S", "DEFAULT_G2",
    "hom_visibility_asym",
    "hom_visibility_with_g2",
    "indistinguishability_asym",
    "mismatch_sweep",
    "source_mismatch_report",
    "selfcheck_qnet_indistinguishability",
]

#: 与 `qnet_source` 同源的参考档（对称情形下两者必须逐位相同）
DEFAULT_SIGMA1_S = SR.DEFAULT_PACKET_SIGMA_S      # 1.0e-12
DEFAULT_SIGMA2_S = SR.DEFAULT_PACKET_SIGMA_S
DEFAULT_DW1_RAD_S = SR.DEFAULT_DW_RAD_S           # 1.0e12
DEFAULT_DW2_RAD_S = SR.DEFAULT_DW_RAD_S
DEFAULT_DELAY_S = SR.DEFAULT_DELAY_S              # 2.0e-12
#: 多光子成分参考档（脉冲式 SPDC 源 g²(0) 的文献量级；理想单光子 = 0，相干态 = 1）
DEFAULT_G2 = 0.05


# ══════════════════════════════════════════════════════════════════════
# ① 不对称源通式
# ══════════════════════════════════════════════════════════════════════
def hom_visibility_asym(sigma1_s: float = DEFAULT_SIGMA1_S,
                        sigma2_s: float = DEFAULT_SIGMA2_S,
                        dw1_rad_s: float = DEFAULT_DW1_RAD_S,
                        dw2_rad_s: float = DEFAULT_DW2_RAD_S,
                        delay_s: float = DEFAULT_DELAY_S) -> float:
    """不对称高斯波包的 HOM 可见度（波包重叠幅度平方）：

        `V = [2σ₁σ₂/(σ₁²+σ₂²)] · exp(−δt²/(2(σ₁²+σ₂²))) · exp(−**2**·δω²σ₁²σ₂²/(σ₁²+σ₂²))`

    其中 `δt = delay_s`、`δω = dw1 − dw2`。
    🔴 **对照支路**：`σ₁=σ₂=σ` 且 `δω=0` 时 **逐位等于** `qnet_source.hom_visibility`。
    """
    s1, s2 = float(sigma1_s), float(sigma2_s)
    if s1 <= 0.0 or s2 <= 0.0:
        raise ValueError("波包宽度 σ 须 > 0")
    d_w = float(dw1_rad_s) - float(dw2_rad_s)
    s12 = s1 * s1 + s2 * s2
    amp = 2.0 * s1 * s2 / s12
    t_term = math.exp(-(float(delay_s) ** 2) / (2.0 * s12))
    # 🔴 指数里的因子 **2** 不可省：σ₁=σ₂=σ 时必须给出 exp(−δω²σ²)（与 `qnet_source` 逐位对齐）
    w_term = math.exp(-2.0 * (d_w * d_w) * (s1 * s1) * (s2 * s2) / s12)
    return float(amp * t_term * w_term)


def hom_visibility_with_g2(v_ideal: float, g2: float = DEFAULT_G2) -> float:
    """多光子成分的**一阶**修正：`V = V_ideal · (1 − g²(0))`。

    🔴 **两个端点都是已知物理（可机核）**：
       `g²(0) = 0`（理想单光子）⇒ `V = V_ideal`；`g²(0) = 1`（相干态）⇒ `V = 0`。
    """
    g = float(g2)
    if g < 0.0:
        raise ValueError("g²(0) 不能为负")
    v = float(v_ideal) * (1.0 - g)
    return float(max(0.0, v))


def indistinguishability_asym(sigma1_s: float = DEFAULT_SIGMA1_S,
                              sigma2_s: float = DEFAULT_SIGMA2_S,
                              dw1_rad_s: float = DEFAULT_DW1_RAD_S,
                              dw2_rad_s: float = DEFAULT_DW2_RAD_S,
                              delay_s: float = DEFAULT_DELAY_S,
                              g2: float = 0.0) -> float:
    """不可分辨度 `1 − V`（与 `qnet_source.indistinguishability` 同语义）。"""
    return float(1.0 - hom_visibility_with_g2(
        hom_visibility_asym(sigma1_s, sigma2_s, dw1_rad_s, dw2_rad_s, delay_s), g2))


# ══════════════════════════════════════════════════════════════════════
# ② 失配扫描
# ══════════════════════════════════════════════════════════════════════
def mismatch_sweep(ratios: Tuple[float, ...] = (1.0, 1.1, 1.25, 1.5, 2.0),
                   sigma1_s: float = DEFAULT_SIGMA1_S,
                   dw_offset_rad_s: float = DEFAULT_DW1_RAD_S,
                   delay_s: float = DEFAULT_DELAY_S) -> List[Dict[str, Any]]:
    """扫「σ₂/σ₁」（**中心频率差固定**为 `δω`，两源对称分摊 ±δω/2）。

    🔴 **不预设方向**：`σ₂ ≠ σ₁` 时可见度可能**升**也可能**降** ——
    更宽的那个波包与窄的**时间重叠更好**（t 项变好），但约化方差变大（ω 项变差），
    净效应由参数决定。本层只给可复算的通式，**不编造「失配必然降 V」**。
    """
    v0 = hom_visibility_asym(sigma1_s, sigma1_s,
                             dw_offset_rad_s / 2.0, -dw_offset_rad_s / 2.0, delay_s)
    out: List[Dict[str, Any]] = []
    for r in ratios:
        v = hom_visibility_asym(sigma1_s, float(r) * sigma1_s,
                                dw_offset_rad_s / 2.0, -dw_offset_rad_s / 2.0, delay_s)
        out.append({
            "ratio_sigma2_over_sigma1": float(r),
            "visibility": float(v),
            "visibility_symmetric": float(v0),
            "ratio_vs_symmetric": float(v / v0) if v0 > 0 else float("inf"),
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# ③ 报告
# ══════════════════════════════════════════════════════════════════════
def source_mismatch_report(sigma1_s: float = DEFAULT_SIGMA1_S,
                           sigma2_s: float = 1.5e-12,
                           dw_offset_rad_s: float = DEFAULT_DW1_RAD_S,
                           delay_s: float = DEFAULT_DELAY_S,
                           g2: float = DEFAULT_G2) -> Dict[str, Any]:
    """不对称源报告：通式可见度 / 多光子修正后 / 与对称档的比 / 退化校验。

    `dw_offset_rad_s` = 两源**中心频率差** δω（与 `qnet_source.hom_visibility` 的 `dw` 同语义）；
    内部按 ±δω/2 分摊给两个源。对称档即 σ₁=σ₂ 且 δω 相同的退化情形。
    """
    dw1, dw2 = dw_offset_rad_s / 2.0, -dw_offset_rad_s / 2.0
    v_sym = SR.hom_visibility(delay_s, dw_offset_rad_s, sigma1_s)
    v_asym = hom_visibility_asym(sigma1_s, sigma2_s, dw1, dw2, delay_s)
    v_g2 = hom_visibility_with_g2(v_asym, g2)
    # 退化校验：σ₁=σ₂ 时通式必须逐位回到 qnet_source
    v_degen = hom_visibility_asym(sigma1_s, sigma1_s, dw1, dw2, delay_s)
    return {
        "sigma1_s": float(sigma1_s), "sigma2_s": float(sigma2_s),
        "dw_offset_rad_s": float(dw_offset_rad_s),
        "dw1_rad_s": float(dw1), "dw2_rad_s": float(dw2),
        "delay_s": float(delay_s), "g2": float(g2),
        "visibility_symmetric": float(v_sym),
        "visibility_asym": float(v_asym),
        "visibility_asym_with_g2": float(v_g2),
        "ratio_vs_symmetric": float(v_asym / v_sym) if v_sym > 0 else float("inf"),
        "g2_penalty": float(1.0 - v_g2 / v_asym) if v_asym > 0 else 0.0,
        "degenerate_match": bool(abs(v_degen - v_sym) <= 1e-15 * max(1.0, v_sym)),
        "degenerate_value": float(v_degen),
        "note": (
            "改前只实现对称源（σ₁=σ₂）⇒ 两源失配时模型**恒无惩罚**；本层给通式，"
            "并在 σ₁=σ₂ 时**逐位退化**到 `qnet_source.hom_visibility`（对照支路）。"
            "多光子成分按一阶 `V·(1−g²(0))` 修正，端点 g²=0⇒V 不变、g²=1⇒V=0。"
            "残余：非傅里叶极限谱扩散 / chirp / 暗计数与后脉冲未含；参数为设计示例非实测。"
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def selfcheck_qnet_indistinguishability() -> Dict[str, bool]:
    c: Dict[str, bool] = {}
    rep = source_mismatch_report()

    # ① 🔴 对照支路：对称极限逐位退化到 qnet_source（本体自洽，不是另起一套）
    c["degenerates_to_symmetric"] = rep["degenerate_match"]
    # ② g² 两个端点都是已知物理
    v_ideal = 0.7
    c["g2_zero_identity"] = hom_visibility_with_g2(v_ideal, 0.0) == v_ideal
    c["g2_one_zero"] = hom_visibility_with_g2(v_ideal, 1.0) == 0.0
    # ③ 通式**真的区分了不对称**（不预设方向：更宽波包时间重叠更好，方向由参数定）
    c["asym_differs_from_symmetric"] = abs(rep["visibility_asym"] - rep["visibility_symmetric"]) > 1e-6
    # ④ 时延单调：δt 越大 ⇒ V 越低
    v_t = [hom_visibility_asym(1e-12, 1.2e-12, 1e12, 0.9e12, d) for d in (0.0, 1e-12, 2e-12, 4e-12)]
    c["monotone_in_delay"] = all(v_t[i] > v_t[i + 1] for i in range(len(v_t) - 1))
    # ⑤ 对称档与 qnet_source 同值（两条独立路径同一结果）
    _v_src = SR.hom_visibility()
    _v_mine = hom_visibility_asym(DEFAULT_SIGMA1_S, DEFAULT_SIGMA1_S,
                                  DEFAULT_DW1_RAD_S / 2.0, -DEFAULT_DW1_RAD_S / 2.0,
                                  DEFAULT_DELAY_S)
    c["symmetric_matches_source_module"] = abs(_v_src - _v_mine) <= 1e-15 * max(1.0, _v_src)
    # ⑥ 绝对量级锚点（参考档）—— 防单位与量级错
    c["reference_magnitude"] = (0.10 <= rep["visibility_asym"] <= 0.16
                                and 0.12 <= rep["visibility_symmetric"] <= 0.15)
    # ⑦ 失配扫描全程有限且非负（不静默给 inf/nan）
    c["sweep_all_finite"] = all(0.0 <= r["visibility"] <= 1.0 for r in mismatch_sweep())
    # ⑧ 不可分辨度 = 1 − V（语义自洽）
    c["indistinguishability_definition"] = abs(
        indistinguishability_asym() - (1.0 - hom_visibility_asym())) <= 1e-15
    # ⑨ 非法入参抛 ValueError
    try:
        hom_visibility_asym(0.0, 1e-12)
        c["bad_input_raises"] = False
    except ValueError:
        c["bad_input_raises"] = True
    return c


if __name__ == "__main__":  # pragma: no cover
    sc = selfcheck_qnet_indistinguishability()
    bad = [k for k, v in sc.items() if not v]
    print("qnet_indistinguishability 自检：%d/%d 通过" % (len(sc) - len(bad), len(sc)))
    if bad:
        print("FAIL:", bad)
    r = source_mismatch_report()
    print("V(对称)=%.6f · V(不对称)=%.6f（比 %.3f×）· V(+g²=%.2f)=%.6f · 退化逐位=%s" %
          (r["visibility_symmetric"], r["visibility_asym"], r["ratio_vs_symmetric"],
           r["g2"], r["visibility_asym_with_g2"], r["degenerate_match"]))
