# -*- coding: utf-8 -*-
"""D1 光-量异质集成**只读案例卡**（WebUI · `GET /api/d1_hetero` · 零重计算）。

本卡是"吃狗粮"见证：用 LDA 自己走完蓝图 v2 新域 D1 —— 从**多模换能阵列**（B523）
到**低温共集成热接口**（B524），并把两条**立不住的章程锚**（M1 界面损耗 / M2 封装良率）
连裁决证据一起摆出来（负结果不藏）。

🔴 **零重计算**：顶层只 `import math`（另加 `os`/`typing`），**不 import** numpy / scipy /
`lda_solver` / `lda_harness` / `lda_l2` —— 所有数字由**闭式算术现算**（erf 差 / DMM 比值 /
Debye 四次幂 / 声子通量加权），微秒级、无 DoS 面 ⇒ **免登录、不进 `HEAVY_POST_PATHS`**。
数值一致性由常驻门禁 `run_webui_d1_render_path_smoke` 对
`lda_l2/qnet_hetero_array` 与 `lda_l2/hetero_thermal` **逐值跨源对拍**（不信任本卡自证）。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`；`θ_D / v / n` 是 Al/Si **手册量级设计
示例**，非 foundry 标定、非实测 Kapitza 数据；`LLM 不进判决路径`。

确定性：纯函数，无时钟/随机/文件 IO（`os` 仅用于拼 `span` 里的相对路径字符串）。
"""

from __future__ import annotations

import math
import os
from typing import Dict, List

__all__ = [
    "CASE_ID",
    "HONEST_NOTE",
    "MILESTONES",
    "ANCHORS",
    "NEGATIVE_RESULTS",
    "GAPS",
    "aperture_clip",
    "array_average_clip",
    "dmm_alpha",
    "debye_capacity",
    "kapitza_h",
    "kapitza_R",
    "case_card",
    "run_selfchecks",
]

CASE_ID = "LDA-D1 · 光-量异质集成（换能阵列 → 低温共集成）"

HONEST_NOTE = (
    "本卡是**设计期预算卡**，不是流片实测、不是性能宣称。"
    "θ_D / v / n 为 Al / Si 手册量级的设计示例（非 foundry 标定、非实测 Kapitza 数据）；"
    "模型为 DMM + 声学 Debye + 单支平均声速（未含声子色散、多支权重、界面粗糙度、氧化层、"
    "电子-声子耦合）；只证「闭式 ⇄ 数值」一致与物理链自洽。零商业依赖；LLM 不进判决路径。"
)

MILESTONES = [
    "M0 多模换能阵列 · 平均孔径截断效率 γ̄（锚 B523 · erf 闭式 ⇄ 限窗复合 Simpson · O(h⁴)）",
    "M1 异质界面损耗 · **裁决：不立新锚**（Fresnel 反射面 ≡ 既有垂直入射反射率锚；"
    "吸收面 ≡ 既有 Beer–Lambert 锚；连候选方法都对得上 ⇒ 参数化扩展）",
    "M3 低温共集成热接口 · Kapitza 界面热导 h_K（锚 B524 · DMM+低温 Debye 闭式 ⇄ "
    "内能温度中心差商 · O(ε²)）· **M3 前移承接 M1 腾出的预算**",
    "M2 封装级耦合容差 · **裁决：不立新锚**（良率 = 既有单通道耦合律的统计包装；"
    "MC 跨种子最坏仍达不到余量要求；限窗 Simpson 与 M0 双重同族）",
    "M4 WebUI 面板 · 本卡（零重计算 · 只读 · 净增 0 锚）",
]

ANCHORS = {
    "B523": "多模换能阵列平均孔径截断效率 γ̄（无量纲 · 几何截断 · erf 闭式 ⇄ 限窗 Simpson）",
    "B524": "Kapitza 界面热导 h_K（W/(m²·K) · 声子界面温跳 · DMM+低温 Debye 闭式 ⇄ 内能差商）",
}

#: 两条**负结果**（裁决面 · 与 `lda_harness/d1_registries.py` 同口径摘要）
NEGATIVE_RESULTS = {
    "M1 异质界面损耗": {
        "verdict": "NOT_ANCHORABLE",
        "why": "两条物理量均已被既有锚 100% 覆盖，且候选方法亦相同 ⇒ 参数化扩展/重复计数",
        "evidence": [
            "反射面 ≡ 既有「垂直入射反射率 R0=((n1−n2)/(n1+n2))² 闭式 ⇄ 1D FD Helmholtz」",
            "吸收面 ≡ 既有「Beer–Lambert 闭式指数 ⇄ RK4 空间推进」",
            "同族 Fresnel 已有 13 条（R0/Rs/Rp/Ts/Tp/非偏振/对比度/比值/布儒斯特/振幅/TIR/β/能量守恒）⇒ 族内饱和",
        ],
    },
    "M2 封装级耦合容差": {
        "verdict": "NOT_ANCHORABLE",
        "why": "良率只是既有单通道耦合律的统计重写（派生量），且两条候选路线各有一处硬伤",
        "evidence": [
            "Y=P(η≥η_min) 且 η(d)=exp(−d²/(2w²)) ⇒ 无新物理量（派生量）",
            "MC 跨 8 种子最坏：N=1e5 → 1.615e-03 · N=1e6 → 3.736e-04（相对 4e-4）⇒ 余量不足且不可复现",
            "正态密度限窗 Simpson 收敛链 12.75/15.25/15.82/15.96/16.02（O(h⁴)）虽干净，但与 M0 数值格式同族",
        ],
    },
}

GAPS = [
    "G-D1-1 多模换能阵列 —— 已闭（锚 B523）",
    "G-D1-2 异质界面损耗 —— 物理面由既有 Fresnel 族 + Beer–Lambert 锚**复用覆盖**（裁决净增 0）",
    "G-D1-3 封装级光耦合 —— 判**派生量**（既有耦合律的统计包装），不立新锚",
    "G-D1-4 低温共集成热接口 —— 已闭（锚 B524 · M3 前移）",
]

# ── 设计点（与 B523/B524 默认档同源）────────────────────────────────────────
N_MODES = 8
SPACING_M = 2.0e-6
WAIST_M = 1.5e-6
APERTURE_HALF_M = 6.0e-6

T_K = 4.0
KB = 1.380649e-23
AL = {"name": "Al", "theta_D_K": 428.0, "v_sound_m_s": 5100.0, "n_atom_m3": 6.02e28}
SI = {"name": "Si", "theta_D_K": 645.0, "v_sound_m_s": 6400.0, "n_atom_m3": 5.00e28}

_SPAN = {
    "gate": "run_v2d1_smoke.py",
    "render_path_smoke": "run_webui_d1_render_path_smoke.py",
    "auth": "免登录（只读 GET）",
    "heavy_post": False,
}


def aperture_clip(mode_offset_m: float = 0.0,
                  waist_m: float = WAIST_M,
                  aperture_half_m: float = APERTURE_HALF_M) -> float:
    """单元功率落入有限孔径的占比 `γ_i=½[erf((a−x)/(√2w))+erf((a+x)/(√2w))]`。"""
    w = float(waist_m)
    a = float(aperture_half_m)
    x = float(mode_offset_m)
    return 0.5 * (math.erf((a - x) / (math.sqrt(2.0) * w))
                  + math.erf((a + x) / (math.sqrt(2.0) * w)))


def array_average_clip(n_modes: int = N_MODES,
                       spacing_m: float = SPACING_M,
                       waist_m: float = WAIST_M,
                       aperture_half_m: float = APERTURE_HALF_M) -> float:
    """阵列平均值 `γ̄=(1/N)Σγ_i`，`x_i=(i−(N−1)/2)d`。"""
    n = int(n_modes)
    d = float(spacing_m)
    return sum(aperture_clip((i - (n - 1) / 2.0) * d, waist_m, aperture_half_m)
               for i in range(n)) / n


def dmm_alpha(v1_m_s: float, v2_m_s: float) -> float:
    """DMM 声子透射概率 `α_{1→2}=v₁²/(v₁²+v₂²)`（细致平衡 ∧ 通量 ∝ 1/v²）。"""
    v1 = float(v1_m_s)
    v2 = float(v2_m_s)
    return v1 * v1 / (v1 * v1 + v2 * v2)


def debye_capacity(T: float = T_K, theta_D_K: float = AL["theta_D_K"],
                   n_atom_m3: float = AL["n_atom_m3"]) -> float:
    """低温 Debye 声子热容 `C=(12π⁴/5)n k_B(T/θ)³`（J/(m³·K)）。"""
    return (12.0 * math.pi ** 4 / 5.0) * float(n_atom_m3) * KB * (float(T) / float(theta_D_K)) ** 3


def kapitza_h(T: float = T_K, s1: Dict[str, object] = None,
              s2: Dict[str, object] = None) -> float:
    """Kapitza 界面热导 `h_K=(1/4)[α_{1→2}v₁C₁+α_{2→1}v₂C₂]`（W/(m²·K)）。"""
    a = AL if s1 is None else s1
    b = SI if s2 is None else s2
    a12 = dmm_alpha(a["v_sound_m_s"], b["v_sound_m_s"])
    c1 = debye_capacity(T, a["theta_D_K"], a["n_atom_m3"])
    c2 = debye_capacity(T, b["theta_D_K"], b["n_atom_m3"])
    return 0.25 * (a12 * float(a["v_sound_m_s"]) * c1
                   + (1.0 - a12) * float(b["v_sound_m_s"]) * c2)


def kapitza_R(T: float = T_K) -> float:
    """界面热阻 `R_K=1/h_K`（m²·K/W）。"""
    return 1.0 / kapitza_h(T)


def case_card() -> Dict[str, object]:
    """只读案例卡（全部闭式现算 · 零重计算）。"""
    g = array_average_clip()
    a12 = dmm_alpha(AL["v_sound_m_s"], SI["v_sound_m_s"])
    c1 = debye_capacity(T_K, AL["theta_D_K"], AL["n_atom_m3"])
    c2 = debye_capacity(T_K, SI["theta_D_K"], SI["n_atom_m3"])
    h = kapitza_h(T_K)
    r = 1.0 / h

    segs: List[Dict[str, object]] = [
        {"segment": "阵列孔径", "metric": "平均孔径截断效率 γ̄（无量纲）", "value": g,
         "detail": {"n_modes": N_MODES, "spacing_m": SPACING_M, "waist_m": WAIST_M,
                    "aperture_half_m": APERTURE_HALF_M},
         "verdict": "ACCEPT" if 0.0 < g <= 1.0 else "REVIEW"},
        {"segment": "声子透射", "metric": "DMM 透射概率 α₁→₂（无量纲）", "value": a12,
         "detail": {"v1_m_s": AL["v_sound_m_s"], "v2_m_s": SI["v_sound_m_s"],
                    "alpha_2to1": 1.0 - a12},
         "verdict": "ACCEPT" if 0.0 < a12 < 1.0 else "REVIEW"},
        {"segment": "声子热容", "metric": "低温 Debye 热容 C₁(Al)（J/(m³·K)）", "value": c1,
         "detail": {"T_K": T_K, "theta_D_K": AL["theta_D_K"], "C2_Si": c2},
         "verdict": "ACCEPT" if c1 > 0.0 else "REVIEW"},
        {"segment": "界面热导", "metric": "Kapitza 热导 h_K（W/(m²·K)）", "value": h,
         "detail": {"T_K": T_K, "per_um2_W_K": h * 1e-12, "scaling": "h_K ∝ T³"},
         "verdict": "ACCEPT" if h > 0.0 else "REVIEW"},
        {"segment": "界面热阻", "metric": "界面热阻 R_K（m²·K/W）", "value": r,
         "detail": {"T_K": T_K, "reciprocal_ok": abs(r * h - 1.0) < 1e-15},
         "verdict": "ACCEPT" if r > 0.0 else "REVIEW"},
    ]
    n_pass = sum(1 for s in segs if s["verdict"] == "ACCEPT")

    return {
        "case_id": CASE_ID,
        "verdict": "DESIGN_BUDGET",
        "honest_note": HONEST_NOTE,
        "milestones": MILESTONES,
        "anchors": ANCHORS,
        "negative_results": NEGATIVE_RESULTS,
        "gaps": GAPS,
        "segments": segs,
        "signing": {"n_pass": n_pass, "n_total": len(segs),
                    "verdict": "ACCEPT" if n_pass == len(segs) else "REVIEW"},
        "budget": {"array_clip_gamma": g, "dmm_alpha": a12,
                   "debye_C1_J_m3K": c1, "debye_C2_J_m3K": c2,
                   "kapitza_h_W_m2K": h, "kapitza_R_m2K_W": r,
                   "at_2K_h_W_m2K": kapitza_h(2.0), "at_8K_h_W_m2K": kapitza_h(8.0)},
        "span": dict(_SPAN),
        "gate_checks": 32,   # 实跑 `lda/run_v2d1_smoke.py` 的 PASS 数（渲染门禁 E1 自洽核验）
        "module_selfchecks": 17,  # `hetero_thermal.selfcheck_hetero_thermal()` 项数
        "negative_net_new_anchors": 0,
        "source_paths": {"array": os.path.join("lda_l2", "qnet_hetero_array.py"),
                         "thermal": os.path.join("lda_l2", "hetero_thermal.py")},
    }


def run_selfchecks() -> Dict[str, bool]:
    """卡内自检（闭式不变式 · 供渲染门禁常驻核验）。"""
    ch: Dict[str, bool] = {}
    cc = case_card()
    segs = {s["segment"]: s for s in cc["segments"]}

    ch["five_segments"] = len(cc["segments"]) == 5
    ch["verdict_is_design_budget"] = cc["verdict"] == "DESIGN_BUDGET"
    ch["signing_rule"] = (cc["signing"]["verdict"] == "ACCEPT") == (
        cc["signing"]["n_pass"] == cc["signing"]["n_total"])

    g = segs["阵列孔径"]["value"]
    ch["gamma_in_range"] = 0.5 < g < 1.0
    a = segs["声子透射"]["value"]
    ch["alpha_complementary"] = abs(a + (1.0 - a) - 1.0) < 1e-15
    ch["alpha_in_range"] = 0.0 < a < 1.0
    ch["alpha_equal_media_half"] = abs(dmm_alpha(5000.0, 5000.0) - 0.5) < 1e-15

    c4 = debye_capacity(4.0, AL["theta_D_K"], AL["n_atom_m3"])
    c8 = debye_capacity(8.0, AL["theta_D_K"], AL["n_atom_m3"])
    ch["capacity_cubic_scaling"] = abs(c8 / c4 - 8.0) < 1e-12
    ch["capacity_positive"] = c4 > 0.0

    h4 = kapitza_h(4.0)
    h8 = kapitza_h(8.0)
    ch["kapitza_cubic_scaling"] = abs(h8 / h4 - 8.0) < 1e-12
    ch["resistance_reciprocal"] = abs(kapitza_R(4.0) * h4 - 1.0) < 1e-15
    ch["kapitza_magnitude_band"] = 1e4 < h4 < 1e6

    ch["two_anchors"] = set(cc["anchors"]) == {"B523", "B524"}
    ch["two_negative_results"] = (len(cc["negative_results"]) == 2
                                  and all(v["verdict"] == "NOT_ANCHORABLE"
                                          for v in cc["negative_results"].values()))
    ch["negatives_carry_evidence"] = all(len(v["evidence"]) >= 3
                                         for v in cc["negative_results"].values())
    ch["heavy_post_false"] = cc["span"]["heavy_post"] is False
    return ch


def main() -> int:  # pragma: no cover
    print("D1 案例卡（%s）" % CASE_ID)
    sc = run_selfchecks()
    bad = 0
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        bad += 0 if v else 1
    cc = case_card()
    print("\n  签核：%d/%d ⇒ %s" % (cc["signing"]["n_pass"], cc["signing"]["n_total"],
                                    cc["signing"]["verdict"]))
    for s in cc["segments"]:
        print("    %-9s %-34s %.6e [%s]" % (s["segment"], s["metric"], s["value"], s["verdict"]))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
