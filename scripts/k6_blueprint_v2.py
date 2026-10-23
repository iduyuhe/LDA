# -*- coding: utf-8 -*-
"""K6 · 蓝图 v2 缺口矩阵（**只起草 · 不动实现** · 机器可读清单）。

🔴 本档性质：**draft_only** —— 不新增锚、不建门禁、不改任何产品面。
   新域落地须**另出章程并经用户定调**（章程 K6 明示）。

输入（全部现算 / 读受跟踪台账）：
  · 蓝图 v1 六层收官状态 → `lda/reports/anchor_gate_coverage.json`（K4 矩阵）
  · 跨档复用沉淀         → `lda/reports/cross_stage_constants.json`（K3 表）
  · 一期未结项状态       → `lda/reports/k0_audit.json`（K0 台账）
  · 候选域现状证据       → 源码关键词命中（0 命中 = 缺口证据）

输出：`lda/reports/blueprint_v2_gap_matrix.json`（人读投影见同名 MD 草案）

确定性：零时间戳 / 零随机 / 零 git HEAD；键序固定；写盘走 `det.write_text`（UTF-8 + LF）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_REPO, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness import deterministic as det  # noqa: E402

SCHEMA = "lda_blueprint_v2_gap_matrix_v1"
OUT_REL = "lda/reports/blueprint_v2_gap_matrix.json"

# ── v1 六层（与 K5 qtrack_case 同口径：按编号区间） ────────────────────
LAYERS = [
    ("L0", "器件与相位（QS-M*）", 473, 496, 0),
    ("L1", "量子纠错（J1）", 497, 505, 19),
    ("L2", "超导处理器（J2）", 506, 509, 37),
    ("L3", "测控与读出（J3）", 510, 514, 44),
    ("L4", "传感系统（J4）", 515, 518, 25),
    ("L5", "量子网络（J5）", 519, 522, 66),
]

# ── 候选新域（章程给三候选；现状证据**现算**） ─────────────────────────
#    probe: (相对 lda/ 的文件列表, 关键词元组) —— 命中数即现状强度
DOMAINS = [
    {
        "id": "V2-D1",
        "name": "光-量异质集成",
        "pitch": "把微波-光换能（J5 M3 已建 B522）推进到**系统级异质集成**：多模换能阵列、"
                 "封装共集成、与 CMOS 控制电路的单片/2.5D 集成",
        "seed": "B522（微波-光换能效率 η = 1.125146902042377e-02）· qnet_transducer.py",
        "probe": (["lda_l2/qnet_transducer.py", "lda_l2/qnet_channel.py"],
                  ["多模", "阵列", "封装", "CMOS", "共集成", "heterogeneous"]),
        "gaps": ["多模换能阵列（单模 → N 模）", "与低温 CMOS 的共集成热/电接口",
                 "封装级光耦合（光纤阵列对准容差）", "异质材料界面损耗模型"],
        "entry_anchors_hint": ["多模换能总效率", "光纤阵列耦合容差预算", "界面吸收损耗"],
        "risk": "**跨域**（光 + 微波 + 封装），单锚难以自洽 ⇒ 建议先做「单指标」再扩系统",
    },
    {
        "id": "V2-D2",
        "name": "QEC 码族扩展",
        "pitch": "J1 只做**表面码**（阈值/解码/综合征/容错门）；扩到 LDPC / 色码 / 拓扑码，"
                 "并比较同一物理错误率下的资源-阈值折衷",
        "seed": "J1 九锚（B497–B505）· decoder.py（MWPM ↔ 自主 Union-Find 位级对拍）",
        "probe": (["lda_qeda/decoder.py", "lda_qeda/logical_error_rate.py",
                   "lda_qeda/qec_noise.py"],
                  ["LDPC", "ldpc", "color code", "色码", "topological", "拓扑码",
                   "bivariate", "hypergraph"]),
        "gaps": ["LDPC / 量子 LDPC 解码（BP + OSD）", "色码解码与阈值",
                 "码族间资源-阈值折衷（同 p 下比较）", "逻辑门集合的可比性度量"],
        "entry_anchors_hint": ["LDPC 阈值（BP+OSD）", "色码阈值", "同 p 下资源比"],
        "risk": "解码器实现重（BP+OSD 需迭代求解器）· **不得借第三方 QEC SDK**（红线）",
    },
    {
        "id": "V2-D3",
        "name": "容错编译（QEC ↔ QPU 联合）",
        "pitch": "在 J1（逻辑层）与 J2（物理层）之间补**编译层**：逻辑门 → 物理脉冲序列的"
                 "映射、调度与错误预算分摊",
        "seed": "J1 容错门（B502/B503）· J2 门错误（B506/B507）—— 两层已有量化输入，但**无编译中间层**",
        # 🔴 探针必须**限定量子模块 + 专指词**：早期用 `compil/schedul/routing`
        #   扫全 `lda_qeda`+`lda_l2` ⇒ 205 命中全是**光子版图的布线/调度**（假阳性）。
        "probe": (["lda_qeda/logical_error_rate.py", "lda_qeda/decoder.py",
                   "lda_qeda/fault_tolerant_gates.py",
                   "lda_l2/qnet_system.py", "lda_l2/qnet_distribution.py"],
                  ["magic_state", "魔术态", "logical_to_physical",
                   "transpile", "fault_tolerant_compil", "测量轮次",
                   "logical_schedul"]),
        "gaps": ["逻辑→物理映射与调度（含测量轮次）", "错误预算在编译期的分摊策略",
                 "门序优化对保真的净收益模型", "编译期资源估计（T 态/魔术态）"],
        "entry_anchors_hint": ["编译后总保真（闭式 vs 模拟）", "调度深度下界",
                               "魔术态消耗率"],
        "risk": "属**软件/算法层**，与现有「物理律锚」范式不同 ⇒ 须先定「golden 是什么」",
    },
]

# ── 继承自 v1 的已知遗留（人读可核） ─────────────────────────────────
INHERITED_GAPS = [
    ("G_Q9", "量子计算征程遗留", "开放（J1–J5 未覆盖该遗留项）"),
    ("G-K-1…7", "一期结算与固化（K 征程）", "已闭合（K0–K5）"),
    ("盲区 415", "全账本 538 锚中仅有统一判决、无专属门禁", "K4 已机器登记，补盲长期化"),
]

# ── 域级裁决（**结算记录**，非新锚/新门禁） ──────────────────────────
#   某域经「先体检后落锚」评估后若判**不可锚**，在这里登记逐条理由与证据，
#   矩阵对应行的 `current` 由「零（v1 未覆盖）」改为「已评估 · 判不可锚」，
#   并附 `adjudication` 子对象（机器可读）。**裁决不改账本、不建门禁。**
ADJUDICATIONS = {
    "V2-D3": {
        "doc": "docs/LDA_V2-D3_容错编译域_短评估_可锚性判定_2026-10-23.md",
        "date": "2026-10-23",
        "verdict": "NOT_ANCHORABLE",
        "basis": "可锚性三问 + 占用体检（全账本 541 锚实扫 + 逐条三处比对）",
        "gaps": {
            1: {
                "cls": "exact_combinatorial",
                "why": "调度深度下界（⌈N/Q⌉ / 关键路径 / LNN 平均 SWAP (n²−1)/(3n)）"
                       "与测量轮次均为整数或精确有理数：任何独立算法都给同一个值 "
                       "⇒ resid ≡ 0 ⇒ 触「零残差」红线 ⇒ 原理上不可锚。",
                "evidence": [
                    "n=4/6/10/16 平均 SWAP 闭式 5/4 · 35/18 · 33/10 · 85/16 与精确枚举（Fraction）差恒 0",
                    "测量轮次为整数（每次 lattice surgery 2d 轮），无截断项",
                ],
            },
            2: {
                "cls": "derived_quantity",
                "why": "同族同预算下等分即最优 ⇒「分摊策略带来的收益」恒 0；非同族时最优解是"
                       "闭式代数（水注）⇒ resid ≡ 0。属既有闭式的派生量，非新物理量。",
                "evidence": [
                    "ε_budget=1e-3 · n=100 ⇒ ε_i=1.000000e-05，Σ=1.000000e-03（精确）",
                    "成本 Σc(2d_i−1)² 在同族同 ε 下同 d ⇒ 等分最优 ⇒ 收益 = 0",
                ],
            },
            3: {
                "cls": "closed_form_direct_candidate",
                "why": "「编译后总保真」= 逐门保真连乘；两种独立实现（连乘 vs exp∘Σlog）实测仅差 "
                       "3–53 ulp，远低于跨平台判据线 1e4·ulp ⇒ 不可复现；若改写成 "
                       "exp(−∫rate·dt) 则与既有三条同形同候选（exp∘中点求积）⇒ 参数化扩展。",
                "evidence": [
                    "n=100/1000/10000（ε=1e-3）⇒ |Δ|/ulp = 3 / 7 / 53；n=1000（ε=1e-4）⇒ 50",
                    "判据线 1e4·ulp = 2.01e-12 / 8.16e-13 / 1.00e-16 / 2.01e-12 ⇒ 全部不过",
                    "累积型写法已被三条既有锚占用（同被测标量 ∧ 同数值格式）",
                ],
            },
            4: {
                "cls": "exact_combinatorial",
                "why": "T 态/魔术态资源全是精确整数或精确有理：15-to-1 产出率 = 1/15、蒸馏轮数为"
                       "整数、Toffoli 的 T 计数下界为 7 ⇒ any 算法同值 ⇒ resid ≡ 0 ⇒ 不可锚。",
                "evidence": [
                    "15-to-1 产出率 = 1/15（精确有理）",
                    "p=1e-2 降到 ≤1e-12 需 3 轮（末轮 p=1.183e-34）",
                    "Toffoli T 计数下界 7 / T 深度 1（整数）",
                ],
            },
        },
    },
}

# ── 蓝图 v2 三域收官（机器可读的结算面 · 2026-10-23） ───────────────────
V2_DOMAIN_OUTCOMES = [
    {"id": "V2-D1", "name": "光-量异质集成", "outcome": "CLOSED_WITH_ANCHORS",
     "anchors_n": 2,
     "detail": "M0 锚 B523（多模换能阵列平均孔径截断效率）· M3 前移锚 B524（Kapitza 界面热导）；"
               "M1/M2 两条章程锚判「已被既有锚 100% 覆盖 / 派生量」⇒ 净增 0；M4 面板交付。"},
    {"id": "V2-D2", "name": "QEC 码族扩展", "outcome": "PARTIALLY_ANCHORABLE",
     "anchors_n": 1,
     "detail": "M0 锚 B525（退极化信道 hashing 界）；三类「不可锚」机器化；"
               "M1 判「码族比较/开销无可锚物」（四类）⇒ 净增 0，改面板 + 裁决。"},
    {"id": "V2-D3", "name": "容错编译（QEC ↔ QPU 联合）", "outcome": "NOT_ANCHORABLE",
     "anchors_n": 0,
     "detail": "四类 gap 逐条判死（精确组合 / 派生量 / 闭式直算脆弱 / 同形同候选）；"
               "结论：「物理律闭式锚」的射程 = 物理层，编译/调度层无物理律标量可锚。"},
]


def _read_json(rel: str):
    p = os.path.join(_REPO, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _iter_py(rel):
    """展开扫描目标：单文件 → 自身；目录 → 其下全部 *.py（排序稳定）。"""
    p = os.path.join(_LDA, rel)
    if os.path.isfile(p):
        return [p]
    if os.path.isdir(p):
        return [os.path.join(p, f) for f in sorted(os.listdir(p))
                if f.endswith(".py")]
    return []


def _count_keywords(files, kws):
    """现算：给定目标的**去整行注释**源码里，各关键词的命中总数。"""
    hits = {}
    for kw in kws:
        n = 0
        for rel in files:
            for path in _iter_py(rel):
                with open(path, encoding="utf-8") as f:
                    for ln in f.read().split("\n"):
                        if ln.lstrip().startswith("#"):
                            continue
                        n += ln.count(kw)
        hits[kw] = n
    return hits


def build():
    cov = _read_json("lda/reports/anchor_gate_coverage.json") or {}
    xtab = _read_json("lda/reports/cross_stage_constants.json") or {}
    k0 = _read_json("lda/reports/k0_audit.json") or {}

    anch = cov.get("anchors") or {}
    layers = []
    for lid, name, lo, hi, judges in LAYERS:
        ids = sorted((a for a in anch
                      if a.startswith("B") and a[1:].isdigit()
                      and lo <= int(a[1:]) <= hi),
                     key=lambda x: int(x[1:]))
        l2 = sum(1 for a in ids if (anch[a].get("l2_count") or 0) > 0)
        layers.append({
            "id": lid, "name": name, "band": "B%d–B%d" % (lo, hi),
            "anchors_n": len(ids), "l2_n": l2,
            "l3_n": sum(1 for a in ids if anch[a].get("l3") is True),
            "judges_n": judges,
            "closed": len(ids) > 0 and l2 == len(ids),
        })

    domains = []
    for d in DOMAINS:
        files, kws = d["probe"]
        hits = _count_keywords(files, kws)
        domains.append({
            "id": d["id"], "name": d["name"], "pitch": d["pitch"],
            "seed": d["seed"],
            "probe_files": list(files),
            "probe_keyword_hits": hits,
            "probe_total_hits": sum(hits.values()),
            "probe_verdict": ("零命中 ⇒ 该域在现有代码中**无对应实现**（缺口证据）"
                              if sum(hits.values()) == 0
                              else "有命中 ⇒ 部分概念已存在，需逐项核可区分性"),
            "gaps": list(d["gaps"]),
            "entry_anchors_hint": list(d["entry_anchors_hint"]),
            "risk": d["risk"],
        })

    gap_matrix = []
    for i, d in enumerate(domains, 1):
        adj = ADJUDICATIONS.get(d["id"])
        for j, g in enumerate(d["gaps"], 1):
            row = {
                "gap_id": "G-V2-D%d-%d" % (i, j),
                "domain": d["name"],
                "gap": g,
                "current": "零（v1 未覆盖）",
                "owner": "待立项章程",
            }
            if adj:
                spec = (adj.get("gaps") or {}).get(j) or {}
                row["current"] = "已评估 · 判不可锚（%s）" % adj["date"]
                row["owner"] = "已结算（短评估 · 不立项）"
                row["adjudication"] = {
                    "verdict": adj["verdict"],
                    "anchorability_class": spec.get("cls"),
                    "why": spec.get("why"),
                    "evidence": list(spec.get("evidence") or []),
                    "doc": adj["doc"],
                }
            gap_matrix.append(row)

    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/k6_blueprint_v2.py",
        "roadmap": "K6（蓝图 v2 奠基 · 只起草矩阵不动实现）",
        "status": "draft_only",
        "subject": "量子赛道蓝图 v2 缺口矩阵（草案）",
        "boundary": [
            "本档**不动实现**：零新增锚、零新增门禁、不改任何产品面",
            "新域落地须**另出章程并经用户定调**（章程 K6 明示）",
            "候选域的现状证据为**源码关键词命中**（现算），属**下限**而非完备",
        ],
        "excluded_fields": ["时间戳（非确定量）", "git HEAD（每次提交都变）"],
        "inherited_v1": {
            "layers": layers,
            "anchors_n": sum(l["anchors_n"] for l in layers),
            "judges_n": sum(l["judges_n"] for l in layers),
            "all_closed": all(l["closed"] for l in layers),
            "ledger": {
                "anchors_total": (cov.get("summary") or {}).get("anchors_total"),
                "l1": (cov.get("summary") or {}).get("l1_unified_covered"),
                "l2": (cov.get("summary") or {}).get("l2_bespoke_covered"),
                "l3": (cov.get("summary") or {}).get("l3_multi_covered"),
                "blind": (cov.get("summary") or {}).get("l2_blind"),
                "core_smokes": (cov.get("summary") or {}).get("core_smokes"),
            },
            "cross_stage": {
                "sites_total": (xtab.get("summary") or {}).get("sites_total"),
                "sites_cross_stage": (xtab.get("summary") or {}).get("sites_cross_stage"),
            },
            "k0_settled": k0.get("items_settled"),
            "k0_items_total": k0.get("items_total"),
        },
        "inherited_gaps": [{"id": a, "gap": b, "status": c}
                           for a, b, c in INHERITED_GAPS],
        "new_domain_candidates": domains,
        "v2_domain_outcomes": [dict(x) for x in V2_DOMAIN_OUTCOMES],
        "gap_matrix": gap_matrix,
        "gap_matrix_n": len(gap_matrix),
        "decision_points": [
            "选哪个候选域作为 v2 首档（或另提新域）？",
            "v2-D3 容错编译的 golden 是什么（物理闭式 / 规格锚 / 模拟基线）？—— 决定其能否沿用现有判据范式",
            "是否允许引入 BP+OSD 类迭代解码（自研 vs 借用的主权分层归属）？",
            "补盲 415 锚 与 新域扩张 的优先级如何排（棘轮只升不降 ⇒ 新域会同时抬 L2 下限）？",
        ],
    }
    return payload


def render(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="K6 蓝图 v2 缺口矩阵生成器（只起草）")
    ap.add_argument("--write", action="store_true", help="写回受跟踪清单")
    args = ap.parse_args(argv)

    payload = build()
    text = render(payload)
    if args.write:
        det.write_text(os.path.join(_REPO, OUT_REL), text)
        print("[written] %s（候选域 %d · 缺口 %d 条 · status=%s）"
              % (OUT_REL, len(payload["new_domain_candidates"]),
                 payload["gap_matrix_n"], payload["status"]))
    else:
        # ⚠️ Windows 下 print 到管道是 CRLF，写盘是纯 LF；对拍须用 text=True
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
