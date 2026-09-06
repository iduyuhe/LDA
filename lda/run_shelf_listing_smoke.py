"""创新超市「上架日期」护栏 smoke（v0.9.43 · N-1）。

防什么
------
**伪造新鲜度**。货架是分批扩出来的（08-27 首批 5 → 08-28 批量 43 → 08-29 商品化
10 → 09-06 三轮新增 17）。若 `listed_at` 允许手填，最省事的做法就是"统一填今天"
——那样 75 条货架会全部假装是新品，且**无人能发现**：数字格式合法、字段非空、
前端渲染正常，一切看起来都对。

这是 LDA 最不能容忍的一类失真：**数字脱离了它的来源**。物理定律锚之所以硬，
是因为它锚在定律上；上架日期要硬，就必须锚在 git 历史上 —— 不可事后编造。

口径
----
`listed_at` = 该货架 id 在本仓库中**首次出现**的提交日期（`git log --follow
--reverse` 逐提交扫描，取首次命中）。不是"设计完成日"，不是"首次公开发布日"，
是"这条货架进入仓库的那天"。口径单一，才可复算。

判据（死标量，LLM 不进判决路径）
--------------------------------
  ① 每条货架 listed_at 非空且为合法 YYYY-MM-DD
  ② 不晚于今天（未来日期 = 时钟异常或数据腐化，一律不接受）
  ③ 不早于货架纪元（首个货架进入仓库的日期；早于它说明填错了年份）
  ④ 🔴 **与 git 历史复算逐条一致**（反腐化核心：手填错一天即红）
  ⑤ `to_public()` 对外输出含 listed_at 且与数据一致（API 契约）
  ⑥ 前端已接：newest / oldest 两个排序选项 + `_cmpDate` / `_isNewListing` 均在位
     （防"后端加了字段、前端没接" —— 与 D-78 同源的断裂）
  ⑦ 🔴 反向 A：注入空 listed_at ⇒ ① 必须报缺口
  ⑧ 🔴 反向 B：注入未来日期 ⇒ ② 必须报
  ⑨ 🔴 反向 C：注入与 git 不符的日期 ⇒ ④ 必须报
  ⑩ 🔴 反向 D：抽掉前端排序选项 ⇒ ⑥ 必须报

运行：python lda/run_shelf_listing_smoke.py
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Tuple

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2.innovation_market import DEFAULT_SHELF as SHELF  # noqa: E402

_REPO = os.path.dirname(_LDA)                       # 仓库根（lda/ 的上一级）
_REL = "lda/lda_l2/innovation_market.py"
_HTML = os.path.join(_LDA, "lda_webui", "static", "store.html")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(r'id\s*=\s*["\'](IM-[A-Za-z0-9\.\-]+)["\']')

CHECKS: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  ← {detail}" if (detail and not ok) else ""))
    return bool(ok)


# --------------------------------------------------------------------------
# git 复算：每个货架 id 首次进入仓库的提交日期
# --------------------------------------------------------------------------
def git_first_seen() -> Tuple[Dict[str, str], str]:
    """返回 ({shelf_id: 'YYYY-MM-DD'}, 错误信息)。错误时字典为空。"""
    try:
        log = subprocess.run(
            ["git", "log", "--follow", "--reverse", "--format=%H|%ad",
             "--date=short", "--", _REL],
            cwd=_REPO, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        if log.returncode != 0:
            return {}, f"git log 失败 rc={log.returncode}: {log.stderr.strip()[:200]}"
        commits = [ln for ln in log.stdout.strip().splitlines() if "|" in ln]
        if not commits:
            return {}, "git log 无提交记录"
    except (OSError, subprocess.SubprocessError) as exc:
        return {}, f"git 不可用: {exc!r}"

    first: Dict[str, str] = {}
    for line in commits:
        sha, date = line.split("|", 1)
        try:
            show = subprocess.run(
                ["git", "show", f"{sha}:{_REL}"],
                cwd=_REPO, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {}, f"git show 失败: {exc!r}"
        if show.returncode != 0:
            continue
        for sid in set(_ID_RE.findall(show.stdout)):
            first.setdefault(sid, date)
    return first, ""


# --------------------------------------------------------------------------
# 判据实现（均可对任意 list 调用 —— 反向测试复用）
# --------------------------------------------------------------------------
def _bad_format(items) -> List[str]:
    out = []
    for s in items:
        v = getattr(s, "listed_at", "")
        if not v or not _DATE_RE.match(v):
            out.append(f"{s.id}={v!r}")
    return out


def _future(items, today: str) -> List[str]:
    return [f"{s.id}={s.listed_at}" for s in items
            if getattr(s, "listed_at", "") and s.listed_at > today]


def _before_epoch(items, epoch: str) -> List[str]:
    return [f"{s.id}={s.listed_at}" for s in items
            if getattr(s, "listed_at", "") and s.listed_at < epoch]


def _git_mismatch(items, truth: Dict[str, str]) -> List[str]:
    out = []
    for s in items:
        want = truth.get(s.id)
        if want is None:
            out.append(f"{s.id}={s.listed_at}（git 历史中查无此 id）")
        elif s.listed_at != want:
            out.append(f"{s.id}: 数据 {s.listed_at} ≠ git {want}")
    return out


def _public_mismatch(items) -> List[str]:
    return [f"{s.id}" for s in items
            if s.to_public().get("listed_at") != getattr(s, "listed_at", "")]


def _frontend_gaps(html: str) -> List[str]:
    """前端是否真的接上了上架日期（防"后端加了、前端没接"）。"""
    gaps = []
    if 'value="newest"' not in html:
        gaps.append("缺 newest 排序选项")
    if 'value="oldest"' not in html:
        gaps.append("缺 oldest 排序选项")
    if "function _cmpDate(" not in html:
        gaps.append("缺 _cmpDate() 排序比较器")
    if "function _isNewListing(" not in html:
        gaps.append("缺 _isNewListing() NEW 判定")
    if "_cmpDate(a.listed_at,b.listed_at" not in html:
        gaps.append("filteredRows 未把 listed_at 接进排序")
    if "上架 " not in html:
        gaps.append("卡片未渲染上架日期")
    return gaps


def main() -> int:
    print("=" * 74)
    print("创新超市「上架日期」护栏（v0.9.43 · N-1）")
    print("=" * 74)

    shelf = list(SHELF)
    today = _dt.date.today().isoformat()
    rc = 0

    # ---- git 复算（反腐化核心）----
    truth, err = git_first_seen()
    if not truth:
        rc |= not check("⓪ git 历史复算可用（后续判据的前置）", False, err)
        print("-" * 74)
        print("FAIL — git 不可用，上架日期失去可溯源基准，无法判定")
        return int(rc)
    epoch = min(truth.values())
    rc |= not check(f"⓪ git 历史复算可用（{len(truth)} 个 id · 货架纪元 {epoch}）", True)

    # ① 格式
    bf = _bad_format(shelf)
    rc |= not check(f"① {len(shelf)} 条货架 listed_at 非空且格式合法", not bf, str(bf[:5]))

    # ② 不晚于今天
    fu = _future(shelf, today)
    rc |= not check(f"② listed_at 不晚于今天（{today}）", not fu, str(fu[:5]))

    # ③ 不早于货架纪元
    be = _before_epoch(shelf, epoch)
    rc |= not check(f"③ listed_at 不早于货架纪元（{epoch}）", not be, str(be[:5]))

    # ④ 与 git 历史逐条一致
    gm = _git_mismatch(shelf, truth)
    rc |= not check(f"④ listed_at 与 git 历史复算逐条一致（{len(shelf)} 条）",
                    not gm, str(gm[:5]))

    # ⑤ 对外 API 契约
    pm = _public_mismatch(shelf)
    rc |= not check(f"⑤ to_public() 对外输出含 listed_at 且与数据一致", not pm, str(pm[:5]))

    # ⑥ 前端已接
    html = open(_HTML, encoding="utf-8").read() if os.path.exists(_HTML) else ""
    fg = _frontend_gaps(html)
    rc |= not check("⑥ 前端已接上架日期（排序选项 + 比较器 + NEW + 卡片渲染）",
                    bool(html) and not fg, str(fg))

    # ---- 反向测试：证明上面每一条都会响 ----
    from dataclasses import replace as _rep

    # ⑦ 注入空 listed_at
    g1 = _rep(shelf[0], id="IM-GHOST-NO-DATE", listed_at="")
    rc |= not check("⑦ 反向 A：注入空 listed_at ⇒ ① 必须报缺口",
                    any("IM-GHOST-NO-DATE" in x for x in _bad_format(list(shelf) + [g1])))

    # ⑧ 注入未来日期
    future_day = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
    g2 = _rep(shelf[0], id="IM-GHOST-FUTURE", listed_at=future_day)
    rc |= not check("⑧ 反向 B：注入未来日期 ⇒ ② 必须报",
                    any("IM-GHOST-FUTURE" in x for x in _future(list(shelf) + [g2], today)))

    # ⑨ 注入与 git 不符的日期（这就是"伪造新鲜度"的样子）
    wrong_day = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    victim = next((s for s in shelf if s.listed_at != wrong_day), shelf[0])
    g3 = _rep(victim, listed_at=wrong_day)
    pool = [g3 if s.id == victim.id else s for s in shelf]
    rc |= not check(f"⑨ 反向 C：把 {victim.id} 改成 {wrong_day}（与 git 不符）⇒ ④ 必报",
                    any(victim.id in x for x in _git_mismatch(pool, truth)))

    # ⑩ 抽掉前端排序选项
    stripped = html.replace('value="newest"', 'value="xxx"')
    rc |= not check("⑩ 反向 D：抽掉前端 newest 选项 ⇒ ⑥ 必须报",
                    any("newest" in x for x in _frontend_gaps(stripped)))

    n_pass = sum(1 for c in CHECKS if c["ok"])
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(CHECKS) - n_pass} FAIL / 共 {len(CHECKS)} 项")
    if rc == 0:
        print("ALL PASS — 上架日期全部可溯源至 git 历史，前端已接，护栏会响")
    else:
        print("FAIL — 上架日期存在腐化或前端未接，请按上方 FAIL 项修复")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
