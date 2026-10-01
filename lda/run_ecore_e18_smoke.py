# -*- coding: utf-8 -*-
"""E18 列侧共享与架构权衡门禁（D-191 · v0.9.167）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`col_share.col_share_self_check` **12 项**）
B 关键事实 name-first（22 条）：热噪声物理律（第三腿）· 面积闭式（电容/逻辑双项）·
  🔴🔴 **第一原理「面积-时间乘积守恒」** · 🔴🔴 **第二原理「保吞吐 ⇒ 面积 ∝1/K²」**
  （电容项严格 −2 · 双项混合 ∈(−2,−1)）· 拐点 `K*` · 吞吐 ∝1/K · 跨模块交叉
  （E14 `_cdac_c_unit` / E17 `sar_stage_time` / E6 `array_footprint`）· 退化 K=1 ·
  🔴 **诚实结论：kT/C 在可达共享度内不是约束** · 架构族对照 · 推荐架构 ·
  复制 vs 共享 · 保护性约束（E7/E14/E15/E16/E17）· 诚实披露
C 反向可证伪：**6 条突变探针**（忽略共享份数 / 保吞吐忘降 C_tot / kT/C 漏除 C /
  吞吐漏乘 K / 面积-时间积人为 ∝K / 注入「已报 TOPS」）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值
═══════════════════════════════════════════════════════════════════════════
1. **两条第一原理**（B5/B6）是本段的骨架：
   · **面积-时间乘积守恒** —— 共享只沿「等面积-时间双曲线」移动，**不改变乘积**
     ⇒ 要突破它只能「缩 `T_conv`」或「复制瓶颈级（反向）」。
   · **保吞吐 ⇒ 面积 ∝1/K²** —— 缩 `T_conv` 的唯一物理路径是降 `C_tot`
     （`T_conv ∝ C_tot·(bits+1)²` · E17 G-5）⇒ 双项闭式 `N·C_tot/(ρK²) + N·A_logic/K`。
     ⇒ B6 分别断言 **不保吞吐严格 −1**、**保吞吐仅电容项严格 −2**、**双项混合 ∈(−2,−1)**
     —— 三条分开判，否则「第二原理」只是口号。
2. 🔴 **诚实拒绝造腿**（B11）：kT/C 是物理律，但 8 bit / 1 pF / k_σ=3 时位数上限 **16.34**，
   跌到 8 位需共享度 **K≈1.05×10⁵** ⇒ **远超任何合理共享度** ⇒
   本段**不硬造精度腿**，结论是「**共享的真实代价是吞吐不是精度**」。
3. 🔴 **量级事实**（B12/B15）：8 bit CCAC 单列电容面积 **128000 µm²**，
   而 64×64 阵列本体足迹仅 **23302 µm²** ⇒ **读出 = 阵列的 355 倍**（全并行 N=64 时 **8.27 mm²**）。
   ⇒ **在二进制 CDAC 口径下，列侧读出压倒性支配芯片面积** —— 这就是「为什么必须共享」。
4. **保护性约束**（B18/B19）：本段**只读消费** E14/E17，**不改**任何既有默认值；
   `keep_throughput` 默认 **False** ⇒ E15/E16/E17 已发布数字**逐位不变**。
   ⇒ 同 `NmosParams` / `mna.vcvs` / `PERIPHERY_PROCESS` 一族纪律。
5. 🔴 **诚实**（B20/B21）：面积为**宏模型占位**（非 PDK）· **只覆盖静态** · **不做功耗估算**；
   **绝不报 TOPS / TOPS-W / fJ/op**。

🔴 判据纪律（E15–E17 通则）：
  · **B21 用「肯定性禁止短语」**（`已报 TOPS` / `已流片` …）而**不是** `"TOPS" not in blob` ——
    披露里写的是「**绝不报** TOPS/TOPS-W/fJ/op」（**正确的自我否定**）⇒ 用否定词窗口会误判（E12/E13/E17 同族）。
  · **探针只对被测机制敏感**：C5 **追加**「已报 TOPS」而不替换原文 ⇒ B20 仍绿、**只有 B21 红**。
  · **对拍「数学等价但算法不同」的两条路径时容差要容得下 double 舍入**（E17 血案）。
"""

from __future__ import annotations

import math
import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import budget as B              # noqa: E402
from lda_l2.ecore import col_share as C           # noqa: E402
from lda_l2.ecore import converter as CV          # noqa: E402
from lda_l2.ecore import layout as LY             # noqa: E402
from lda_l2.ecore import parasitic as PA          # noqa: E402
from lda_l2.ecore import periphery as PR          # noqa: E402
from lda_l2.ecore import timing as T              # noqa: E402
from lda_l2.ecore import weight_prog as WP        # noqa: E402

_results: list = []

# ── 实测锚（本机默认几何 ‖ 默认工艺 · 8 bit / N=64）─────────────────────
AN_T_CONV_8 = 9.213525600058347e-08      # 一次 SAR 转换周期（= E17 sar_stage_time(8)）
AN_RATE_MSA = 10.8536                    # 每列采样率（K=1 · MSa/s）
AN_CAP_AREA_8 = 128000.0                 # 单列 CDAC 电容面积（µm² @ 256 pF / 2 fF·µm⁻²）
AN_BITS_CEIL_8 = 16.3386                 # kT/C 位数上限（256 pF · k_σ=3）
AN_K_STAR = 160.0                        # 收益拐点
AN_K_CRIT_8 = 1.0479e5                   # kT/C 跌到 8 位所需共享度
AN_FULLPARA_AREA_64 = 8270400.0          # 全并行 N=64（µm²）
AN_ARCH_RATIO_64 = 63.2                  # 全并行 / 全串行（N=64）
AN_READOUT_ARRAY_RATIO = 354.9           # 读出 / 阵列本体（N=64）


def check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, bool(cond), detail))
    return bool(cond)


# ── 复用的绿色判据（突变探针也调同一份 —— 保证「打的判据」就是「守的判据」）──
def _thermal_ok() -> bool:
    """B1 · 热噪声物理律 σ = √(kT/C)：C ×4 ⇒ σ ÷2 + 量级核对（逐位）。"""
    s1 = C.thermal_noise_rms_v(1.0e-12)
    s4 = C.thermal_noise_rms_v(4.0e-12)
    return (abs(s4 / s1 - 0.5) < 1e-12
            and abs(s1 - math.sqrt(C.KB * 300.0 / 1.0e-12)) < 1e-24)


def _bits_ceiling_ok() -> bool:
    """B2 · 位数上限闭式 `log2(V_ref/(k_σ·σ))` + 8 bit 锚值。"""
    bc = C.thermal_noise_bits_ceiling(T.cdac_total_cap(8))
    return (abs(bc - AN_BITS_CEIL_8) / AN_BITS_CEIL_8 < 1e-4
            and abs(bc - math.log2(1.0 / (3.0 * C.thermal_noise_rms_v(
                T.cdac_total_cap(8))))) < 1e-12)


def _cap_area_ok() -> bool:
    """B3 · 电容面积闭式 `A = C/ρ`（手算锚 128000 µm²）。"""
    return (abs(C.cap_area_um2(2.56e-10) - AN_CAP_AREA_8) < 1e-6
            and abs(C.cap_area_um2(1.0e-12) - 500.0) < 1e-9)


def _conv_area_ok() -> bool:
    """B4 · 转换器面积双项（电容 + 逻辑）+ 电容支配判定（160×）。"""
    ca = C.converter_area_um2(8)
    return (abs(ca["cap_area_um2"] - AN_CAP_AREA_8) < 1e-6
            and abs(ca["logic_area_um2"] - 800.0) < 1e-9
            and abs(ca["area_um2"] - (ca["cap_area_um2"] + ca["logic_area_um2"])) < 1e-9
            and ca["cap_dominated"] is True
            and abs(ca["cap_area_um2"] / ca["logic_area_um2"] - 160.0) < 1e-9)


def _area_time_ok() -> bool:
    """B5 · 🔴🔴 **第一原理**：`面积 × 每列周期` 与 K 无关（相对散布 < 1e-12）。"""
    prods = [C.area_period_product_um2_s(64, k)["product_um2_s"]
             for k in (1, 2, 4, 8, 16, 32)]
    spread = (max(prods) - min(prods)) / max(prods)
    return spread < 1e-12 and len(set(prods)) >= 1


def _scaling_ok() -> bool:
    """B6 · 🔴🔴 **第二原理**：不保吞吐严格 ∝1/K（−1）· 保吞吐仅电容项严格 ∝1/K²（−2）
    · 双项混合斜率 ∈ (−2, −1)。"""
    sl = C.scaling_law_report(4096, 8, ks=(1, 2, 4, 8, 16, 32))
    return (abs(sl["slope_plain"] + 1.0) < 1e-9
            and abs(sl["slope_keep_cap"] + 2.0) < 1e-9
            and -2.0 < sl["slope_keep_total"] < -1.0)


def _k_star_ok() -> bool:
    """B7 · 🔴 拐点 `K* = C_tot(1)/(ρ·A_logic)`：该点电容项 == 逻辑项。"""
    ks = C.k_star(8)
    cap_at = C.cap_area_um2(T.cdac_total_cap(8) / ks["k_star"])
    return (abs(ks["k_star"] - AN_K_STAR) < 1e-9
            and abs(cap_at - ks["logic_area_um2"]) / ks["logic_area_um2"] < 1e-12
            and abs(ks["cap_over_logic_at_k1"] - 160.0) < 1e-9)


def _throughput_ok() -> bool:
    """B8 · 吞吐 ∝1/K + `converter_period_s` ⟷ E17 `sar_stage_time` 逐位一致。"""
    return (abs(C.col_throughput_sps(1, 8) / C.col_throughput_sps(4, 8) - 4.0) < 1e-12
            and C.converter_period_s(8) == float(T.sar_stage_time(8)["t_s"])
            and abs(C.converter_period_s(8) - AN_T_CONV_8) < 1e-24
            and abs(C.col_throughput_sps(1, 8) / 1e6 - AN_RATE_MSA) < 1e-3)


def _e14_cross_ok() -> bool:
    """B9 · 跨模块交叉：`T.cdac_total_cap` ⟷ E14 `_cdac_c_unit` 之和（等价 · 不复制）。"""
    return all(abs(T.cdac_total_cap(nb, 1.0e-12) - sum(CV._cdac_c_unit(nb, 1.0e-12))) < 1e-24
               for nb in (6, 8, 10))


def _degenerate_ok() -> bool:
    """B10 · 🔴 退化：K=1 ⇒ 保吞吐 ≡ 不保吞吐（逐位）· 面积 == N×(A_conv+A_tia+A_sw)。"""
    rp = C.readout_area_um2(16, 1, 1, 8, False)
    rk = C.readout_area_um2(16, 1, 1, 8, True)
    unit = C.converter_area_um2(8)["area_um2"]
    return (rp["area_um2"] == rk["area_um2"]
            and abs(rp["area_um2"] - (16.0 * unit + 16.0 * 400.0 + 16.0 * 25.0)) < 1e-9)


def _ktc_honest_ok() -> bool:
    """B11 · 🔴🔴 **诚实结论**：kT/C 跌到 8 位需 K≈1.05e5 ≫ 可达共享度（列数级）。"""
    x = C.ktc_crossing_share(8)
    return (abs(x["k_share_crit"] - AN_K_CRIT_8) / AN_K_CRIT_8 < 1e-3
            and x["k_share_crit"] > 1.0e4
            and abs(C.bits_ceiling_of_share(x["k_share_crit"], 8) - 8.0) < 1e-6)


def _arch_family_ok() -> bool:
    """B12 · 🔴 架构族对照：全并行 vs 全串行面积比 63.2×；面积沿共享度**单调降**。"""
    a = C.architectures(64, 8)
    by = {r["architecture"]: r for r in a["rows"]}
    areas = [by[k]["area_um2"] for k in ("fully_parallel", "tia_shared_k4",
                                         "adc_shared_k4_plain", "adc_shared_k4_keep",
                                         "fully_serial")]
    return (abs(by["fully_parallel"]["area_um2"] - AN_FULLPARA_AREA_64) < 1e-6
            and abs(a["area_ratio_max_over_min"] - AN_ARCH_RATIO_64) / AN_ARCH_RATIO_64 < 0.02
            and areas[0] > areas[2] > areas[3] > areas[4]
            and areas[0] > areas[1] > areas[4])


def _keep_vs_plain_ok() -> bool:
    """B13 · 🔴 **第二原理的兑现**：保吞吐 k4 比不保吞吐 k4 再省 ≈K 倍（≈3.78×）。"""
    a = C.architectures(64, 8)
    by = {r["architecture"]: r for r in a["rows"]}
    plain = by["adc_shared_k4_plain"]["area_um2"]
    keep = by["adc_shared_k4_keep"]["area_um2"]
    ratio = plain / keep
    return (3.0 < ratio < 4.0
            and abs(by["adc_shared_k4_keep"]["per_col_sps"]
                    - by["fully_parallel"]["per_col_sps"]) < 1.0
            and by["adc_shared_k4_plain"]["per_col_sps"]
            < by["fully_parallel"]["per_col_sps"] * 0.3)


def _recommend_ok() -> bool:
    """B14 · 🔴 推荐架构（N=64 / 8 bit / 10 MSa/s）：共享度饱和到列数 ⇒ 面积 30000 µm²
    （全并行 8270400 µm² 的 1/276）。"""
    rc = C.recommend_architecture(64, 8, 10.0e6)
    return (rc["k_best"] == 64 and rc["n_adc_units"] == 1
            and abs(rc["best"]["area_um2"] - 30000.0) < 1e-6
            and rc["best"]["meets_target"] is True
            and rc["bits_ceiling"] >= 8.0
            and abs(rc["c_tot_unit_f"] - 4.0e-12) < 1e-18)


def _readout_vs_array_ok() -> bool:
    """B15 · 🔴 读出面积 ⟷ 阵列本体面积（与 E6 `array_footprint` 交叉核对 · 355×）。"""
    a = C.architectures(64, 8)
    fp = LY.array_footprint(64, 64)
    fp_um2 = float(fp[0]) * float(fp[1])
    return (abs(a["array_footprint_um2"] - fp_um2) < 1e-9
            and a["readout_over_array_ratio_parallel"] > 300.0
            and abs(a["readout_over_array_ratio_parallel"] - AN_READOUT_ARRAY_RATIO) \
            / AN_READOUT_ARRAY_RATIO < 0.02)


def _replication_ok() -> bool:
    """B16 · 🔴 复制 vs 共享：**复制**方向 `A×T` 严格常数（spread = 0）。"""
    rv = C.replication_vs_sharing(64, 8)
    return (rv["product_replicated_spread"] < 1e-12
            and rv["product_shared_spread"] < 0.1
            and len(rv["shared"]) == len(rv["replicated"]))


def _arch_shape_ok() -> bool:
    """B17 · 架构族字段完整 + `meets_target` 语义正确。"""
    a = C.architectures(64, 8, target_sps=10.0e6)
    need = ("architecture", "k_adc", "k_tia", "keep_throughput", "area_um2",
            "area_mm2", "per_col_sps", "converter_period_s", "c_total_unit_f",
            "bits_ceiling", "meets_target")
    rows = a["rows"]
    return (len(rows) == 5 and all(k in rows[0] for k in need)
            and all(r["meets_target"] == (r["per_col_sps"] >= 10.0e6) for r in rows)
            and all(r["area_mm2"] - r["area_um2"] * 1e-6 == 0.0 for r in rows))


def _protect_upstream_ok() -> bool:
    """B18 · 🔴 保护性约束：E7 τ 逐位不变 · `PERIPHERY_PROCESS` 键集不变 · E14/E17 默认未改。"""
    p = PA.array_parasitics(8, 8)
    return (abs(float(p["tau_row_s"]) - 3.1186932940799992e-15) < 1e-27
            and set(PR.PERIPHERY_PROCESS.keys()) == {"a_gain", "r_out_open_ohm", "vfs_v", "vdd_v"}
            and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
            and CV.CONV_PROCESS["r_unit_ohm"] == 10.0e3
            and CV.CONV_PROCESS["rs_ohm"] == 1.0e3
            and T.TIMING_PROCESS["bits"] == 8
            and set(T.TIMING_PROCESS.keys()) == {"bits", "r2r_node_cap_f"})


def _protect_published_ok() -> bool:
    """B19 · 🔴 保护性约束：E15 已发布数字（4.06012% / 4.6223 / N≤12）与 E16 地板逐位不变。"""
    r = B.error_budget_report(8, 8)
    sig = WP.noise_floor_sigma(WP.WEIGHT_PROG_PROCESS["sigma_pulse_rel"],
                               WP.WEIGHT_PROG_PROCESS["alpha_pulse"])
    return (abs(r["worst_pct"] - 4.06012) < 1e-4
            and abs(r["worst_bits"] - 4.6223) < 1e-3
            and abs(sig * 100.0 - 0.70014) < 1e-4
            and B.max_scale_full_chain(5.0)["n_max"] == 12)


def _disclosure_ok() -> bool:
    """B20 · 🔴 诚实（肯定）：披露含「不报 TOPS」「宏模型」「非 PDK」「只覆盖静态」。"""
    blob = " ".join(str(v) for v in C.COL_SHARE_DISCLOSURE.values())
    return ("不报 TOPS" in blob and "宏模型" in blob and "非 PDK" in blob
            and "只覆盖静态" in blob and "不做功耗估算" in blob)


_FALSE_CLAIMS = ("已报 TOPS", "已报能效", "已流片", "已含功耗", "已签核",
                 "实测硅数据", "已含真实版图寄生")


def _no_false_claim_ok() -> bool:
    """B21 · 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含功耗。

    🔴 用「**肯定性禁止短语**」而非 `"TOPS" not in blob` ——
    披露里写的是「**绝不报** TOPS/TOPS-W/fJ/op」（正确的自我否定），
    否定词窗口会误判（E12/E13/E17 血案同族）。
    """
    blob = " ".join(str(v) for v in C.COL_SHARE_DISCLOSURE.values())
    return all(k not in blob for k in _FALSE_CLAIMS)


def _report_shape_ok() -> bool:
    """B22 · 报告结构完整（第一/第二原理 + 拐点 + 架构族 + 推荐 + 复制共享齐备）。"""
    sl = C.scaling_law_report(512, 8)
    rc = C.recommend_architecture(32, 8, 5.0e6)
    rv = C.replication_vs_sharing(32, 8)
    need_sl = ("slope_plain", "slope_keep_cap", "slope_keep_total", "k_star",
               "area_plain_um2", "area_keep_cap_only_um2")
    need_rc = ("k_best", "n_adc_units", "c_tot_unit_f", "bits_ceiling", "best")
    need_rv = ("shared", "replicated", "product_shared_spread", "product_replicated_spread")
    return (all(k in sl for k in need_sl) and all(k in rc for k in need_rc)
            and all(k in rv for k in need_rv)
            and rc["k_best"] is not None and len(rv["shared"]) == len(rv["k_points"]))


def main() -> int:
    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = C.col_share_self_check(verbose=False)
    check("A1 模块自检 12/12 PASS（热噪声物理律 / 面积闭式 / 第一原理守恒 / 第二原理双指数 / "
          "拐点 K* / 跨模块 E14 交叉 / 退化 K=1 / kT/C 诚实结论 / 保护性约束）", ok_a,
          "K*=%.1f · K_crit(8bit)=%.3e" % (C.k_star(8)["k_star"],
                                            C.ktc_crossing_share(8)["k_share_crit"]))

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    check("B1 🔴 **第三腿物理律**：采样热噪声 σ = √(kT/C)（C ×4 ⇒ σ ÷2 · 教科书结果）",
          _thermal_ok(), "σ(1 pF)=%.4e V ⟷ σ(4 pF)=%.4e V"
          % (C.thermal_noise_rms_v(1e-12), C.thermal_noise_rms_v(4e-12)))

    check("B2 位数上限 = log2(V_ref/(k_σ·σ))：8 bit CDAC（C_tot=256 pF · k_σ=3）⇒ %.2f 位"
          % AN_BITS_CEIL_8,
          _bits_ceiling_ok(), "bits_ceiling=%.4f" % C.thermal_noise_bits_ceiling(
              T.cdac_total_cap(8)))

    check("B3 电容面积闭式 A = C/ρ：C_tot(8)=256 pF · ρ=2 fF/µm² ⇒ **128000 µm²（0.128 mm²）**",
          _cap_area_ok(), "A(256 pF)=%.1f µm² · A(1 pF)=%.1f µm²"
          % (C.cap_area_um2(2.56e-10), C.cap_area_um2(1e-12)))

    ca8 = C.converter_area_um2(8)
    check("B4 转换器面积**双项**（电容 + 逻辑）：8 bit ⇒ 电容项 %.0f µm² ≫ 逻辑项 %.0f µm²（%.0f×）"
          % (ca8["cap_area_um2"], ca8["logic_area_um2"],
             ca8["cap_area_um2"] / ca8["logic_area_um2"]),
          _conv_area_ok(), "A_conv=%.1f µm² · cap_dominated=%s"
          % (ca8["area_um2"], ca8["cap_dominated"]))

    _p = C.area_period_product_um2_s(64, 1)["product_um2_s"]
    _sp = (max(C.area_period_product_um2_s(64, k)["product_um2_s"] for k in (1, 2, 4, 8, 16, 32))
           - min(C.area_period_product_um2_s(64, k)["product_um2_s"] for k in (1, 2, 4, 8, 16, 32))) \
        / max(C.area_period_product_um2_s(64, k)["product_um2_s"] for k in (1, 2, 4, 8, 16, 32))
    check("B5 🔴🔴 **第一原理「面积-时间乘积守恒」**：`面积 × 每列周期 = N·A_u·T_conv`"
          "（与 K **无关** · 跨 6 个 K 的相对散布 %.2e）⇒ 共享只沿等面积-时间双曲线移动"
          % _sp,
          _area_time_ok(), "A×T = %.6e µm²·s（K=1..32）" % _p)

    _sl = C.scaling_law_report(4096, 8, ks=(1, 2, 4, 8, 16, 32))
    check("B6 🔴🔴 **第二原理「保吞吐 ⇒ 面积 ∝1/K²」**：不保吞吐**严格 ∝1/K**（%.6f）· "
          "保吞吐**仅电容项严格 ∝1/K²**（%.6f）· 双项混合 %.6f ∈ (−2, −1)（K* 后退化为 ∝1/K）"
          % (_sl["slope_plain"], _sl["slope_keep_cap"], _sl["slope_keep_total"]),
          _scaling_ok(), "plain=%.6f · keep_cap=%.6f · keep_total=%.6f"
          % (_sl["slope_plain"], _sl["slope_keep_cap"], _sl["slope_keep_total"]))

    check("B7 🔴 **收益拐点 K\\* = C_tot(1)/(ρ·A_logic) = %.0f**（该点电容项 == 逻辑项 %.0f µm²）· "
          "K<K\\* 电容支配（1/K² 收益显著）· K>K\\* 逻辑支配（退化 ∝1/K）"
          % (C.k_star(8)["k_star"], C.k_star(8)["logic_area_um2"]),
          _k_star_ok(), "cap/logic @K=1 = %.0f×" % C.k_star(8)["cap_over_logic_at_k1"])

    check("B8 吞吐 ∝1/K（K ×4 ⇒ 每列速率 ÷4）· `converter_period_s` ⟷ E17 `sar_stage_time` "
          "**逐位一致** · 每列 %.4f MSa/s（K=1）" % AN_RATE_MSA,
          _throughput_ok(), "T_conv=%.6f ns ⟷ E17=%.6f ns"
          % (C.converter_period_s(8) * 1e9, float(T.sar_stage_time(8)["t_s"]) * 1e9))

    check("B9 跨模块交叉：`T.cdac_total_cap` ⟷ E14 `_cdac_c_unit` 之和（等价 · **不复制公式**）",
          _e14_cross_ok(), "C_tot(8)=%.4e F" % T.cdac_total_cap(8, 1e-12))

    check("B10 🔴 **退化**：K=1 ⇒ 保吞吐 **逐位等同**不保吞吐 · 且 == N×(A_conv + A_tia + A_sw)",
          _degenerate_ok(), "K=1 面积=%.1f µm²（N=16）" % C.readout_area_um2(16, 1, 1, 8)["area_um2"])

    _x = C.ktc_crossing_share(8)
    check("B11 🔴🔴 **诚实结论（拒绝造腿）**：kT/C 跌到 8 位需共享度 **K≈%.3e** ≫ 可达共享度"
          "（列数级）⇒ **共享的真实代价是「吞吐」不是「精度」**（位数上限 16.34 远高于 8）"
          % _x["k_share_crit"],
          _ktc_honest_ok(), "σ@K_crit=%.4e V · C_tot@K_crit=%.4e F"
          % (_x["sigma_v_at_crit"], _x["c_tot_at_crit_f"]))

    _a = C.architectures(64, 8)
    check("B12 🔴 **架构族对照**（N=64 / 8 bit）：全并行 **%.4f mm²** → 全串行 **%.4f mm²**"
          "（**%.1f×**）· 面积沿共享度单调降"
          % (_a["area_max_mm2"], _a["area_min_mm2"], _a["area_ratio_max_over_min"]),
          _arch_family_ok(), "全并行=%.1f µm² · 全串行=%.1f µm²"
          % (_a["rows"][0]["area_um2"], _a["rows"][4]["area_um2"]))

    _by = {r["architecture"]: r for r in _a["rows"]}
    check("B13 🔴 **第二原理的兑现**：保吞吐 k4（%.1f µm²）比不保吞吐 k4（%.1f µm²）"
          "**再省 %.2f×**（≈K 倍）· 且保吞吐的每列速率 **== 全并行**（吞吐真的保住了）"
          % (_by["adc_shared_k4_keep"]["area_um2"], _by["adc_shared_k4_plain"]["area_um2"],
             _by["adc_shared_k4_plain"]["area_um2"] / _by["adc_shared_k4_keep"]["area_um2"]),
          _keep_vs_plain_ok(), "plain=%.4f MSa/s · keep=%.4f MSa/s（全并行 %.4f）"
          % (_by["adc_shared_k4_plain"]["per_col_sps"] / 1e6,
             _by["adc_shared_k4_keep"]["per_col_sps"] / 1e6,
             _by["fully_parallel"]["per_col_sps"] / 1e6))

    _rc = C.recommend_architecture(64, 8, 10.0e6)
    check("B14 🔴 **推荐架构**（N=64 / 8 bit / 目标 10 MSa/s）：共享度**饱和到列数**（k=64 ⇒ 1 个 ADC · "
          "C_tot=4 pF）⇒ 面积 **%.0f µm²**（全并行 %.0f µm² 的 **1/%.0f**）"
          % (_rc["best"]["area_um2"], AN_FULLPARA_AREA_64,
             AN_FULLPARA_AREA_64 / _rc["best"]["area_um2"]),
          _recommend_ok(), "k_best=%d · n_adc=%d · bits_ceiling=%.3f"
          % (_rc["k_best"], _rc["n_adc_units"], _rc["bits_ceiling"]))

    check("B15 🔴 **量级事实**：全并行读出面积 = 阵列本体 **%.1f 倍**（⟷ E6 `array_footprint(64,64)` "
          "= %.0f µm²）⇒ **在二进制 CDAC 口径下，列侧读出压倒性支配芯片面积**"
          % (_a["readout_over_array_ratio_parallel"], _a["array_footprint_um2"]),
          _readout_vs_array_ok(), "读出/阵列 = %.2f×"
          % _a["readout_over_array_ratio_parallel"])

    _rv = C.replication_vs_sharing(64, 8)
    check("B16 🔴 **复制 vs 共享**（接 E17 的 0.289 锚）：**复制瓶颈级**方向 `A×每列周期` 严格常数"
          "（散布 %.1e）⇒ 提吞吐（复制）与省面积（共享）是**同一条双曲线**的两端"
          % _rv["product_replicated_spread"],
          _replication_ok(), "shared 散布=%.3e · replicated 散布=%.3e"
          % (_rv["product_shared_spread"], _rv["product_replicated_spread"]))

    check("B17 架构族字段完整（11 键）+ `meets_target` 语义正确（== 每列速率 ≥ 目标）",
          _arch_shape_ok(), "5 条架构 × 11 字段")

    check("B18 🔴 **保护性约束**：E7 τ 逐位不变 · `PERIPHERY_PROCESS` **键集不变** · "
          "E14 `CONV_PROCESS` / E17 `TIMING_PROCESS` 值未改（本段**只读消费**）",
          _protect_upstream_ok(), "τ_row(8×8)=%.6e" % float(PA.array_parasitics(8, 8)["tau_row_s"]))

    _b19 = B.error_budget_report(8, 8)
    check("B19 🔴 **保护性约束**：E15 已发布数字（8×8 worst %.5f%% / %.4f 位 / 5%% 上界 N≤%d）"
          "与 E16 写入噪声地板（0.70014%%）**逐位不变**"
          % (_b19["worst_pct"], _b19["worst_bits"], B.max_scale_full_chain(5.0)["n_max"]),
          _protect_published_ok(), "`keep_throughput` 默认 False ⇒ 上游全不受影响")

    check("B20 🔴 诚实（肯定）：披露含「不报 TOPS」+「宏模型」+「非 PDK」+「只覆盖静态」+"
          "「不做功耗估算」",
          _disclosure_ok(), "披露 %d 键全含要求项" % len(C.COL_SHARE_DISCLOSURE))

    check("B21 🔴 诚实（否定）：**未声称** TOPS / 能效 / 已流片 / 已含功耗（🔴 用**肯定性禁止短语**，"
          "不用 `\"TOPS\" not in blob` —— 否则误伤「**绝不报** TOPS」这句正确的自我否定）",
          _no_false_claim_ok(), "禁止短语 %d 条无一命中" % len(_FALSE_CLAIMS))

    check("B22 报告结构完整（标度律 6 键 + 推荐 5 键 + 复制共享 4 键 · `k_best` 非空）",
          _report_shape_ok())

    # ══════════════════════ C 反向可证伪（6 条突变探针）══════════════════════
    _ORIG_readout = C.readout_area_um2
    _ORIG_analytic = C.analytic_area_um2
    _ORIG_product = C.area_period_product_um2_s

    # C1 忽略共享份数（份数恒为 N）⇒ B12/B13 必红
    def _ignore_share(n_cols, k_adc=1, k_tia=1, bits=None, keep_throughput=False, **kw):
        return _ORIG_readout(n_cols, k_adc=1, k_tia=1, bits=bits,
                             keep_throughput=keep_throughput, **kw)

    with mock.patch.object(C, "readout_area_um2", _ignore_share):
        c1 = not (_arch_family_ok() and _keep_vs_plain_ok())
    check("C1 反向：**忽略共享份数**（面积不随 K 降 · 每列恒一套）⇒ B12/B13 必红"
          "（共享的核心收益必须能被判据看出来）", c1, "架构族判据实测变红 = %s" % c1)

    # C2 保吞吐忘降 C_tot（只除份数）⇒ B6（keep_cap 斜率变 −1）/ B13 必红
    def _keep_no_cap(n_cols, k_adc, bits=None, keep_throughput=False,
                     c_unit_f=None, **kw):
        return _ORIG_analytic(n_cols, k_adc, bits, False, c_unit_f, **kw)

    with mock.patch.object(C, "analytic_area_um2", _keep_no_cap):
        c2 = not _scaling_ok()
    check("C2 反向：**保吞吐忘降 C_tot**（只除份数 ⇒ 面积退化为 ∝1/K）⇒ B6 必红"
          "（🔴 第二原理要求「仅电容项严格 ∝1/K²」，退化后斜率变 −1 ⇒ 判据必红）", c2,
          "标度律判据实测变红 = %s" % c2)

    # C3 kT/C 写成 kT（漏除 C）⇒ B1/B2 必红
    with mock.patch.object(C, "thermal_noise_rms_v",
                           lambda c_f, temperature_k=None: math.sqrt(
                               C.KB * (300.0 if temperature_k is None else temperature_k))):
        c3 = not (_thermal_ok() and _bits_ceiling_ok())
    check("C3 反向：热噪声写成 `√(kT)`（**漏除电容 C**）⇒ B1/B2 必红"
          "（物理律 `σ=√(kT/C)` 一旦丢掉 1/√C，C×4 ⇒ σ÷2 立刻不成立）", c3,
          "热噪声判据实测变红 = %s" % c3)

    # C4 吞吐漏乘 K（K 列共享却按单列周期算）⇒ B8 必红
    def _rate_no_k(k_adc=1, bits=None, c_unit_f=None, r_on=None, keep_throughput=False):
        return 1.0 / C.converter_period_s(bits, c_unit_f, r_on)

    with mock.patch.object(C, "col_throughput_sps", _rate_no_k):
        c4 = not _throughput_ok()
    check("C4 反向：吞吐**漏乘共享度 K**（K 列共享却按单列周期算速率）⇒ B8 必红"
          "（「吞吐 ∝1/K」必须能被判出来）", c4, "吞吐判据实测变红 = %s" % c4)

    # C5 披露**追加**「已报 TOPS」（而非替换）⇒ **只有 B21 红**，B20 仍绿（探针特异性）
    _bad_disc = dict(C.COL_SHARE_DISCLOSURE)
    _bad_disc["no_power"] = _bad_disc["no_power"] + " 已报 TOPS：8.3 TOPS"
    with mock.patch.object(C, "COL_SHARE_DISCLOSURE", _bad_disc):
        c5_false = not _no_false_claim_ok()
        c5_still_true = _disclosure_ok()
    check("C5 反向：披露**追加**「已报 TOPS」（而非替换原文）⇒ B21 必红 · **且 B20 仍绿**"
          "（🔴 探针只对被测机制敏感）", c5_false and c5_still_true,
          "B21 变红 = %s · B20 仍绿 = %s" % (c5_false, c5_still_true))

    # C6 面积-时间积人为 ∝K（伪造「放大共享度能增大乘积」）⇒ B5 必红
    def _prod_times_k(n_cols, k_adc=1, bits=None, keep_throughput=False, **kw):
        r = dict(_ORIG_product(n_cols, k_adc, bits, keep_throughput, **kw))
        r["product_um2_s"] = r["product_um2_s"] * float(max(1, int(k_adc)))
        return r

    with mock.patch.object(C, "area_period_product_um2_s", _prod_times_k):
        c6 = not _area_time_ok()
    check("C6 反向：面积-时间积人为 **∝K**（伪造「共享能增大乘积」）⇒ B5 必红"
          "（守恒律必须能被破坏出来）", c6, "守恒判据实测变红 = %s" % c6)

    # 还原重跑（无残留漂移）
    check("C7 还原完整性：全部探针退出后，A1 自检 + B5/B6/B8/B12/B13/B21 复跑仍全绿",
          C.col_share_self_check(verbose=False) and _area_time_ok() and _scaling_ok()
          and _throughput_ok() and _arch_family_ok() and _keep_vs_plain_ok()
          and _no_false_claim_ok())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e18_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        if not ok:
            print("FAIL | " + name + (("  :: " + detail) if detail else ""))
        elif detail:
            print("PASS | " + name + "  :: " + detail)
    print()
    print("=" * 74)
    print("E18 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
