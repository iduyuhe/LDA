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
  - 锚覆盖 S1/S2/S5（功率/频率/最坏情况）——统计锚（S7/S8）留作
    提案筛选的下一层（Phase 4 后续）；
  - 人终审：输出 ranked 提案列表 + 逐案锚证据，选择权在人。
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List, Tuple

# ---- 行为级黑箱参数（system_budget 同源，文献典型值） ----
GRATING_DB = -3.0
WG_LOSS_DB_CM = 3.0
RING_IL_DB = -0.5
DETECTOR_SENS_DBM = -20.0


# ---------------------------------------------------------------------------
# ① 功能需求 → 结构化提案（编译入口）
# ---------------------------------------------------------------------------
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
        },
        "acceptance_spec": {
            "min_margin_db": float(req.get("link_budget_db", 3.0)),
            "worst_case_il_db": 10.0,  # S5 同式（SS 角最坏插损合计）
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
                        n_top: int = 3) -> List[Dict[str, Any]]:
    """在可行域内生成候选（功率×信道间隔×滤波带宽 网格）。

    MVP 确定性网格扫描：p_tx ∈ {0, 3, 6} dBm × spacing ∈ {50, 100} GHz
    × bw ∈ {25, 50} GHz——每个候选携带完整 link_spec 供锚验。
    生成后先经 feasible_domain 剪枝（废案不出域）。
    """
    base = compile_proposal(proposal.get("req_source", {}))
    grid = []
    for p_tx, spacing, bw in itertools.product((0.0, 3.0, 6.0),
                                               (50.0, 100.0),
                                               (25.0, 50.0)):
        cand = compile_proposal({**base["req_source"],
                                 "p_tx_dbm": p_tx,
                                 "channel_spacing_ghz": spacing,
                                 "filter_bw_ghz": bw})
        dom = feasible_domain(cand)
        if dom["feasible"]:
            grid.append(cand)
    return grid[: max(n_top * 4, 12)]  # 域内候选池（排序前）


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
    ]
    accepted = all(c["passed"] for c in checks)
    return {"accepted": accepted, "checks": checks,
            "margin_db": round(margin, 3)}


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
                                   f"{sum(ch['passed'] for ch in s['checks'])}/3 锚过")}
            for i, (c, s) in enumerate(scored)]


# ---------------------------------------------------------------------------
# 端到端入口：需求 → 过锚提案列表（人终审材料）
# ---------------------------------------------------------------------------
def design_pipeline(req: Dict[str, Any], n_top: int = 3) -> Dict[str, Any]:
    """完整管线：编译 → 剪枝 → 生成 → 逐案锚验 → 排序 → 人审材料。

    诚实边界：输出是「过了系统锚的候选列表」，不是「最优架构」——
    终审选择权在人（杜先生五共识的第 4 步）。
    """
    proposal = compile_proposal(req)
    domain = feasible_domain(proposal)
    cands = generate_candidates(proposal, n_top=n_top)
    ranked = rank_proposals(cands)[:n_top]
    accepted = [r for r in ranked if r["screening"]["accepted"]]
    return {"input_req": req,
            "compiled": proposal,
            "feasible_domain": domain,
            "n_domain_candidates": len(cands),
            "ranked": ranked,
            "n_accepted": len(accepted),
            "honest_note": ("提案过 S1/S2/S5 系统锚（死标量）；生成器当前为确定性"
                            "网格（LLM 接口预留）；终审选择权在人。")}
