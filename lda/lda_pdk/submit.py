"""L2 生态共建 · 社区提交入口（D-94，建在 D-93 Registry 地基之上）。

提供社区 / 退休专家 / 晶圆厂向开放 PDK·器件本体 Registry 与 harness 题库提案
的「统一提交入口」：

  - submit_device(payload, overwrite=False, contrib_path=None)
      提交一条器件本体；sovereign_class 缺省时按 foundry/tech/name 匹配主权清单
      自动推断（A 永不借 / B 借今踢后 / C 第一天自主）；校验后登记入贡献库；
      冲突感知（同 id 未覆盖 → conflict）。
  - submit_devices_batch(payloads, contrib_path=None)
      批量提交，逐条返回 accepted / conflict / rejected。
  - BenchmarkProposal + ProposalStore + submit_benchmark_proposal
      社区可提案新的物理定律锚（id/title/metric/公式文本/建议 oracle_fn 签名/
      容差/默认参数）；状态 = pending，需代码评审与 golden 函数注册后才纳入
      统一回归——诚实：绝不自动注入 golden 函数，LLM 不进判决路径。
  - list_contributions(contrib_path=None)
      读取贡献库快照（Registry 计数 + 器件列表 + 提案列表），供 WebUI 展示。

持久化：贡献库存于 contributions.json（gitignore，不进版本库）。真实晶圆厂
NDA-PDK 对接仍属发动期事项 D-62，暂缓；本模块仅提供入口与贡献库，不硬编码
任何商业 PDK 参数。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .registry import PDKRegistry, DeviceEntry
from .sovereign_deps import SOVEREIGN_DEPS

CONTRIB_PATH = os.path.join(os.path.dirname(__file__), "contributions.json")

# 主权分级推断关键字（仅用于提交入口的便捷默认，可被显式 sovereign_class 覆盖）
_A_KEYWORDS = ("lumerical", "ansys", "synopsys", "cadence", "siemens", "nda-pdk", "商业闭源")
_B_KEYWORDS = ("gdsfactory", "meep", "klayout", "sax", "mpb", "nazca", "tidy3d")


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _resolve_path(contrib_path: Optional[str]) -> str:
    return contrib_path or CONTRIB_PATH


def _norm_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return list(v)


def _norm_params(v) -> Dict:
    if v is None:
        return {}
    if isinstance(v, str):
        try:
            return dict(json.loads(v))
        except Exception:
            return {}
    return dict(v)


def infer_sovereign_class(payload: dict) -> str:
    """sovereign_class 缺省时按 foundry/tech/name 匹配主权清单推断；默认 C。"""
    if payload.get("sovereign_class") in ("A", "B", "C"):
        return payload["sovereign_class"]
    hay = " ".join(str(payload.get(k, "")) for k in ("foundry", "tech", "name", "note")).lower()
    for kw in _A_KEYWORDS:
        if kw in hay:
            return "A"
    for kw in _B_KEYWORDS:
        if kw in hay:
            return "B"
    return "C"


def _build_entry(payload: dict, sclass: str) -> DeviceEntry:
    return DeviceEntry(
        id=str(payload.get("id", "")).strip(),
        name=str(payload.get("name", "")).strip(),
        tech=str(payload.get("tech", "")).strip(),
        foundry=str(payload.get("foundry", "")).strip(),
        sovereign_class=sclass,
        layers=_norm_list(payload.get("layers")),
        params=_norm_params(payload.get("params")),
        tags=_norm_list(payload.get("tags")),
        note=str(payload.get("note", "")).strip(),
    )


# --------------------------------------------------------------------------
# 贡献库读写
# --------------------------------------------------------------------------
def _load_store(contrib_path: str):
    """返回 (PDKRegistry, ProposalStore)；文件不存在/损坏则返回空。"""
    reg = PDKRegistry()
    store = ProposalStore()
    if not os.path.exists(contrib_path):
        return reg, store
    try:
        with open(contrib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return reg, store
    for it in data.get("registry", []):
        try:
            reg.add(DeviceEntry(**it))
        except Exception:
            pass
    for it in data.get("proposals", []):
        try:
            store.add(BenchmarkProposal(**it))
        except Exception:
            pass
    return reg, store


def _save_store(reg: PDKRegistry, contrib_path: str, store: "ProposalStore") -> None:
    rec = {
        "registry": [e.__dict__ for e in reg._items.values()],
        "proposals": store.list(),
    }
    with open(contrib_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# 器件提交
# --------------------------------------------------------------------------
def submit_device(payload: dict, overwrite: bool = False,
                  contrib_path: Optional[str] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    sclass = infer_sovereign_class(payload)
    try:
        entry = _build_entry(payload, sclass)
        entry.validate()
    except Exception as ex:
        return {"status": "rejected", "id": payload.get("id"),
                "reason": f"校验失败：{ex}"}
    res = reg.add(entry, overwrite=overwrite)
    if res == "conflict":
        existing = reg.get(entry.id)
        return {"status": "conflict", "id": entry.id,
                "reason": "id 已存在（如需覆盖请置 overwrite=true）",
                "existing": existing.__dict__ if existing else None}
    _save_store(reg, path, store)
    return {"status": "accepted", "id": entry.id, "sovereign_class": sclass,
            "reason": "已登记入贡献库"}


def submit_devices_batch(payloads: List[dict],
                         contrib_path: Optional[str] = None) -> List[dict]:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    results: List[dict] = []
    changed = False
    for p in payloads:
        sclass = infer_sovereign_class(p)
        try:
            entry = _build_entry(p, sclass)
            entry.validate()
        except Exception as ex:
            results.append({"status": "rejected", "id": p.get("id"),
                            "reason": f"校验失败：{ex}"})
            continue
        res = reg.add(entry, overwrite=False)
        if res == "conflict":
            results.append({"status": "conflict", "id": entry.id,
                            "reason": "id 已存在"})
        else:
            results.append({"status": "accepted", "id": entry.id,
                            "sovereign_class": sclass,
                            "reason": "已登记入贡献库"})
            changed = True
    if changed:
        _save_store(reg, path, store)
    return results


# --------------------------------------------------------------------------
# harness 物理定律锚提案（仅登记 pending，绝不自动注入 golden 函数）
# --------------------------------------------------------------------------
@dataclass
class BenchmarkProposal:
    """社区提案：新的物理定律锚（需代码评审 + golden 函数注册后纳入回归）。"""
    id: str
    title: str
    metric: str
    formula: str                       # 人类可读公式文本
    oracle_fn_name: str                # 建议 golden 函数名（须注册于 golden.dispatch + physical_law）
    tol: float = 0.0
    default_params: Dict = field(default_factory=dict)
    proposed_by: str = "community"
    status: str = "pending"            # pending / accepted / rejected
    note: str = ""

    def validate(self) -> bool:
        if not self.id or not self.title or not self.metric:
            raise ValueError("id/title/metric 必填")
        if not self.formula:
            raise ValueError("formula 必填（人类可读公式文本）")
        if not self.oracle_fn_name:
            raise ValueError("oracle_fn_name 必填（须注册于 golden.dispatch）")
        return True


class ProposalStore:
    def __init__(self, items=None):
        self._items: List[BenchmarkProposal] = list(items or [])

    def add(self, p: BenchmarkProposal) -> str:
        p.validate()
        for i, ex in enumerate(self._items):
            if ex.id == p.id:
                self._items[i] = p            # 同 id 提案：保留最新，状态重置 pending
                return "updated"
        self._items.append(p)
        return "added"

    def list(self):
        return [asdict(p) for p in self._items]

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"proposals": self.list()}, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "ProposalStore":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return cls()
        items = data.get("proposals", []) if isinstance(data, dict) else data
        out = cls()
        for it in items:
            try:
                out.add(BenchmarkProposal(**it))
            except Exception:
                pass
        return out


def submit_benchmark_proposal(payload: dict,
                              contrib_path: Optional[str] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    try:
        p = BenchmarkProposal(
            id=str(payload.get("id", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            metric=str(payload.get("metric", "")).strip(),
            formula=str(payload.get("formula", "")).strip(),
            oracle_fn_name=str(payload.get("oracle_fn_name", "")).strip(),
            tol=float(payload.get("tol", 0.0) or 0.0),
            default_params=_norm_params(payload.get("default_params")),
            proposed_by=str(payload.get("proposed_by", "community")).strip(),
            status="pending",
            note=str(payload.get("note", "")).strip(),
        )
        p.validate()
    except Exception as ex:
        return {"status": "rejected", "id": payload.get("id"),
                "reason": f"校验失败：{ex}"}
    res = store.add(p)
    _save_store(reg, path, store)
    return {"status": "accepted_pending", "id": p.id, "review_status": "pending",
            "reason": "提案已登记，待代码评审与 golden 函数注册后纳入回归（LLM 不进判决路径）",
            "store_op": res}


# --------------------------------------------------------------------------
# 快照
# --------------------------------------------------------------------------
def list_contributions(contrib_path: Optional[str] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    return {
        "registry_stats": reg.stats(),
        "device_count": len(reg._items),
        "devices": [asdict(e) for e in reg._items.values()],
        "proposals": store.list(),
        "proposal_count": len(store._items),
    }
