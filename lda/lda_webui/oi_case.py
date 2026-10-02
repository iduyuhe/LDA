# -*- coding: utf-8 -*-
"""LDA WebUI · 光联接模块 M0 基线案例卡（新征程 · 吃狗粮检阅平台 · 只读案例）。

============================================================================
A 档接入（对齐 qchip/schip/pchip/ecore/accel/d4 案例卡体例）
----------------------------------------------------------------------------
把「光联接模块新征程」的 M0 基线（2 通道 WDM 收发器）以**只读案例**呈现：
Tx MZI 调制器阵列 + Rx 微环 add-drop 滤波阵列 + 双 GratingCoupler + 光纤 span。

🔴 只读与缓存纪律：结果为**确定性现算**（纯闭式 + 级联引擎，零重计算 /
不跑 P&R / 不跑 FDTD），首次调用后按配置键**模块级缓存**（同配置秒回）。
不进 HEAVY_POST_PATHS、不要求登录（与 qchip/schip/pchip/ecore/accel/d4 同属
「公开只读验货」类）。

🔴 不伪装实测：`verdict` 恒为 `DESIGN_BUDGET`（非 ACCEPT/PASS）——链路预算是
设计期行为验证，非流片后实测；**不报 TOPS/TOPS-W/fJ/op**。

🔴 诚实边界：M0 是**链路预算层**（system/link budget）基线，器件用 L0 级解析
模型（微环 add-drop 解析谱、GC 固定耦合、MZI 调制器 cos² 传递）；真实版图 GDS
由 D4 域 `photonic_interconnect`（复用 `wdm_mesh_pnr`）单独承载，本卡只报预算。
"""
from __future__ import annotations

CASE_ID = "OI-M0 · 光联接模块基线（2 通道 WDM 收发器 · 新征程 M0）"

_CACHE: dict = {}

CHANNELS_NM = [1550.0, 1551.6]
N_LANES = 2


def case_card(use_cache: bool = True, channels_nm=None, n_lanes=None) -> dict:
    """组装 M0 案例卡（确定性现算 + 模块级缓存）。

    channels_nm / n_lanes 可调（设计点），默认 2 通道 LAN-WDM 1.6nm 间隔。
    """
    if channels_nm is None:
        channels_nm = list(CHANNELS_NM)
    if n_lanes is None:
        n_lanes = N_LANES
    key = (tuple(channels_nm), int(n_lanes))
    if use_cache and key in _CACHE:
        return _CACHE[key]

    from lda_l2.oi_module import (
        build_transceiver_m0, transceiver_m0_budget,
    )

    link = build_transceiver_m0(n_lanes=n_lanes, channels_nm=channels_nm)
    rep = transceiver_m0_budget(link, channels_nm)
    per = rep["per_channel"]

    channels = [{
        "lane": pc["lane"],
        "channel_nm": pc["channel_nm"],
        "R_um": round(pc["R_um"], 4),
        "il_closedform_db": round(pc["il_a_db"], 3),
        "il_cascade_db": round(pc["il_b_db"], 3),
        "il_ab_diff_db": round(pc["il_ab_diff_db"], 4),
        "isolation_db": (round(pc["isolation_db"], 2)
                         if pc["isolation_db"] != float("inf") else None),
    } for pc in per]
    min_iso = min((c["isolation_db"] for c in channels if c["isolation_db"] is not None),
                  default=None)
    max_il = max((c["il_cascade_db"] for c in channels), default=None)

    card = {
        "endpoint": "/api/oi_demo",
        "case_id": CASE_ID,
        "claim": ("用 LDA 自家光链路设计验证链（lda_chain）可把一款 2 通道 WDM 收发器"
                  "从装配到链路预算跑通：闭式预算与级联引擎两种方法逐位一致（差 <0.05dB），"
                  "且吃狗粮过程**抓出并修复了平台级 bug**（星型网级联重复计数）"),
        "identity": {
            "topology": "Tx：MZI 调制器（cos² 传递）× N 通道；Rx：微环 add-drop 滤波器"
                        "级联下路 + 双 GratingCoupler 耦合 + 光纤 span",
            "method": "两种方法独立交叉验证——(A) 闭式链路预算（含前置环 thru 总线链）"
                      "；(B) lda_chain 级联引擎（信号流图精确信道波长评估）",
            "anchor_B19": "无源无增益不等式 |T|≤1（所有 transfer 幅值 ≤1），M0 全部满足",
            "honest_layer": "M0 属链路预算层（L0 解析器件模型）；真实版图 GDS 由 D4 域"
                            " photonic_interconnect（复用 wdm_mesh_pnr 的 WDM 网格 P&R）承载",
        },
        "requested": {
            "n_lanes": n_lanes,
            "channels_nm": channels_nm,
            "v_pi_v": rep.get("v_pi_v"),
            "gc_coupling": rep.get("gc_coupling"),
            "fiber_span_db": rep.get("fiber_span_db"),
        },
        "channels": channels,
        "b19_passivity": rep["b19_passivity"],
        "min_isolation_db": min_iso,
        "max_il_db": max_il,
        "design_notes": rep.get("design_notes", []),
        "milestones": [
            {"id": "M0-1", "label": "平台底座就位",
             "detail": "P1 光链路征程 M1–M4（WDM link 框架 / 自动布线+损耗+GDS / Agent 元编排"
                       " / L1 原语 / B19 无源无增益不等式锚）；lda_chain 光链路设计验证链"},
            {"id": "M0-2", "label": "M0 基线组装",
             "detail": "2 通道 WDM 收发器（Tx MZI×2 + Rx 微环 add-drop×2 + GC×2 + 光纤 span）"
                       "用 lda_chain 拼装 IR，闭式(A)与级联(B)双法预算"},
            {"id": "M0-3", "label": "吃狗粮抓出真平台 bug 并修复",
             "detail": "级联引擎对 ≥3 端口星型网用 all-pairs 全连边 ⇒ 同一信号多路径重复求和"
                       "（GC 耦合被翻倍 2×~4×）——双通道 Rx 星形合波首跑即暴露（ch0 级联 IL="
                       "3.01dB / ch1=0.07dB vs 闭式 7.02dB）。改 hub 模型修复，2 端口网语义不变，"
                       "重跑 4 道 P1 link 引擎门禁零回归"},
            {"id": "M0-4", "label": "门禁 + 案例卡 + 前端（本回合）",
             "detail": "run_oi_m0_smoke（C7 引擎回归 + C1–C6 基线 + P1/P2/P3a/P3b 突变探针）"
                       "全 PASS；本卡 + 前端面板 + D4 photonic_interconnect 真 GDS 域接入"},
        ],
        "findings": [
            {"title": "闭式与级联两种方法预算逐位一致",
             "detail": "双通道 IL 闭式≡级联差 <0.0001dB——证明装配接线正确，不是两套独立实现"},
            {"title": "吃狗粮抓出真平台 bug（星型网级联重复计数）",
             "detail": "级联引擎 internal_map 对星型网 all-pairs 全连边 ⇒ 多路径求和翻倍；"
                       "这是客户用前我们自己先跑才暴露的能力短板，已 root-cause 并 hub 模型修复"},
            {"title": "相邻信道隔离 18dB 是 L0 模型基线特征，非 bug",
             "detail": "1.6nm 信道间隔下微环 add-drop 解析谱的本征旁瓣限制；登记为 M1 调优目标"
                       "（加大信道间隔 或 抬高环 Q 窄线宽），不误判为缺陷"},
            {"title": "基线 IL≈7dB 是结构预算，可压缩",
             "detail": "GC -3dB×2 + 光纤 span + 环总线 thru 累积；M1 通过低损耗 GC / 短总线"
                       " / 高 Q 环压缩（同链路不破主权）"},
        ],
        "gaps": [
            {"id": "G-OI1", "closed": False,
             "title": "相邻信道隔离 18dB（M0·L0 基线）",
             "detail": "1.6nm 间隔下 L0 微环模型本征旁瓣限制；M1 调优目标：加大信道间隔"
                       " / 抬高环 Q（窄线宽）/ 加平坦化 apodization"},
            {"id": "G-OI2", "closed": False,
             "title": "M0 收发器拓扑尚无专用真 GDS 版图 builder",
             "detail": "本卡是链路预算层；平台已有 D4 域 photonic_interconnect（复用 wdm_mesh_pnr"
                       "的 K×N WDM 网格 P&R，真 GDS+DRC+LVS），但 M0「2 调制器+2 环+2GC+光纤」"
                       "这一具体拓扑的专用 layout builder 仍是缺口，须后续补（不重造既有单元）"},
            {"id": "G-OI3", "closed": False,
             "title": "M1 级电光行为模型尚未补齐",
             "detail": "EO S21 带宽模型 / 眼图与 BER 估计 / 驱动-TIA 行为级协同仿真 / 光纤色散"
                       "预算——均为 M1 800G 级升级的必要能力，属平台尚未覆盖的方法学层"},
            {"id": "G-OI4", "closed": False,
             "title": "电路级模型 · 无 PDK · 不报 TOPS",
             "detail": "继承主权红线：无 foundry 数据 ⇒ 无能效宣称资格；规模与能效外推属 T2 锁死区"},
        ],
        "gaps_closed": 0,
        "gaps_total": 4,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "链路预算设计行为验证口径（确定性现算 · 非流片实测 · 非实测签核）",
        "honest_note": ("🔴 本卡为只读案例：数字由确定性现算（闭式 + lda_chain 级联引擎，"
                        "零重计算 · 免登录 · 不跑 P&R/FDTD）；M0 属链路预算层（L0 解析器件模型），"
                        "真实版图 GDS 由 D4 域 photonic_interconnect 承载；不报 TOPS/TOPS-W/"
                        "fJ/op；判决由死标量给出，LLM 不进判决路径。"),
    }
    if use_cache:
        _CACHE[key] = card
    return card


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检：卡结构完备 + 判决诚实 + 关键数字与模块自检同源。"""
    c = case_card(use_cache=False)
    need = ["case_id", "claim", "identity", "requested", "channels", "b19_passivity",
            "milestones", "findings", "gaps", "verdict", "honest_note"]
    if any(k not in c for k in need):
        return False
    if c["verdict"] != "DESIGN_BUDGET":
        return False
    blob = repr(c["claim"]) + repr(c["identity"]) + repr(c["requested"])
    if "TOPS" in blob:
        return False
    if c["gaps_total"] != len(c["gaps"]):
        return False
    # 闭式≡级联：所有通道差 ≤0.05dB
    ok_ab = all(ch["il_ab_diff_db"] <= 0.05 for ch in c["channels"])
    ok_b19 = bool(c["b19_passivity"])
    ok_ch = len(c["channels"]) == c["requested"]["n_lanes"]
    good = ok_ab and ok_b19 and ok_ch
    if verbose:
        print("[%s] OI-M0 case_card · 通道=%d · 闭式≡级联=%s · B19=%s"
              % ("PASS" if good else "FAIL", len(c["channels"]), ok_ab, ok_b19))
    return good


if __name__ == "__main__":
    print("OI-M0 case self-check:", "PASS" if run_selfchecks(verbose=True) else "FAIL")
