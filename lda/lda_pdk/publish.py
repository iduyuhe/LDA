"""L2 生态共建 · 评审流端到端收官 —— 发布（Publish，D-98）。

把 D-95 的「评审→落地」闭环推至端到端最后一环：landed ORACLE 固化为
正式版本控制补丁 + Release Notes 草稿，形成完整生命周期：

    提案 → 评审 → 落地(自动纳入统一回归) → 发布(补丁+发布草稿) → 维护者 git 合并

  - publish_proposal(proposal_id, author, note="")
      仅 landed 可发布；须具名发布人；确定性重编译 ORACLE 自测（死标量门禁）；
      用 difflib 生成 golden.py / benchmarks.py 的正式 unified diff 补丁
      （EOF 追加：ORACLE 函数 + 注册 / BENCHMARK_DEFS 条目 + ORDER）；
      写补丁文件 + Release Notes 草稿；提案状态 landed → published；
      landed 记录加 published_at / patch_path；审计追加 publish。
  - list_published()

诚实边界（与验证锚哲学一致）：
  - 发布不改源文件、不做 git commit —— 产出「正式补丁 + Release Notes 草稿」，
    经维护者 git apply / 合并（开放评审流）后方成为权威版本控制内容；
  - LLM 不进判决路径：发布自检 = 死标量门禁（重编译 + 默认参数返回有限标量）；
  - 真实晶圆厂 NDA-PDK 对接仍属发动期 D-62，暂缓。
"""
from __future__ import annotations

import difflib
import os
from datetime import datetime
from typing import List, Optional

from .submit import _load_store, _save_store, _resolve_path
from .review import _compile_oracle, _load_landed, _save_landed, _now

PATCHES_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "reports", "patches"))


def _golden_path() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "lda_harness", "golden.py"))


def _benchmarks_path() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "lda_harness", "benchmarks.py"))


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _golden_append_block(bid: str, rec: dict) -> str:
    src = str(rec.get("oracle_fn_source", "")).strip()
    fn = rec.get("oracle_fn_name", "")
    return (
        f"\n\n"
        f"# ---- 社区落地基准 {bid}（D-98 发布 · 评审人 "
        f"{rec.get('reviewed_by', '')} @{rec.get('reviewed_at', '')}）----\n"
        f"{src}\n"
        f"_GOLDEN_DISPATCH[\"{bid}\"] = {fn}\n"
        f"_PHYSICAL_LAW.add(\"{bid}\")\n"
    )


def _benchmarks_append_block(bid: str, rec: dict) -> str:
    entry = {
        "title": rec.get("title", ""),
        "metric": rec.get("metric", ""),
        "oracle": f"analytical(community:{rec.get('formula', '')})",
        "tol": rec.get("tol", 0.0),
        "default_params": dict(rec.get("default_params") or {}),
        "golden_fn": rec.get("oracle_fn_name", ""),
        "note": (f"社区提案 {bid} 经评审→落地→发布（评审人 {rec.get('reviewed_by', '')}"
                 f" 于 {rec.get('reviewed_at', '')}）；权威版本控制内容，见 {bid}.publish.patch。"),
    }
    return (
        f"\n\n"
        f"# ---- 社区落地基准 {bid}（D-98 发布）----\n"
        f"BENCHMARK_DEFS[\"{bid}\"] = {entry!r}\n"
        f"if \"{bid}\" not in BENCHMARK_ORDER:\n"
        f"    BENCHMARK_ORDER.append(\"{bid}\")\n"
    )


def _unified_patch(bid: str, rec: dict) -> str:
    """生成 golden.py + benchmarks.py 的正式 unified diff（EOF 追加，可 git apply）。"""
    parts = []
    for path, block in ((_golden_path(), _golden_append_block(bid, rec)),
                        (_benchmarks_path(), _benchmarks_append_block(bid, rec))):
        orig = _read_text(path)
        new = orig + block
        diff = difflib.unified_diff(
            orig.splitlines(), new.splitlines(),
            fromfile=f"a/{os.path.relpath(path, os.path.dirname(path))}",
            tofile=f"b/{os.path.relpath(path, os.path.dirname(path))}",
            lineterm="")
        dtext = "\n".join(diff)
        if dtext:
            parts.append(dtext)
    header = (
        f"# LDA 社区基准发布补丁 · {bid}\n"
        f"# 生成：{_now()} · 评审人 {rec.get('reviewed_by', '')}\n"
        f"# 用法：git apply {bid}.publish.patch（或按 diff 手工合并），"
        f"经维护者评审后提交。\n"
        f"# 诚实边界：本补丁由社区评审流产出，LLM 不进判决路径；"
        f"git 提交前不产生持久权威 ORACLE。\n"
    )
    return header + "\n\n" + "\n\n".join(parts)


def _write_release_note(bid: str, rec: dict, author: str, patch_name: str,
                        value: float) -> str:
    md = (
        f"# Release · Benchmark {bid}（社区发布 · D-98）\n\n"
        f"- **标题**：{rec.get('title', '')}\n"
        f"- **指标**：{rec.get('metric', '')}\n"
        f"- **公式**：{rec.get('formula', '')}\n"
        f"- **ORACLE**：`{rec.get('oracle_fn_name', '')}`（确定性物理定律，评审通过）\n"
        f"- **容差**：{rec.get('tol', 0.0)}\n"
        f"- **默认参数**：{dict(rec.get('default_params') or {})!r}\n"
        f"- **评审人**：{rec.get('reviewed_by', '')} @ {rec.get('reviewed_at', '')}\n"
        f"- **落地自测值**：{value:.6g}\n"
        f"- **发布人**：{author} @ {_now()}\n"
        f"- **补丁**：`{patch_name}`（git apply 后即成为版本控制内正式基准，"
        f"自动纳入统一回归）\n\n"
        f"## 合并说明\n\n"
        f"1. `git apply {patch_name}`（或按 diff 手工合并）；\n"
        f"2. 运行 harness 全量回归确认新题 PASS；\n"
        f"3. 提交后关闭对应提案。\n"
    )
    return md


def publish_proposal(proposal_id: str, author: str, note: str = "",
                     contrib_path: Optional[str] = None,
                     landed_path: Optional[str] = None,
                     patches_dir: Optional[str] = None) -> dict:
    path = _resolve_path(contrib_path)
    reg, store = _load_store(path)
    p = next((x for x in store._items if x.id == proposal_id), None)
    if p is None:
        return {"status": "error", "reason": f"提案 {proposal_id} 不存在"}
    if p.status != "landed":
        return {"status": "error",
                "reason": f"提案 {proposal_id} 状态为 {p.status}，仅 landed 可发布"}
    author = str(author or "").strip()
    if not author:
        return {"status": "error",
                "reason": "发布人（具名/授权签署）必填——git 提交是维护者动作"}
    if not p.oracle_fn_source:
        return {"status": "error", "id": p.id, "reason": "缺 ORACLE 源码，无法发布"}
    # 确定性重编译自测（死标量门禁）
    try:
        fn, val = _compile_oracle(p.oracle_fn_source, p.oracle_fn_name,
                                  p.default_params)
    except ValueError as ex:
        return {"status": "error", "id": p.id, "reason": f"发布自测失败：{ex}"}

    rec = {
        "bid": p.id, "title": p.title, "metric": p.metric,
        "formula": p.formula, "oracle_fn_name": p.oracle_fn_name,
        "tol": p.tol, "default_params": dict(p.default_params),
        "oracle_fn_source": p.oracle_fn_source,
        "reviewed_by": p.reviewed_by, "reviewed_at": p.reviewed_at,
        "landed_at": p.landed_at,
    }
    patch_text = _unified_patch(p.id, rec)
    if not patch_text.strip():
        return {"status": "error", "id": p.id,
                "reason": "补丁生成为空（源文件读取失败？）"}

    pdir = patches_dir or PATCHES_DIR
    os.makedirs(pdir, exist_ok=True)
    patch_name = f"{p.id}.publish.patch"
    release_name = f"{p.id}.RELEASE.md"
    patch_path = os.path.join(pdir, patch_name)
    release_path = os.path.join(pdir, release_name)
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(patch_text)
    with open(release_path, "w", encoding="utf-8") as f:
        f.write(_write_release_note(p.id, rec, author, patch_name, val))

    # 状态 landed → published + 审计
    p.status = "published"
    p.audit.append({"ts": _now(), "op": "publish", "author": author,
                    "note": note, "value": val,
                    "patch_path": patch_path, "release_path": release_path})
    _save_store(reg, path, store)

    # landed 记录补发布元数据
    all_ = _load_landed(landed_path)
    if p.id in all_ and isinstance(all_[p.id], dict):
        all_[p.id]["published_at"] = _now()
        all_[p.id]["published_by"] = author
        all_[p.id]["patch_path"] = patch_path
        all_[p.id]["release_path"] = release_path
        _save_landed(all_[p.id], landed_path)

    return {"status": "published", "id": p.id, "value": val,
            "author": author,
            "patch_path": patch_path, "release_path": release_path,
            "diff_lines": len(patch_text.splitlines()),
            "reason": "已生成正式补丁 + Release Notes 草稿；git apply/合并与正式发布由维护者执行"}


def list_published(landed_path: Optional[str] = None) -> List[dict]:
    """已发布记录（含 published_at/patch/release 路径），供 WebUI 展示。"""
    all_ = _load_landed(landed_path)
    out = []
    for bid in sorted(all_.keys()):
        rec = all_[bid]
        if rec.get("published_at"):
            out.append({"bid": bid,
                        "title": rec.get("title", ""),
                        "metric": rec.get("metric", ""),
                        "oracle_fn_name": rec.get("oracle_fn_name", ""),
                        "reviewed_by": rec.get("reviewed_by", ""),
                        "reviewed_at": rec.get("reviewed_at", ""),
                        "landed_at": rec.get("landed_at", ""),
                        "published_at": rec.get("published_at", ""),
                        "published_by": rec.get("published_by", ""),
                        "patch_path": rec.get("patch_path", ""),
                        "release_path": rec.get("release_path", "")})
    return out
