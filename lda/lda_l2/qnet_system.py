"""LDA J5 量子网络与接口征程 · **M4 总装 + 签核链**（G-QNET-5 收官件）。

把 J5 六段能力组装成「一条端到端量子链路」的**设计期签核报告**：

  ① 信道层      `qnet_channel`      —— 公里级光纤损耗 / 偏振退相干 / 时延
  ② 纠缠分发    `qnet_distribution` —— 分发后两体纠缠保真度（B519）
  ③ 纠缠源      `qnet_source`       —— HOM 干涉可见度（B520）
  ④ 量子中继    `qnet_repeater`     —— 期望交换产出数 / 吞吐率（B521）
  ⑤ 微波-光换能 `qnet_transducer`   —— 换能效率 η（B522）
  ⑥ 经典接口    `qnet_classical`    —— 时钟抖动 → 保真损失（**M4 净增 0**）

🔴 **签核口径**：逐段给 `PASS / REVIEW` **确定性判据**（阈值写死在 `_GATES`），
   不引入 LLM 判断；报告只做「设计期签核」，**不作制造/流片/性能宣称**。
🔴 零量子 SDK；LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from lda_l2 import qnet_channel as CH
from lda_l2 import qnet_classical as CL
from lda_l2 import qnet_distribution as DS
from lda_l2 import qnet_repeater as RP
from lda_l2 import qnet_source as SR
from lda_l2 import qnet_transducer as TR

QNET_SYSTEM_CALIBER = "qnet_end_to_end_signing__design_stage_only"

#: 链路设计示例默认档（100 km 城际链路 · 20 段中继）
DEFAULT_LINK_LENGTH_M = 1.0e5
DEFAULT_SEGMENTS = 20

#: 🔴 逐段签核门限（**写死的确定性判据** · 不进 LLM）
_GATES: Dict[str, Dict[str, Any]] = {
    "channel":  {"key": "transmission", "op": "ge", "thr": 1.0e-3},
    "dist":     {"key": "fidelity", "op": "ge", "thr": 0.5},
    "source":   {"key": "visibility", "op": "ge", "thr": 0.1},
    "repeater": {"key": "storage_window_factor", "op": "ge", "thr": 0.3},
    "transducer": {"key": "eta_band", "op": "ge", "thr": 1.0e-2},
    "classical": {"key": "infidelity", "op": "le", "thr": 1.0e-1},
}


def _gate(seg: str, value: float) -> str:
    g = _GATES[seg]
    ok = (value >= g["thr"]) if g["op"] == "ge" else (value <= g["thr"])
    return "PASS" if ok else "REVIEW"


# ══════════════════════════════════════════════════════════════════════
# ① 逐段汇总
# ══════════════════════════════════════════════════════════════════════
def link_segments(length_m: float = DEFAULT_LINK_LENGTH_M,
                  segments: int = DEFAULT_SEGMENTS) -> List[Dict[str, Any]]:
    """六段端到端链路的设计期汇总（每段给标量 + 签核结论）。"""
    if length_m <= 0.0:
        raise ValueError("链路长度须 > 0")
    if segments < 1:
        raise ValueError("中继段数须 ≥ 1")
    seg_len = length_m / segments

    t_link = CH.transmission(length_m)
    fid = CH.link_fidelity(length_m)
    vis = SR.hom_visibility()
    rp_r = RP.repeater_report(length_m)
    tr_r = TR.transducer_report()
    cl_r = CL.jitter_report()

    rows = [
        {"segment": "channel", "metric": "transmission", "value": float(t_link),
         "detail": {"length_m": float(length_m), "seg_len_m": float(seg_len),
                    "l_att_m": float(CH.attenuation_length_m())}},
        {"segment": "dist", "metric": "fidelity", "value": float(fid),
         "detail": {"werner_p": float(DS.werner_parameter(length_m)),
                    "chsh": float(DS.chsh_parameter(fid))}},
        {"segment": "source", "metric": "visibility", "value": float(vis),
         "detail": {"overlap_sq": float(SR.overlap_magnitude_sq())}},
        {"segment": "repeater", "metric": "storage_window_factor",
         "value": float(rp_r["storage_window_factor"]),
         "detail": {"yield": float(rp_r["yield"]), "rate_s1": float(rp_r["rate_s1"]),
                   "gain": float(rp_r["gain"])}},
        {"segment": "transducer", "metric": "eta_band",
         "value": float(tr_r["band_overlap"]),
         "detail": {"peak_efficiency": float(tr_r["peak_efficiency"]),
                    "efficiency": float(tr_r["efficiency"])}},
        {"segment": "classical", "metric": "infidelity",
         "value": float(cl_r["infidelity"]),
         "detail": {"phase_variance_rad2": float(cl_r["phase_variance_rad2"]),
                    "fidelity": float(cl_r["fidelity"])}},
    ]
    for r in rows:
        r["verdict"] = _gate(r["segment"], r["value"])
        r["gate"] = dict(_GATES[r["segment"]])
    return rows


def signing_chain(length_m: float = DEFAULT_LINK_LENGTH_M,
                  segments: int = DEFAULT_SEGMENTS) -> Dict[str, Any]:
    """端到端签核链：逐段 PASS/REVIEW ⇒ 总签核（**全 PASS 才 ACCEPT**）。"""
    rows = link_segments(length_m, segments)
    n_pass = sum(1 for r in rows if r["verdict"] == "PASS")
    return {
        "caliber": QNET_SYSTEM_CALIBER,
        "link_length_m": float(length_m),
        "segments": int(segments),
        "seg_len_m": float(length_m / segments),
        "rows": rows,
        "n_pass": n_pass,
        "n_total": len(rows),
        "verdict": "ACCEPT" if n_pass == len(rows) else "REVIEW",
    }


def end_to_end_fidelity(length_m: float = DEFAULT_LINK_LENGTH_M,
                        segments: int = DEFAULT_SEGMENTS) -> Dict[str, float]:
    """端到端**设计期**保真度预算（直接链路 vs 中继链路 · 逐段乘法近似）。

    🔴 **近似口径**（诚实边界）：逐段保真度按**独立乘性衰减**近似
       （`F_tot = Π F_i`），未建模**纠缠交换递推 / 纯化 / 纠错**；
       ⇒ `relay_chain_fidelity = F_seg^N` **只是朴素上界**，
       **不可**据它断言「中继保真 > 直连保真」（中继的真实优势在**速率**，见 M2
       `repeater_gain = 53.70×`）。本函数仅作**设计期量级判据**。
    """
    if segments < 1 or length_m <= 0.0:
        raise ValueError("参数非法")
    seg_len = length_m / segments
    f_direct = CH.link_fidelity(length_m)
    f_seg = CH.link_fidelity(seg_len)
    f_relay = f_seg ** segments            # 中继链：每段独立
    f_source = SR.overlap_magnitude_sq()
    f_tr = TR.transducer_report()["efficiency"]
    f_cl = CL.jitter_limited_fidelity()
    return {
        "direct_fidelity": float(f_direct),
        "relay_segment_fidelity": float(f_seg),
        "relay_chain_fidelity": float(f_relay),
        "source_factor": float(f_source),
        "transducer_factor": float(f_tr),
        "classical_factor": float(f_cl),
        "end_to_end_direct": float(f_direct * f_source * f_tr * f_cl),
        "end_to_end_relay": float(f_relay * f_source * f_tr * f_cl),
    }


def full_qnet_report(length_m: float = DEFAULT_LINK_LENGTH_M,
                     segments: int = DEFAULT_SEGMENTS) -> Dict[str, Any]:
    """J5 全征程总装报告（六段签核 + 端到端预算 + 锚号清单）。"""
    chain = signing_chain(length_m, segments)
    budget = end_to_end_fidelity(length_m, segments)
    return {
        "caliber": QNET_SYSTEM_CALIBER,
        "milestones": ["M0 分发", "M1 源", "M2 中继", "M3 换能", "M4 经典接口"],
        "anchors": {"B519": "分发后两体纠缠保真度", "B520": "HOM 干涉可见度",
                    "B521": "中继站期望交换产出数", "B522": "微波-光换能效率 η"},
        "net_new_anchors_M4": 0,
        "net_new_reason": "经典接口三证据否决（见 qnet_classical.negative_evidence）",
        "signing": chain,
        "budget": budget,
        "verdict": chain["verdict"],
    }


# ══════════════════════════════════════════════════════════════════════
# ② 自检
# ══════════════════════════════════════════════════════════════════════
def selfcheck_qnet_system() -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    rows = link_segments()
    chain = signing_chain()
    budget = end_to_end_fidelity()

    checks["six_segments"] = (len(rows) == 6
                              and [r["segment"] for r in rows] ==
                              ["channel", "dist", "source", "repeater", "transducer", "classical"])
    checks["verdicts_valid"] = all(r["verdict"] in ("PASS", "REVIEW") for r in rows)
    checks["chain_consistent"] = chain["n_pass"] == sum(
        1 for r in rows if r["verdict"] == "PASS")
    checks["verdict_rule"] = (chain["verdict"] == "ACCEPT") == (chain["n_pass"] == chain["n_total"])

    # 逐段与各能力层真源逐位对拍（防「case 卡与真源不同源」· J4 血案）
    checks["matches_channel"] = abs(
        rows[0]["value"] - CH.transmission(DEFAULT_LINK_LENGTH_M)) < 1e-15
    checks["matches_dist"] = abs(rows[1]["value"] - CH.link_fidelity()) < 1e-15
    checks["matches_source"] = abs(rows[2]["value"] - SR.hom_visibility()) < 1e-15
    checks["matches_repeater"] = abs(
        rows[3]["value"] - RP.repeater_report()["storage_window_factor"]) < 1e-15
    checks["matches_transducer"] = abs(
        rows[4]["value"] - TR.transducer_report()["band_overlap"]) < 1e-15
    checks["matches_classical"] = abs(rows[5]["value"] - CL.jitter_infidelity()) < 1e-15

    # 中继的**物理优势在速率**（M2 真源：`repeater_gain = 53.70×`），不在「逐段乘法」的保真度
    # 🔴 逐段乘积 `F_seg^N` 只是**朴素上界**（不含纠缠交换递推/纯化/纠错），
    #    故**不可**用它断言「中继保真 > 直连保真」——那是错误近似。
    checks["repeater_rate_gain_beats_direct"] = bool(
        RP.repeater_report()["gain"] > 1.0)
    checks["budget_keys_complete"] = set(budget) == {
        "direct_fidelity", "relay_segment_fidelity", "relay_chain_fidelity",
        "source_factor", "transducer_factor", "classical_factor",
        "end_to_end_direct", "end_to_end_relay"}

    # 报告自洽
    rep = full_qnet_report()
    checks["report_m4_zero_net_new"] = (rep["net_new_anchors_M4"] == 0
                                        and "negative_evidence" in rep["net_new_reason"])
    checks["report_four_anchors"] = set(rep["anchors"]) == {"B519", "B520", "B521", "B522"}

    # 反向：非法参数抛 ValueError（先校验）
    def _raises(fn):
        try:
            fn(); return False
        except ValueError:
            return True

    checks["reverse_bad_length_raises"] = _raises(lambda: link_segments(length_m=0.0))
    checks["reverse_bad_segments_raises"] = _raises(lambda: signing_chain(segments=0))
    checks["reverse_bad_budget_raises"] = _raises(lambda: end_to_end_fidelity(segments=0))
    return checks


def main() -> int:  # pragma: no cover
    print("J5 M4 总装 + 签核链（六段 · 设计期签核）")
    sc = selfcheck_qnet_system()
    bad = 0
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        if not v:
            bad += 1
    rep = full_qnet_report()
    print("\n  签核：%d/%d PASS ⇒ %s" % (rep["signing"]["n_pass"],
                                        rep["signing"]["n_total"], rep["verdict"]))
    for r in rep["signing"]["rows"]:
        print("    %-11s %-22s %.6e  [%s]" % (r["segment"], r["metric"], r["value"], r["verdict"]))
    b = rep["budget"]
    print("\n  端到端（直连）= %.6e | （中继）= %.6e" % (b["end_to_end_direct"], b["end_to_end_relay"]))
    print("  锚：%s" % ", ".join(rep["anchors"]))
    print("  M4 净增锚 = %d（%s）" % (rep["net_new_anchors_M4"], rep["net_new_reason"]))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
