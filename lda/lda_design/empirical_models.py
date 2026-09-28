"""LDA 实证锚「半解析独立模型」族（T5.3 · M6 实测对照扩容）。

本模块为「A 级实证锚 ↔ 计算路径」的对照提供**方法学独立**的第二种来源
（第一种是 `lda_design/loss_engines.py` 的 loss/效率类引擎）。三朵纪律：

1. **只吃几何 + 材料常数**：引擎签名里**没有** `measured_value`，也**不读**该
   语料 geometry 里由测量反演出来的字段（如 `n_g`）——否则 rel% 就是自证残差，
   而不是预测误差。对照器 `lda_harness/empirical_m6.py` 用**突变探针**证明这一点
   （改动语料实测值/派生字段，引擎输出必须**逐位不动**）。
2. **不拟合、如实报**：所有系数取自物理/公开材料数据；rel% 无论 PASS/FAIL 都
   如实登记（例如 Y-branch 的 43% 偏差就照实留着，不做拟合回算把它们抹平）。
3. **模型边界显式标注**：`model` 字段里写清用了什么近似、缺什么项（如
   「无 apodization 项 ⇒ 系统性低估」），使读者能判断偏差是"模型粗糙"还是"器件异常"。

材料色散取 `lda_solver.semivec_mode_solver` 的 Sellmeier（Si / SiO2 / Si3N4），
**不重写**另一份材料常数（单一来源）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

#: 理想响应度常数：R = η·q·λ/(h·c) = η·λ[µm]/1.2398  [A/W]
_HC_OVER_Q_UM = 1.2398


# ---------------------------------------------------------------------------
# 材料 / 色散
# ---------------------------------------------------------------------------
def _material_pair(geom: Dict[str, Any]) -> Tuple[str, str]:
    """由 geometry 的线索判平台（只认"芯材"标记，不看任何测量量）。

    `n_sin` / `n_si3n4` 出现 ⇒ SiN 平台；否则默认 Si（SOI）。该判据只用到
    **器件声明**（用的什么材料），不涉及测到的数值。
    """
    if "n_sin" in geom or "n_si3n4" in geom:
        return "Si3N4", "SiO2"
    return "Si", "SiO2"


def _refractive_index(material: str, wl_um: float) -> float:
    from lda_solver.semivec_mode_solver import (
        sellmeier_si, sellmeier_sio2, sellmeier_si3n4,
    )

    fn = {"Si": sellmeier_si, "SiO2": sellmeier_sio2,
          "Si3N4": sellmeier_si3n4}[material]
    return float(fn(wl_um))


# ---------------------------------------------------------------------------
# 有效折射率法（EIM）—— 两段一维对称平板解析解串联
# ---------------------------------------------------------------------------
def eim_neff(w_um: float, h_um: float, wl_um: float,
             core_mat: str = "Si", clad_mat: str = "SiO2",
             pol: str = "TE") -> float:
    """EIM 矩形波导基模 n_eff：先解竖直约束（厚度 h），再解水平约束（宽度 w）。

    诚实边界：EIM 在**低对比度**（SiN/SiO2）下与 2D 全矢量解一致到 ~1e-3；
    在**高对比度**（Si/SiO2）下会系统性**高估** n_eff（500x220 实测：EIM
    ≈2.63 vs 2D 全矢量 2.44）—— 这正是 n_g 对照里 SOI 项偏差偏大的原因，
    属**已知模型边界**，不修（修 = 拟合）。
    """
    from lda_solver.semivec_mode_solver import slab_neff

    n_core = _refractive_index(core_mat, wl_um)
    n_clad = _refractive_index(clad_mat, wl_um)
    n_vert = slab_neff(h_um, n_core, n_clad, wl_um, pol=pol)
    return float(slab_neff(w_um, n_vert, n_clad, wl_um, pol=pol))


def eim_group_index(w_um: float, h_um: float, wl_um: float,
                    core_mat: str = "Si", clad_mat: str = "SiO2",
                    pol: str = "TE", d_wl: float = 0.01
                    ) -> Tuple[float, float]:
    """n_g = n_eff − λ·dn_eff/dλ（λ 中心差分）＋返回 n_eff。"""
    n_mid = eim_neff(w_um, h_um, wl_um, core_mat, clad_mat, pol)
    n_lo = eim_neff(w_um, h_um, wl_um - d_wl, core_mat, clad_mat, pol)
    n_hi = eim_neff(w_um, h_um, wl_um + d_wl, core_mat, clad_mat, pol)
    n_g = n_mid - wl_um * (n_hi - n_lo) / (2.0 * d_wl)
    return float(n_g), float(n_mid)


# ---------------------------------------------------------------------------
# 引擎：波导群折射率
# ---------------------------------------------------------------------------
def engine_wg_ng(geom: Dict[str, Any], pol: str = "TE") -> Dict[str, Any]:
    """波导基模群折射率 n_g（EIM + 材料 Sellmeier 色散）。

    🔴 不读 `geom["n_g"]`（那是同一条语料的测量反演值 ⇒ 读它就是自证）。
    """
    w = float(geom["w_core_um"])
    h = float(geom["h_core_um"])
    wl = float(geom.get("wl_um", 1.55))
    core_mat, clad_mat = _material_pair(geom)
    n_g, n_eff = eim_group_index(w, h, wl, core_mat, clad_mat, pol)
    return {
        "metric": "n_g",
        "value": round(n_g, 4),
        "n_eff": round(n_eff, 4),
        "model": (f"EIM 两级平板（{core_mat}/{clad_mat} Sellmeier 色散）+ λ 中心差分 "
                  f"n_g=n_eff−λ·dn_eff/dλ；w={w} h={h} µm wl={wl} µm {pol}"),
    }


# ---------------------------------------------------------------------------
# 引擎：环形 / 跑马场谐振腔 FSR
# ---------------------------------------------------------------------------
def engine_ring_fsr(geom: Dict[str, Any], pol: str = "TE") -> Dict[str, Any]:
    """FSR = λ²/(n_g·L)，其中 n_g 由 EIM 从几何**算出**，L 由声明给出。

    周长的取值优先级：`L_um`（直接声明）> 2π`R_um`（圆环）。二者都缺则报错
    （不猜——猜出来的周长会让 FSR 对照变成数字游戏）。
    """
    w = float(geom["w_core_um"])
    h = float(geom["h_core_um"])
    wl = float(geom.get("wl_um", 1.55))
    if geom.get("L_um"):
        L = float(geom["L_um"])
        l_src = "L_um 声明"
    elif geom.get("R_um"):
        L = 2.0 * math.pi * float(geom["R_um"])
        l_src = f"2πR（R={float(geom['R_um'])} µm）"
    else:
        raise ValueError("geometry 缺 L_um 与 R_um：无周长则 FSR 不可算")
    core_mat, clad_mat = _material_pair(geom)
    n_g, n_eff = eim_group_index(w, h, wl, core_mat, clad_mat, pol)
    fsr_nm = (wl * 1000.0) ** 2 / (n_g * L * 1000.0)
    return {
        "metric": "FSR_nm",
        "value": round(fsr_nm, 4),
        "n_g": round(n_g, 4),
        "n_eff": round(n_eff, 4),
        "L_um": round(L, 3),
        "model": (f"FSR=λ²/(n_g·L)，n_g 由 EIM 算出（{core_mat}/{clad_mat}）；"
                  f"L={L:.2f} µm 来自 {l_src}"),
    }


# ---------------------------------------------------------------------------
# 引擎：介质波导传播损耗的**内禀 Q 上界**（跨器件一致性对照用）
# ---------------------------------------------------------------------------
def engine_ring_intrinsic_q(geom: Dict[str, Any], loss_dBcm: float,
                            pol: str = "TE") -> Dict[str, Any]:
    """由**另一条语料测得的**波导损耗反推内禀 Q：Q ≤ 2π·n_g/(λ·α)。

    α[1/m] = PL[dB/cm]·(ln10/10)·100。n_g 由 EIM 从几何算出（不读测量）。
    本引擎是「同平台跨器件一致性对照」：损耗测在**直波导**上、Q 测在**微环**上，
    两条测量独立 ⇒ 该对照检验「环的 Q 与平台波导损耗是否自洽」，而不是自证。

    ⚠️ 分母用 n_g 而非 n_eff 是既有工程约定（与 `golden_product_benchmarks`
    的 Q 口径一致）；两者在弱色散下差别在百分级，不影响量级判断。
    """
    w = float(geom.get("w_core_um", geom.get("h_core_um", 0.5)))
    h = float(geom["h_core_um"])
    wl = float(geom.get("wl_um", 1.55))
    core_mat, clad_mat = _material_pair(geom)
    n_g, _ = eim_group_index(w, h, wl, core_mat, clad_mat, pol)
    alpha = float(loss_dBcm) * (math.log(10.0) / 10.0) * 100.0
    q = 2.0 * math.pi * n_g / (wl * 1e-6 * alpha)
    return {
        "metric": "intrinsic_Q",
        "value": round(q, 1),
        "n_g": round(n_g, 4),
        "alpha_per_m": round(alpha, 3),
        "model": (f"Q=2π·n_g/(λ·α)，n_g 由 EIM 算出；α 取自**另一条**语料实测 "
                  f"PL={loss_dBcm} dB/cm（跨器件一致性对照，非同条自证）"),
    }


# ---------------------------------------------------------------------------
# 引擎：光栅耦合器（复用既有 Bragg 引擎，显式标注缺 apodization 项）
# ---------------------------------------------------------------------------
def engine_grating_apod(geom: Dict[str, Any]) -> Dict[str, Any]:
    """apodized 光栅耦合器：**复用** `engine_grating_eff` 的 Bragg 模型。

    诚实边界（必须与结果一起读）：该模型**没有** apodization / 方向性 / 背反射
    抑制项 ⇒ 对「周期+占空比双 apodization」的高效率器件**系统性低估**；
    实测与模型的 gap 即被模型漏掉的 apodization 增益。**不新增拟合项去追它**。
    """
    from lda_design.loss_engines import engine_grating_eff

    out = engine_grating_eff(dict(geom))
    return {
        "metric": "coupling_efficiency",
        "value": out["value"],
        "model": out["model"] + "；⚠️ 本模型无 apodization/方向性项 ⇒ 系统性低估",
    }


# ---------------------------------------------------------------------------
# 引擎：光电探测器响应度的**理想上界**
# ---------------------------------------------------------------------------
def engine_pd_responsivity_ideal(geom: Dict[str, Any]) -> Dict[str, Any]:
    """理想单位量子效率上界 R = λ[µm]/1.2398 [A/W]（无几何依赖）。

    这不是器件模型，而是**上界参照**：实测 R 与该上界之比即外量子效率。
    用上界作对照是刻意选择——它**永远不读测量值**，因此不可能被"拟合"。
    """
    wl = float(geom.get("wl_um", 1.55))
    r = wl / _HC_OVER_Q_UM
    return {
        "metric": "responsivity_A_per_W",
        "value": round(r, 4),
        "model": (f"理想单位量子效率上界 R=λ/1.2398（λ={wl} µm）—— "
                  f"实测/上界 = 外量子效率，非器件结构模型"),
    }


#: 引擎名 → 函数（供 `empirical_m6` 注册表按名分发，避免 import 期成环）
ENGINE_FUNCS = {
    "engine_wg_ng": engine_wg_ng,
    "engine_ring_fsr": engine_ring_fsr,
    "engine_ring_intrinsic_q": engine_ring_intrinsic_q,
    "engine_grating_apod": engine_grating_apod,
    "engine_pd_responsivity_ideal": engine_pd_responsivity_ideal,
}
