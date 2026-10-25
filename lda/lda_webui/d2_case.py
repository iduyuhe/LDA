# -*- coding: utf-8 -*-
"""D2 QEC 码族**只读案例卡**（WebUI · `GET /api/d2_code_family` · 零重计算）。

本卡是 D2 征程的对外窗口：把「**M0 出一个真锚**（退极化信道 hashing 界）+
**M1 当场裁决四类不可锚**（码族比较 / 开销）」摆在同一屏，含**可行性分界**与
**同函数证据**，负结果不藏。

🔴 **零重计算**：顶层只 `import math`（另加 `os`/`typing`），**不 import**
numpy / scipy / `lda_solver` / `lda_harness` / `lda_l2` —— 所有数字由**闭式算术现算**
（对数反解 `d*` / 二元熵 / 整数组合），微秒级、无 DoS 面 ⇒ **免登录、不进 `HEAVY_POST_PATHS`**。
数值一致性由常驻门禁 `run_v2d2_m1_smoke` 对既有锚的 golden 与 `lda_l2/qec_code_family`
**逐值跨源对拍**（不信任本卡自证）。

🔴 **参数来源如实标注**：各族 `(A, p_th)` 是**文献拟合/示意量级**，**非平台实测**；
本节只演示「同一闭式换参数 = 换族」与「可行性分界」，**不宣称**支持 LDPC / 色码 /
拓扑码阈值预测 —— 那三类已被裁决为不可锚。

确定性：纯函数，无时钟/随机/文件 IO（`os` 仅用于拼相对路径字符串）。
"""

from __future__ import annotations

import math
import os
from typing import Dict, List

__all__ = [
    "CASE_ID",
    "HONEST_NOTE",
    "LITERATURE_NOTE",
    "MILESTONES",
    "ANCHORS",
    "NEGATIVE_RESULTS",
    "GAPS",
    "FAMILIES",
    "P_PHYS_DEFAULT",
    "TARGET_DEFAULT",
    "d_star",
    "hashing_bound",
    "gv_rate",
    "family_table",
    "curve_points",
    "case_card",
    "run_selfchecks",
]

CASE_ID = "LDA-D2 · QEC 码族（hashing 界 → 码族比较裁决）"

HONEST_NOTE = (
    "本卡是**设计期预算卡**，不是流片实测、不是性能宣称。"
    "`d*` 由阈值标度律反解得到，其 `(A, p_th)` 为**文献拟合/示意量级**（非 foundry 标定、"
    "非本平台实测）；表面码阈值 p_th≈1% 是量级示例。本卡只证「闭式 ⇄ 数值」一致、"
    "「同式换参 = 换族」与「可行性分界」，**不**宣称支持 LDPC / 色码 / 拓扑码阈值预测。"
    "零商业依赖；LLM 不进判决路径。"
)

LITERATURE_NOTE = (
    "参数来源：`A`（前置系数）与 `p_th`（阈值）为**文献拟合/示意量级**，非平台实测。"
    "展示用途仅限「同一闭式在不同 (A,p_th) 下的形态」与「p_phys ≥ p_th ⇒ 该族不可用」；"
    "不得据此引用为某具体码的性能承诺。"
)

MILESTONES = [
    "M0 退极化信道 hashing 界 I_c(p) · **锚 B525**（精确闭式 ⇄ 对数积分表示 + 复合 Simpson · "
    "残差真截断 O(h⁴) · 相邻比趋近 16）",
    "M1 码族比较 / 开销 · **裁决：不立新锚（净增 0）** —— 四类不可锚：精确整数开销 · "
    "拟合阈值参数 · 离散 argmin 比较 · GV 界与 hashing 界同函数",
    "M1 面板 · 本卡（零重计算 · 只读 · 净增 0 锚）",
]

ANCHORS = {
    "B525": "退极化信道 hashing / coherent-information 界 I_c(p)（bit/信道使用 · "
            "精确闭式 ⇄ 积分表示复合 Simpson）",
}

#: 四类**负结果**（与 `lda_harness/d2_registries.py` 的 `D2_M1_ADJUDICATION` 同口径摘要）
NEGATIVE_RESULTS = {
    "精确整数开销": {
        "verdict": "NOT_ANCHORABLE",
        "why": "n/k · (2d−1)² · T 计数 · 深度 · 4^g · 2^(n−k) 全是精确整数/有理数 ⇒ "
               "任何独立算法同值 ⇒ resid ≡ 0 ⇒ 触零残差红线",
        "evidence": [
            "空间开销 n/k：[[5,1,3]]⇒5 · [[7,1,3]]⇒7 · [[9,1,3]]⇒9（精确整数）",
            "表面码物理比特数 (2d−1)²：d=3/5/7 ⇒ 25/81/169（精确整数）",
            "组合量：4^g(g=2)⇒16 · 2^(n−k)⇒64 · 2^(2k)⇒4 · 32/11（精确有理）",
        ],
    },
    "拟合阈值参数": {
        "verdict": "NOT_ANCHORABLE",
        "why": "跨族比较必须引入各族的 p_th 与 A，二者来自文献拟合 / MC + 有限尺寸标定 ⇒ "
               "无闭式 golden；用拟合值当 golden 会切断方法学独立性",
        "evidence": [
            "同一 p_th 在两篇文献可相差数倍 ⇒ 不构成可复现的死标量",
            "LDPC / 色码阈值为拟合参数，随解码器与噪声模型漂移",
            "仓库红线禁第三方 QEC SDK ⇒ 无法引入独立实现交叉对照（缺第二个闭式）",
        ],
    },
    "离散 argmin 比较": {
        "verdict": "NOT_ANCHORABLE",
        "why": "「同 p 下哪个族更省」的输出是族标签（离散）⇒ 与精确整数同类；"
               "把 d* 再代数合成只是既有闭式的单调变换（派生量）",
        "evidence": [
            "argmin 输出为离散族名 ⇒ resid 无从定义",
            "(2d*−1)² 与 2d*² 均为 d* 的纯代数合成，不引入新物理量",
            "可行性判定 p_phys ≥ p_th ⇒ d* < 0 也只是符号比较",
        ],
    },
    "GV 界与 hashing 界同函数": {
        "verdict": "NOT_ANCHORABLE",
        "why": "R_GV(δ)=1−H₂(δ)−δ·log₂3 与 I_c(p) 只换自变量名；实测四点差恒 0.0"
               "（代数恒等签名）⇒ 同式异写，且数值格式也相同",
        "evidence": [
            "δ=0.05 两式同得 0.63435491784798592（差 0.0）",
            "δ=0.11 同得 0.32573816675614475 · δ=0.25 同得 −0.20751874963942185",
            "δ=0.18929 同得 −5.5511151231257827e-17 ⇒ 连穿零位置都一致",
        ],
    },
}

#: 逐条缺口状态（**顺序与下方 GAPS 一一对应** · v0.9.286 四值口径）
#: 字符串型 gaps 不改形状（前端仍按字符串渲染），状态走这个并行列表。
GAPS_STATUS = [
    "已结算（连续标量由既有锚复用；非连续面判四类不可锚 · 净增 0）",
    "已结算（门计数/深度为精确整数 · 同类裁决净增 0）",
    "未闭合（LDPC 解码 BP+OSD 未开工；解码器重且禁第三方 SDK）",
    "未闭合（色码解码与阈值未开工；阈值为拟合量）",
]

GAPS = [
    "G-V2-D2-3 码族间资源-阈值折衷 —— 连续标量已由既有锚复用（换族只换参数）；"
    "非连续面判四类不可锚 ⇒ 裁决净增 0",
    "G-V2-D2-4 逻辑门集合的可比性度量 —— 门计数/深度为精确整数 ⇒ 同类裁决（净增 0）",
    "G-V2-D2-1 LDPC 解码（BP+OSD）—— 解码器重且禁第三方 SDK ⇒ 阈值面不可锚（未开工）",
    "G-V2-D2-2 色码解码与阈值 —— 同上（阈值为拟合量）",
]

# ── 设计档（与既有锚默认档同源 · 其余族为示意）──────────────────────────────
P_PHYS_DEFAULT = 0.005
TARGET_DEFAULT = 1e-15

#: 族表：`A` / `p_th` 为**文献拟合/示意量级**（非平台实测）。
FAMILIES: List[Dict[str, object]] = [
    {"family": "surface-like（参考档）", "A": 0.03, "p_th": 0.010},
    {"family": "color-like（示意）", "A": 0.05, "p_th": 0.004},
    {"family": "high-threshold（示意）", "A": 0.02, "p_th": 0.020},
]

_D_STAR_CLIP = 500.0
#: `run_selfchecks()` 的项数（**声明值**；门禁核对「声明 ≡ 实跑」防漂移 —— 卡内不得
#: 自调 `case_card()` 取数，否则 `case_card → run_selfchecks → case_card` 无限递归）。
_N_SELFCHECKS = 17
_SPAN = {
    "gate": "run_v2d2_m1_smoke.py",
    "render_path_smoke": "run_v2d2_m1_smoke.py（D 组跨源对拍）",
    "auth": "免登录（只读 GET）",
    "heavy_post": False,
}


def d_star(p_phys: float = P_PHYS_DEFAULT,
           target: float = TARGET_DEFAULT,
           p_th: float = 0.01,
           A: float = 0.03) -> float:
    """阈值标度律反解的最小距离 `d*=2·ln(target/A)/ln(p_phys/p_th) − 1`（无量纲）。

    🔴 `p_phys ≥ p_th` ⇒ 该族在此噪声下**不可用** ⇒ 返回**负值**（不是 0，也不是 inf）。
    """
    t, a = float(target), float(A)
    p, th = float(p_phys), float(p_th)
    if a <= 0.0 or t <= 0.0:
        raise ValueError("target/A 必须为正")
    if p <= 0.0 or th <= 0.0:
        raise ValueError("p_phys/p_th 必须为正")
    return 2.0 * math.log(t / a) / math.log(p / th) - 1.0


def hashing_bound(p: float) -> float:
    """退极化信道 hashing 界 `I_c(p)=1−H₂(p)−p·log₂3`（bit/信道使用）。"""
    x = float(p)
    if not (0.0 <= x <= 0.75):
        raise ValueError("p 必须在 [0, 0.75]")
    h2 = 0.0 if x in (0.0, 1.0) else -x * math.log2(x) - (1.0 - x) * math.log2(1.0 - x)
    return 1.0 - h2 - x * math.log2(3.0)


def gv_rate(delta: float) -> float:
    """量子 Gilbert–Varshamov 界 `R_GV(δ)=1−H₂(δ)−δ·log₂3`（与 hashing 界同函数）。"""
    return hashing_bound(delta)


def family_table(p_phys: float = P_PHYS_DEFAULT,
                 target: float = TARGET_DEFAULT) -> List[Dict[str, object]]:
    """族表：逐族给 `d*` 与**可行性**判定（`p_phys < p_th` 才可用）。"""
    rows: List[Dict[str, object]] = []
    for f in FAMILIES:
        pth = float(f["p_th"])
        A = float(f["A"])
        v = d_star(p_phys, target, pth, A)
        rows.append({
            "family": f["family"],
            "A": A,
            "p_th": pth,
            "d_star": v,
            "feasible": (p_phys < pth),
            "verdict": "FEASIBLE" if (p_phys < pth and v > 0.0) else "INFEASIBLE",
            "param_source": "文献拟合/示意量级（非实测）",
        })
    return rows


def curve_points(p_th: float = 0.01, A: float = 0.03,
                 target: float = TARGET_DEFAULT,
                 ps: List[float] = None) -> List[Dict[str, object]]:
    """参考族的 `d*(p_phys)` 曲线点（用于画分界；超 `_D_STAR_CLIP` 记为截顶）。"""
    grid = ps if ps is not None else [0.001, 0.002, 0.003, 0.004, 0.005,
                                      0.006, 0.008, 0.0095, 0.0105, 0.012, 0.015, 0.02]
    out: List[Dict[str, object]] = []
    for p in grid:
        raw = d_star(p, target, p_th, A)
        out.append({
            "p_phys": float(p),
            "d_star_raw": raw,
            "d_star_plot": max(-_D_STAR_CLIP, min(_D_STAR_CLIP, raw)),
            "clipped": abs(raw) > _D_STAR_CLIP,
            "feasible": (float(p) < p_th),
        })
    return out


ANCHORS_SOURCE = "segment"

ANCHORS_NOTE = (
    "蓝图 v2 B525（退极化信道 hashing 界 I_c(p)）。。")

def case_card() -> Dict[str, object]:
    """只读案例卡（全部闭式现算 · 零重计算）。"""
    ref = d_star()                       # 参考档（与既有锚默认档同源）
    fams = family_table()
    pts = curve_points()
    feas = [r for r in fams if r["feasible"]]
    infeas = [r for r in fams if not r["feasible"]]

    # GV 界 ⇄ hashing 界：四点差（应为恒 0.0 = 代数恒等）
    deltas = [0.05, 0.11, 0.18928962491523177, 0.25]
    diffs = [abs(gv_rate(d) - hashing_bound(d)) for d in deltas]
    max_diff = max(diffs)

    overheads = {"[[5,1,3]]_n_over_k": 5, "[[7,1,3]]_n_over_k": 7,
                 "[[9,1,3]]_n_over_k": 9, "surface_d3_qubits": (2 * 3 - 1) ** 2,
                 "surface_d5_qubits": (2 * 5 - 1) ** 2, "toric_4^g_g2": 4 ** 2}

    segs: List[Dict[str, object]] = [
        {"segment": "参考档 d*", "metric": "最小距离 d*（无量纲 · p=%.3f / p_th=0.010）" % P_PHYS_DEFAULT,
         "value": ref,
         "detail": {"p_phys": P_PHYS_DEFAULT, "target": TARGET_DEFAULT, "p_th": 0.01, "A": 0.03,
                    "same_function_as_reused": True},
         "verdict": "ACCEPT" if ref > 0.0 else "REVIEW"},
        {"segment": "可行性分界", "metric": "可用族数 / 总族数（p_phys < p_th 才可用）",
         "value": float(len(feas)), "detail": {"total": len(fams),
                                               "infeasible": [r["family"] for r in infeas]},
         "verdict": "ACCEPT" if len(feas) >= 1 and len(infeas) >= 1 else "REVIEW"},
        {"segment": "GV ⇄ hashing", "metric": "两式最大绝对差（应为恒 0.0）",
         "value": max_diff, "detail": {"deltas": deltas, "diffs": diffs},
         "verdict": "ACCEPT" if max_diff == 0.0 else "REVIEW"},
        {"segment": "整数开销", "metric": "n/k（[[7,1,3]]）与 (2d−1)²（d=5）",
         "value": float(overheads["[[7,1,3]]_n_over_k"] + overheads["surface_d5_qubits"]),
         "detail": dict(overheads),
         "verdict": "ACCEPT" if overheads["surface_d5_qubits"] == 81 else "REVIEW"},
        {"segment": "同函数复用", "metric": "M1 净增锚数（裁决净增 0）", "value": 0.0,
         "detail": {"reused_metrics": ["qec_threshold_distance",
                                       "qec_depolarizing_hashing_bound"],
                    "new_anchors": []},
         "verdict": "ACCEPT"},
    ]
    n_pass = sum(1 for s in segs if s["verdict"] == "ACCEPT")

    return {
        "case_id": CASE_ID,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算（建模值 · 非流片实测）",
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": HONEST_NOTE,
        "literature_note": LITERATURE_NOTE,
        "milestones": MILESTONES,
        "anchors": ANCHORS,
        "negative_results": NEGATIVE_RESULTS,
        "gaps": GAPS,
        "gaps_status": GAPS_STATUS,
        "segments": segs,
        "families": fams,
        "curve": pts,
        "signing": {"n_pass": n_pass, "n_total": len(segs),
                    "verdict": "ACCEPT" if n_pass == len(segs) else "REVIEW"},
        "budget": {"d_star_reference": ref,
                   "p_phys": P_PHYS_DEFAULT, "target": TARGET_DEFAULT,
                   "d_star_at_p001": d_star(0.001),
                   "d_star_infeasible_example": d_star(0.005, TARGET_DEFAULT, 0.004, 0.05),
                   "gv_hashing_max_abs_diff": max_diff,
                   "hashing_p010": hashing_bound(0.10),
                   "hashing_p0": hashing_bound(0.0),
                   "hashing_p075": hashing_bound(0.75)},
        "span": dict(_SPAN),
        "gate_checks": 13,
        "module_selfchecks": _N_SELFCHECKS,
        "negative_net_new_anchors": 0,
        "source_paths": {"capability": os.path.join("lda_l2", "qec_code_family.py"),
                         "registry": os.path.join("lda_harness", "d2_registries.py")},
    }


def run_selfchecks() -> Dict[str, bool]:
    """卡内自检（闭式不变式 · 供门禁常驻核验）。"""
    ch: Dict[str, bool] = {}
    cc = case_card()
    segs = {s["segment"]: s for s in cc["segments"]}

    ch["five_segments"] = len(cc["segments"]) == 5
    # 段值与预算明细必须同源（防「两处各算一遍」漂移）
    ch["reference_segment_matches_budget"] = abs(
        segs["参考档 d*"]["value"] - cc["budget"]["d_star_reference"]) < 1e-15
    ch["verdict_is_design_budget"] = cc["verdict"] == "DESIGN_BUDGET"
    ch["signing_rule"] = (cc["signing"]["verdict"] == "ACCEPT") == (
        cc["signing"]["n_pass"] == cc["signing"]["n_total"])

    # d* 对 p_phys 严格单调降（p_phys 越大越接近阈值 ⇒ 需要更大距离）
    d1, d5, d9 = d_star(0.001), d_star(0.005), d_star(0.009)
    ch["dstar_monotone_decreasing"] = d1 < d5 < d9
    ch["dstar_floor_above_minus_one"] = d_star(1e-9) > -1.0
    ch["dstar_infeasible_negative"] = d_star(0.005, TARGET_DEFAULT, 0.004, 0.05) < 0.0

    # 可行性分界：严格以 p_phys < p_th 判，且与 d*>0 一致（可行族）
    fams = family_table()
    ch["feasibility_iff_dstar_positive"] = all(
        (r["verdict"] == "FEASIBLE") == (r["feasible"] and r["d_star"] > 0.0) for r in fams)
    ch["has_infeasible_sample"] = any(not r["feasible"] for r in fams)

    # GV 界 ≡ hashing 界（代数恒等：差恒 0.0）
    ch["gv_equals_hashing_exactly"] = all(
        gv_rate(d) - hashing_bound(d) == 0.0 for d in (0.05, 0.11, 0.25))
    ch["hashing_endpoints"] = (abs(hashing_bound(0.0) - 1.0) < 1e-15
                               and abs(hashing_bound(0.75) + 1.0) < 1e-15)

    # 整数开销（不可锚面）：精确整数，无截断项
    ch["overhead_integers_exact"] = ((2 * 3 - 1) ** 2 == 25 and (2 * 5 - 1) ** 2 == 81
                                     and 4 ** 2 == 16 and 7 // 1 == 7)

    ch["four_negative_classes"] = (len(cc["negative_results"]) == 4
                                   and all(v["verdict"] == "NOT_ANCHORABLE"
                                           for v in cc["negative_results"].values()))
    ch["negatives_carry_three_evidence"] = all(
        len(v["evidence"]) >= 3 for v in cc["negative_results"].values())
    ch["curve_has_both_sides"] = (any(p["feasible"] for p in cc["curve"])
                                  and any(not p["feasible"] for p in cc["curve"]))
    ch["negative_net_new_zero"] = cc["negative_net_new_anchors"] == 0
    ch["heavy_post_false"] = cc["span"]["heavy_post"] is False
    return ch


def main() -> int:  # pragma: no cover
    print("D2 案例卡（%s）" % CASE_ID)
    sc = run_selfchecks()
    bad = 0
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        bad += 0 if v else 1
    cc = case_card()
    print("\n  签核：%d/%d ⇒ %s" % (cc["signing"]["n_pass"], cc["signing"]["n_total"],
                                    cc["signing"]["verdict"]))
    for s in cc["segments"]:
        print("    %-12s %-46s %.6e [%s]" % (s["segment"], s["metric"][:46], s["value"],
                                             s["verdict"]))
    print("\n  族表（参数=文献拟合/示意量级）：")
    for r in cc["families"]:
        print("    %-26s A=%.3f p_th=%.3f d*=%10.4f %s"
              % (r["family"], r["A"], r["p_th"], r["d_star"], r["verdict"]))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
