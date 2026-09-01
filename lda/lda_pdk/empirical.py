"""LDA · D-62 实证大数据锚 · 实测语料经社区评审流落库（提交 → 具名评审 → 落地）。

实证锚 = 验证的第二道**非 AI ground**（真实流片/测量语料，众人贡献非遗留）。
本模块把实证语料提交流闭环成与 harness 提案（D-94~D-98）同构的评审流：

  submit_measurement  → 确定性校验（citation 必填=可追溯来源 / 数值有限 / σ≥0 /
                       防重）→ pending
  review_measurement  → 具名人工评审（LLM 不进判决路径）+ 前置确定性自测门禁
  land_measurement    → 写 empirical_contributions.json（gitignore）+ 实时 reload
                        进语料库 —— harness E1-E7 实证锚题立即可用
  list_measurements / measurement_stats

诚实边界：
  - 种子语料（seed_empirical.json）= 公开文献/PDK 量级；真实晶圆厂 NDA 流片
    实测属发动期事项，经本管道在数据到达后流入（管道先建好）；
  - 评审 = 具名人工（非自动/非 LLM）；落库(live) ≠ 进版本控制，权威语料以
    维护者 git 提交为准（与 landed.json 语义一致）。
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from math import isfinite
from typing import List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROPOSALS_PATH = os.path.join(_HERE, "empirical_proposals.json")
DEFAULT_CORPUS_PATH = os.path.join(_HERE, "empirical_contributions.json")

_STATUS = ("pending", "approved", "rejected", "landed")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class EmpiricalProposal:
    """实测语料提案（提交 → 具名评审 → 落地）。"""
    id: str
    device: str
    metric: str
    measured_value: float
    uncertainty_abs: float
    fab_source: str
    citation: str
    method: str = ""
    source_url: str = ""
    geometry: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    status: str = "pending"
    proposed_by: str = "community"
    submitted_at: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    rationale: str = ""
    audit: list = field(default_factory=list)

    def validate(self):
        if not self.id or not self.device or not self.metric:
            raise ValueError("id/device/metric 必填")
        if not isinstance(self.measured_value, (int, float)) or not isfinite(self.measured_value):
            raise ValueError("measured_value 须为有限数值")
        if not isinstance(self.uncertainty_abs, (int, float)) or self.uncertainty_abs < 0:
            raise ValueError("uncertainty_abs 须 ≥0")
        if not self.fab_source:
            raise ValueError("fab_source（来源 fab/文献/PDK）必填")
        if not self.citation:
            raise ValueError("citation 必填——实证锚必须有可追溯来源（无引用不予收录）")
        return True


class EmpiricalProposalStore:
    def __init__(self, items=None):
        self._items: List[EmpiricalProposal] = list(items or [])

    def get(self, mid):
        return next((p for p in self._items if p.id == mid), None)

    def add(self, p: EmpiricalProposal) -> str:
        p.validate()
        for i, ex in enumerate(self._items):
            if ex.id == p.id:
                self._items[i] = p
                return "updated"
        self._items.append(p)
        return "added"

    def list(self):
        return [asdict(p) for p in self._items]

    def to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"measurements": self.list()}, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path) -> "EmpiricalProposalStore":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return cls()
        items = data.get("measurements", []) if isinstance(data, dict) else data
        out = cls()
        for it in items:
            try:
                out.add(EmpiricalProposal(**it))
            except Exception:
                pass
        return out


def _resolve_path(proposals_path: Optional[str]) -> str:
    return proposals_path or DEFAULT_PROPOSALS_PATH


def _resolve_corpus(corpus_path: Optional[str]) -> str:
    return corpus_path or DEFAULT_CORPUS_PATH


def _load(proposals_path):
    return EmpiricalProposalStore.load(proposals_path)


def _save(store: EmpiricalProposalStore, proposals_path) -> None:
    store.to_json(proposals_path)


def submit_measurement(payload: dict,
                       proposals_path: Optional[str] = None) -> dict:
    """提交实测语料提案（确定性校验 → pending）。citation 必填（可追溯来源）。"""
    path = _resolve_path(proposals_path)
    store = _load(path)
    p = EmpiricalProposal(
        id=str(payload.get("id", "")).strip(),
        device=str(payload.get("device", "")).strip(),
        metric=str(payload.get("metric", "")).strip(),
        measured_value=float(payload.get("measured_value", 0.0)),
        uncertainty_abs=float(payload.get("uncertainty_abs", 0.0) or 0.0),
        fab_source=str(payload.get("fab_source", "")).strip(),
        citation=str(payload.get("citation", "")).strip(),
        method=str(payload.get("method", "")).strip(),
        source_url=str(payload.get("source_url", "") or "").strip(),
        geometry=payload.get("geometry") or {},
        tags=list(payload.get("tags") or []),
        proposed_by=str(payload.get("proposed_by", "community")).strip(),
        status="pending",
        submitted_at=_now(),
    )
    try:
        p.validate()
    except Exception as ex:
        return {"status": "rejected", "id": payload.get("id"),
                "reason": f"校验失败：{ex}"}
    # D-63 来源边界门禁：仅限公开论文 / datasheet / 公开测量数据集，且必须可公开溯源。
    # 「可公开溯源」= citation 含 DOI / arXiv / 公开 URL 之一（机器可判，非主观描述）。
    try:
        from ..lda_harness.provenance import classify_citation
    except ImportError:  # 兼容脚本态（sys.path 直指 lda/）
        from lda_harness.provenance import classify_citation
    _tr = classify_citation(p.citation, p.source_url)
    if not _tr["traceable"]:
        return {"status": "rejected", "id": p.id,
                "reason": f"溯源门禁：来源边界仅限①公开论文②公开 datasheet③公开测量数据集，"
                          f"且必须可公开溯源。当前 citation 未含 DOI / arXiv / 公开 URL "
                          f"定位符，定为 {_tr['tier']} 级（不可独立复验），不予收录。"
                          f"请补充可解析的公开出处（如 DOI 或 https:// 链接）。"}
    # 防重：与 pending/approved/landed 语料重复 → 拒
    ex = store.get(p.id)
    if ex is not None and ex.status in ("pending", "approved", "landed"):
        return {"status": "rejected", "id": p.id,
                "reason": f"防重守卫：语料 {p.id} 已存在（{ex.status}）"}
    store.add(p)
    _save(store, path)
    return {"status": "accepted_pending", "id": p.id, "review_status": "pending",
            "reason": "实证语料已登记，待具名人工评审后落库（citation=可追溯来源；LLM 不进判决路径）"}


def review_measurement(mid: str, decision: str, reviewer: str, rationale: str,
                       proposals_path: Optional[str] = None) -> dict:
    """具名人工评审（LLM 不进判决路径）+ 前置确定性自测门禁。"""
    path = _resolve_path(proposals_path)
    store = _load(path)
    p = store.get(mid)
    if p is None:
        return {"status": "error", "reason": f"语料提案 {mid} 不存在"}
    if p.status != "pending":
        return {"status": "error",
                "reason": f"语料提案 {mid} 状态为 {p.status}，仅 pending 可评审"}
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        return {"status": "error",
                "reason": "评审人（具名/授权签署）必填——LLM 不进判决路径"}
    decision = str(decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        return {"status": "error", "reason": "decision 须为 approve/reject"}
    if decision == "approve":
        # 前置确定性自测：数值有限 + σ≥0 + citation 可追溯（validate 已做）——
        # 额外验证可被语料库解析（无 citation 的伪造/无源数据绝不落库）
        try:
            p.validate()
        except ValueError as ex:
            return {"status": "error", "id": p.id, "reason": f"评审前置自测失败：{ex}"}
        p.status = "approved"
    else:
        p.status = "rejected"
    p.reviewed_by = reviewer
    p.reviewed_at = _now()
    p.rationale = str(rationale or "").strip()
    p.audit.append({"ts": p.reviewed_at, "op": "review", "decision": decision,
                    "reviewer": reviewer, "rationale": p.rationale})
    _save(store, path)
    return {"status": p.status, "id": p.id, "decision": decision,
            "reviewer": reviewer, "reviewed_at": p.reviewed_at,
            "reason": "评审已记录（审计轨迹已落盘）"}


def land_measurement(mid: str, proposals_path: Optional[str] = None,
                     corpus_path: Optional[str] = None) -> dict:
    """落地已批准语料 → 写入 empirical_contributions.json（gitignore），
    harness E1-E7 实证锚题实时可用（verification_adapters 启动即 reload）。"""
    ppath = _resolve_path(proposals_path)
    cpath = _resolve_corpus(corpus_path)
    store = _load(ppath)
    p = store.get(mid)
    if p is None:
        return {"status": "error", "reason": f"语料提案 {mid} 不存在"}
    if p.status != "approved":
        return {"status": "error",
                "reason": f"语料提案 {mid} 状态为 {p.status}，仅 approved 可落地"}
    # 读现有 corpus 文件（追加模式）
    try:
        with open(cpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data.get("corpus", data) if isinstance(data, dict) else data
    except Exception:
        records = []
    if any(str(r.get("id", "")) == p.id for r in records):
        return {"status": "error", "id": p.id,
                "reason": f"语料 {p.id} 已落地（权威语料以维护者 git 提交为准）"}
    records.append({
        "id": p.id, "device": p.device, "metric": p.metric,
        "measured_value": p.measured_value, "uncertainty_abs": p.uncertainty_abs,
        "fab_source": p.fab_source, "citation": p.citation, "method": p.method,
        "geometry": p.geometry, "tags": p.tags,
        "provenance": {"contributor": p.proposed_by, "reviewer": p.reviewed_by,
                       "landed_at": _now()},
    })
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump({"corpus": records}, f, indent=2, ensure_ascii=False)
    p.status = "landed"
    p.audit.append({"ts": _now(), "op": "land", "by": p.reviewed_by})
    _save(store, ppath)
    return {"status": "landed", "id": p.id, "device": p.device,
            "metric": p.metric, "measured_value": p.measured_value,
            "reason": "实证语料已落地（empirical_contributions.json）；harness E 题实证锚实时可用"}


def list_measurements(status: Optional[str] = None,
                      proposals_path: Optional[str] = None) -> List[dict]:
    path = _resolve_path(proposals_path)
    store = _load(path)
    out = []
    for p in store._items:
        if status and p.status != status:
            continue
        d = asdict(p)
        d["audit"] = p.audit
        out.append(d)
    return out


def measurement_stats(proposals_path: Optional[str] = None) -> dict:
    path = _resolve_path(proposals_path)
    store = _load(path)
    by_status = {s: 0 for s in _STATUS}
    for p in store._items:
        by_status[p.status] = by_status.get(p.status, 0) + 1
    return {"total": len(store._items), "by_status": by_status}


def list_landed_measurements(corpus_path: Optional[str] = None) -> List[dict]:
    """已落地语料（harness E 题实证锚当前生效集）。"""
    cpath = _resolve_corpus(corpus_path)
    try:
        with open(cpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data.get("corpus", data) if isinstance(data, dict) else data
    except Exception:
        return []
    return records
