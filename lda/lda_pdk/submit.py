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
from datetime import datetime
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


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# 评审策略（D-97 门槛再扩展 · 全确定性，LLM 不进判决路径）
# --------------------------------------------------------------------------
@dataclass
class ReviewPolicy:
    """可配置评审门槛策略（默认保持 D-95/D-96 行为不变）。

    - enforce_positive_tol:     提交期 tol 必须为正
    - enforce_nonempty_params:  提交期 default_params 非空（物理定律锚需要参数）
    - enforce_value_bounds:     提交期强制声明 value_min/value_max
    - authorized_reviewers:     评审人白名单（空 = 任意具名可；非空 = 白名单制）
    - min_source_length:        ORACLE 源码最短长度（>0 时防空壳实现）
    - strict_dedup:             防重用 token 集比较（True 时 "n_g·L" == "n_g*L"）
    - min_quorum:               core 提案双评审基准数（默认 2）
    """
    enforce_positive_tol: bool = True
    enforce_nonempty_params: bool = True
    enforce_value_bounds: bool = False
    authorized_reviewers: frozenset = field(default_factory=frozenset)
    min_source_length: int = 0
    strict_dedup: bool = False
    min_quorum: int = 2


def get_policy(overrides: Optional[dict] = None) -> ReviewPolicy:
    """读取评审策略：默认 + 环境变量覆盖（LDA_REVIEW_*）+ 显式 overrides。"""
    p = ReviewPolicy()
    env = os.environ
    if env.get("LDA_REVIEW_ENFORCE_BOUNDS") in ("1", "true", "True"):
        p.enforce_value_bounds = True
    ar = env.get("LDA_REVIEW_AUTH_REVIEWERS", "")
    if ar.strip():
        p.authorized_reviewers = frozenset(
            x.strip() for x in ar.split(",") if x.strip())
    msl = env.get("LDA_REVIEW_MIN_SOURCE_LEN", "")
    if msl.strip().isdigit():
        p.min_source_length = int(msl)
    if env.get("LDA_REVIEW_STRICT_DEDUP") in ("1", "true", "True"):
        p.strict_dedup = True
    if overrides:
        for k, v in overrides.items():
            if hasattr(p, k):
                setattr(p, k, v)
    return p


def policy_info(overrides: Optional[dict] = None) -> dict:
    """策略快照（WebUI 展示用）。"""
    p = get_policy(overrides)
    return {
        "enforce_positive_tol": p.enforce_positive_tol,
        "enforce_nonempty_params": p.enforce_nonempty_params,
        "enforce_value_bounds": p.enforce_value_bounds,
        "authorized_reviewers": sorted(p.authorized_reviewers),
        "min_source_length": p.min_source_length,
        "strict_dedup": p.strict_dedup,
        "min_quorum": p.min_quorum,
    }


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
    """社区提案：新的物理定律锚（需代码评审 + golden 函数注册后纳入回归）。

    状态机：pending →（review approve）approved →（land）landed；
            pending →（review reject）rejected。
    评审/落地字段由 lda_pdk/review.py 维护（D-95）。
    """
    id: str
    title: str
    metric: str
    formula: str                       # 人类可读公式文本
    oracle_fn_name: str                # 建议 golden 函数名（须注册于 golden.dispatch + physical_law）
    tol: float = 0.0
    default_params: Dict = field(default_factory=dict)
    proposed_by: str = "community"
    status: str = "pending"            # pending / approved / rejected / landed
    note: str = ""
    # ---- D-95 评审/落地字段（缺省兼容旧 contributions.json）----
    oracle_fn_source: str = ""         # 评审通过后附带的 ORACLE 参考实现源码
    reviewed_by: str = ""              # 具名评审人/授权签署（LLM 不进判决路径）
    reviewed_at: str = ""
    review_rationale: str = ""
    landed_at: str = ""
    audit: List[dict] = field(default_factory=list)   # 审计轨迹
    # ---- D-96 门槛扩展字段（缺省兼容旧 JSON）----
    value_min: Optional[float] = None  # 数值界限下限（自测值须 ≥ 此值；None=不检查）
    value_max: Optional[float] = None  # 数值界限上限（自测值须 ≤ 此值；None=不检查）
    core: bool = False                 # core 提案需双评审人 quorum（2 位不同具名评审人）
    approvals: List[dict] = field(default_factory=list)  # quorum 票（{reviewer,ts,rationale}）
    submitted_at: str = ""             # 提交时间（评审统计用）

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


def _norm_formula(formula: str) -> str:
    """公式规范化（防重比对用）：去空白 + 小写。"""
    return "".join(str(formula).split()).lower()


def _formula_tokens(formula: str) -> set:
    """公式 token 集（严格防重用）：规范化后提取标识符。"""
    import re
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", _norm_formula(formula)))


def _dup_check(payload: dict, store: "ProposalStore", contrib_path: str,
               strict: bool = False):
    """提交期防重守卫（确定性，D-96/D-97）：

      - oracle_fn_name 与已落地基准（landed.json）重复 → 拒；
      - 公式（strict 时按 token 集）与本贡献库内已有
        pending/approved/landed 提案重复 → 拒。
    返回 None（无重复）或拒绝原因字符串。
    """
    fn = str(payload.get("oracle_fn_name", "")).strip()
    formula = _norm_formula(payload.get("formula", ""))
    # ① 已落地（本地最小读 landed.json，避免与 review 循环导入）
    landed_path = os.path.join(os.path.dirname(__file__), "landed.json")
    try:
        with open(landed_path, "r", encoding="utf-8") as f:
            landed = json.load(f)
    except Exception:
        landed = {}
    if landed:
        landed_fns = {str(v.get("oracle_fn_name", "")).lower()
                      for v in landed.values() if isinstance(v, dict)}
        if fn.lower() in landed_fns:
            return f"oracle_fn_name {fn!r} 已落地为权威 ORACLE，禁止重复提案（维护者 git 提交的权威版本已存在）"
    # ② 本贡献库内已有提案（pending/approved/landed 均禁重——已落地即权威）
    for p in store._items:
        if p.status in ("pending", "approved", "landed"):
            if p.oracle_fn_name and p.oracle_fn_name.lower() == fn.lower():
                return f"oracle_fn_name {fn!r} 已存在于提案 {p.id}（{p.status}）"
            if formula:
                if strict:
                    if _formula_tokens(p.formula) == _formula_tokens(formula):
                        return f"公式(token)与提案 {p.id}（{p.status}）重复"
                elif _norm_formula(p.formula) == formula:
                    return f"公式与提案 {p.id}（{p.status}）重复"
    return None


def submit_benchmark_proposal(payload: dict,
                              contrib_path: Optional[str] = None,
                              policy_override: Optional[dict] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    pol = get_policy(policy_override)
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
            value_min=(float(payload["value_min"])
                       if payload.get("value_min") not in (None, "") else None),
            value_max=(float(payload["value_max"])
                       if payload.get("value_max") not in (None, "") else None),
            core=bool(payload.get("core", False)),
            submitted_at=_now_iso(),
        )
        p.validate()
    except Exception as ex:
        return {"status": "rejected", "id": payload.get("id"),
                "reason": f"校验失败：{ex}"}
    # D-97 策略门槛预检（提交期，确定性）
    if pol.enforce_positive_tol and p.tol <= 0:
        return {"status": "rejected", "id": p.id,
                "reason": f"策略门槛：tol 必须为正（当前 {p.tol}）"}
    if pol.enforce_nonempty_params and not p.default_params:
        return {"status": "rejected", "id": p.id,
                "reason": "策略门槛：default_params 不能为空（物理定律锚需要参数）"}
    if (p.value_min is not None and p.value_max is not None
            and p.value_min > p.value_max):
        return {"status": "rejected", "id": p.id,
                "reason": f"策略门槛：value_min {p.value_min} > value_max {p.value_max}"}
    if pol.enforce_value_bounds and (p.value_min is None or p.value_max is None):
        return {"status": "rejected", "id": p.id,
                "reason": "策略门槛：当前策略要求提案声明 value_min/value_max（数值界限强制）"}
    dup = _dup_check(payload, store, path, strict=pol.strict_dedup)
    if dup:
        return {"status": "rejected", "id": payload.get("id"),
                "reason": f"防重守卫：{dup}"}
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
