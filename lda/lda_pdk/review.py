"""L2 生态共建 · 社区评审流 + 提案→golden 落地（D-95，建在 D-94 提交入口之上）。

把 D-94 的 pending 提案闭环成「提案 → 具名人工评审 → 确定性自测 → 落地接入
统一回归」：

  - review_proposal(proposal_id, decision, reviewer, rationale, oracle_fn_source)
      仅 pending 可评审；decision ∈ {approve, reject}；approve 须附 ORACLE
      参考实现源码（oracle_fn_source），且先做前置确定性自测（可编译、默认
      参数下返回有限标量），通过才置为 approved；reject 直接置 rejected。
      每次评审写入审计轨迹（谁/何时/决定/理由）。
  - land_proposal(proposal_id, contrib_path, landed_path, apply_live)
      仅 approved 可落地：受限命名空间编译 ORACLE 源码（仅 math + 安全
      builtins）→ 提取 oracle_fn_name → 确定性自测 → register_golden +
      register_benchmark 接入统一回归（build_harness_specs 自动纳入，零接线）
      → 持久化 landed.json → 生成 golden.py/benchmarks.py 补丁文本供维护者
      git 提交（权威 ORACLE 最终以版本控制为准）。
  - reload_landed(landed_path, apply_live)
      启动时按 landed.json 恢复已落地注册（live 一致性）。
  - list_proposals(status=None) / get_audit(proposal_id)

诚实红线（与验证锚哲学 §11 一致）：
  - LLM 不进判决路径：评审 = 具名人工/授权签署；自测 = 死标量门禁；
  - ORACLE 必须是确定性物理定律（方程必然），落地仅做登记与接线；
  - 落库(live) ≠ 进版本控制：生成的补丁须经维护者 git/PR 评审提交——
    这正是社区开放评审流本身。
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Dict, List, Optional

from .submit import (
    BenchmarkProposal, ProposalStore, _load_store, _save_store, _resolve_path,
)
# 项目包风格：lda/ 目录入 sys.path，lda_pdk 与 lda_harness 为同级顶层包，
# 故用绝对导入（相对导入 ..lda_harness 会越出顶层包）。
from lda_harness.golden import register_golden
from lda_harness.benchmarks import register_benchmark

LANDED_PATH = os.path.join(os.path.dirname(__file__), "landed.json")

# 受限命名空间：仅 math + 安全 builtins 白名单（防御纵深；信任锚=具名人工评审）
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "float": float, "int": int, "round": round, "range": range,
    "enumerate": enumerate, "zip": zip, "list": list, "dict": dict,
    "tuple": tuple, "bool": bool, "str": str, "divmod": divmod, "pow": pow,
    "isinstance": isinstance, "sorted": sorted, "reversed": reversed,
    "all": all, "any": any,
}


# --------------------------------------------------------------------------
# ORACLE 编译 + 确定性自测（死标量门禁）
# --------------------------------------------------------------------------
def _compile_oracle(source: str, fn_name: str, params: Dict):
    """受限命名空间编译 ORACLE 源码，提取 fn_name，默认参数下自测。

    返回 (fn, value)。任一环节失败抛 ValueError（确定性拒绝，非 LLM 判断）。
    """
    ns = {"math": math, "__builtins__": dict(_SAFE_BUILTINS)}
    try:
        code = compile(source, f"<oracle:{fn_name}>", "exec")
        exec(code, ns)
    except Exception as ex:
        raise ValueError(f"ORACLE 编译失败：{ex}")
    fn = ns.get(fn_name)
    if not callable(fn):
        raise ValueError(f"未在源码中找到可调用函数 {fn_name}")
    try:
        val = fn(**dict(params))
    except Exception as ex:
        raise ValueError(f"ORACLE 自测调用失败：{ex}")
    if not isinstance(val, (int, float)) or not math.isfinite(float(val)):
        raise ValueError(f"ORACLE 自测未返回有限标量：{val!r}")
    return fn, float(val)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# 评审流
# --------------------------------------------------------------------------
def review_proposal(proposal_id: str, decision: str, reviewer: str,
                    rationale: str, oracle_fn_source: Optional[str] = None,
                    contrib_path: Optional[str] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    p = next((x for x in store._items if x.id == proposal_id), None)
    if p is None:
        return {"status": "error", "reason": f"提案 {proposal_id} 不存在"}
    if p.status != "pending":
        return {"status": "error",
                "reason": f"提案 {proposal_id} 状态为 {p.status}，仅 pending 可评审"}
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        return {"status": "error",
                "reason": "评审人（具名/授权签署）必填——LLM 不进判决路径"}
    decision = str(decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        return {"status": "error", "reason": "decision 须为 approve/reject"}
    rationale = str(rationale or "").strip()

    if decision == "approve":
        src = str(oracle_fn_source or "").strip()
        if not src:
            return {"status": "error",
                    "reason": "approve 须附 ORACLE 参考实现源码（oracle_fn_source）"}
        # 前置确定性自测（不落地，仅验证可编译 + 默认参数返回有限标量）
        try:
            _, val = _compile_oracle(src, p.oracle_fn_name, p.default_params)
        except ValueError as ex:
            return {"status": "error", "id": p.id, "reason": f"approve 前置自测失败：{ex}"}
        p.oracle_fn_source = src
        p.status = "approved"
        p.reviewed_at = _now()
        p.audit.append({"ts": p.reviewed_at, "op": "review",
                        "decision": "approve", "reviewer": reviewer,
                        "rationale": rationale, "self_test_value": val})
    else:
        p.status = "rejected"
        p.reviewed_at = _now()
        p.audit.append({"ts": p.reviewed_at, "op": "review",
                        "decision": "reject", "reviewer": reviewer,
                        "rationale": rationale})
    p.reviewed_by = reviewer
    p.review_rationale = rationale
    _save_store(reg, path, store)
    return {"status": p.status, "id": p.id, "decision": decision,
            "reviewer": reviewer, "reviewed_at": p.reviewed_at,
            "reason": "评审已记录（审计轨迹已落盘）"}


# --------------------------------------------------------------------------
# 落地（接入统一回归）
# --------------------------------------------------------------------------
def _generate_patch(p: BenchmarkProposal) -> str:
    src = p.oracle_fn_source.strip()
    params_repr = dict(p.default_params)
    return (
        f"# ===== 社区提案落地补丁（{p.id}）=====\n"
        f"# 请合并到 lda_harness/golden.py 与 lda_harness/benchmarks.py，\n"
        f"# 经维护者评审后提交 git（PR 即开放评审流）。落库(live) ≠ 进版本控制。\n"
        f"\n"
        f"## 1) golden.py —— 新增 ORACLE 函数（建议置于 B18 之后）\n"
        f"{src}\n"
        f"\n"
        f"## 2) golden.py —— 注册（模块级 _GOLDEN_DISPATCH / _PHYSICAL_LAW）\n"
        f'_GOLDEN_DISPATCH["{p.id}"] = {p.oracle_fn_name}\n'
        f'_PHYSICAL_LAW.add("{p.id}")\n'
        f"\n"
        f"## 3) benchmarks.py —— BENCHMARK_DEFS 条目\n"
        f'"{p.id}": {{\n'
        f'    "title": "{p.title}", "metric": "{p.metric}",\n'
        f'    "oracle": "analytical(community)",\n'
        f'    "tol": {p.tol},\n'
        f'    "default_params": {params_repr!r},\n'
        f'    "golden_fn": {p.oracle_fn_name},\n'
        f'    "note": "社区提案 {p.id} 经评审落地；评审人 {p.reviewed_by} 于 {p.reviewed_at}。",\n'
        f"}},\n"
    )


def land_proposal(proposal_id: str, contrib_path: Optional[str] = None,
                  landed_path: Optional[str] = None,
                  apply_live: bool = True) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    p = next((x for x in store._items if x.id == proposal_id), None)
    if p is None:
        return {"status": "error", "reason": f"提案 {proposal_id} 不存在"}
    if p.status != "approved":
        return {"status": "error",
                "reason": f"提案 {proposal_id} 状态为 {p.status}，仅 approved 可落地"}
    if not p.oracle_fn_source:
        return {"status": "error", "reason": "缺 ORACLE 源码，无法落地"}
    try:
        fn, val = _compile_oracle(p.oracle_fn_source, p.oracle_fn_name,
                                  p.default_params)
    except ValueError as ex:
        return {"status": "error", "id": p.id, "reason": f"落地自测失败：{ex}"}

    if apply_live:
        register_golden(p.id, fn, physical_law=True)
        register_benchmark({
            "bid": p.id,
            "title": p.title,
            "metric": p.metric,
            "oracle": f"analytical(community:{p.formula})",
            "tol": p.tol,
            "default_params": dict(p.default_params),
            "golden_fn": fn,
            "note": f"社区提案 {p.id} 经评审落地（评审人 {p.reviewed_by} 于 {p.reviewed_at}）；权威版本以维护者 git 提交为准。",
        })

    p.status = "landed"
    p.landed_at = _now()
    p.audit.append({"ts": p.landed_at, "op": "land",
                    "value": val, "live_registered": apply_live})
    _save_store(reg, path, store)

    patch = _generate_patch(p)
    rec = {
        "bid": p.id, "title": p.title, "metric": p.metric,
        "formula": p.formula, "oracle_fn_name": p.oracle_fn_name,
        "tol": p.tol, "default_params": dict(p.default_params),
        "oracle_fn_source": p.oracle_fn_source,
        "reviewed_by": p.reviewed_by, "reviewed_at": p.reviewed_at,
        "landed_at": p.landed_at, "patch": patch,
    }
    _save_landed(rec, landed_path)
    return {"status": "landed", "id": p.id, "value": val,
            "reason": "已注册 golden._GOLDEN_DISPATCH + _PHYSICAL_LAW + benchmarks.BENCHMARK_DEFS，自动纳入统一回归；补丁已生成，待维护者 git 提交",
            "patch": patch}


# --------------------------------------------------------------------------
# landed.json 持久化 + 启动恢复
# --------------------------------------------------------------------------
def _landed_path(landed_path: Optional[str]) -> str:
    return landed_path or LANDED_PATH


def _load_landed(landed_path: Optional[str] = None) -> dict:
    path = _landed_path(landed_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_landed(rec: dict, landed_path: Optional[str] = None) -> None:
    path = _landed_path(landed_path)
    all_ = _load_landed(path)
    all_[rec["bid"]] = rec
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_, f, indent=2, ensure_ascii=False)


def reload_landed(landed_path: Optional[str] = None,
                  apply_live: bool = True):
    """启动时按 landed.json 恢复已落地注册。返回 (count, [bid,...])。"""
    all_ = _load_landed(landed_path)
    loaded: List[str] = []
    if not apply_live:
        return 0, loaded
    for bid in sorted(all_.keys()):
        rec = all_[bid]
        try:
            fn, _ = _compile_oracle(rec.get("oracle_fn_source", ""),
                                    rec.get("oracle_fn_name", ""),
                                    rec.get("default_params") or {})
        except Exception:
            continue
        register_golden(bid, fn, physical_law=True)
        register_benchmark({
            "bid": bid,
            "title": rec.get("title", ""),
            "metric": rec.get("metric", ""),
            "oracle": "analytical(community)",
            "tol": rec.get("tol", 0.0),
            "default_params": rec.get("default_params") or {},
            "golden_fn": fn,
            "note": "社区落地（landed.json 启动恢复）",
        })
        loaded.append(bid)
    return len(loaded), loaded


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
def list_proposals(status: Optional[str] = None,
                   contrib_path: Optional[str] = None) -> List[dict]:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    items = [dict(x) for x in store.list()]
    if status:
        items = [x for x in items if x.get("status") == status]
    return items


def get_audit(proposal_id: str, contrib_path: Optional[str] = None) -> List[dict]:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    p = next((x for x in store._items if x.id == proposal_id), None)
    return list(p.audit) if p else []


def list_landed(landed_path: Optional[str] = None) -> List[dict]:
    """已落地记录（含补丁），供 WebUI 展示。"""
    all_ = _load_landed(landed_path)
    return [all_[k] for k in sorted(all_.keys())]
