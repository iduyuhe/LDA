"""D-73 热光/电光可调 WDM（Track D 系统级纵深 · M7 第一件）。

把 D-42/D-57 静态 WDM 升级为**运行时可重构**：在每条 add-drop 环上叠加
热光相位 shifter（heater），通过热光效应实时移动每环谐振波长，实现"可调
信道分配"——从"设计即固定"走向"运行时可重构"。

物理模型（诚实标注）：
- 静态 WDM：复用 design_wdm_with_coupler（D-42/D-57，FDTD 标定 κ_c 驱动 gap，
  多环级联解复用），每环谐振对齐一个信道 λ_i。
- 热光调谐（物理定律锚，非拟合）：
    环谐振条件 2πR·n_eff = m·λ  →  Δλ/λ = Δn_eff/n_eff
    Δn_eff = (dn/dT)·ΔT          （硅热光系数 dn/dT ≈ 1.86e-4 /K）
    ΔT = R_th · P                （R_th = 加热器热阻 K/mW）
    ⇒ Δλ_nm = λ_nm · (dn/dT) · R_th · P / n_eff   （闭式，死标量）
  dn/dT 与 n_eff 是材料/波导常数（非拟合），故 Δλ(P) 是**物理定律预测**——
  ORACLE 比对"真实 Si 加热器调谐斜率区间 [0.02, 0.5] nm/mW"（器件物理已知范围）。
- 信道重分配：给定目标信道集 T_i，所需功率
    P_i = Δλ_i · n_eff / (λ_i · (dn/dT) · R_th)，  Δλ_i = T_i − λ_i
  验收：① |P_i| ≤ P_max（加热功率预算）；② |Δλ_i| ≤ FSR_i/2（不跨入相邻 FSR，
  无混叠）；③ 全系统最大可达位移 P_max·S_min ≥ FSR_min/2（证明整 FSR 内可重构）。
- 纯光子域器件（Ring + heater + Waveguide），无跨物理域声称。
  LLM 不进判决路径：是否 PASS 由死标量比对决定。
"""
from typing import Any, Dict, List, Optional

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

# 物理常数（材料/波导，非拟合）
DN_DT_SI = 1.86e-4          # 硅热光系数 (/K) @1550nm，文献公认值
N_EFF_TUNE = 2.4            # SOI 条形波导有效折射率（谐振位移灵敏度用）
R_TH_DEFAULT = 1.0          # 加热器热阻 (K/mW)，典型集成 TiN 加热器优化值
P_MAX_DEFAULT = 50.0        # 单环加热功率预算 (mW)
# 真实 Si 热光加热器调谐斜率区间（nm/mW），器件物理已知范围（ORACLE 比对窗）
S_MIN_REAL = 0.02
S_MAX_REAL = 0.50

_DEF_CHANNELS = [1550.0, 1553.0, 1556.0]


def _tuning_slope_nm_per_mw(channel_nm: float, dn_dT: float,
                            R_th: float, n_eff: float) -> float:
    """调谐斜率 S = dλ/dP = λ·(dn/dT)·R_th/n_eff（nm/mW），闭式物理定律。"""
    return channel_nm * dn_dT * R_th / n_eff


def design_tunable_wdm(channels_nm: Optional[List[float]] = None,
                       target_channels_nm: Optional[List[float]] = None,
                       dn_dT: float = DN_DT_SI, n_eff: float = N_EFF_TUNE,
                       R_th: float = R_TH_DEFAULT, P_max: float = P_MAX_DEFAULT,
                       grid_calibrated: bool = True,
                       m: int = 170, n_g: float = 4.2) -> Dict[str, Any]:
    """热光可调 WDM 设计：静态 WDM + 每环热光调谐 + 信道重分配验收。

    target_channels_nm=None → 默认演示目标 = 设计信道各 +Δ（Δ=min(FSR)/2·0.6，
    安全落在 FSR/2 内，演示全局热调谐）。返回静态 WDM 摘要 + 热模型 + 每环
    调谐计划 + 死标量验收。
    """
    if channels_nm is None:
        channels_nm = list(_DEF_CHANNELS)
    n_ch = len(channels_nm)
    if n_ch < 2:
        return {"ok": False, "error": "至少 2 个 WDM 信道"}

    from lda_agent.wdm_coupler import design_wdm_with_coupler  # noqa: E402
    from lda_agent.wdm_system import fsr_nm  # noqa: E402

    # 1) 静态 WDM 设计（复用 D-42/D-57，FDTD 标定驱动）
    wdm = design_wdm_with_coupler(channels_nm, grid_calibrated=grid_calibrated,
                                  n_g=n_g, m=m)
    if not wdm.get("ok") or not wdm["acceptance"]["passed"]:
        return {"ok": False,
                "error": f"静态 WDM 设计未过: {wdm.get('verdict', '')[:120]}",
                "static_wdm": {k: wdm.get(k) for k in
                               ("chosen_gap_um", "chosen_k_ring",
                                "acceptance", "verdict")}}
    sub = wdm["wdm"]
    Rs = sub.get("ring_radii_um")
    if not Rs or len(Rs) != n_ch:
        return {"ok": False, "error": "无法提取每环半径 R，无法叠加热调谐层"}

    # 2) 每环 FSR + 调谐斜率
    per_ring: List[Dict[str, Any]] = []
    for i, (ch, R) in enumerate(zip(channels_nm, Rs)):
        fsr = fsr_nm(ch, R, n_g)
        S = _tuning_slope_nm_per_mw(ch, dn_dT, R_th, n_eff)
        per_ring.append({"index": i, "channel_nm": ch, "R_um": round(R, 4),
                          "FSR_nm": round(fsr, 3),
                          "S_nm_per_mW": round(S, 4)})

    # 3) 信道重分配：默认目标 = 设计信道各 +Δ（演示全局热调谐）
    fsr_min = min(p["FSR_nm"] for p in per_ring)
    if target_channels_nm is None:
        delta = min(fsr_min / 2.0 * 0.6, 3.0)  # 安全落在 FSR/2 内
        target_channels_nm = [round(ch + delta, 3) for ch in channels_nm]
    elif len(target_channels_nm) != n_ch:
        return {"ok": False, "error": "目标信道数须与信道数等长"}

    plan: List[Dict[str, Any]] = []
    for i, (ch, t) in enumerate(zip(channels_nm, target_channels_nm)):
        S = per_ring[i]["S_nm_per_mW"]
        fsr = per_ring[i]["FSR_nm"]
        dlam = t - ch
        # P_i = Δλ · n_eff / (λ · (dn/dT) · R_th)
        P = dlam * n_eff / (ch * dn_dT * R_th) if (ch * dn_dT * R_th) != 0 else 0.0
        within_budget = abs(P) <= P_max + 1e-9
        no_alias = abs(dlam) <= fsr / 2.0 + 1e-9
        plan.append({
            "index": i, "channel_nm": ch, "target_nm": t,
            "delta_nm": round(dlam, 3), "P_mW": round(P, 3),
            "FSR_nm": fsr, "S_nm_per_mW": S,
            "within_budget": bool(within_budget),
            "no_fsr_alias": bool(no_alias),
        })

    # 4) 死标量验收
    S_vals = [p["S_nm_per_mW"] for p in per_ring]
    slopes_ok = all(S_MIN_REAL <= s <= S_MAX_REAL for s in S_vals)
    realloc_ok = all(p["within_budget"] and p["no_fsr_alias"] for p in plan)
    # 整 FSR 内可重构：最大可达位移 ≥ FSR_min/2
    S_min = min(S_vals)
    max_shift = P_max * S_min
    full_fsr_reconfig = max_shift >= fsr_min / 2.0 - 1e-9

    checks = [
        {"name": "静态 WDM 验收（D-42/D-57，IL≤3dB/XT≥15dB/DRC）",
         "ok": True,
         "detail": f"gap={wdm['chosen_gap_um']}µm k_ring={wdm['chosen_k_ring']}；"
                   f"IL≤{max(sub['metrics']['il_drop_db']):.2f}dB "
                   f"XT≥{min(sub['metrics']['xt_min_db']):.1f}dB"},
        {"name": "热调谐斜率 S 在真实器件区间",
         "ok": bool(slopes_ok),
         "detail": f"S∈[{min(S_vals):.3f},{max(S_vals):.3f}] nm/mW "
                   f"（ORACLE [{S_MIN_REAL},{S_MAX_REAL}] nm/mW，Si 加热器已知范围）"},
        {"name": "信道重分配功率预算（|P|≤P_max）",
         "ok": bool(all(p["within_budget"] for p in plan)),
         "detail": "；".join(f"λ{p['channel_nm']}→{p['target_nm']}nm: "
                             f"P={p['P_mW']}mW" for p in plan)},
        {"name": "无 FSR 混叠（|Δλ|≤FSR/2）",
         "ok": bool(all(p["no_fsr_alias"] for p in plan)),
         "detail": "；".join(f"Δλ={p['delta_nm']}nm ≤ FSR/2={p['FSR_nm']/2:.2f}nm"
                             for p in plan)},
        {"name": "整 FSR 内可重构（P_max·S_min≥FSR_min/2）",
         "ok": bool(full_fsr_reconfig),
         "detail": f"最大可达位移 {max_shift:.2f}nm ≥ FSR_min/2="
                   f"{fsr_min/2:.2f}nm"},
    ]
    accepted = all(c["ok"] for c in checks)

    verdict = (f"热光可调 WDM（{n_ch} 信道）PASS：静态 WDM 验收通过 + 每环热光调谐"
               f"斜率 S∈[{min(S_vals):.3f},{max(S_vals):.3f}] nm/mW（物理定律锚，"
               f"命中真实 Si 加热器区间）+ 目标信道 "
               f"{[round(t,1) for t in target_channels_nm]}nm 重分配功率预算内、"
               f"无 FSR 混叠，整 FSR 内可重构。"
               if accepted else
               "热光可调 WDM 未全过：" +
               "；".join(c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"{n_ch}-信道热光可调 WDM（运行时可重构）",
        "channels_nm": channels_nm,
        "target_channels_nm": target_channels_nm,
        "thermal_model": {
            "dn_dT_per_K": dn_dT, "n_eff_tune": n_eff, "R_th_K_per_mW": R_th,
            "P_max_mW": P_max,
            "formula": "Δλ_nm = λ_nm·(dn/dT)·R_th·P/n_eff",
            "anchor": "物理定律（硅热光系数 dn/dT + 谐振位移 Δλ/λ=Δn/n_eff，非拟合）",
        },
        "static_wdm": {
            "gap_um": wdm["chosen_gap_um"], "k_ring": wdm["chosen_k_ring"],
            "Rs_um": [round(r, 4) for r in Rs],
            "il_drop_db": sub["metrics"]["il_drop_db"],
            "xt_min_db": sub["metrics"]["xt_min_db"],
        },
        "per_ring": per_ring,
        "reallocation_plan": plan,
        "max_reachable_shift_nm": round(max_shift, 3),
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "静态 WDM 复用 D-42/D-57（FDTD 标定 κ_c 驱动 gap 的多环级联解复用）；"
                "热调谐为每环叠加加热器（热光效应），Δλ/λ=(dn/dT)·R_th·P/n_eff 是"
                "闭式物理定律（dn/dT=1.86e-4/K 材料常数，n_eff=2.4 波导有效折射率），"
                "与静态半径用 n_g=4.2 的约定解耦（位移物理只依赖于 n_eff）。"
                "诚实边界：①未建模环间热串扰（默认加热器热隔离）；②仅热光调谐"
                "（未实现电光载流子注入型，后者速度更快但损耗更高）；③静态重配置"
                "（信道再分配）非高速调制（不声称调制带宽）；④FSR 仍由静态环半径"
                "决定，调谐仅在其内重分配。LLM 不进判决路径。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="D-73 热光可调 WDM")
    ap.add_argument("--channels", default=",".join(map(str, _DEF_CHANNELS)))
    ap.add_argument("--target", default=None,
                    help="目标信道集（nm，逗号分隔），缺省演示全局热调谐")
    ap.add_argument("--R_th", type=float, default=R_TH_DEFAULT)
    ap.add_argument("--n_eff", type=float, default=N_EFF_TUNE)
    ap.add_argument("--P_max", type=float, default=P_MAX_DEFAULT)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ch = [float(x) for x in a.channels.split(",") if x.strip()]
    tgt = ([float(x) for x in a.target.split(",") if x.strip()]
           if a.target else None)
    r = design_tunable_wdm(ch, target_channels_nm=tgt, R_th=a.R_th,
                           n_eff=a.n_eff, P_max=a.P_max)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:4000])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n[written] {a.out}")
    return 0 if r.get("ok") and r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
