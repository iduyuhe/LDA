# -*- coding: utf-8 -*-
"""生产红队自动攻击端点核心（T0 LLM 红队闭环 · 周期化）。

把「蓝队生成 / 红队出题 / 锚判卷 / 人终审」四层闭环周期化、可观测：
- 蓝队(DeepSeek 生成器)出候选 → 红队(GLM)出对抗候选 → 每个攻击经三层判卷
  （结构校验 validate_params → 可行域 feasible_domain → 四锚 screen_proposal）。
- 死标量（红队自身可证伪，同构「生态/智能体出题，锚判卷」）：
    hit_rate     = 被锚确认的真实缺陷数 / 出题数   （目标 0：健康管线不应漏过）
    attack_ratio = 管线拒收攻击数 / 出题数         （红队是否真在对抗，目标 ≥0.3）
    coverage     = 意图攻击的锚种类数              （目标 ≥2：多角打法）
- 每次调用把死标量追加进 trend 文件（带时间戳），供 /api/redteam_trend 拉取趋势。

纪律（五共识 ② 红蓝分工）：
- 红队模型必须 ≠ 生成器模型（防同源假独立）→ 由生产 drop-in 保证（DeepSeek 蓝 / GLM 红）。
- 红队自身也必须被证伪：命中率 = 被锚确认缺陷 ÷ 出题数（死标量），一旦回归引入漏洞
  漏过数>0 ⇒ 命中率飙升即告警。红队价值=覆盖面，非判决。

降级（核心零依赖优雅降级铁律）：未配 LDA_REDTEAM_* → 返回 status=skipped，
不报错、不联网；设计流调用本模块失败也绝不阻断主设计返回。

依赖：仅 Python 标准库（urllib 在 redteam_proposer 内）。无新外部依赖。
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

# 保证 lda_harness / lda_agent 可导入（与 app.py 同约定）。
_LDA_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

_WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_WEBUI_DIR, "data")
_TREND_PATH = os.path.join(_DATA_DIR, "redteam_trend.jsonl")
_MAX_TREND_LINES = 2000  # 趋势文件旋转上限，防无限增长
_LOCK = threading.Lock()


def _ensure_data_dir():
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass


def _append_trend(rec: Dict[str, Any]):
    """线程安全追加趋势记录；超限时旋转保留最近 N 行。"""
    _ensure_data_dir()
    line = json.dumps(rec, ensure_ascii=False)
    with _LOCK:
        try:
            # 旋转：若超上限，重写保留尾部
            if os.path.exists(_TREND_PATH):
                with open(_TREND_PATH, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                if len(lines) >= _MAX_TREND_LINES:
                    lines = lines[-(_MAX_TREND_LINES - 1):]
                    with open(_TREND_PATH, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
            with open(_TREND_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:  # noqa: BLE001 —— 落盘失败不影响主流程
            pass


def read_trend(limit: int = 50) -> Dict[str, Any]:
    """读取趋势：返回最近 limit 条原始记录 + 抽平的趋势序列（按时间升序）。"""
    rows: List[Dict[str, Any]] = []
    try:
        with open(_TREND_PATH, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    continue
    except FileNotFoundError:
        rows = []
    rows = rows[-limit:]
    trend = [{
        "t": r.get("timestamp"),
        "status": r.get("status"),
        "hit_rate": (r.get("dead_scalars") or {}).get("hit_rate"),
        "attack_ratio": (r.get("dead_scalars") or {}).get("attack_ratio"),
        "coverage": (r.get("dead_scalars") or {}).get("coverage"),
        "confirmed_defects": (r.get("dead_scalars") or {}).get("confirmed_defects"),
        "n_proposed": (r.get("dead_scalars") or {}).get("n_proposed"),
        "redteam_model": r.get("redteam_model"),
    } for r in rows]
    return {"count": len(rows), "records": rows, "trend": trend}


def judge_attacks(req: Dict[str, Any],
                  attacks: List[Dict[str, Any]],
                  blue: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """三层判卷：结构校验 → 可行域 → 四锚。返回死标量 + 逐攻击明细。

    判卷口径（防常数假绿 / 良性滑过误报）：
    - n_proposed   出题数
    - n_clamped   结构非法，被 validate_params 钳掉（红队弱攻击，无价值）
    - n_caught    结构合法但被 feasible_domain/四锚 拦下 = 红队真在攻击
    - n_slip      红队生成的本是合法设计，管线接受 = 红队没攻击到（诊断，非缺陷）
    - confirmed_defects 出题带 target 锚、该锚独立复算违规却仍被管线接受
                     （健康管线 accepted⟹全锚过 ⇒ 恒为 0；回归破坏 accepted 才>0）
    """
    from lda_agent.llm_proposer import LLMProposer
    from lda_harness.proposal_compiler import (
        compile_proposal, feasible_domain, screen_proposal,
    )

    proposer = LLMProposer()  # 复用其 validate_params 作结构钳制判据
    n_proposed = len(attacks)
    n_clamped = n_caught = n_slip = confirmed_defects = 0
    anchors_hit: set = set()      # 实际被某锚拦下的锚种类（诊断）
    intended_targets: set = set()  # 红队意图攻击的锚种类（覆盖度）
    per_attack: List[Dict[str, Any]] = []

    for atk in attacks:
        tgt = atk.get("target")
        if tgt:
            intended_targets.add(tgt)
        clean = {k: v for k, v in atk.items()
                 if k in ("p_tx_dbm", "channel_spacing_ghz", "filter_bw_ghz", "wg_length_cm")}
        # ① 结构校验（钳制越界/非法）
        if not proposer.validate_params(clean):
            n_clamped += 1
            per_attack.append({"verdict": "clamped", "target": tgt,
                               "params": clean, "anchors_hit": []})
            continue
        # ② 可行域 + ③ 四锚判卷
        prop = compile_proposal({**req, **clean})
        fd = feasible_domain(prop)
        scr = screen_proposal(prop)
        passed_all = fd["feasible"] and scr["accepted"]
        hit = [c["anchor"] for c in scr["checks"] if not c["passed"]]
        if not passed_all:
            n_caught += 1
            anchors_hit.update(hit)
            per_attack.append({"verdict": "caught", "target": tgt,
                               "params": clean, "anchors_hit": hit})
        else:
            # 滑过：管线全过。是缺陷吗？仅当出题明确 target 且该锚独立复算仍违规
            is_defect = False
            if tgt:
                tgt_check = next((c for c in scr["checks"]
                                 if c["anchor"].startswith(tgt)), None)
                if tgt_check is not None and not tgt_check["passed"]:
                    is_defect = True
            if is_defect:
                confirmed_defects += 1
                per_attack.append({"verdict": "defect", "target": tgt,
                                   "params": clean, "anchors_hit": hit})
            else:
                n_slip += 1
                per_attack.append({"verdict": "slip", "target": tgt,
                                   "params": clean, "anchors_hit": []})

    n_rejected = n_clamped + n_caught
    attack_ratio = (n_rejected / n_proposed) if n_proposed else 0.0
    hit_rate = (confirmed_defects / n_proposed) if n_proposed else 0.0
    coverage = len(intended_targets)
    return {
        "n_proposed": n_proposed,
        "n_clamped": n_clamped,
        "n_caught": n_caught,
        "n_slip": n_slip,
        "confirmed_defects": confirmed_defects,
        "attack_ratio": round(attack_ratio, 4),
        "hit_rate": round(hit_rate, 4),
        "coverage": coverage,
        "anchors_hit": sorted(anchors_hit),
        "intended_targets": sorted(intended_targets),
        "per_attack": per_attack,
    }


def run_redteam_probe(req: Dict[str, Any], n: int = 6,
                      generator: str = "llm") -> Dict[str, Any]:
    """周期化红队自动攻击：蓝队生成 → 红队(GLM)出题 → 三层判卷 → 落盘趋势。

    入参 req：WDM 链路需求（同 proposal_compiler 约定键）。
    返回 dict：status(skipped/ok/error) + 死标量 + 逐攻击明细 + 时间戳。
    无 LDA_REDTEAM_* 时返回 skipped（不联网）；任何异常不抛出（优雅降级）。
    """
    from lda_harness.proposal_compiler import generate_candidates
    from lda_agent.redteam_proposer import RedTeamProposer

    rt = RedTeamProposer()
    if not rt.enabled:
        rec = {
            "status": "skipped",
            "reason": "LDA_REDTEAM_* 未配置",
            "redteam_model": rt.model,
            "timestamp": time.time(),
            "req": req,
            "dead_scalars": {"hit_rate": 0.0, "attack_ratio": 0.0,
                             "coverage": 0, "confirmed_defects": 0, "n_proposed": 0},
            "per_attack": [],
        }
        _append_trend(rec)
        return rec

    try:
        try:
            blue = generate_candidates(req, generator=generator)
        except Exception:  # noqa: BLE001 —— 蓝队上下文失败不影响红队独立出题
            blue = []
        attacks = rt.propose_attacks(req, blue_candidates=blue, n=n)
        verdict = judge_attacks(req, attacks, blue)
        rec = {
            "status": "ok",
            "redteam_model": rt.model,
            "generator": generator,
            "n_blue": len(blue),
            "timestamp": time.time(),
            "req": req,
            "dead_scalars": {
                "hit_rate": verdict["hit_rate"],
                "attack_ratio": verdict["attack_ratio"],
                "coverage": verdict["coverage"],
                "confirmed_defects": verdict["confirmed_defects"],
                "n_proposed": verdict["n_proposed"],
            },
            "per_attack": verdict["per_attack"],
        }
    except Exception as e:  # noqa: BLE001 —— 红队端点永不抛错到主流程
        rec = {
            "status": "error",
            "detail": str(e)[:200],
            "redteam_model": rt.model,
            "timestamp": time.time(),
            "req": req,
            "dead_scalars": {"hit_rate": None, "attack_ratio": None,
                             "coverage": 0, "confirmed_defects": None, "n_proposed": 0},
            "per_attack": [],
        }
    _append_trend(rec)
    return rec


if __name__ == "__main__":
    demo_req = {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
                "filter_bw_ghz": 25.0, "wg_length_cm": 1.0}
    print(json.dumps(run_redteam_probe(demo_req, n=6), ensure_ascii=False, indent=2))
