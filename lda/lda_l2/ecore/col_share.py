# -*- coding: utf-8 -*-
"""E18 列侧共享与架构权衡（`lda/lda_l2/ecore/col_share.py` · D-190）。

═══════════════════════════════════════════════════════════════════════════
定位：**面积维度上的 E15/E17**
═══════════════════════════════════════════════════════════════════════════
E15 合成「误差」，E17 合成「时间」，本段补上此前**完全没有建模**的第三个维度：**面积**，
并回答那个 E1–E17 从未敢答的架构问题：

    「列侧读出电路（TIA + ADC）能不能共享？共享的代价是什么？」

E1–E17 里 TIA/ADC **始终是「每列一份」**（`crossbar_mvm` 每列一个理想运放 ·
`mvm_datapath` 每列一个 ADC · `converter.sar_convert` 是单通道）。
全仓 `share` / `mux` / `multiplex` / `复用器` / `时分` 在 `lda_l2/ecore/` **零命中**。

🔴 **量级事实（本段实测 · 对外可讲）**：`c_unit_f = 1 pF` / 8 bit ⇒ `C_tot = 256 pF`；
按 MIM 密度 2 fF/µm² ⇒ **单列 CDAC 面积 128 000 µm²**，而 8×8 阵列本体足迹只有 **333 µm²**
⇒ **单列读出 = 阵列的 384 倍**；N=8 全并行读出 **1.03 mm² = 阵列的 ~3090 倍**。
⇒ **在二进制 CDAC 口径下，列侧读出电路压倒性支配芯片面积** —— 这就是「为什么必须共享」。

═══════════════════════════════════════════════════════════════════════════
🔴🔴 第一原理：**面积-时间乘积守恒**（与 E15/E17 的合成律并列的第三条律）
═══════════════════════════════════════════════════════════════════════════
设每份转换器面积 `A_u`、每次转换周期 `T_conv`、`N` 列：

    全并行 (K=1) ：面积 N·A_u        · 每列周期 T_conv
    K 列共享     ：面积 (N/K)·A_u    · 每列周期 K·T_conv
    ⇒  A_total × 每列周期 = N·A_u·T_conv = **常数（与 K 无关）**

⇒ **共享只沿「等面积-时间双曲线」移动，不改变乘积。**
要突破它只有两条路：**① 缩短 `T_conv` 本身**；**② 复制瓶颈级（反向沿曲线走）**。

🔴 **与 E17 锚的接续**：E17 实测**流水线收益仅 0.289** ⇒ 提吞吐不能靠流水线，
只能**并行复制瓶颈级**（SAR）⇒ 复制是**面积线性增**、共享是**面积降**
⇒ **二者是同一条 (面积, 吞吐) 帕累托前沿的两端**（本模块 `replication_vs_sharing` 给出论证）。

═══════════════════════════════════════════════════════════════════════════
🔴 第二原理：**保吞吐共享 ⇒ 面积 ∝ 1/K²**（不是 1/K）
═══════════════════════════════════════════════════════════════════════════
共享 K 倍同时**保住吞吐** ⇒ 必须把 `T_conv` 缩短 K 倍。由 E17 G-5：

    T_conv = (bits+1)·t_clk,   t_clk ≥ R_on·C_tot·(bits+1)·ln2  ⇒  T_conv ∝ C_tot·(bits+1)²
    ⇒ 缩 T_conv 的唯一物理路径 = **降 C_tot**（降 CDAC 电容）：C_tot(K) = C_tot(1)/K

⇒ 面积**双项闭式**（🔴 两项指数不同，这是本段最实用的工程结论）：

    A(K) = (N/K)·( C_tot(1)/(ρ·K) + A_logic )
         =  N·C_tot(1)/(ρ·K²)   +   N·A_logic/K
            └── 电容项 ∝ 1/K² ──┘     └── 逻辑项 ∝ 1/K ─┘

**拐点** `K* = C_tot(1)/(ρ·A_logic)`：`K<K*` 电容项支配（1/K² 收益显著）；
`K>K*` 逻辑面积支配（退化为 1/K）。8 bit / 1 pF / 2 fF·µm⁻² / 800 µm² ⇒ **`K* = 160`**。

═══════════════════════════════════════════════════════════════════════════
🔴 第三腿：精度 —— **诚实结论：kT/C 在可达共享度内不是约束**
═══════════════════════════════════════════════════════════════════════════
降 `C_tot` 的代价是采样热噪声 **`σ = √(kT/C_tot)`（物理律）** ⇒ 位数上限 `log2(V_ref/(k_σ·σ))`：

    bits_ceiling(K) = bits_ceiling(1) − 0.5·log2(K)

8 bit / 1 pF / 300 K / `k_σ=3` ⇒ `bits_ceiling(1) = 17.92` ⇒ 跌到 **8 位**需 **`K_crit ≈ 1.05×10⁵`**
⇒ **远超任何合理共享度**。
⇒ 本段**不硬造精度腿**：在「二进制 CDAC + 电容支配面积」口径下，**共享的真实代价是「吞吐」不是「精度」**；
kT/C 只是**很远的渐近地板**（给出公式与交叉点，并作为探针可打的一条闭式）。

═══════════════════════════════════════════════════════════════════════════
保护性约束
═══════════════════════════════════════════════════════════════════════════
**只读消费** E14/E17 —— **不改** `CONV_PROCESS` / `TIMING_PROCESS` / 任何既有默认值；
`keep_throughput` **默认 False**（保守口径）⇒ **E15/E16/E17 已发布数字逐位不变**。

═══════════════════════════════════════════════════════════════════════════
诚实边界（详见 `COL_SHARE_DISCLOSURE`）
═══════════════════════════════════════════════════════════════════════════
面积为**宏模型占位**（ρ=2 fF/µm² · A_logic=800 µm² · A_tia=400 µm² 为公开量级 · **非 PDK**）；
真实芯片用分段 CDAC / 更小 `C_u` / 采样电容共享 ⇒ 面积远小于此；
**只覆盖静态**（不含动态功耗 / 时钟树 / 供电网络 / 驱动器面积）；**不做功耗估算 ⇒ 不谈能效**；
共享的**动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动）未建模**；
🔴 **绝不报 TOPS / TOPS-W / fJ/op**。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from . import converter as CV
from . import layout as LY
from . import timing as T

KB = 1.380649e-23

# ═══════════════════════════════════════════════════════════════════════════
# 工艺 / 默认参数（**公开典型量级占位 · 非 PDK**）
# ═══════════════════════════════════════════════════════════════════════════
COL_SHARE_PROCESS: Dict[str, float] = {
    "cap_density_ff_per_um2": 2.0,   # MIM 电容密度（典型 1–2 fF/µm²）
    "adc_logic_area_um2": 800.0,     # SAR 逻辑 + 比较器 + 寄存器（常数面积）
    "tia_area_um2": 400.0,           # 单级 OTA + Rf + 补偿电容（宏模型）
    "mux_switch_area_um2": 25.0,     # 单个多路开关（大 W/L ⇒ R_on 小）
    "switch_wl": 500.0,              # 开关 W/L（与 E14 `dac_sw_wl` 同口径）
    "switch_vgate_v": 3.0,
    "temperature_k": 300.0,
    "ref_v": 1.0,
    "k_sigma": 3.0,
}

COL_SHARE_DISCLOSURE: Dict[str, str] = {
    "role": "E18 = 列侧共享与架构权衡 —— 补上全仓此前**完全没有建模**的「面积」维度，"
            "并回答「列侧 TIA/ADC 能不能共享、共享的代价是什么」",
    "first_principle": "🔴 **面积-时间乘积守恒**：`A_total × 每列周期 = N·A_u·T_conv`（与 K 无关）"
                       "⇒ 共享只沿「等面积-时间双曲线」移动，不改变乘积",
    "second_principle": "🔴 **保吞吐共享 ⇒ 面积 ∝ 1/K²**（不是 1/K）：缩 T_conv 的唯一物理路径是降 C_tot"
                        "（`T_conv ∝ C_tot·(bits+1)²` · E17 G-5）⇒ 面积双项闭式"
                        "`N·C_tot/(ρK²) + N·A_logic/K`，拐点 `K* = C_tot(1)/(ρ·A_logic)`",
    "third_leg": "🔴 **精度腿（诚实结论）**：`σ = √(kT/C_tot)` 是物理律，但 8 bit / 1 pF / k_σ=3 时"
                 "位数上限 17.92，跌到 8 位需共享度 `K ≈ 1.05×10⁵` ⇒ **在可达共享度内 kT/C 不是约束**；"
                 "**共享的真实代价是「吞吐」不是「精度」**（不硬造精度腿）",
    "upstream_anchor": "接 E17 两个锚：**流水线收益仅 0.289** ⇒ 提吞吐只能**并行复制瓶颈级**（面积线性增）"
                       "⇒ 与共享（面积降）是**同一条 (面积, 吞吐) 帕累托前沿的两端**；"
                       "**DAC/SAR 主导项随位数交叉** ⇒ 共享/复制的对象随位数切换",
    "area_model": "面积为**宏模型占位**：ρ=2 fF/µm²（MIM）· A_logic=800 µm² · A_tia=400 µm² · "
                  "开关 25 µm² —— 均为**公开量级 · 非 PDK · 无实测锚** ⇒ 结论随参数变",
    "scope": "**只覆盖静态 + 面积/周期估算**：不含动态功耗 / 时钟树 / 供电网络 / 驱动器面积 / IO pad；"
             "共享的**动态代价（多路开关电荷注入 / 串扰 / 采样孔径抖动）未建模**",
    "no_power": "🔴 **不做功耗估算 ⇒ 不谈能效**；**绝不报 TOPS / TOPS-W / fJ/op**"
                "（那是吞吐 × 能效的联合指标，本段既无功耗模型、也无实测硅）",
    "protect": "**只读消费** E14/E17 —— 不改 `CONV_PROCESS` / `TIMING_PROCESS` / 任何既有默认值；"
               "`keep_throughput` 默认 **False** ⇒ E15/E16/E17 已发布数字**逐位不变**",
    "red_line": "纯标准库（复用 E14/E17）· LLM 不进判决路径 · 零商业 EDA 依赖 · **非签核级 SPICE**",
}

__all__ = [
    "KB", "COL_SHARE_PROCESS", "COL_SHARE_DISCLOSURE",
    # ① 物理律（第三腿）
    "thermal_noise_rms_v", "thermal_noise_bits_ceiling", "bits_ceiling_of_share",
    "ktc_crossing_share",
    # ② 面积闭式
    "cap_area_um2", "converter_area_um2", "readout_area_um2",
    "analytic_area_um2", "area_period_product_um2_s",
    # ③ 时间 / 吞吐
    "converter_period_s", "col_throughput_sps",
    # ④ 标度律 / 拐点
    "k_star", "fit_loglog_slope", "scaling_law_report",
    # ⑤ 架构族 / 推荐 / 复制
    "architectures", "recommend_architecture", "replication_vs_sharing",
    # ⑥ 自检
    "col_share_self_check",
]


def _p(key: str, override: Optional[dict] = None):
    if override and key in override:
        return override[key]
    return COL_SHARE_PROCESS[key]


def _bits(bits: Optional[int]) -> int:
    return int(T.TIMING_PROCESS["bits"] if bits is None else bits)


# ═══════════════════════════════════════════════════════════════════════════
# ① 第三腿：物理律（热噪声 kT/C）
# ═══════════════════════════════════════════════════════════════════════════
def thermal_noise_rms_v(c_f: float, temperature_k: Optional[float] = None) -> float:
    """**采样热噪声（物理律）**：`σ = √(k_B·T / C)`。

    = 电容上 `kT/C` 噪声的 RMS 电压（教科书结果 · 由 `⟨v²⟩ = kT/C` 给出）。
    """
    c = float(c_f)
    if c <= 0.0:
        raise ValueError("电容须 > 0")
    t = float(_p("temperature_k") if temperature_k is None else temperature_k)
    if t <= 0.0:
        raise ValueError("温度须 > 0")
    return math.sqrt(KB * t / c)


def thermal_noise_bits_ceiling(c_f: float, ref_v: Optional[float] = None,
                               k_sigma: Optional[float] = None,
                               temperature_k: Optional[float] = None) -> float:
    """**热噪声给出的位数上限**：`log2(V_ref / (k_σ·σ))`。

    🔴 这是**渐近地板**，不是当前精度：见模块 docstring 第三腿（可达共享度内远未触及）。
    """
    r = float(_p("ref_v") if ref_v is None else ref_v)
    k = float(_p("k_sigma") if k_sigma is None else k_sigma)
    sig = thermal_noise_rms_v(c_f, temperature_k)
    if sig <= 0.0:
        return float("inf")
    return math.log2(r / (k * sig))


def bits_ceiling_of_share(k_adc: float, bits: Optional[int] = None,
                          c_unit_f: Optional[float] = None, **kw) -> float:
    """**共享 K 倍（保吞吐）后的位数上限** = `bits_ceiling(C_tot(1)/K)`。"""
    k = float(k_adc)
    if k <= 0.0:
        raise ValueError("共享度须 > 0")
    ct = T.cdac_total_cap(_bits(bits), c_unit_f) / k
    return thermal_noise_bits_ceiling(ct, **kw)


def ktc_crossing_share(bits_target: int, c_unit_f: Optional[float] = None,
                       ref_v: Optional[float] = None, k_sigma: Optional[float] = None,
                       temperature_k: Optional[float] = None) -> Dict:
    """**kT/C 何时开始咬人** —— 保吞吐共享使位数上限跌到 `bits_target` 所需的共享度。

    令 `log2(V_ref/(k_σ·√(kT·K/C_tot(1)))) = bits` ⇒ `K = C_tot(1)·V_ref² / (k_σ²·kT·4^bits)`。
    """
    b = int(bits_target)
    r = float(_p("ref_v") if ref_v is None else ref_v)
    ks = float(_p("k_sigma") if k_sigma is None else k_sigma)
    t = float(_p("temperature_k") if temperature_k is None else temperature_k)
    ct0 = T.cdac_total_cap(_bits(None), c_unit_f)
    k = ct0 * r * r / (ks * ks * KB * t * (4.0 ** b))
    return {
        "bits_target": b, "k_share_crit": k,
        "c_tot_at_crit_f": ct0 / k,
        "sigma_v_at_crit": thermal_noise_rms_v(ct0 / k, t),
        "c_tot_1_f": ct0,
        "note": "🔴 该 K 远超任何合理共享度 ⇒ **可达范围内 kT/C 不是约束**",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ② 面积闭式
# ═══════════════════════════════════════════════════════════════════════════
def cap_area_um2(c_f: float, cap_density_ff_per_um2: Optional[float] = None) -> float:
    """**电容面积闭式**：`A = C / ρ`（ρ 单位 fF/µm² ⇒ `C[F]/(ρ·10⁻¹⁵)`）。"""
    d = float(_p("cap_density_ff_per_um2")
              if cap_density_ff_per_um2 is None else cap_density_ff_per_um2)
    if d <= 0.0:
        raise ValueError("电容密度须 > 0")
    return float(c_f) / (d * 1e-15)


def converter_area_um2(bits: Optional[int] = None, c_unit_f: Optional[float] = None,
                       cap_density_ff_per_um2: Optional[float] = None,
                       logic_area_um2: Optional[float] = None) -> Dict:
    """**单个 SAR/CDAC 转换器面积** = 电容面积 + 逻辑面积（双项）。

    电容项**复用** E17 `cdac_total_cap`（= E14 `_cdac_c_unit` 之和 · 不复制公式）。
    """
    b = _bits(bits)
    ct = T.cdac_total_cap(b, c_unit_f)
    a_cap = cap_area_um2(ct, cap_density_ff_per_um2)
    a_log = float(_p("adc_logic_area_um2") if logic_area_um2 is None else logic_area_um2)
    return {"bits": b, "c_total_f": ct, "cap_area_um2": a_cap, "logic_area_um2": a_log,
            "area_um2": a_cap + a_log, "cap_dominated": bool(a_cap > a_log),
            "is_oracle": False}


def readout_area_um2(n_cols: int, k_adc: int = 1, k_tia: int = 1,
                     bits: Optional[int] = None,
                     keep_throughput: bool = False,
                     c_unit_f: Optional[float] = None,
                     cap_density_ff_per_um2: Optional[float] = None,
                     logic_area_um2: Optional[float] = None,
                     tia_area_um2: Optional[float] = None,
                     mux_switch_area_um2: Optional[float] = None) -> Dict:
    """**列侧读出电路总面积**（TIA + ADC + 多路开关）。

    份数取 **ceil**（物理上必须是整数份）⇒ 列数小于共享度时**共享度饱和**（1 份就够）。

    🔴 `keep_throughput=True` 时按**第二原理**把 `C_tot` 降到 `C_tot(1)/K`
    （否则 `T_conv` 缩不下来 ⇒ 吞吐会掉 K 倍）。
    """
    n = int(n_cols)
    if n < 1:
        raise ValueError("列数须 >= 1")
    ka = max(1, int(k_adc))
    kt = max(1, int(k_tia))
    n_adc = int(math.ceil(n / float(ka)))
    n_tia = int(math.ceil(n / float(kt)))
    ct0 = T.cdac_total_cap(_bits(bits), c_unit_f)
    ct_eff = (ct0 / float(ka)) if keep_throughput else ct0
    a_cap_unit = cap_area_um2(ct_eff, cap_density_ff_per_um2)
    a_log = float(_p("adc_logic_area_um2") if logic_area_um2 is None else logic_area_um2)
    a_tia_u = float(_p("tia_area_um2") if tia_area_um2 is None else tia_area_um2)
    a_sw_u = float(_p("mux_switch_area_um2")
                   if mux_switch_area_um2 is None else mux_switch_area_um2)
    a_adc = n_adc * (a_cap_unit + a_log)
    a_tia = n_tia * a_tia_u
    a_mux = n_adc * min(ka, n) * a_sw_u
    total = a_adc + a_tia + a_mux
    return {
        "n_cols": n, "k_adc": ka, "k_tia": kt, "bits": _bits(bits),
        "keep_throughput": bool(keep_throughput),
        "n_adc_units": n_adc, "n_tia_units": n_tia,
        "c_total_unit_f": ct_eff, "c_total_nominal_f": ct0,
        "adc_area_um2": a_adc, "tia_area_um2": a_tia, "mux_area_um2": a_mux,
        "area_um2": total, "area_mm2": total * 1e-6,
        "is_oracle": False,
    }


def analytic_area_um2(n_cols: int, k_adc: float,
                      bits: Optional[int] = None,
                      keep_throughput: bool = False,
                      c_unit_f: Optional[float] = None,
                      cap_density_ff_per_um2: Optional[float] = None,
                      logic_area_um2: Optional[float] = None,
                      include_tia: bool = False,
                      tia_area_um2: Optional[float] = None) -> float:
    """**连续口径**（不取整）的列侧面积 —— 用于**标度律拟合**（`ceil` 会造台阶）。

    `keep_throughput=True` ⇒ `A = N·C_tot(1)/(ρK²) + N·A_logic/K`（第二原理双项闭式）。
    """
    n = float(n_cols)
    k = float(k_adc)
    if n <= 0.0 or k <= 0.0:
        raise ValueError("列数与共享度须 > 0")
    ct0 = T.cdac_total_cap(_bits(bits), c_unit_f)
    ct = (ct0 / k) if keep_throughput else ct0
    a = (n / k) * (cap_area_um2(ct, cap_density_ff_per_um2)
                   + float(_p("adc_logic_area_um2")
                           if logic_area_um2 is None else logic_area_um2))
    if include_tia:
        a += n * float(_p("tia_area_um2") if tia_area_um2 is None else tia_area_um2)
    return a


def area_period_product_um2_s(n_cols: int, k_adc: int = 1,
                              bits: Optional[int] = None,
                              keep_throughput: bool = False, **kw) -> Dict:
    """🔴 **第一原理验证用**：`面积 × 每列周期` 在**不保吞吐**时与 K **无关**。

    🔴 只计**被共享的那份单元**（ADC 读出 = 电容 + 逻辑）的**连续口径**面积：
    TIA 与多路开关**不参与**共享律（前者按 `k_tia` 独立共享、后者 ∝K 抵消），
    且 `ceil` 取整会造台阶 ⇒ 用 `analytic_area_um2`（不取整）才能看到严格守恒。
    """
    a = analytic_area_um2(n_cols, max(1, int(k_adc)), bits, keep_throughput, **kw)
    per = float(max(1, int(k_adc))) * converter_period_s(bits)
    return {"area_um2": a, "period_s": per, "product_um2_s": a * per,
            "k_adc": int(max(1, int(k_adc))), "is_oracle": False}


# ═══════════════════════════════════════════════════════════════════════════
# ③ 时间 / 吞吐（**复用 E17 G-4/G-5**，不复制公式）
# ═══════════════════════════════════════════════════════════════════════════
def converter_period_s(bits: Optional[int] = None, c_unit_f: Optional[float] = None,
                       r_on: Optional[float] = None) -> float:
    """**一次 SAR 转换周期** = E17 `sar_stage_time`（= G-4 拍数 × G-5 每拍建立）。

    `(bits+1)·settle_half_lsb(R_on·C_tot, bits)` ⇒ `∝ C_tot·(bits+1)²`（**第二原理的根**）。
    """
    return float(T.sar_stage_time(_bits(bits), c_unit=c_unit_f, r_on=r_on)["t_s"])


def col_throughput_sps(k_adc: int = 1, bits: Optional[int] = None,
                       c_unit_f: Optional[float] = None,
                       r_on: Optional[float] = None,
                       keep_throughput: bool = False) -> float:
    """**每列采样率**。

    · `keep_throughput=False`（默认）：`1/(K·T_conv)` —— 转换器尺寸不变 ⇒ 每列周期 ×K。
    · `keep_throughput=True`：`C_tot → C_tot(1)/K` ⇒ `T_conv → T_conv/K`
      ⇒ 每列周期 = `K·(T_conv/K)` = **`T_conv(1)`（与 K 无关）** ⇒ **吞吐被保住**（第二原理的兑现）。
    """
    k = max(1, int(k_adc))
    cu = float(CV.CONV_PROCESS["c_unit_f"] if c_unit_f is None else c_unit_f)
    cu_eff = (cu / float(k)) if keep_throughput else cu
    return 1.0 / (float(k) * converter_period_s(bits, cu_eff, r_on))


# ═══════════════════════════════════════════════════════════════════════════
# ④ 标度律 / 拐点
# ═══════════════════════════════════════════════════════════════════════════
def k_star(bits: Optional[int] = None, c_unit_f: Optional[float] = None,
           cap_density_ff_per_um2: Optional[float] = None,
           logic_area_um2: Optional[float] = None) -> Dict:
    """**收益拐点 `K*`**：保吞吐下「电容项 == 逻辑项」处的共享度。

    `C_tot(1)/(ρ·K*) = A_logic` ⇒ `K* = C_tot(1)/(ρ·A_logic)`。
    `K<K*` ⇒ 电容项支配（面积 ∝1/K² 收益显著）；`K>K*` ⇒ 逻辑支配（退化为 ∝1/K）。
    """
    ct0 = T.cdac_total_cap(_bits(bits), c_unit_f)
    d = float(_p("cap_density_ff_per_um2")
              if cap_density_ff_per_um2 is None else cap_density_ff_per_um2)
    al = float(_p("adc_logic_area_um2") if logic_area_um2 is None else logic_area_um2)
    ks = ct0 / (d * 1e-15 * al)
    return {"k_star": ks, "bits": _bits(bits), "c_tot_1_f": ct0,
            "cap_area_1_um2": cap_area_um2(ct0, d), "logic_area_um2": al,
            "cap_over_logic_at_k1": cap_area_um2(ct0, d) / al,
            "is_oracle": False}


def fit_loglog_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """对 `(x, y)` 做 **log-log 最小二乘斜率**（= 标度指数）。纯标准库实现。"""
    pts = [(float(x), float(y)) for x, y in zip(xs, ys) if float(x) > 0 and float(y) > 0]
    if len(pts) < 2:
        raise ValueError("至少需要 2 个正点")
    lx = [math.log(p[0]) for p in pts]
    ly = [math.log(p[1]) for p in pts]
    n = float(len(pts))
    mx, my = sum(lx) / n, sum(ly) / n
    den = sum((v - mx) ** 2 for v in lx)
    if den == 0.0:
        raise ValueError("x 无变化 ⇒ 斜率无定义")
    num = sum((lx[i] - mx) * (ly[i] - my) for i in range(len(pts)))
    return num / den


def scaling_law_report(n_cols: int = 512, bits: Optional[int] = None,
                       ks: Sequence[int] = (1, 2, 4, 8, 16, 32, 64),
                       c_unit_f: Optional[float] = None, **kw) -> Dict:
    """**两条标度律的数值验证**（连续口径 · 无 `ceil` 台阶）。

    · **不保吞吐**（`keep_throughput=False`）⇒ `A = (N/K)(A_cap+A_logic)` ⇒ **严格 ∝ 1/K**（指数 = **−1**）
    · **保吞吐**（`keep_throughput=True`）⇒ `A = N·A_cap(1)/K² + N·A_logic/K`
      ⇒ 整体是**双项混合**（指数 ∈ (−2, −1)）；🔴 **仅电容项**严格 **∝ 1/K²**（指数 = **−2**）

    ⇒ 三条斜率分别报告：`slope_plain`（严格 −1）· `slope_keep_cap`（严格 −2）· `slope_keep_total`（混合）。
    """
    xs = [int(k) for k in ks]
    a_plain = [analytic_area_um2(n_cols, k, bits, False, c_unit_f, **kw) for k in xs]
    a_keep = [analytic_area_um2(n_cols, k, bits, True, c_unit_f, **kw) for k in xs]
    kw_cap = dict(kw)
    kw_cap["logic_area_um2"] = 0.0            # 只留电容项 ⇒ 严格 1/K²
    a_keep_cap = [analytic_area_um2(n_cols, k, bits, True, c_unit_f, **kw_cap) for k in xs]
    return {
        "n_cols": int(n_cols), "k_points": xs,
        "area_plain_um2": a_plain, "area_keep_um2": a_keep,
        "area_keep_cap_only_um2": a_keep_cap,
        "slope_plain": fit_loglog_slope(xs, a_plain),
        "slope_keep_total": fit_loglog_slope(xs, a_keep),
        "slope_keep_cap": fit_loglog_slope(xs, a_keep_cap),
        "k_star": k_star(bits, c_unit_f, **kw)["k_star"],
        "conclusion": "🔴 不保吞吐 ⇒ 面积 ∝1/K（双曲线守恒）；保吞吐 ⇒ 电容项 ∝1/K²（第二原理），"
                      "整体混合斜率 ∈ (−2, −1) · 拐点 K* 之后退化为 ∝1/K",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 架构族 / 推荐 / 复制-共享对照
# ═══════════════════════════════════════════════════════════════════════════
def _arch_row(name: str, n_cols: int, bits: int, k_adc: int, k_tia: int,
              keep_throughput: bool, target_sps: Optional[float], **kw) -> Dict:
    rd = readout_area_um2(n_cols, k_adc=k_adc, k_tia=k_tia, bits=bits,
                          keep_throughput=keep_throughput, **kw)
    sps = col_throughput_sps(k_adc, bits, c_unit_f=kw.get("c_unit_f"),
                             keep_throughput=keep_throughput)
    cu_eff = rd["c_total_unit_f"] / float(1 << int(bits))
    return {
        "architecture": name,
        "k_adc": int(k_adc), "k_tia": int(k_tia),
        "keep_throughput": bool(keep_throughput),
        "area_um2": rd["area_um2"], "area_mm2": rd["area_mm2"],
        "per_col_sps": sps, "converter_period_s": converter_period_s(bits, c_unit_f=cu_eff),
        "c_total_unit_f": rd["c_total_unit_f"], "unit_cap_f": cu_eff,
        "bits_ceiling": bits_ceiling_of_share(k_adc, bits, kw.get("c_unit_f")),
        "meets_target": (bool(sps >= float(target_sps))
                         if target_sps is not None else None),
        "is_oracle": False,
    }


def architectures(n_cols: int = 64, bits: Optional[int] = None,
                  target_sps: Optional[float] = None, **kw) -> Dict:
    """**架构族对照**（列侧读出）—— 五条典型路线。

    · `fully_parallel`   —— 每列一套 TIA + ADC（面积最大 · 吞吐最高）
    · `tia_shared_k4`    —— TIA 共享 K=4 份（ADC 仍每列一套）
    · `adc_shared_k4_plain` —— ADC 共享 K=4（**不保吞吐** ⇒ 面积 ∝1/K）
    · `adc_shared_k4_keep`  —— ADC 共享 K=4 + **同比降 C_tot**（**保吞吐** ⇒ 面积 ∝1/K²）
    · `fully_serial`     —— 全阵列一套（面积最小 · 吞吐最低）
    """
    n = int(n_cols)
    b = _bits(bits)
    rows = [
        _arch_row("fully_parallel", n, b, 1, 1, False, target_sps, **kw),
        _arch_row("tia_shared_k4", n, b, 1, 4, False, target_sps, **kw),
        _arch_row("adc_shared_k4_plain", n, b, 4, 1, False, target_sps, **kw),
        _arch_row("adc_shared_k4_keep", n, b, 4, 1, True, target_sps, **kw),
        _arch_row("fully_serial", n, b, n, n, False, target_sps, **kw),
    ]
    areas = [r["area_um2"] for r in rows]
    fp = LY.array_footprint(n, n)
    fp_um2 = float(fp[0]) * float(fp[1])
    return {
        "n_cols": n, "bits": b, "target_sps": target_sps,
        "rows": rows,
        "area_max_mm2": max(areas) * 1e-6, "area_min_mm2": min(areas) * 1e-6,
        "area_ratio_max_over_min": (max(areas) / min(areas)) if min(areas) > 0 else float("inf"),
        "array_footprint_um": [float(fp[0]), float(fp[1])],
        "array_footprint_um2": fp_um2,
        "readout_over_array_ratio_parallel": (rows[0]["area_um2"] / fp_um2) if fp_um2 > 0 else None,
        "is_oracle": False,
    }


def recommend_architecture(n_cols: int = 64, bits: Optional[int] = None,
                           target_sps: float = 10.0e6, **kw) -> Dict:
    """**按约束推荐**：给定目标每列采样率，在「满足吞吐」的架构里取**面积最小**者。

    🔴 保吞吐共享（`C_tot` 同比降）下的候选把整条吞吐约束**化解为与 K 无关**
    ⇒ 面积最小者 = 共享度**最大**者 ⇒ 上界是**列数 N**（共享度超过列数无意义）
    与 **kT/C 位数上限**（`bits_ceiling` 必须 ≥ 目标位数）。
    """
    b = _bits(bits)
    n = int(n_cols)
    ks = [k for k in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024) if k <= n] or [1]
    cand = [_arch_row("keep_k%d" % k, n, b, int(k), 1, True, target_sps, **kw) for k in ks]
    feasible = [r for r in cand if r["meets_target"] and r["bits_ceiling"] >= float(b)]
    best = min(feasible, key=lambda r: r["area_um2"]) if feasible else None
    k_best = int(best["k_adc"]) if best else None
    return {
        "n_cols": n, "bits": b, "target_sps": float(target_sps),
        "k_searched": ks,
        "best": best, "k_best": k_best,
        "n_adc_units": (int(math.ceil(n / float(k_best))) if k_best else None),
        "c_tot_unit_f": (best["c_total_unit_f"] if best else None),
        "bits_ceiling": (best["bits_ceiling"] if best else None),
        "note": "满足吞吐的候选里取面积最小；🔴 上界 = 列数 N（共享度 > N 无意义）"
                "与 kT/C 位数上限（本口径下远未触及）",
        "is_oracle": False,
    }


def replication_vs_sharing(n_cols: int = 64, bits: Optional[int] = None,
                           ks: Sequence[int] = (1, 2, 4, 8, 16),
                           **kw) -> Dict:
    """🔴 **复制瓶颈级 ⟷ 共享列侧**的对照（接 E17 的 0.289 锚）。

    E17 实测流水线收益仅 **0.289** ⇒ 提吞吐只能**并行复制瓶颈级**：
    复制 `r` 份 ⇒ 吞吐 ×`r`、面积 ×`r`（`C_tot` 不变）⇒ **沿同一条 `A×rate = 常数` 双曲线反向走**。
    而共享 K 倍（不保吞吐）⇒ 面积 ÷K、吞吐 ÷K ⇒ **同一条曲线**。
    """
    n = int(n_cols)
    b = _bits(bits)
    a1 = readout_area_um2(n, 1, 1, b, **kw)["area_um2"]
    r1 = col_throughput_sps(1, b, c_unit_f=kw.get("c_unit_f"))
    shared, repl = [], []
    for k in ks:
        k = int(k)
        shared.append({"k": k, "area_um2": readout_area_um2(n, k, 1, b, **kw)["area_um2"],
                       "per_col_sps": col_throughput_sps(k, b, c_unit_f=kw.get("c_unit_f"))})
        repl.append({"r": k, "area_um2": a1 * k, "per_col_sps": r1 * k})
    prod_s = [p["area_um2"] * (1.0 / p["per_col_sps"]) for p in shared]
    prod_r = [p["area_um2"] * (1.0 / p["per_col_sps"]) for p in repl]
    return {
        "n_cols": n, "bits": b, "k_points": [int(k) for k in ks],
        "shared": shared, "replicated": repl,
        "product_shared_spread": ((max(prod_s) - min(prod_s)) / max(prod_s)
                                  if max(prod_s) > 0 else 0.0),
        "product_replicated_spread": ((max(prod_r) - min(prod_r)) / max(prod_r)
                                      if max(prod_r) > 0 else 0.0),
        "note": "🔴 复制（提吞吐）与共享（省面积）是**同一条 A×rate=常数 双曲线**的两端；"
                "流水线收益仅 0.289 ⇒ 提吞吐必须复制，不能靠流水线",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 自检（12 项）
# ═══════════════════════════════════════════════════════════════════════════
def col_share_self_check(verbose: bool = True) -> bool:
    """模块自检 **12 项**（物理律 + 面积闭式 + 标度律 + 跨模块交叉 + 保护性约束）。"""
    res = True

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        nonlocal res
        if verbose:
            print(("PASS | " if cond else "FAIL | ") + name
                  + (("  :: " + detail) if detail else ""))
        res = res and bool(cond)
        return bool(cond)

    # ① 热噪声物理律：σ ∝ 1/√C（面积 4× ⇒ σ 减半）+ 量级核对
    s1 = thermal_noise_rms_v(1.0e-12)
    s4 = thermal_noise_rms_v(4.0e-12)
    chk("① 🔴 热噪声物理律 σ = √(kT/C)：C ×4 ⇒ σ ÷2（1 pF 时 σ=%.3e V）"
        % s1,
        abs(s4 / s1 - 0.5) < 1e-12
        and abs(s1 - math.sqrt(KB * 300.0 / 1.0e-12)) < 1e-24,
        "σ(1pF)=%.4e ⟷ σ(4pF)=%.4e V" % (s1, s4))

    # ② 位数上限闭式 + 与 σ 自洽
    ct8 = T.cdac_total_cap(8)
    bc = thermal_noise_bits_ceiling(ct8)
    chk("② 位数上限 = log2(V_ref/(k_σ·σ))：8 bit CDAC（C_tot=%.1f pF）⇒ %.2f 位"
        % (ct8 * 1e12, bc),
        abs(bc - math.log2(1.0 / (3.0 * thermal_noise_rms_v(ct8)))) < 1e-12 and bc > 15.0,
        "C_tot=%.4e F ⇒ bits_ceiling=%.4f" % (ct8, bc))

    # ③ 面积闭式：电容面积 = C/ρ（手算核对）
    chk("③ 电容面积闭式 A = C/ρ：C_tot(8)=256 pF、ρ=2 fF/µm² ⇒ 128000 µm²（0.128 mm²）",
        abs(cap_area_um2(2.56e-10) - 128000.0) < 1e-6,
        "A=%.1f µm²" % cap_area_um2(2.56e-10))

    # ④ 转换器双项面积 + 电容支配判定
    ca = converter_area_um2(8)
    chk("④ 转换器面积双项（电容 + 逻辑）：8 bit ⇒ 电容项 %.0f µm² ≫ 逻辑项 %.0f µm²"
        % (ca["cap_area_um2"], ca["logic_area_um2"]),
        abs(ca["area_um2"] - (ca["cap_area_um2"] + ca["logic_area_um2"])) < 1e-9
        and ca["cap_dominated"] is True,
        "比值 %.1f×" % (ca["cap_area_um2"] / ca["logic_area_um2"]))

    # ⑤ 🔴 第一原理：面积-时间乘积与 K 无关（不保吞吐）
    prods = [area_period_product_um2_s(64, k)["product_um2_s"] for k in (1, 2, 4, 8, 16, 32)]
    spread = (max(prods) - min(prods)) / max(prods)
    chk("⑤ 🔴🔴 **第一原理**：面积 × 每列周期 = 常数（与 K 无关）· 跨 5 个 K 的相对散布 = %.2e"
        % spread,
        spread < 1e-12,
        "A×T = %.6e µm²·s（K=1..32）" % prods[0])

    # ⑥ 🔴 第二原理：保吞吐 ⇒ 面积 ∝ 1/K²（电容项严格 −2）；不保吞吐 ⇒ ∝1/K（严格 −1）
    sl = scaling_law_report(4096, 8, ks=(1, 2, 4, 8, 16, 32))
    chk("⑥ 🔴🔴 **第二原理**：不保吞吐 ⇒ 面积**严格 ∝1/K**（%.6f）· 保吞吐**仅电容项严格 ∝1/K²**"
        "（%.6f）· 双项混合斜率 %.6f ∈ (−2, −1)（K* 之后退化为 ∝1/K）"
        % (sl["slope_plain"], sl["slope_keep_cap"], sl["slope_keep_total"]),
        abs(sl["slope_plain"] + 1.0) < 1e-9 and abs(sl["slope_keep_cap"] + 2.0) < 1e-9
        and -2.0 < sl["slope_keep_total"] < -1.0,
        "plain=%.6f · keep_cap=%.6f · keep_total=%.6f"
        % (sl["slope_plain"], sl["slope_keep_cap"], sl["slope_keep_total"]))

    # ⑦ 拐点 K*：电容项 == 逻辑项
    ksr = k_star(8)
    ks_ = ksr["k_star"]
    cap_at = cap_area_um2(T.cdac_total_cap(8) / ks_)
    chk("⑦ 🔴 拐点 K* = C_tot(1)/(ρ·A_logic) = %.1f（该点电容项 == 逻辑项 %.0f µm²）"
        % (ks_, ksr["logic_area_um2"]),
        abs(ks_ - 160.0) < 1e-9
        and abs(cap_at - ksr["logic_area_um2"]) / ksr["logic_area_um2"] < 1e-12,
        "K*=%.4f · cap_area(K*)=%.4f µm²" % (ks_, cap_at))

    # ⑧ 吞吐 ∝ 1/K（且与 E17 `sar_stage_time` 逐位一致）
    sps1 = col_throughput_sps(1, 8)
    sps4 = col_throughput_sps(4, 8)
    t17 = float(T.sar_stage_time(8)["t_s"])
    chk("⑧ 吞吐 ∝ 1/K（K 4× ⇒ 每列速率 ÷4）· 且 `converter_period_s` ⟷ E17 `sar_stage_time` 逐位一致",
        abs(sps1 / sps4 - 4.0) < 1e-12 and converter_period_s(8) == t17,
        "T_conv=%.6f ns ⟷ E17=%.6f ns · rate=%.4f MSa/s"
        % (converter_period_s(8) * 1e9, t17 * 1e9, sps1 / 1e6))

    # ⑨ 跨模块交叉：C_tot ⟷ E14 `_cdac_c_unit` 之和（等价不复制）
    ok9 = all(abs(T.cdac_total_cap(nb, 1.0e-12) - sum(CV._cdac_c_unit(nb, 1.0e-12))) < 1e-24
              for nb in (6, 8, 10))
    chk("⑨ 跨模块交叉：`T.cdac_total_cap` ⟷ E14 `_cdac_c_unit` 之和（等价 · 不复制公式）", ok9,
        "C_tot(8)=%.4e F" % T.cdac_total_cap(8, 1.0e-12))

    # ⑩ 🔴 退化：K=1 ⇒ 保吞吐与不保吞吐**逐位相同**，且 == 每列一套
    r1p = readout_area_um2(16, 1, 1, 8, False)
    r1k = readout_area_um2(16, 1, 1, 8, True)
    unit = converter_area_um2(8)["area_um2"]
    chk("⑩ 🔴 **退化**：K=1 ⇒ 保吞吐 ≡ 不保吞吐（逐位）· 且面积 = N×(A_conv) + N×A_tia + N×A_sw",
        r1p["area_um2"] == r1k["area_um2"]
        and abs(r1p["area_um2"] - (16 * unit + 16 * 400.0 + 16 * 25.0)) < 1e-9,
        "K=1 面积=%.1f µm²（N=16）" % r1p["area_um2"])

    # ⑪ 🔴 诚实结论：kT/C 交叉点远超可达共享度（不硬造精度腿）
    x = ktc_crossing_share(8)
    ks_chk = scaling_law_report(64, 8, ks=(1, 2, 4, 8))["k_star"]
    chk("⑪ 🔴🔴 **诚实结论**：kT/C 跌到 8 位需共享度 K≈%.3e ≫ 可达共享度（列数级）"
        "⇒ **共享的代价是吞吐不是精度**" % x["k_share_crit"],
        x["k_share_crit"] > 1.0e4 and abs(bits_ceiling_of_share(x["k_share_crit"], 8) - 8.0) < 1e-6
        and ks_chk > 0,
        "K_crit=%.4e · K*=%.1f" % (x["k_share_crit"], ks_chk))

    # ⑫ 🔴 保护性约束 + 诚实披露
    chunk3 = [{"name": "a", "t_s": 3e-9}, {"name": "b", "t_s": 7e-9}, {"name": "c", "t_s": 11e-9}]
    chk("⑫ 🔴 保护性：E17 合成律仍成立（Σ=21 ns）· `CONV_PROCESS`/`TIMING_PROCESS` 键值未改 · "
        "披露含「不报 TOPS」「宏模型」「非 PDK」",
        abs(T.serial_sum(chunk3)["t_s"] - 21.0e-9) < 1e-24
        and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
        and CV.CONV_PROCESS["r_unit_ohm"] == 10.0e3
        and T.TIMING_PROCESS["bits"] == 8
        and set(T.TIMING_PROCESS.keys()) == {"bits", "r2r_node_cap_f"}
        and ("不报 TOPS" in COL_SHARE_DISCLOSURE["no_power"])
        and ("宏模型" in COL_SHARE_DISCLOSURE["area_model"])
        and ("非 PDK" in COL_SHARE_DISCLOSURE["area_model"]),
        "披露 %d 键 · K_crit(8bit)=%.3e" % (len(COL_SHARE_DISCLOSURE), x["k_share_crit"]))

    if verbose:
        print("\n" + ("ALL PASS" if res else "SOME FAILED") + " · col_share_self_check")
    return res


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(0 if col_share_self_check(verbose=True) else 1)
