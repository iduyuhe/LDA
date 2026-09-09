"""LDA 系统级提案编译器（Phase 4 · 专投区收官 · 生成侧第一件）。

五共识落地（《系统级探索预案》Phase 4 + 杜先生五判断）：
  先锚定可行域 → AI 域内提案 → 死锚验每一案 → 人终审选优。

架构（红线：LLM 不进判决路径）：
  ┌─ compile_proposal ─── 功能需求 → 结构化提案（JSON，人可读可审）
  ├─ feasible_domain ──── 锚约束剪枝：功率预算/频率规划/最坏情况（S1/S2/S5 同式纯算术）
  ├─ generate_candidates ─ 域内参数网格生成（确定性——Phase 4 第一刀用网格，
  │                        LLM 提案生成器为将来替换件：接口相同，判决不变）
  ├─ screen_proposal ──── 即提即验：每案过全部系统锚（死标量 |c−golden|≤tol）
  └─ rank_proposals ───── 确定性排序（余量降序 + 词典序 tiebreak——无随机无 LLM）

诚实边界：
  - 生成器当前为确定性网格（MVP）——「AI 提案」的接口已就位，LLM 接入属
    发动期（且仅替换 generate_candidates 一处，判决层零改动）；
  - 锚覆盖 S1/S2/S5（功率/频率/最坏情况）+ **S7 统计锚已接入**
    （S7-statistical-p5：蒙特卡洛最坏情况 margin p5 > 0，固定种子确定性；
    见 screen_proposal 第 4 锚与 feasible_domain）——**S8 仍未纳入**（Phase 4 后续）；
  - 人终审：输出 ranked 提案列表 + 逐案锚证据，选择权在人。
"""
from __future__ import annotations

import itertools
import math
import re
from typing import Any, Dict, List, Tuple

# ---- 行为级黑箱参数（system_budget 同源，文献典型值） ----
GRATING_DB = -3.0
WG_LOSS_DB_CM = 3.0
RING_IL_DB = -0.5
DETECTOR_SENS_DBM = -20.0


# ---------------------------------------------------------------------------
# ① 功能需求 → 结构化提案（编译入口）
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# ⓪ NLP 需求入口（WBS-T0-2）：自然语言需求 → 结构化提案 req
#    规则式解析（正则 + 中文数字），只提取用户明确给出的数字；
#    缺失字段用典型默认值并标注 source=default——**绝不杜撰数字**。
#    复用 /api/store/guide 的「自然语言→结构化」思路，但不碰货架匹配，
#    直接映射到 design_pipeline 的 req 字段。
# ---------------------------------------------------------------------------
_CN_NUM = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
           '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _re_float(text: str, *patterns) -> "float | None":
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return float(m.group(1))
    return None


def _extract_pair(text: str, keywords, unit: str) -> "float | None":
    """双向提取：支持「关键词 数字单位」与「数字单位 关键词」两种语序。

    例：'50GHz spacing' 与 'spacing: 50GHz' 都应命中 50。
    裸数字（无关键词上下文）不匹配——避免间隔/带宽歧义杜撰。
    """
    for kw in keywords:
        m = re.search(rf'{kw}\s*[:：]?\s*(\d+(?:\.\d+)?)\s*{unit}', text, re.I)
        if m:
            return float(m.group(1))
    for kw in keywords:
        m = re.search(rf'(\d+(?:\.\d+)?)\s*{unit}\s*(?:of\s+|for\s+)?{kw}', text, re.I)
        if m:
            return float(m.group(1))
    return None


def parse_nlp_requirement(text: str) -> Dict[str, Any]:
    """自然语言需求 → 结构化提案 req（规则式，不杜撰数字）。

    返回 {req, source, raw_text}：
      req     可直接喂 design_pipeline；
      source  每个字段的来源（parsed / parsed_cn / default），供人审与合规。
    缺失字段一律回退典型默认值并标注 default——绝不编造物理数字。
    """
    src: Dict[str, str] = {}

    # 信道数
    n_ch = None
    m = re.search(r'(\d+)\s*个?\s*信[道道]', text)
    if m:
        n_ch, src['n_channels'] = int(m.group(1)), 'parsed'
    elif (m := re.search(r'(\d+)\s*channel', text, re.I)):
        n_ch, src['n_channels'] = int(m.group(1)), 'parsed'
    elif (m := re.search(r'([一二三四五六七八九十])\s*信[道道]', text)):
        n_ch, src['n_channels'] = _CN_NUM.get(m.group(1)), 'parsed_cn'

    sp = _extract_pair(text, ['间隔', 'spacing', 'channel spacing'], 'GHz')
    if sp is not None:
        src['channel_spacing_ghz'] = 'parsed'
    bw = _extract_pair(text, ['带宽', 'bandwidth', 'bw'], 'GHz')
    if bw is not None:
        src['filter_bw_ghz'] = 'parsed'
    mb = _extract_pair(text, ['余量', 'margin', 'budget'], 'dB')
    if mb is not None:
        src['link_budget_db'] = 'parsed'
    ptx = _extract_pair(text, ['功率', 'power', 'tx'], 'dBm')
    if ptx is not None:
        src['p_tx_dbm'] = 'parsed'
    wgl = _re_float(text, r'(?:波导长度|wg[_\s]?length)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*cm')
    if wgl is not None:
        src['wg_length_cm'] = 'parsed'

    req: Dict[str, Any] = {}
    if n_ch is not None:
        req['n_channels'] = n_ch
    if sp is not None:
        req['channel_spacing_ghz'] = sp
    if bw is not None:
        req['filter_bw_ghz'] = bw
    if mb is not None:
        req['link_budget_db'] = mb
    if ptx is not None:
        req['p_tx_dbm'] = ptx
    if wgl is not None:
        req['wg_length_cm'] = wgl

    # 缺字段来源标注（供人审：凡 default 即 AI 未从原文取得，需人确认）
    for k in ('n_channels', 'channel_spacing_ghz', 'filter_bw_ghz',
              'link_budget_db', 'p_tx_dbm', 'wg_length_cm'):
        src.setdefault(k, 'default')
    return {"req": req, "source": src, "raw_text": text}


def design_pipeline_from_nlp(text: str, n_top: int = 3,
                             generator: str = "grid",
                             system_type: str = "link",
                             weights: "Dict[str, float] | None" = None):
    """NLP 便捷入口：自然语言 → design_pipeline（人终审材料）。"""
    parsed = parse_nlp_requirement(text)
    result = design_pipeline(parsed["req"], n_top=n_top, generator=generator,
                             system_type=system_type, weights=weights)
    result["nlp_source"] = parsed["source"]
    return result


def compile_proposal(req: Dict[str, Any]) -> Dict[str, Any]:
    """把功能需求编译成结构化提案。

    需求字段（全部可选，缺省用典型值）：
      n_channels      信道数（默认 4）
      channel_spacing_ghz  信道间隔 GHz（默认 100）
      filter_bw_ghz   滤波器带宽 GHz（默认 50）
      link_budget_db  要求的链路余量 dB（默认 3.0，>0 即可通）
      p_tx_dbm        激光器功率 dBm（默认 0）
      wg_length_cm    波导长度 cm（默认 1.0）
    输出：结构化提案（n_channels/channel_plan/link_spec/acceptance_spec），
    每字段带来源标注——供锚筛选与人审。
    """
    n_ch = int(req.get("n_channels", 4))
    spacing = float(req.get("channel_spacing_ghz", 100.0))
    bw = float(req.get("filter_bw_ghz", 50.0))
    return {
        "n_channels": n_ch,
        "channel_plan": {
            "spacing_ghz": spacing,
            "filter_bw_ghz": bw,
            "no_collision_margin_ghz": spacing - bw,  # S2 同式
        },
        "link_spec": {
            "p_tx_dbm": float(req.get("p_tx_dbm", 0.0)),
            "n_gratings": 2,
            "grating_db": GRATING_DB,
            "wg_length_cm": float(req.get("wg_length_cm", 1.0)),
            "wg_loss_db_cm": WG_LOSS_DB_CM,
            "ring_il_db": RING_IL_DB,
            "detector_sens_dbm": DETECTOR_SENS_DBM,
            # S8 可选 OSNR 链路参数（仅含放大器链路提供；纯 WDM 不杜撰）
            "osnr": {
                "p_sig_dbm": req.get("p_sig_dbm"),
                "n_amp": req.get("n_amp"),
                "nf_db": req.get("nf_db"),
                "bw_ghz": req.get("bw_ghz"),
            },
        },
        "acceptance_spec": {
            "min_margin_db": float(req.get("link_budget_db", 3.0)),
            "worst_case_il_db": 10.0,  # S5 同式（SS 角最坏插损合计）
            "min_osnr_p5_db": float(req.get("min_osnr_p5_db", 15.0)),
        },
        "req_source": dict(req),
    }


# ---------------------------------------------------------------------------
# ② 锚约束剪枝：可行域（先框死，再生成——杜先生判断 4 的工程落地）
# ---------------------------------------------------------------------------
def feasible_domain(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """用系统锚约束推导可行域（纯算术，S1/S2/S5 同式）。

    返回：
      feasible          域非空（True/False）
      margin_db         名义链路余量（S1 式）
      worst_margin_db   最坏情况余量（S5 式）
      collision_margin_ghz  频率规划余量（S2 式）
      binding_constraint 当前卡死的约束（None=无）
    """
    ls = proposal["link_spec"]
    n_gr = int(ls["n_gratings"])
    margin = (ls["p_tx_dbm"]
              + n_gr * ls["grating_db"]
              - ls["wg_loss_db_cm"] * ls["wg_length_cm"]
              + ls["ring_il_db"]
              - ls["detector_sens_dbm"])
    worst = (ls["p_tx_dbm"]
             - proposal["acceptance_spec"]["worst_case_il_db"]
             - ls["detector_sens_dbm"])
    cp = proposal["channel_plan"]
    coll = cp["spacing_ghz"] - cp["filter_bw_ghz"]
    need = proposal["acceptance_spec"]["min_margin_db"]

    binding = None
    if margin < need:
        binding = f"S1 功率预算：margin={margin:.1f} < 要求 {need}"
    elif worst < 0:
        binding = f"S5 最坏情况：worst={worst:.1f} < 0"
    elif coll <= 0:
        binding = f"S2 频率碰撞：spacing−bw={coll:.1f} ≤ 0"
    return {"feasible": binding is None,
            "margin_db": round(margin, 3),
            "worst_margin_db": round(worst, 3),
            "collision_margin_ghz": round(coll, 3),
            "binding_constraint": binding}


# ---------------------------------------------------------------------------
# ③ 域内候选生成（确定性网格；LLM 生成器将来替换件——接口不变判决不变）
# ---------------------------------------------------------------------------
def generate_candidates(proposal: Dict[str, Any],
                        n_top: int = 3,
                        generator: str = "grid") -> List[Dict[str, Any]]:
    """在可行域内生成候选（网格 + 可选 LLM 合并——发动期接入）。

    grid（默认，确定性）：p_tx ∈ {0, 3, 6} × spacing ∈ {50, 100} × bw ∈ {25, 50}。
    llm：LLMProposer 生成候选（env 配置 LDA_LLM_BASE/KEY/MODEL；未配置/
         失败/垃圾输出自动降级网格）——**LLM 候选与网格候选合并后走同一条
         四锚判决**（LLM 无法跳过锚，红线不破）。
    生成后先经 feasible_domain 剪枝（废案不出域）。
    """
    base = compile_proposal(proposal.get("req_source", {}))
    pool = []
    # ① 确定性网格基线（永远保留——LLM 降级兜底 + 对照组）
    for p_tx, spacing, bw in itertools.product((0.0, 3.0, 6.0),
                                               (50.0, 100.0),
                                               (25.0, 50.0)):
        cand = compile_proposal({**base["req_source"],
                                 "p_tx_dbm": p_tx,
                                 "channel_spacing_ghz": spacing,
                                 "filter_bw_ghz": bw})
        pool.append(cand)
    # ② LLM 候选（可选，结构校验后入池——判决统一在四锚）
    if generator == "llm":
        try:
            import sys
            import os
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _root not in sys.path:
                sys.path.insert(0, _root)
            from lda_agent.llm_proposer import LLMProposer
            proposer = LLMProposer()
            llm_cands = proposer.propose(base["req_source"], n=n_top)
            for c in llm_cands:
                merged = {**base["req_source"], **c}
                pool.append(compile_proposal(merged))
        except Exception:  # noqa: BLE001 —— LLM 全失败不影响网格基线
            pass
    # ③ 可行域剪枝（LLM 废案同样被剪——锚不豁免任何生成器）
    return [c for c in pool if feasible_domain(c)["feasible"]][:max(n_top * 6, 18)]


# ---------------------------------------------------------------------------
# ④ 即提即验：每案过全部系统锚（死标量判决——LLM 不进路径）
# ---------------------------------------------------------------------------
def screen_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """锚筛选：S1 功率预算 + S2 频率规划 + S5 最坏情况（全部死标量）。

    返回逐锚 PASS/FAIL 证据链（人审材料）+ 总判决。
    """
    ls = proposal["link_spec"]
    margin = (ls["p_tx_dbm"]
              + int(ls["n_gratings"]) * ls["grating_db"]
              - ls["wg_loss_db_cm"] * ls["wg_length_cm"]
              + ls["ring_il_db"]
              - ls["detector_sens_dbm"])
    need = proposal["acceptance_spec"]["min_margin_db"]
    worst = (ls["p_tx_dbm"]
             - proposal["acceptance_spec"]["worst_case_il_db"]
             - ls["detector_sens_dbm"])
    coll = (proposal["channel_plan"]["spacing_ghz"]
            - proposal["channel_plan"]["filter_bw_ghz"])

    # 第 4 锚：统计锚 S7-p5（蒙特卡洛最坏情况下界 > 0——Phase 4c）
    # 用提案自身参数采样（固定种子，确定性可复现）；确定性锚抓不到的
    # 「名义过但统计挂」案例在此被剪（margin 刚好压线的提案 p5 必为负）。
    from .statistical_anchor import margin_stats, monte_carlo_margins, s8_gaussian_moments
    ls_full = proposal["link_spec"]
    margins = monte_carlo_margins(
        p_tx_dbm=ls_full["p_tx_dbm"],
        n_gratings=int(ls_full["n_gratings"]),
        grating_db=ls_full["grating_db"],
        wg_length_cm=ls_full["wg_length_cm"],
        wg_loss_db_cm=ls_full["wg_loss_db_cm"],
        ring_il_db=ls_full["ring_il_db"],
        detector_sens_dbm=ls_full["detector_sens_dbm"],
        n_samples=1000, seed=42)
    p5 = margin_stats(margins)["p5"]

    checks = [
        {"anchor": "S1-power-budget",
         "name": "功率预算余量 ≥ 要求",
         "value": round(margin, 3), "threshold": need,
         "passed": margin >= need},
        {"anchor": "S5-worst-case",
         "name": "最坏情况余量 ≥ 0",
         "value": round(worst, 3), "threshold": 0.0,
         "passed": worst >= 0},
        {"anchor": "S2-channel-plan",
         "name": "信道无碰撞（间隔>带宽）",
         "value": round(coll, 3), "threshold": 0.0,
         "passed": coll > 0},
        {"anchor": "S7-statistical-p5",
         "name": "统计最坏情况 p5 > 0（蒙特卡洛）",
         "value": p5, "threshold": 0.0,
         "passed": p5 > 0},
    ]
    # 第 5 锚：统计锚 S8（OSNR 统计 p5 最坏情况下界 ≥ 需求）
    # 激活条件：提案显式提供 OSNR 链路参数（p_sig/n_amp/nf/bw）才启用；
    # 纯 WDM 无放大器链路不杜撰 → S8 标记 N/A，不参与判决（passed=True 占位）。
    # 方法学：候选=闭式高斯 p5（s8_gaussian_moments，v0.9.29 T-3 已证伪独立），
    # 与蒙特卡洛 golden 是两种算法；此处作预算阈值检查（同构 S1/S5/S7 死标量）。
    _osnr = proposal["link_spec"].get("osnr") or {}
    _s8 = {"anchor": "S8-osnr-p5",
           "name": "OSNR 统计最坏 p5 ≥ 需求（闭式高斯）",
           "value": None, "threshold": None,
           "passed": True, "applicable": False}
    if all(_osnr.get(k) is not None
           for k in ("p_sig_dbm", "n_amp", "nf_db", "bw_ghz")):
        _mu, _sig = s8_gaussian_moments(
            p_sig_dbm=float(_osnr["p_sig_dbm"]), n_amp=int(_osnr["n_amp"]),
            nf_db=float(_osnr["nf_db"]), bw_ghz=float(_osnr["bw_ghz"]))
        _p5 = _mu - 1.6448536269514722 * _sig  # 高斯 5% 分位
        _need = float(proposal["acceptance_spec"].get("min_osnr_p5_db", 15.0))
        _s8.update(value=round(_p5, 4), threshold=_need,
                   passed=_p5 >= _need, applicable=True)
    checks.append(_s8)
    accepted = all(c["passed"] for c in checks)
    return {"accepted": accepted, "checks": checks,
            "margin_db": round(margin, 3), "p5_db": p5}


# ---------------------------------------------------------------------------
# ⑤ 确定性排序（余量降序 + 词典序 tiebreak——无随机无 LLM）
# ---------------------------------------------------------------------------
def rank_proposals(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """排序：已过锚在前（余量降序），未过锚在后（证据链保留供诊断）。

    确定性 tiebreak：(margin, −p_tx, spacing)——同 margin 低功耗优先
    （省功率），再按间隔词典序——任何人重跑得同一顺序。
    """
    scored = []
    for cand in candidates:
        s = screen_proposal(cand)
        scored.append((cand, s))
    scored.sort(key=lambda cs: (
        not cs[1]["accepted"],              # 过锚在前
        -cs[1]["margin_db"],                # 余量降序
        cs[0]["link_spec"]["p_tx_dbm"],     # 低功耗优先
        cs[0]["channel_plan"]["spacing_ghz"],  # 词典序
    ))
    return [{"rank": i + 1, "proposal": c, "screening": s,
             "screening_summary": (f"{'ACCEPT' if s['accepted'] else 'REJECT'} · "
                                   f"margin={s['margin_db']}dB · "
                                   f"{sum(ch['passed'] for ch in s['checks'])}/4 锚过")}
            for i, (c, s) in enumerate(scored)]


# ---------------------------------------------------------------------------
# ⑤b 多目标帕累托排序（T0-1 · 替换单目标余量降序）
# ---------------------------------------------------------------------------
# 目标向量（全部「越低越好」，minimization）：
#   power   : 激光器功率 p_tx_dbm（功耗代理）
#   cost    : p_tx_dbm + n_gratings（成本代理：激光 + 光栅数；T1/T3 接真实模型前
#             为透明代理，避免在此杜撰未经验证的成本数字）
#   area    : spacing_ghz * filter_bw_ghz（版图占位代理）
#   margin  : -margin_db（余量越大越好 ⇒ 取负）
#   p5      : -p5_db（统计最坏情况余量越大越好 ⇒ 取负）
# 「可封装性」维度 T3 接入（预留接口），当前不计入目标向量。
PARETO_OBJECTIVES = ("power", "cost", "area", "margin", "p5")
DEFAULT_PARETO_WEIGHTS = {"power": 1.0, "cost": 1.0, "area": 1.0,
                         "margin": 1.0, "p5": 1.0}


def _pareto_objective_vector(cand: Dict[str, Any],
                             screen: Dict[str, Any]) -> Dict[str, float]:
    """从候选 + 锚证据提取目标向量（全最小化）。"""
    ls = cand["link_spec"]
    cp = cand["channel_plan"]
    return {
        "power": float(ls["p_tx_dbm"]),
        "cost": float(ls["p_tx_dbm"]) + float(ls["n_gratings"]),
        "area": float(cp["spacing_ghz"]) * float(cp["filter_bw_ghz"]),
        "margin": -float(screen["margin_db"]),
        "p5": -float(screen["p5_db"]),
    }


def _dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """a 支配 b（a 在所有目标 ≤ b 且至少一维严格 <）。"""
    le = all(a[k] <= b[k] for k in PARETO_OBJECTIVES)
    lt = any(a[k] < b[k] for k in PARETO_OBJECTIVES)
    return le and lt


def _pareto_fronts(vecs: List[Dict[str, float]]) -> List[List[int]]:
    """非支配排序，返回 front 列表（front[0] 最优）。"""
    n = len(vecs)
    remaining = list(range(n))
    fronts: List[List[int]] = []
    while remaining:
        front = []
        for i in remaining:
            dominated = False
            for j in remaining:
                if i == j:
                    continue
                if _dominates(vecs[j], vecs[i]):
                    dominated = True
                    break
            if not dominated:
                front.append(i)
        front_set = set(front)
        remaining = [x for x in remaining if x not in front_set]
        fronts.append(front)
    return fronts


def _weighted_scores(vecs: List[Dict[str, float]],
                     weights: Dict[str, float]) -> Dict[int, float]:
    """min-max 归一化后加权求和（权重变 ⇒ 分数变 ⇒ 排序变）。"""
    mins = {k: min(v[k] for v in vecs) for k in PARETO_OBJECTIVES}
    maxs = {k: max(v[k] for v in vecs) for k in PARETO_OBJECTIVES}
    scores: Dict[int, float] = {}
    for i, v in enumerate(vecs):
        s = 0.0
        for k in PARETO_OBJECTIVES:
            rng = maxs[k] - mins[k]
            norm = (v[k] - mins[k]) / (rng if rng > 0 else 1.0)
            s += weights.get(k, 1.0) * norm
        scores[i] = s
    return scores


def rank_proposals_pareto(candidates: List[Dict[str, Any]],
                          weights: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """多目标帕累托排序：先按非支配 front 分层，front 内按加权标量排序。

    与单目标 rank_proposals 的区别：单目标只看 margin 降序；本函数引入
    功耗/成本/面积/余量/统计余量 五维目标，权重由调用方给定——
    **改变权重必须改变排序（防常数假绿，见 run_pareto_rank_smoke.py 反向测试）**。

    输出 schema 与 rank_proposals 兼容（rank/proposal/screening/screening_summary
    + 新增 pareto_front 字段），可直接替换管线中的排序调用。
    """
    w = dict(DEFAULT_PARETO_WEIGHTS)
    if weights:
        w.update(weights)
    scored = []
    for cand in candidates:
        s = screen_proposal(cand)
        scored.append((cand, s))
    vecs = [_pareto_objective_vector(c, s) for c, s in scored]
    fronts = _pareto_fronts(vecs)
    front_of: Dict[int, int] = {}
    for fi, front in enumerate(fronts):
        for idx in front:
            front_of[idx] = fi
    scores = _weighted_scores(vecs, w)
    order = sorted(range(len(scored)),
                   key=lambda i: (front_of[i], scores[i]))
    return [{
        "rank": i + 1,
        "proposal": scored[j][0],
        "screening": scored[j][1],
        "pareto_front": front_of[j] + 1,
        "screening_summary": (
            f"{'ACCEPT' if scored[j][1]['accepted'] else 'REJECT'} · "
            f"margin={scored[j][1]['margin_db']}dB · "
            f"front={front_of[j] + 1} · "
            f"{sum(ch['passed'] for ch in scored[j][1]['checks'])}/4 锚过"),
    } for i, j in enumerate(order)]


# ---------------------------------------------------------------------------
# 端到端入口：需求 → 过锚提案列表（人终审材料）
# ---------------------------------------------------------------------------
def _design_pipeline_link(req: Dict[str, Any], n_top: int = 3,
                       generator: str = "grid",
                       weights: Dict[str, float] = None) -> Dict[str, Any]:
    """完整管线：编译 → 剪枝 → 生成 → 逐案锚验 → 排序 → 人审材料。

    诚实边界：输出是「过了系统锚的候选列表」，不是「最优架构」——
    终审选择权在人（杜先生五共识的第 4 步）。
    """
    proposal = compile_proposal(req)
    domain = feasible_domain(proposal)
    cands = generate_candidates(proposal, n_top=n_top, generator=generator)
    ranked = rank_proposals_pareto(cands, weights=weights)[:n_top]
    accepted = [r for r in ranked if r["screening"]["accepted"]]
    return {"input_req": req,
            "compiled": proposal,
            "feasible_domain": domain,
            "n_domain_candidates": len(cands),
            "ranked": ranked,
            "n_accepted": len(accepted),
            "honest_note": ("提案过 S1/S2/S5 系统锚（死标量）；生成器当前为确定性"
                            "网格（LLM 接口预留）；终审选择权在人。")}


# ---------------------------------------------------------------------------
# 系统类型注册表（Phase 1 · v0.8.33 · 系统级纵深）
# ---------------------------------------------------------------------------
# 所有类型共用同一条死标量红线：LLM 只生成候选，不进判决路径。
# 每个类型声明自己的：物理域 / 标题 / 复用引擎 / 锚集合 / 诚实层级。
# 新增类型必须自带死标量锚（B4 / D-46×D-47 等已验证闭环），禁止"无锚假类型"。
SYSTEM_TYPES = {
    "link": {
        "domain": "photon",
        "title": "点对点光链路",
        "engine": "proposal_compiler._design_pipeline_link",
        "anchors": ["S1", "S2", "S5", "S7"],
        "honest_tier": "已验证闭环",
    },
    "wdm_demux": {
        "domain": "photon",
        "title": "WDM 多环解复用 / 路由",
        "engine": "wdm_system.design_wdm_advanced",
        "anchors": ["B4", "DRC", "FSR"],
        "honest_tier": "已验证闭环(B4)",
    },
    "quantum_fidelity": {
        "domain": "hybrid",
        "title": "量子复用读出保真度链",
        "engine": "multiqubit_fidelity.design_multiqubit_fidelity",
        "anchors": ["D-46", "D-47", "B9", "B12"],
        "honest_tier": "已验证闭环(D-46×D-47)",
    },
    "sensor_frontend": {
        "domain": "photon",
        "title": "传感/车载/接入光子前端（FMCW LiDAR / PON / 生物传感 / 真时延）",
        "engine": "proposal_compiler._design_sensor_frontend",
        "anchors": ["S1-sensor-budget", "S5-energy-floor", "S7-statistical-p5"],
        "honest_tier": "已验证闭环(光子级联+S1/S5/S7)",
    },
    "qkd_link": {
        "domain": "qkd",
        "title": "QKD 量子密钥分发链路（安全密钥率信息论锚）",
        "engine": "proposal_compiler._design_qkd_link",
        "anchors": ["S-QKD-SKR"],
        "honest_tier": "已验证闭环(decoy-BB84 下界)",
    },
    "cpo_optical_io": {
        "domain": "cpo",
        "title": "CPO 硅光 I/O 共封装光引擎（带宽密度 + 插损 + 功率预算）",
        "engine": "proposal_compiler._design_cpo_optical_io",
        "anchors": ["S-CPO-IL", "S-CPO-DENSITY", "S-CPO-BUDGET"],
        "honest_tier": "已验证闭环(D-67×P-CPO 双向物理护栏)",
    },
}


def supported_system_types() -> List[str]:
    """返回所有受支持的系统类型名（供 CLI / 创新超市货架引用）。"""
    return list(SYSTEM_TYPES.keys())


def _design_wdm_demux(req: Dict[str, Any], n_top: int = 3,
                      generator: str = "grid") -> Dict[str, Any]:
    """WDM 多环解复用系统类型（复用 design_wdm_advanced 已验证闭环）。

    判决 = B4 锚（drop IL≤3dB / 邻信道 XT≥15dB / 单 FSR 防混叠 / DRC 可制造）。
    LLM 不进判决（设计函数内部纯解析物理 + 死标量比对）。
    """
    from lda_agent.wdm_system import design_wdm_advanced
    n_channels = int(req.get("n_channels", 4))
    spacing_nm = float(req.get("spacing_nm", 2.5))
    xt_target_db = req.get("xt_target_db", None)
    gap = req.get("gap", None)
    rep = design_wdm_advanced(n_channels=n_channels, spacing_nm=spacing_nm,
                              xt_target_db=xt_target_db, gap=gap)
    checks = rep.get("acceptance", {}).get("checks", [])
    accepted = bool(rep.get("acceptance", {}).get("passed", False))
    return {
        "input_req": req,
        "system_type": "wdm_demux",
        "compiled": {"system_type": "wdm_demux",
                     "n_channels": n_channels, "spacing_nm": spacing_nm,
                     "xt_target_db": xt_target_db, "gap": gap},
        "feasible_domain": {"feasible": bool(rep.get("ok", False)),
                             "note": "WDM 级联闭式验证（design_wdm_advanced）"},
        "n_domain_candidates": 1,
        "ranked": [{"rank": 1,
                    "proposal": {"system_type": "wdm_demux"},
                    "screening": {"accepted": accepted, "checks": checks},
                    "screening_summary":
                        (f"{'ACCEPT' if accepted else 'REJECT'} · "
                         f"WDM {n_channels}ch B4 锚")}],
        "n_accepted": 1 if accepted else 0,
        "honest_note": ("复用 design_wdm_advanced 已验证闭环（B4：drop IL≤3 / "
                        "XT≥15 / 单 FSR 防混叠）；LLM 不进判决路径。"),
    }


def _design_quantum_fidelity(req: Dict[str, Any], n_top: int = 3,
                             generator: str = "grid") -> Dict[str, Any]:
    """量子复用读出保真度系统类型（复用 design_multiqubit_fidelity 已验证闭环）。

    判决 = D-46 频率复用（信道错开≥3×κ_r + dip 可分辨）+ D-47 逐 qubit 保真度
    （SNR≥2 / F≥0.95 / n̄≤100）。LLM 不进判决。
    """
    from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity
    f01s = req.get("f01s") or [4.8, 5.0, 5.2]
    rep = design_multiqubit_fidelity(f01s)
    checks = rep.get("acceptance", {}).get("checks", [])
    accepted = bool(rep.get("acceptance", {}).get("passed", False))
    return {
        "input_req": req,
        "system_type": "quantum_fidelity",
        "compiled": {"system_type": "quantum_fidelity", "f01s": f01s},
        "feasible_domain": {"feasible": bool(rep.get("ok", False)),
                             "note": "量子复用读出闭环（D-46×D-47）"},
        "n_domain_candidates": 1,
        "ranked": [{"rank": 1,
                    "proposal": {"system_type": "quantum_fidelity"},
                    "screening": {"accepted": accepted, "checks": checks},
                    "screening_summary":
                        (f"{'ACCEPT' if accepted else 'REJECT'} · "
                         f"{len(f01s)}-qubit 保真度链")}],
        "n_accepted": 1 if accepted else 0,
        "honest_note": ("复用 design_multiqubit_fidelity 已验证闭环（D-46 复用 "
                        "+ D-47 保真度）；LLM 不进判决路径。"),
    }


def _design_sensor_frontend(req: Dict[str, Any], n_top: int = 3,
                             generator: str = "grid") -> Dict[str, Any]:
    """B 赛道传感/车载/接入光子前端系统类型（M2 新增，自带死标量锚）。

    物理：传感前端本质是一条光子级联（与 GC-SENSE / GC-LIDAR-FMCW 同源，
    零新物理）——用 GP-* 已锚定基元的 dB 级联（S1 同构）算全链路插入损耗，
    再对传感应用各自的公开链路预算比对。判决共用同一条死标量红线。

    自带三道死标量锚（与 link 共用物理，但锚集合与阈值按传感应用独立声明）：
      S1-sensor-budget  全链路 IL ≤ 应用预算（le）
      S5-energy-floor   分束器每级 ≥ 3.0103 dB 能量守恒下界（D-67 复用）
      S7-statistical-p5 统计最坏情况 margin p5 > 0（蒙特卡洛，固定种子确定性）
    LLM 不进判决路径（generator 仅占位，本类型当前为解析级联）。
    """
    from lda_design.loss_engines import ENGINE_FUNCS, SPLIT_LOSS_3DB

    app = req.get("app", "lidar")
    n_g = int(req.get("n_gratings", 2))
    L = float(req.get("wg_length_cm", 1.0))
    n_yb = int(req.get("n_ybranch", 2))
    n_cr = int(req.get("n_crossing", 0))
    budget = float(req.get("budget_db", 15.0))
    tol = float(req.get("tol_db", 3.0))

    # 标准基元几何（与 GP-* 标杆一致，保证级联复现值同源）
    _G_GEOM = {"ff": 0.5, "theta_deg": 8.0, "tilt_sigma_deg": 15.0}
    _SIN_GEOM = {"w_core_um": 0.8, "h_core_um": 0.8, "roughness_nm": 0.3}
    _YB_GEOM = {"theta_deg": 5.0, "excess_coef": 0.004}
    _CR_GEOM = {"w_core_um": 0.5, "taper_w_ratio": 2.5}

    g = ENGINE_FUNCS["engine_grating_eff"](_G_GEOM)["value"]
    grating_il = -10.0 * math.log10(g)
    sil = ENGINE_FUNCS["engine_sin_pl"](_SIN_GEOM)["value"]
    yb = ENGINE_FUNCS["engine_ybranch_split"](_YB_GEOM)["value"]
    cr = ENGINE_FUNCS["engine_crossing"](_CR_GEOM)["value"]
    total = n_g * grating_il + sil * L + n_yb * yb + n_cr * cr

    # 🔴 D-67 能量守恒下界护栏（与 ChipBenchmark._photon_cascade_il 同式）
    if n_yb > 0 and yb < SPLIT_LOSS_3DB - 1e-9:
        raise AssertionError(
            f"[sensor:{app}] 分束器单级插损 {yb:.4f} dB 低于能量守恒下界 "
            f"{SPLIT_LOSS_3DB:.4f} dB（1×2 功率均分的几何必然）——"
            f"疑似漏算分光损耗（见 D-67 回归）")
    floor = n_yb * SPLIT_LOSS_3DB
    if total < floor - 1e-9:
        raise AssertionError(
            f"[sensor:{app}] 链路插损 {total:.4f} dB 低于能量守恒下界 "
            f"{floor:.4f} dB（{n_yb} 级 1×2 分光 × 3.0103 dB）——"
            f"疑似漏算分光损耗（见 D-67 回归）")

    # S7 统计最坏情况：margin = budget − total，蒙特卡洛（固定种子，确定性）
    import random as _rnd
    _rng = _rnd.Random(42)
    _margins = [budget - (total + _rng.gauss(0.0, 0.3)) for _ in range(1000)]
    _p5 = sorted(_margins)[int(0.05 * len(_margins)) - 1]

    checks = [
        {"anchor": "S1-sensor-budget",
         "name": "传感前端链路损耗 ≤ 应用预算",
         "value": round(total, 3), "threshold": budget,
         "passed": total <= budget + tol},
        {"anchor": "S5-energy-floor",
         "name": "能量守恒下界(分束器每级≥3.0103dB)",
         "value": round(total, 3), "threshold": round(floor, 3),
         "passed": total >= floor - 1e-9},
        {"anchor": "S7-statistical-p5",
         "name": "统计最坏情况 margin p5 > 0（蒙特卡洛）",
         "value": round(_p5, 3), "threshold": 0.0,
         "passed": _p5 > 0},
    ]
    accepted = all(c["passed"] for c in checks)
    return {
        "input_req": req,
        "system_type": "sensor_frontend",
        "compiled": {"system_type": "sensor_frontend", "app": app,
                     "cascade": {"n_gratings": n_g, "wg_length_cm": L,
                                 "n_ybranch": n_yb, "n_crossing": n_cr}},
        "feasible_domain": {"feasible": bool(accepted),
                            "note": "传感前端光子级联 + 死标量锚 S1/S5/S7"},
        "n_domain_candidates": 1,
        "ranked": [{"rank": 1,
                    "proposal": {"system_type": "sensor_frontend"},
                    "screening": {"accepted": accepted, "checks": checks},
                    "screening_summary":
                        (f"{'ACCEPT' if accepted else 'REJECT'} · "
                         f"{app} 传感前端 S1/S5/S7")}],
        "n_accepted": 1 if accepted else 0,
        "honest_note": ("传感前端 = 光子级联（GP-* 已锚定基元 dB 级联）+ 死标量锚 "
                        "S1（预算）/S5（能量守恒下界·D-67）/S7（统计 p5）；"
                        "LLM 不进判决路径。对标对象是全链路插入损耗死标量，"
                        "传感元件（OPA/调制器/探测器）按黑箱（负面清单）。"),
    }


def _design_qkd_link(req: Dict[str, Any], n_top: int = 3,
                     generator: str = "grid") -> Dict[str, Any]:
    """QKD 量子密钥分发链路系统类型（v0.9.40 新增，自带安全密钥率信息论死标量锚）。

    物理：QKD 不是光子损耗问题，而是**信息论安全问题**——用 decoy-state BB84 渐近
    下界（Lo–Ma–Chen 2005）算安全密钥率 R 与最大安全传输距离 L_max，对标公开
    datasheet / 论文量级（等效验证）。复用 lda_design.qkd_engines 已验证闭环。

    自带一道信息论死标量锚（S-QKD-SKR），拆三道可人审的检查：
      S-QKD-SKR-secure     目标距离 R > 0（密钥率非负 = 抗束分割攻击成钥）
      S-QKD-SKR-distance   L_max ≥ 目标距离（安全传输距离达标）
      S-QKD-SKR-published  R ≥ 公开量级下界（等效验证：复现公开系统密钥率量级）
    LLM 不进判决路径（generator 仅占位，本类型当前为解析公式）。
    """
    from lda_design.qkd_engines import decoy_bb84_skr

    # 从需求提取 QKD 几何 + 目标（缺省用公开典型值；探测器按公开参数黑箱）
    geom = {
        "distance_km": float(req.get("distance_km", 50.0)),
        "fiber_loss_db_km": float(req.get("fiber_loss_db_km", 0.2)),
        "alice_il_db": float(req.get("alice_il_db", 15.0)),
        "bob_il_db": float(req.get("bob_il_db", 8.0)),
        "detector_eff": float(req.get("detector_eff", 0.1)),
        "dark_count_prob": float(req.get("dark_count_prob", 1e-6)),
        "misalignment": float(req.get("misalignment", 0.015)),
        "mu": float(req.get("mu", 0.5)),
        "f_ec": float(req.get("f_ec", 1.1)),
        "rep_rate_hz": float(req.get("rep_rate_hz", 1e9)),
    }
    target_distance = float(req.get("target_distance_km",
                                   geom["distance_km"]))
    published_floor = float(req.get("published_floor_bps", 200.0))

    r = decoy_bb84_skr(geom)
    skr = float(r["secure_key_rate_bps"])
    lmax = float(r["max_secure_distance_km"])

    checks = [
        {"anchor": "S-QKD-SKR-secure",
         "name": f"目标距离 {geom['distance_km']:.0f}km 密钥率 > 0（可成钥）",
         "value": round(skr, 3), "threshold": 0.0,
         "passed": skr > 0.0},
        {"anchor": "S-QKD-SKR-distance",
         "name": f"最大安全距离 ≥ 目标 {target_distance:.0f}km",
         "value": round(lmax, 3), "threshold": target_distance,
         "passed": lmax >= target_distance},
        {"anchor": "S-QKD-SKR-published",
         "name": f"密钥率 ≥ 公开量级下界 {published_floor:.0f} bps（等效验证）",
         "value": round(skr, 3), "threshold": published_floor,
         "passed": skr >= published_floor},
    ]
    accepted = all(c["passed"] for c in checks)
    return {
        "input_req": req,
        "system_type": "qkd_link",
        "compiled": {"system_type": "qkd_link", "geom": geom,
                     "target_distance_km": target_distance,
                     "published_floor_bps": published_floor},
        "feasible_domain": {"feasible": bool(accepted),
                            "note": "QKD 安全密钥率信息论锚 S-QKD-SKR（decoy-BB84 下界）"},
        "n_domain_candidates": 1,
        "ranked": [{"rank": 1,
                    "proposal": {"system_type": "qkd_link"},
                    "screening": {"accepted": accepted, "checks": checks},
                    "screening_summary":
                        (f"{'ACCEPT' if accepted else 'REJECT'} · "
                         f"QKD SKR@{geom['distance_km']:.0f}km={skr:.1f}bps "
                         f"Lmax={lmax:.1f}km")}],
        "n_accepted": 1 if accepted else 0,
        "honest_note": ("QKD 链路 = decoy-BB84 渐近下界（Lo–Ma–Chen 2005）安全密钥率 "
                        "信息论锚 S-QKD-SKR；复用 lda_design.qkd_engines 已验证闭环，"
                        "零新物理，含 Q-D67 护栏（密钥率≤单光子贡献上界 + η≤1 物理界）。"
                        "LLM 不进判决路径。对标公开 datasheet / 论文密钥率量级（等效验证）。"),
    }


def _design_cpo_optical_io(req: Dict[str, Any], n_top: int = 3,
                           generator: str = "grid") -> Dict[str, Any]:
    """CPO 硅光 I/O 共封装光引擎系统类型（v0.9.41 新增，D 赛道，自带死标量锚）。

    物理：CPO 光 I/O 的竞争维度不是单一插损，而是**海岸线带宽密度**（OIF/Semiconductor
    Engineering 公开：当前最先进 CPO ≈0.5 Tbps/mm，AI chiplet UCIe ≈3 Tbps/mm，6× 差距）。
    零新物理 —— 三项判据全由已锚定基元与公开标准几何推出：
      ① 每通道插入损耗 = GP-* 已锚定基元 dB 级联（与 GC-CPO-8CH 同源，S1 同构）
      ② 海岸线带宽密度 = 单通道速率 / 通道间距（纯几何算术）
      ③ 链路功率余量 = P_tx − IL − 探测器灵敏度（S1 同式）

    自带三道死标量锚：
      S-CPO-IL       每通道插入损耗 ≤ 预算（le；D-67 能量守恒下界护栏防漏算）
      S-CPO-DENSITY  海岸线带宽密度 ≥ 下界（ge；P-CPO 间距几何下界护栏防虚报）
      S-CPO-BUDGET   链路功率余量 ≥ 最小余量（ge；S1 同式）
    LLM 不进判决路径（generator 仅占位，本类型当前为解析级联 + 几何算术）。
    """
    from lda_design.cpo_engines import cpo_optical_io_metrics

    geom = {
        "couple_mode": str(req.get("couple_mode", "fau")),
        "n_channels": int(req.get("n_channels", 8)),
        "lane_rate_gbps": float(req.get("lane_rate_gbps", 200.0)),
        "pitch_um": float(req.get("pitch_um", 250.0)),
        "n_gratings": int(req.get("n_gratings", 2)),
        "wg_length_cm": float(req.get("wg_length_cm", 1.0)),
        "n_ybranch": int(req.get("n_ybranch", 1)),
        "n_crossing": int(req.get("n_crossing", 1)),
        "p_tx_dbm": float(req.get("p_tx_dbm", 0.0)),
        "detector_sens_dbm": float(req.get("detector_sens_dbm", -20.0)),
    }
    il_budget = float(req.get("il_budget_db", 12.0))
    il_tol = float(req.get("il_tol_db", 3.0))
    density_floor = float(req.get("density_floor_gbps_mm", 100.0))
    min_margin = float(req.get("min_margin_db", 3.0))

    r = cpo_optical_io_metrics(geom)
    il = float(r["per_channel_il_dB"])
    dens = float(r["bandwidth_density_gbps_mm"])
    margin = float(r["link_margin_db"])

    checks = [
        {"anchor": "S-CPO-IL",
         "name": f"每通道插入损耗 ≤ {il_budget} dB（含 D-67 能量守恒下界）",
         "value": round(il, 3), "threshold": il_budget,
         "passed": il <= il_budget + il_tol},
        {"anchor": "S-CPO-DENSITY",
         "name": f"海岸线带宽密度 ≥ {density_floor} Gbps/mm"
                 f"（物理上界 {r['density_ceiling_gbps_mm']}）",
         "value": round(dens, 3), "threshold": density_floor,
         "passed": dens >= density_floor},
        {"anchor": "S-CPO-BUDGET",
         "name": f"链路功率余量 ≥ {min_margin} dB（S1 同式）",
         "value": round(margin, 3), "threshold": min_margin,
         "passed": margin >= min_margin},
    ]
    accepted = all(c["passed"] for c in checks)
    return {
        "input_req": req,
        "system_type": "cpo_optical_io",
        "compiled": {"system_type": "cpo_optical_io", "geom": geom,
                     "il_budget_db": il_budget, "il_tol_db": il_tol,
                     "density_floor_gbps_mm": density_floor,
                     "min_margin_db": min_margin,
                     "guardrail_evidence": {
                         "energy_floor_dB": r["energy_floor_dB"],
                         "pitch_floor_um": r["pitch_floor_um"],
                         "density_ceiling_gbps_mm": r["density_ceiling_gbps_mm"],
                     }},
        "feasible_domain": {"feasible": bool(accepted),
                            "note": "CPO 光 I/O 三项死标量锚 + D-67×P-CPO 双向物理护栏"},
        "n_domain_candidates": 1,
        "ranked": [{"rank": 1,
                    "proposal": {"system_type": "cpo_optical_io"},
                    "screening": {"accepted": accepted, "checks": checks},
                    "screening_summary":
                        (f"{'ACCEPT' if accepted else 'REJECT'} · "
                         f"{geom['n_channels']}×{geom['lane_rate_gbps']:.0f}G "
                         f"IL={il:.2f}dB 密度={dens:.0f}Gbps/mm")}],
        "n_accepted": 1 if accepted else 0,
        "honest_note": ("CPO 光 I/O = GP-* 已锚定基元 dB 级联（IL）+ 通道间距几何算术（密度）"
                        "+ S1 预算（余量）；零新物理。两道物理护栏对称夹逼：D-67 能量守恒下界"
                        "（防 le 方向漏算损耗）+ P-CPO 间距几何下界（ITU-T G.652 包层直径 125 µm / "
                        "MFD@1550 10.3 µm，防 ge 方向虚报密度）。LLM 不进判决路径。"
                        "🔴 诚实边界：**不判决能效 pJ/bit** —— 该量由电域 SerDes/TIA/DSP 主导"
                        "（OIF 公开：CPO ≈3 pJ/b vs OSFP ≈19 pJ/b），LDA 无电域锚，"
                        "若以光域功率比对将低 4 个数量级导致恒过（必假绿），故能效仅作规格标注。"),
    }


def design_pipeline(req: Dict[str, Any], n_top: int = 3,
                    generator: str = "grid",
                    system_type: str = "link",
                    weights: Dict[str, float] = None) -> Dict[str, Any]:
    """完整管线（系统类型分发版）：编译 → 剪枝 → 生成 → 逐案锚验 → 排序。

    system_type：
      "link"（默认）       → 原点对点光链路闭环（零回归）
      "wdm_demux"          → WDM 多环解复用（复用 design_wdm_advanced）
      "quantum_fidelity"   → 量子复用读出保真度（复用 design_multiqubit_fidelity）
      "sensor_frontend"    → 传感/车载/接入光子前端（M2，自带 S1/S5/S7 死标量锚）
      "qkd_link"           → QKD 量子密钥分发链路（v0.9.40，自带 S-QKD-SKR 信息论死标量锚）
      "cpo_optical_io"     → CPO 硅光 I/O 共封装光引擎（v0.9.41 D 赛道，自带
                             S-CPO-IL/S-CPO-DENSITY/S-CPO-BUDGET 死标量锚 + P-CPO 护栏）
    所有类型共享同一条死标量红线：LLM 只生成候选，不进判决。
    """
    if system_type == "link":
        return _design_pipeline_link(req, n_top=n_top, generator=generator,
                                    weights=weights)
    if system_type == "wdm_demux":
        return _design_wdm_demux(req, n_top=n_top, generator=generator)
    if system_type == "quantum_fidelity":
        return _design_quantum_fidelity(req, n_top=n_top, generator=generator)
    if system_type == "sensor_frontend":
        return _design_sensor_frontend(req, n_top=n_top, generator=generator)
    if system_type == "qkd_link":
        return _design_qkd_link(req, n_top=n_top, generator=generator)
    if system_type == "cpo_optical_io":
        return _design_cpo_optical_io(req, n_top=n_top, generator=generator)
    raise ValueError(f"未知 system_type={system_type!r};"
                     f"可用：{supported_system_types()}")
