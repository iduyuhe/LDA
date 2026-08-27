"""创新超市货架注册表（v0.8.34 · 创新超市 · 前瞻预研货架）。

战略落点（2026-08-27 整合规划 Phase 2）：
  在「产品级基准库」（v0.8.32 实证锚）与「系统类型注册表」（v0.8.33）之上，
  建立第三层——创新超市：把"已锚定基元 + 公开信号驱动"的**前瞻预研预设计**
  作为货架供社区挑选。

核心纪律（红线下护栏，与全局一致）：
  - LLM 只生成候选拓扑/默认参数，绝不写判决逻辑（判决 = 锚）；
  - 货架 = 预填的 SYSTEM_TYPES 实例 + 已锚定基元 composition；
  - honest_tier 强制 = "前瞻预研"，CI 绝不输出"已流片验证"字样；
  - 信号源须可溯源（roadmap 文献 / 标准草案 / 厂商公开产品动向）；
  - 组合创新：货架仅由"已锚定基元"组装，任何含未锚定基元的货架 CI 直接拒。

落点：A/B 阶段内，纯内部+公开信号，不碰 C 闸门。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                          # 本目录（lda_l2）
sys.path.insert(0, os.path.dirname(_HERE))         # 父目录（lda，含 lda_harness/lda_l2/lda_agent）

from lda_harness.proposal_compiler import (
    design_pipeline, SYSTEM_TYPES,
)
from lda_l2.golden_product_benchmarks import DEFAULT_BENCHMARKS

GOLDEN_IDS = {b.product_id for b in DEFAULT_BENCHMARKS}

HONEST_TIER = "前瞻预研"
HONEST_BANNER = (
    "创新超市货架为**前瞻预研**预设计：组合已锚定基元（产品级基准库 GP-*）"
    "+ 公开信号驱动（行业 roadmap / 标准草案 / 厂商公开动向）。属等效验证"
    "（复用已锚定基元 + 系统预算不破），**非本团队流片验证**、**非对未来的承诺**。"
    "信号源可溯源；判决复用 system_type 已验证闭环，LLM 不进判决路径。"
)


@dataclass
class ShelfItem:
    """单个创新超市货架（前瞻预研预设计）。"""
    id: str                              # 货架 id（IM- 前缀）
    title: str                          # 货架标题
    target_app: str                     # 目标应用场景
    signal_ref: str                     # 公开信号来源（可溯源）
    domain: str                         # photon / hybrid / quantum（复用 IR domain）
    system_type: str                    # 引用 proposal_compiler.SYSTEM_TYPES 的 key
    composition: List[str]              # 已锚定基元 id 列表（须全部在 GOLDEN_IDS）
    default_req: Dict[str, Any]         # 传给 design_pipeline 的默认需求参数
    honest_tier: str = HONEST_TIER      # 强制 = 前瞻预研
    design_note: str = ""               # 设计说明/扩展路径（诚实标注）
    ci_status: str = ""

    def validate_composition(self) -> Dict[str, Any]:
        """校验 composition 全部为已锚定基元（红线下护栏①：禁止含未锚定基元）。"""
        unknown = [c for c in self.composition if c not in GOLDEN_IDS]
        return {"all_anchored": len(unknown) == 0, "unknown": unknown}

    def evaluate(self) -> Dict[str, Any]:
        """判决：调 design_pipeline（复用 system_type 已验证闭环）。

        返回：feasible / n_accepted / 逐锚证据链（screening）+ 货架元数据。
        LLM 不进判决路径（design_pipeline 内部纯解析 + 死标量）。
        """
        meta = {
            "id": self.id, "title": self.title,
            "target_app": self.target_app, "signal_ref": self.signal_ref,
            "composition": list(self.composition), "design_note": self.design_note,
            "honest_tier": self.honest_tier,
        }
        comp = self.validate_composition()
        if not comp["all_anchored"]:
            return {**meta, "error": f"含未锚定基元 {comp['unknown']}",
                    "feasible": False, "n_accepted": 0, "screening": None, "summary": ""}
        if self.system_type not in SYSTEM_TYPES:
            return {**meta, "error": f"system_type {self.system_type} 未注册",
                    "feasible": False, "n_accepted": 0, "screening": None, "summary": ""}
        rep = design_pipeline(self.default_req, system_type=self.system_type)
        accepted = rep.get("n_accepted", 0) >= 1
        ranked = rep.get("ranked") or [{}]
        scr = ranked[0].get("screening") if ranked else None
        feasible = bool(rep.get("feasible_domain", {}).get("feasible", False)) or accepted
        return {
            **meta,
            "system_type": self.system_type,
            "feasible": feasible and not rep.get("error"),
            "n_accepted": rep.get("n_accepted", 0),
            "screening": scr,
            "summary": ranked[0].get("screening_summary", "") if ranked else "",
        }


# ---------------------------------------------------------------------------
# 默认货架：5 个低风险高复用（直接复用已验证闭环，零新物理）
#   IM-CPO-WDM5   → 复用 wdm_demux（design_wdm_advanced, B4 锚）            [光子·WDM]
#   IM-QCHIP-INT  → 复用 quantum_fidelity（design_multiqubit_fidelity, D-46×D-47）[混合·量子]
#   IM-SENSE-RING → 复用 link（微环传感前端，S1/S2/S5/S7）                  [光子·传感]
#   IM-LASER-INT  → 复用 link（异质集成激光源=黑箱源，负面清单）             [光子·发射]
#   IM-QCOM-LINK  → 复用 quantum_fidelity（5 比特频率复用读出）             [混合·量子]
# 组合创新：货架仅由产品级基准库已锚定基元（GP-*）组装；active 器件按负面清单
# 作黑箱源（不新增未锚定基元），激光源要进锚集须先按 v0.8.32 加 golden 基准。
# ---------------------------------------------------------------------------
DEFAULT_SHELF: List[ShelfItem] = [
    ShelfItem(
        id="IM-CPO-WDM5",
        title="CPO 多通道 WDM 共封装光模块预设计（5 通道基准）",
        target_app="共封装光学（CPO）/ 数据中心光互连，单光纤多波长并行",
        signal_ref="OIF CPO 2.0 共封装光学路线图（公开草案）；业界 8× 100G/200G WDM "
                   "硅光 CPO 模组量产前夕动向（公开报道）",
        domain="photon",
        system_type="wdm_demux",
        composition=["GP-GRATING-EFF", "GP-MMI-1X2", "GP-CROSSING"],
        default_req={"n_channels": 5, "spacing_nm": 2.0},
        design_note="面向 8 通道 CPO 的预研货架；以 5ch@2.0nm 单 FSR 闭环（B4："
                    "drop IL≤3 / XT≥15 / 单 FSR 防混叠）验证基元可行性。8 通道扩展需 "
                    "FSR 扩展（更小环 R）属参数化下一迭代，不破现有已验证闭环。",
        ci_status="",
    ),
    ShelfItem(
        id="IM-QCHIP-INT",
        title="量子芯片间读出互联模板（多比特保真度链）",
        target_app="超导量子芯片读出总线 / 多比特频率复用读出链",
        signal_ref="量子计算多比特频率复用读出公开路线（IBM/Google 公开架构文档）；"
                   "D-46×D-47 已验证保真度预算框架",
        domain="hybrid",
        system_type="quantum_fidelity",
        composition=["GP-YBRANCH", "GP-SIN-PL"],
        default_req={"f01s": [4.8, 5.0, 5.2, 5.4]},
        design_note="4 比特频率复用读出链（D-46 复用 + D-47 保真度，已验证闭环）。"
                    "基元复用 Y-branch（分束）+ SiN 低损波导（量子光路互联）。",
        ci_status="",
    ),
    # —— 以下为 v0.8.35 货架库扩展（仍严守"组合已锚定基元"护栏）——
    ShelfItem(
        id="IM-SENSE-RING",
        title="微环折射率传感前端预设计（复用光链路拓扑）",
        target_app="生物/化学折射率传感、光纤传感前端、实验室芯片（LoC）片上传感",
        signal_ref="微环谐振传感公开路线（硅光折射率/生物传感 roadmap、公开文献与标准草案）；"
                   "复用 link 系统预算锚 S1/S2/S5/S7 已验证闭环",
        domain="photon",
        system_type="link",
        composition=["GP-GRATING-EFF", "GP-SIN-PL"],
        default_req={"n_channels": 1, "channel_spacing_ghz": 100, "filter_bw_ghz": 50,
                     "link_budget_db": 3.0, "p_tx_dbm": 0, "wg_length_cm": 1.0},
        design_note="环谐振器作折射率传感单元，复用 link 拓扑（激光→grating→SiN 波导→"
                    "ring→探测器）+ 系统预算锚 S1/S2/S5/S7。基元复用 grating coupler（"
                    "GP-GRATING-EFF）+ SiN 低损波导（GP-SIN-PL）。传感灵敏度由环 Q / 波长"
                    "偏移换算，属参数化下一迭代，不破现有已验证闭环。",
        ci_status="",
    ),
    ShelfItem(
        id="IM-LASER-INT",
        title="片上激光源集成发射模板（异质集成黑箱源 + 已锚定无源网）",
        target_app="共封装光模块发射端、硅光异质集成光源、片上收发前端",
        signal_ref="异质集成 III-V/Si 片上光源公开路线图（AIM Photonics 等公开 PDK 动向 / "
                   "学术异质集成 laser 公开文献）；复用 link 系统预算锚",
        domain="photon",
        system_type="link",
        composition=["GP-GRATING-EFF", "GP-SIN-PL"],
        default_req={"p_tx_dbm": 3.0, "wg_length_cm": 1.0, "link_budget_db": 3.0},
        design_note="激光源作为**异质集成黑箱源**（有源器件不物理级建模——负面清单："
                    "有源不物理级建模，行为黑箱 + 文献锚走完闭环），本货架组合其余已锚定"
                    "基元：grating coupler（GP-GRATING-EFF）+ SiN 低损波导（GP-SIN-PL）。"
                    "判决复用 link 系统预算锚 S1/S2/S5/S7（死标量，LLM 不进路径）。激光源"
                    "本身**非本团队新锚定器件**——如要将其纳入锚集，须先按 v0.8.32 方式"
                    "新增 golden 基准（待发动期/社区贡献）；本货架严守『组合创新、不新增"
                    "未锚定基元』。",
        ci_status="",
    ),
    ShelfItem(
        id="IM-QCOM-LINK",
        title="量子计算频率复用读出链路（5 比特保真度链）",
        target_app="超导量子计算多比特频率复用读出、量子处理器读出总线",
        signal_ref="IBM/Google 公开多比特频率复用读出架构；D-46×D-47 已验证保真度预算框架",
        domain="hybrid",
        system_type="quantum_fidelity",
        composition=["GP-YBRANCH", "GP-SIN-PL"],
        default_req={"f01s": [4.8, 5.0, 5.2, 5.4, 5.6]},
        design_note="5 比特频率复用读出链（D-46 复用 + D-47 保真度，已验证闭环）。基元复用"
                    "Y-branch（分束，GP-YBRANCH）+ SiN 低损波导（GP-SIN-PL，量子光路互联）。"
                    "与 IM-QCHIP-INT（4 比特）互补，演示库随比特数扩展仍零新物理。",
        ci_status="",
    ),
]


def evaluate_all(shelf: List[ShelfItem] = None) -> List[Dict[str, Any]]:
    shelf = shelf or DEFAULT_SHELF
    return [s.evaluate() for s in shelf]


def to_markdown(results: List[Dict[str, Any]]) -> str:
    """生成创新超市可浏览目录（docs/innovation_market.md）。"""
    n_total = len(results)
    n_ok = sum(1 for r in results if r.get("feasible") and not r.get("error"))
    lines = [
        "# LDA 创新超市（Innovation Marketplace）· 前瞻预研货架目录",
        "",
        "> 生成口径：每个货架 = 已锚定基元（产品级基准库 GP-*）+ 公开信号驱动的**前瞻预研**预设计。",
        f"> **{n_ok}/{n_total} 货架通过结构可行 + 系统预算不破检查**。",
        "",
        "**诚实边界（红线下护栏）**：",
        f"> {HONEST_BANNER}",
        "> - 货架仅由**已锚定基元**组装（组合创新），禁止含未锚定基元；",
        "> - 判决复用 system_type 已验证闭环（B4 / D-46×D-47），LLM 不进判决路径；",
        "> - 属等效验证（复用已锚定基元 + 系统预算不破），**非本团队流片验证**、**非对未来的承诺**。",
        "",
        "## 货架明细",
        "",
        "| 货架 ID | 标题 | 目标应用 | system_type | 已锚定基元 | 结构可行 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        comp = ", ".join(r.get("composition", []))
        status = "OK" if (r.get("feasible") and not r.get("error")) else "X"
        lines.append(
            f"| {r['id']} | {r.get('title','')} | {r.get('target_app','')} | "
            f"{r.get('system_type','')} | {comp} | {status} |"
        )
    lines += ["", "## 货架设计说明（诚实标注）", ""]
    for r in results:
        if r.get("design_note"):
            lines.append(f"- **{r['id']}**：{r['design_note']}")
    lines += ["", "## 信号来源（可溯源）", ""]
    for r in results:
        lines.append(f"- **{r['id']}** · {r.get('title','')}：{r.get('signal_ref','')}")
    lines += [
        "",
        "---",
        "_LDA · 开源 Agent-native EDA（光子 PDA + 量子 QEDA）· 物理定律锚红线 · LLM 不进判决路径_",
    ]
    return "\n".join(lines)


def library_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "innovation_market.json")


def save_library_json(shelf: List[ShelfItem] = None, path: str = None) -> str:
    """落盘货架库（可增量扩展：社区/文献贡献追加货架）。"""
    shelf = shelf or DEFAULT_SHELF
    path = path or library_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in shelf], f, ensure_ascii=False, indent=2)
    return path


def load_library_json(path: str = None) -> List[ShelfItem]:
    path = path or library_path()
    if not os.path.exists(path):
        return list(DEFAULT_SHELF)
    data = json.load(open(path, encoding="utf-8"))
    return [ShelfItem(**d) for d in data]


if __name__ == "__main__":
    for r in evaluate_all():
        tag = "OK" if (r.get("feasible") and not r.get("error")) else "FAIL"
        print(r["id"], tag, r.get("error", ""), r.get("summary", ""))
