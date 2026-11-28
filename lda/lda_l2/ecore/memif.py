# -*- coding: utf-8 -*-
"""MEM1 · 超宽并行内存接口**闭式核对器**（`memif`）。

═══════════════════════════════════════════════════════════════════════════════
这一层做什么 / 不做什么
───────────────────────────────────────────────────────────────────────────────
做：**公开参数之间的守恒与量级核对**。给定 (总 DQ / 通道数 / 每通道 DQ /
带宽 / 速率)，复算结构式、带宽式、标准退化、反解速率、全片读时间、堆叠高度；
MEM1.1 扩出单位间隔 UI、每通道带宽、全片读时间毫秒与代际比值守恒，并给
`dclaim` 提供带宽↔UI 跨项同源判据（不复制第二套闭式）。
不做的：
  · 不设计 DRAM / 内存控制器 / 混合键合 / 3D 热-应力-良率；
  · 不报任何吞吐、能效、容量"达成"结论（`claimable=False`）；
  · 不碰 E38 数字主链九数（不是 E38 域）；
  · **不 import 任何求解器或产品链**（纯 `math`，C 级自主）。

🔴 三态（本层最重要的口径）
  `PASS`            = 结构 + 带宽自洽，且反解速率落在公开代际窗口；
  `NOT_APPLICABLE`  = 结构/带宽自洽，但反解速率**出窗** ⇒ **口径不适用**（不是算错！）；
  `FAIL`            = 结构或带宽式本身不成立 ⇒ 数据或单位错。
  `NOT_APPLICABLE` **不计入 PASS 率**。二值化会把"950PR 不是那颗 4096DQ 方案"
  这条真结论压成"我们算错了"——这是本层从第一轮探针里抓出来的判据缺陷。

出处（A 级公开来源，照录、未验证、仅作核对输入，不用于计算 LDA 成就值）：
  · ISSCC 2027 议程草案（2026-11-23 IEEE 公布；会议 2027-02-14~18 旧金山）：
    定制 HBM = 64 通道 / 4096 DQ / 5 层 W2W 混合键合 / 集成内存控制器。
  · 华为昇腾社区 Ascend 950PR 规格页：128 GB / 1.6 TB/s（HiBL 1.0）。
  · 华为 2025 全联接大会路线图：950DT 144 GB / 4 TB/s（HiZQ 2.0）。
  · HBM4 标准位宽 2048 DQ；速率 8 GT/s ⇒ 2.048 TB/s（通式退化对照）。

MEM1 预注册判据（G1 冻结：先定判据后写代码；本常量供门禁核对条数）
  J1 结构守恒 DQ_total=N_ch×DQ_per_ch
  J2 带宽守恒 BW_TBps=DQ×R_GTps/8000
  J3 标准退化 HBM4(2048,8GT/s)→2.048 TB/s
  J4 反解速率窗口三态（3.2–16 GT/s）
  J5 全片读时间 cap/bw 闭式
  J6 堆叠高度 n·t_die+(n−1)·t_bond
  J7 物料必含白名单声明
  J8 剥离白名单后无禁用词
  J9 正文数字通式回算（非白名单）
  J10 三态完备（N/A 不得记 PASS）
  J11 manifest ↔ 文件双向完备
  J12 消费者 fail-closed
  J13 claimable/in_blocking=False 显式存在
  J14 门禁自检元判据（合规样板必须过）

MEM1.1 预注册扩展（G1 冻结 2026-11-28，先定判据后写代码）
  K1 UI 闭式 UI_ps=1000/R_GT/s
  K2 每通道带宽双路复算 BW/n_ch ≡ DQ_per_ch×R/8×1000 GB/s
  K3 全片读时间毫秒 read_ms=cap/bw×1000
  K4 代际比值守恒 BW_H/BW_S ≡ (DQ_H/DQ_S)×(R_H/R_S)
  K5 带宽↔UI 跨项同源（不得各自白名单）
  K6 数字正则含整数（`4TB/s` 不得绕过）
  K7 比值 claim 语境敏感（位宽两倍放行 / 带宽两倍判红）
  K8 三态保持：950PR 仍 NOT_APPLICABLE
"""
from __future__ import annotations

import math

__all__ = [
    "PREREG_MEM1", "DQ_CANONICAL", "R_WINDOW_GT", "HBM4_STD", "VERDICTS",
    "PUBLIC_CASES", "PUBLIC_READS",
    "dq_struct", "bw_closed", "r_implied", "read_time_s", "stack_height_um",
    "ui_ps", "bw_per_ch_gbs", "read_ms", "ratio_chain",
    "ui_from_bw", "ui_consistent", "public_derived",
    "bw_is_derivable", "verdict_for", "self_check",
]

# G1 冻结：14 条，条数由门禁机核（先定后写的证据）
PREREG_MEM1 = (
    "J1 结构守恒 DQ_total=N_ch×DQ_per_ch",
    "J2 带宽守恒 BW_TBps=DQ×R_GTps/8000",
    "J3 标准退化 HBM4(2048,8GT/s)→2.048 TB/s",
    "J4 反解速率窗口三态（3.2–16 GT/s）",
    "J5 全片读时间 cap/bw 闭式",
    "J6 堆叠高度 n·t_die+(n−1)·t_bond",
    "J7 物料必含白名单声明",
    "J8 剥离白名单后无禁用词",
    "J9 正文数字通式回算（非白名单）",
    "J10 三态完备（N/A 不得记 PASS）",
    "J11 manifest ↔ 文件双向完备",
    "J12 消费者 fail-closed",
    "J13 claimable/in_blocking=False 显式存在",
    "J14 门禁自检元判据（合规样板必须过）",
    "K1 UI 闭式 UI_ps=1000/R_GT/s",
    "K2 每通道带宽双路复算 BW/n_ch ≡ DQ_per_ch×R/8×1000 GB/s",
    "K3 全片读时间毫秒 read_ms=cap/bw×1000",
    "K4 代际比值守恒 BW_H/BW_S ≡ (DQ_H/DQ_S)×(R_H/R_S)",
    "K5 带宽↔UI 跨项同源（不得各自白名单）",
    "K6 数字正则含整数（`4TB/s` 不得绕过）",
    "K7 比值 claim 语境敏感（位宽两倍放行 / 带宽两倍判红）",
    "K8 三态保持：950PR 仍 NOT_APPLICABLE",
)

DQ_CANONICAL = (2048, 4096)      # 公开代际位宽（HBM4 / 该定制方案）
R_WINDOW_GT = (3.2, 16.0)        # 反解速率窗口（GT/s）——口径适用性边界，非物理定律
HBM4_STD = {"dq": 2048, "r_gtps": 8.0, "bw_tbps": 2.048}
VERDICTS = ("PASS", "FAIL", "NOT_APPLICABLE")
_EPS = 1e-12

# A 级公开工作点（照录 · 只作投影来源 · 非任何实测 / 非 LDA 成就值）
PUBLIC_CASES = (
    ("ISSCC_2027_draft", 4096, 64, 64, 4.000, 7.8125),
    ("HBM4_std", 2048, 32, 64, 2.048, 8.0),
    ("Ascend_950PR", 4096, 64, 64, 1.600, 3.125),
)
# 容量与带宽必须成对来自同一公开产品，不能跨产品相除
PUBLIC_READS = (("950PR", 128.0, 1.600), ("950DT", 144.0, 4.000))


def _pos(name: str, value: float) -> float:
    v = float(value)
    if not v > 0.0:
        raise ValueError("%s 须 > 0" % name)
    return v


def dq_struct(n_ch: int, dq_per_ch: int) -> int:
    """结构守恒：总 DQ = 通道数 × 每通道 DQ（整数恒等式）。"""
    if int(n_ch) != n_ch or int(dq_per_ch) != dq_per_ch:
        raise ValueError("通道数与每通道 DQ 须为整数")
    if n_ch <= 0 or dq_per_ch <= 0:
        raise ValueError("通道数与每通道 DQ 须 > 0")
    return int(n_ch) * int(dq_per_ch)


def bw_closed(dq_total: int, r_gtps: float) -> float:
    """带宽闭式：TB/s = DQ × GT/s ÷ 8（bit→Byte 的量纲桥）。"""
    if int(dq_total) != dq_total or dq_total <= 0:
        raise ValueError("DQ 总数须为正整数")
    return int(dq_total) * _pos("R_GT/s", r_gtps) / 8000.0


def r_implied(bw_tbps: float, dq_total: int) -> float:
    """反解单引脚速率：GT/s = TB/s × 8000 ÷ DQ。"""
    if int(dq_total) != dq_total or dq_total <= 0:
        raise ValueError("DQ 总数须为正整数")
    return _pos("BW_TB/s", bw_tbps) * 8000.0 / int(dq_total)


def read_time_s(cap_gb: float, bw_tbps: float) -> float:
    """全片顺序读一遍的闭式时间：GB ÷ (TB/s) ⇒ 秒。"""
    return _pos("容量 GB", cap_gb) / (_pos("带宽 TB/s", bw_tbps) * 1000.0)


def stack_height_um(n_layer: int, t_die_um: float, t_bond_um: float) -> float:
    """堆叠高度量级：n 层裸片 + (n−1) 个键合界面。

    🔴 参数为**设计示例量级**（非任何实测封装）；本式只做几何恒等式核对，
    不产良率 / 热 / 应力结论。
    """
    if int(n_layer) != n_layer or n_layer < 1:
        raise ValueError("层数须为 ≥1 整数")
    return int(n_layer) * _pos("裸片厚度", t_die_um) + (int(n_layer) - 1) * _pos("界面厚度", t_bond_um)


def ui_ps(r_gtps: float) -> float:
    """单位间隔（1 bit 时长）：UI[ps] = 1000 / R[GT/s]。纯定义式。"""
    return 1000.0 / _pos("R_GT/s", r_gtps)


def bw_per_ch_gbs(bw_tbps: float, n_ch: int) -> float:
    """每通道带宽：TB/s × 1000 / 通道数 ⇒ GB/s。"""
    if int(n_ch) != n_ch or n_ch <= 0:
        raise ValueError("通道数须为正整数")
    return _pos("BW_TB/s", bw_tbps) * 1000.0 / int(n_ch)


def read_ms(cap_gb: float, bw_tbps: float) -> float:
    """全片顺序读一遍的毫秒数：cap/bw × 1000。"""
    return read_time_s(cap_gb, bw_tbps) * 1000.0


def ratio_chain(dq_a: int, dq_b: int, r_a: float, r_b: float) -> float:
    """代际带宽比的定义式：位宽比 × 速率比（不依赖带宽实测）。"""
    return (_pos("DQ_a", dq_a) / _pos("DQ_b", dq_b)
            * _pos("R_a", r_a) / _pos("R_b", r_b))


def ui_from_bw(bw_tbps: float, dq_set=DQ_CANONICAL,
               r_window=R_WINDOW_GT) -> list:
    """给定带宽，返回口径窗口内的 (DQ, R_GT/s, UI_ps) 候选。

    🔴 供 `dclaim` 做带宽↔UI 跨项同源：UI 不能各自过白名单，
    必须由正文带宽隐含的速率反推（K5）。
    """
    bw = _pos("BW_TB/s", bw_tbps)
    out = []
    for dq in dq_set:
        r = r_implied(bw, dq)
        if r_window[0] <= r <= r_window[1]:
            out.append((int(dq), r, ui_ps(r)))
    return out


def ui_consistent(bw_tbps: float, ui_value_ps: float, tol: float = 1e-6) -> bool:
    """正文带宽隐含的速率是否给出一致 UI。"""
    ui = _pos("UI_ps", ui_value_ps)
    return any(abs(ui - c[2]) <= tol for c in ui_from_bw(bw_tbps))


def public_derived() -> dict:
    """公开工作点的派生量投影（文本门禁 ONLY；不是白名单式 TB/s 判决）。

    TB/s 仍走 `bw_is_derivable` 通式（4.096 合法值不能误伤）；这里只给
    GB/s / ps / ms 三类带单位派生值一个**公开来源**集合。
    """
    out = {"gb_s": set(), "ps": set(), "ms": set()}
    for _name, dq, n_ch, dq_per_ch, bw, r in PUBLIC_CASES:
        out["gb_s"].add(round(bw_per_ch_gbs(bw, n_ch), 6))
        out["ps"].add(round(ui_ps(r), 6))
    for _name, cap, bw in PUBLIC_READS:
        out["ms"].add(round(read_ms(cap, bw), 6))
    return out


def bw_is_derivable(bw_tbps: float, dq_set=DQ_CANONICAL,
                    r_window=R_WINDOW_GT) -> bool:
    """通式回算（J9）：给定带宽，是否存在公开 DQ 与窗口内速率使其成立。

    🔴 不用白名单：4.096 TB/s = 4096×8GT/s 是**合法值**，列白名单会误伤
    （§4.3 实证）。通式必须能退化到已实现的特例。
    """
    bw = _pos("BW_TB/s", bw_tbps)
    for dq in dq_set:
        r = r_implied(bw, dq)
        if r_window[0] <= r <= r_window[1] and abs(bw_closed(dq, r) - bw) <= 1e-9:
            return True
    return False


def verdict_for(dq_total: int, n_ch: int, dq_per_ch: int,
                bw_tbps: float, r_gtps: float | None = None) -> dict:
    """公开参数核对：返回三态判决 + 逐项证据（不产任何能力断言）。"""
    r = float(r_gtps) if r_gtps is not None else r_implied(bw_tbps, dq_total)
    j1 = (dq_struct(n_ch, dq_per_ch) == int(dq_total))
    j2 = abs(bw_closed(int(dq_total), r) - float(bw_tbps)) <= _EPS
    j3 = (HBM4_STD["dq"] == 2048 and
          abs(bw_closed(HBM4_STD["dq"], HBM4_STD["r_gtps"]) - HBM4_STD["bw_tbps"]) <= _EPS)
    j4 = R_WINDOW_GT[0] <= r <= R_WINDOW_GT[1]

    if not (j1 and j2):
        verdict = "FAIL"
    elif not j4:
        verdict = "NOT_APPLICABLE"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "dq_total": int(dq_total), "n_ch": int(n_ch), "dq_per_ch": int(dq_per_ch),
        "bw_tbps": float(bw_tbps), "r_implied_GTps": r,
        "j1_struct": bool(j1), "j2_bw": bool(j2),
        "j3_std_degenerate": bool(j3), "j4_window": bool(j4),
        "claimable": False, "in_blocking": False,
        "boundary": "设计期闭式核对·非流片实测；仅验证量级自洽，不构成设计能力或性能结论",
    }


def self_check() -> tuple:
    """模块自检（不 import 产品链；输入全部为字面量）。返回 (bool, detail)。"""
    v_ok = verdict_for(4096, 64, 64, 4.000, 7.8125)
    v_na = verdict_for(4096, 64, 64, 1.600, 3.125)
    v_bad = verdict_for(4096, 4096, 64, 4.000, 7.8125)
    ok = (
        len(PREREG_MEM1) == 22
        and v_ok["verdict"] == "PASS"
        and v_na["verdict"] == "NOT_APPLICABLE"
        and v_bad["verdict"] == "FAIL"
        and abs(bw_closed(2048, 8.0) - 2.048) <= _EPS
        and abs(read_time_s(128, 1.6) - 0.08) <= _EPS
        and abs(stack_height_um(5, 50.0, 1.0) - 254.0) <= _EPS
        and bw_is_derivable(4.096)
        and not bw_is_derivable(999.0)
        # K1/K2/K3/K4 正例
        and abs(ui_ps(7.8125) - 128.0) <= _EPS
        and abs(ui_ps(8.0) - 125.0) <= _EPS
        and abs(bw_per_ch_gbs(4.0, 64) - 62.5) <= _EPS
        and abs(read_ms(128, 1.6) - 80.0) <= _EPS
        and abs(ratio_chain(4096, 2048, 7.8125, 8.0) - 1.953125) <= _EPS
        # K5 跨项同源（4.096+125 是合法特例）
        and ui_consistent(4.0, 128.0)
        and not ui_consistent(4.0, 125.0)
        and ui_consistent(4.096, 125.0)
        # K8 三态保持
        and v_na["verdict"] != "PASS"
    )
    return bool(ok), "PREREG=%d PASS/N-A/FAIL=%s/%s/%s" % (
        len(PREREG_MEM1), v_ok["verdict"], v_na["verdict"], v_bad["verdict"])
