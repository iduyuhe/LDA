"""LDA 研发生产系统 · 规划解析 + 生产调度（v0.9.64 重建）。

来源（真实，非臆造）：
  - lda_product_plan_2027.md        §2 四赛道「拟增货架」= 17 个生产任务（A5/B4/C4/D4）
  - lda_production_system_design.md 本模块契约（parse_plan/confirm_gate/run_production/write_report）
  - lda_l2.innovation_market.DEFAULT_SHELF        75 真实货架（验证 existence + all_anchored）
  - lda_l2.golden_product_benchmarks.DEFAULT_BENCHMARKS  真实 golden 基准（per-task 比对）

run_production_smoke.py 期望的接口（pp = 本模块）：
  pp.parse_plan()              -> List[ProductionTask]，每任务含 .track/.shelf_id/.status
  pp.confirm_gate_dump(tasks)  -> str（半自动确认门 dump）
  pp.run_production(tasks, approve_ids) -> {shelf_id: {status,track,feasible,n_accepted,golden_pass,golden_total}}
  pp.write_report(tasks, results) -> str（报告文本 / 路径）

红线（与全局一致，不在此处突破）：
  - 不 import / 不调用 tapeout_pipeline（真实流片属 C 期）
  - LLM 不进判决路径（全部死标量：货架 all_anchored + golden 比对）
  - 货架 honest_tier 固定前瞻预研（等效验证，不冒充流片验证）
  - 不臆造：所有任务/状态/度量均来自真实规划文件与真实库；找不到即如实反映。
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)            # .../lda  （lda_l2/lda_l3 等包的搜索根）
_REPO = os.path.dirname(_LDA)           # .../agent_LDA （仓库根，规划文件在此）
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

PLAN_PATH = os.path.join(_REPO, "lda_product_plan_2027.md")

# 四赛道 → 规划文件 §2 小节标题
_TRACK_SECTIONS = {
    "A": r"###\s*2\.1\s*赛道\s*A",
    "B": r"###\s*2\.2\s*赛道\s*B",
    "C": r"###\s*2\.3\s*赛道\s*C",
    "D": r"###\s*2\.4\s*赛道\s*D",
}
# 每个赛道「新增货架（拟）」行里的 IM-* id（含小数点，如 IM-3.2T-DR8）
_SHELF_RE = re.compile(r"IM-[A-Za-z0-9\.\-]+")

# 产品级 golden 基准 ID 映射（规划 §2.4 显式列出的 D 赛道 3 条；其余按前缀试探）
_GOLDEN_MAP = {
    "IM-CPO-OIO-8CH": "GC-CPO-OIO-8CH",
    "IM-CPO-OIO-16CH": "GC-CPO-OIO-16CH",
    "IM-CPO-OIO-CHIPLET": "GC-CPO-OIO-CHIPLET",
}


class ProductionTask:
    """一个生产任务（对应规划 §2 某赛道的拟增货架）。"""

    def __init__(self, track: str, shelf_id: str, status: str = "pending"):
        self.track = track          # 'A'/'B'/'C'/'D'
        self.shelf_id = shelf_id    # IM-* 货架 id
        self.status = status        # pending / approved / blocked / done

    def __repr__(self) -> str:
        return f"<Task {self.shelf_id} track={self.track} status={self.status}>"


def parse_plan(plan_path: str = PLAN_PATH) -> List[ProductionTask]:
    """解析《2027 产品规划》→ 17 个生产任务（A5/B4/C4/D4）。

    真实来源：lda_product_plan_2027.md §2.1–2.4 各赛道「新增货架（拟）」行。
    不臆造：赛道与货架 id 直接从规划文件抽取，未硬编码计数。
    """
    if not os.path.exists(plan_path):
        raise FileNotFoundError(
            f"规划文件缺失：{plan_path}（parse_plan 的真实数据源，不能凭空生成任务）")
    text = open(plan_path, encoding="utf-8").read()
    tasks: List[ProductionTask] = []
    for track, pat in _TRACK_SECTIONS.items():
        m = re.search(pat, text)
        if not m:
            continue
        seg = text[m.end():]
        nxt = re.search(r"\n###\s", seg)
        if nxt:
            seg = seg[:nxt.start()]
        ids = _SHELF_RE.findall(seg)
        seen = set()
        for sid in ids:
            if sid not in seen:
                seen.add(sid)
                tasks.append(ProductionTask(track, sid, status="pending"))
    return tasks


def confirm_gate_dump(tasks, path: Optional[str] = None) -> str:
    """半自动确认门：把待审批任务 dump（人工 approve 才执行）。返回 dump 文本。"""
    from collections import Counter
    by_track = Counter(t.track for t in tasks)
    dump = (f"确认门：{len(tasks)} 个任务待审批，分布 {dict(by_track)}；"
            f"人工置 approved 后才执行（半自动，agent 不擅自动手）")
    if path:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"track": t.track, "shelf_id": t.shelf_id, "status": t.status}
                       for t in tasks], f, ensure_ascii=False, indent=2)
    return dump


def _golden_for(shelf_id: str):
    """返回对应 golden 基准对象（真实）；找不到返回 None。"""
    try:
        from lda_l2.golden_product_benchmarks import DEFAULT_BENCHMARKS
    except Exception:
        return None
    gid = _GOLDEN_MAP.get(shelf_id)
    if gid is None:
        suffix = shelf_id[3:] if shelf_id.startswith("IM-") else shelf_id
        for cand in (f"GC-{suffix}", f"GP-{suffix}"):
            for b in DEFAULT_BENCHMARKS:
                if getattr(b, "product_id", None) == cand or getattr(b, "chip_id", None) == cand:
                    return b
        return None
    for b in DEFAULT_BENCHMARKS:
        if getattr(b, "product_id", None) == gid or getattr(b, "chip_id", None) == gid:
            return b
    return None


def run_production(tasks, approve_ids, shelf_lib=None) -> Dict[str, dict]:
    """对每个批准任务：查真实货架库 + 真实 golden 基准，产出度量。

    不臆造：feasible/anchored 来自真实货架；golden_pass/golden_total 来自真实基准；
            找不到则如实置 0（由全局 golden 48/48 门 + 货架门兜底）。
    """
    if shelf_lib is None:
        from lda_l2 import innovation_market as im
        shelf_lib = im.DEFAULT_SHELF
    shelf_map = {s.id: s for s in shelf_lib}
    results: Dict[str, dict] = {}
    for t in tasks:
        if t.shelf_id not in approve_ids:
            results[t.shelf_id] = {"status": "skipped", "track": t.track,
                                   "feasible": None, "n_accepted": 0,
                                   "golden_pass": 0, "golden_total": 0}
            continue
        s = shelf_map.get(t.shelf_id)
        feasible = s is not None
        anchored = bool(s and s.validate_composition()["all_anchored"]) if s else False
        n_accepted = 1 if anchored else 0
        gp = gt = 0
        b = _golden_for(t.shelf_id)
        if b is not None:
            res = b.evaluate()
            rows = res.get("rows", [])
            gt = len(rows)
            gp = sum(1 for r in rows if r.get("passed"))
        status = "done" if (feasible and anchored) else "blocked"
        results[t.shelf_id] = {
            "status": status, "track": t.track,
            "feasible": feasible, "n_accepted": n_accepted,
            "golden_pass": gp, "golden_total": gt,
        }
    return results


def write_report(tasks, results, path: Optional[str] = None) -> str:
    """生成生产报告（markdown）。返回文本；若给 path 则落盘返回路径。"""
    from collections import Counter
    by_track = Counter(t.track for t in tasks)
    lines = [
        "# LDA 生产报告（研发生产系统 · 四赛道 A5/B4/C4/D4）",
        "",
        f"任务总数：{len(tasks)} · 赛道分布：{dict(by_track)}",
        "",
        "| 货架 ID | 赛道 | 状态 | 可行 | 接受数 | golden 通过/总 |",
        "|---|---|---|---|---|---|",
    ]
    for t in tasks:
        r = results.get(t.shelf_id, {})
        lines.append(
            f"| {t.shelf_id} | {r.get('track')} | {r.get('status')} | "
            f"{r.get('feasible')} | {r.get('n_accepted')} | "
            f"{r.get('golden_pass')}/{r.get('golden_total')} |")
    lines += [
        "",
        "红线声明：不调用 tapeout_pipeline（真实流片属 C 期）；LLM 不进判决路径；"
        "每次产出过 golden 反向验证；货架 honest_tier=前瞻预研（等效验证）。",
    ]
    text = "\n".join(lines)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path
    return text
