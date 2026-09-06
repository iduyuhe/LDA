"""创新超市分类体系护栏 smoke（v0.9.42 · 分类下沉 + 派生表防漂移）。

防什么
------
1. **货架漏分类标签**。`ShelfItem.track` / `app_domain` 是筛选器与（二期）锚定导购
   的检索底座。新增货架若漏标，用户就筛不到它 —— 静默丢失，无人报警。
2. **派生表漂移**（与上一轮定价归档 58/75 同一病根）。分类标签存 .py，同时
   落盘 `innovation_market.json`；两处必须逐条一致。
3. **前端回潮**。`store.html` 曾硬编码 `DIR_SHELVES` ID 列表（6 方向 → 只覆盖
   58/75），随货架扩张静默漂移。现已改为由 `/api/store/config` 的 directions
   动态下发；本 smoke 断言前端不得再出现该硬编码。
4. **方向映射脏 ID**。`store.py: CUSTOM_DIRECTION_SHELVES` 里的 ID 必须全部真实
   存在（原前端版本就漏了 17 条近三轮新增货）。
5. **UI 计数失真**。`/api/shelf` 的 facets 计数必须与实数据一致 —— 否则用户看到
   「CPO 12 条」点进去只有 11 条。

判据（死标量，LLM 不进判决路径）
--------------------------------
  ① 每条货架 track 与 app_domain 均非空（全覆盖）
  ② 枚举闭合：track ∈ SHELF_TRACKS；app_domain ∈ SHELF_APP_DOMAINS[track]
  ③ app_domain key 跨赛道全局唯一（否则 facets 计数会跨赛道合并 → 数字失真）
  ④ .json 派生表与 .py 逐条一致
  ⑤ 方向映射覆盖全部货架且无脏 ID
  ⑥ store.html 不再含 DIR_SHELVES / DIR_LABELS 硬编码（防回潮）
  ⑦ facets 计数与实数据一致（track / app_domain / tier 三维）
  ⑧ 🔴 反向测试 A：注入无 track 货架 ⇒ ① 必须报缺口
  ⑨ 🔴 反向测试 B：注入跨赛道 app_domain ⇒ ② 必须报非法
  ⑩ 🔴 反向测试 C：方向映射注入脏 ID ⇒ ⑤ 必须报脏
  ⑪ 对外文档（README/CHANGELOG）里的「N 应用域」与代码实际一致
  ⑫ 🔴 反向测试 D：文档写错数字 ⇒ ⑪ 必须报

判据 ⑪ 由来（v0.9.42 实证）：文档写「5 赛道 + 20 应用域」，代码实际 **24** 个应用域
（datacom 5 + sensing 6 + quantum 2 + cpo 4 + component 7）。散文里的数字是**对外账本**，
会随代码演进静默失真 —— 与 CI core 97≠117 属同一类，故一并纳入门禁。
注：只锁「N 应用域」（该表述在两份文档里各只出现一次，无歧义）；
「N 赛道」不锁，因 CHANGELOG 历史文案里另有「4 赛道」表述，断言会误报。

运行：python lda/run_shelf_taxonomy_smoke.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Set

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_l2.innovation_market import (  # noqa: E402
    DEFAULT_SHELF, SHELF_TRACKS, SHELF_APP_DOMAINS, taxonomy_check,
)
from lda_webui.shelf_pricing import tier_of  # noqa: E402

_JSON = os.path.join(_LDA, "lda_l2", "innovation_market.json")
_HTML = os.path.join(_LDA, "lda_webui", "static", "store.html")
_ROOT = os.path.dirname(_LDA)
_README = os.path.join(_ROOT, "README.md")
_CHANGELOG = os.path.join(_ROOT, "CHANGELOG.md")

CHECKS: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


# --- 判据实现（纯函数，便于反向测试注入） -------------------------------

def _missing_labels(shelf) -> List[str]:
    """① 返回缺 track 或 app_domain 的货架 id。"""
    return [s.id for s in shelf if not (s.track and s.app_domain)]


def _illegal_combos(shelf) -> List[str]:
    """② 返回 (track, app_domain) 组合非法的货架 id。"""
    return [s.id for s in shelf if taxonomy_check(s.track, s.app_domain)]


def _dup_domain_keys() -> List[str]:
    """③ 返回跨赛道重复出现的 app_domain key。"""
    seen: Dict[str, Set[str]] = {}
    for tr, doms in SHELF_APP_DOMAINS.items():
        for d in doms:
            seen.setdefault(d, set()).add(tr)
    return sorted(d for d, trs in seen.items() if len(trs) > 1)


def _json_mismatch(shelf) -> List[str]:
    """④ 返回 .json 与 .py 标签不一致的货架 id。"""
    if not os.path.exists(_JSON):
        return ["<json 不存在>"]
    data = json.load(open(_JSON, encoding="utf-8"))
    by_id = {d.get("id"): d for d in data}
    out = []
    for s in shelf:
        d = by_id.get(s.id)
        if d is None:
            out.append(f"{s.id}(json 缺)")
        elif d.get("track") != s.track or d.get("app_domain") != s.app_domain:
            out.append(f"{s.id}(py={s.track}/{s.app_domain} "
                       f"json={d.get('track')}/{d.get('app_domain')})")
    return out


def _direction_problems(shelf, dir_shelves: Dict[str, List[str]]) -> List[str]:
    """⑤ 返回方向映射的问题：脏 ID / 未覆盖的货架。"""
    ids = {s.id for s in shelf}
    out = []
    covered: Set[str] = set()
    for k, v in dir_shelves.items():
        for sid in v:
            covered.add(sid)
            if sid not in ids:
                out.append(f"脏 ID {sid}（方向 {k}）")
    uncovered = sorted(ids - covered)
    if uncovered:
        out.append(f"未覆盖 {len(uncovered)} 条：{uncovered[:5]}"
                   f"{'…' if len(uncovered) > 5 else ''}")
    return out


def _html_hardcode() -> List[str]:
    """⑥ 返回 store.html 中回潮的硬编码痕迹。"""
    if not os.path.exists(_HTML):
        return ["<store.html 不存在>"]
    src = open(_HTML, encoding="utf-8").read()
    return [t for t in ("DIR_SHELVES", "DIR_LABELS") if t in src]


def _facet_mismatch(shelf) -> List[str]:
    """⑦ 真跑 app.shelf_status() 的 facets，与实数据逐维比对。

    🔴 必须调**生产代码**算 facets，不能在 smoke 里另写一份同式复算 ——
    那样只是自我比对（重言式），app.py 口径改错了也测不出来。
    """
    from lda_webui.app import shelf_status  # noqa: E402（延迟：避免 import 期副作用）
    d = shelf_status(None)
    facets = d.get("facets") or {}
    labels = d.get("labels") or {}
    out: List[str] = []

    real: Dict[str, Dict[str, int]] = {}
    for s in shelf:
        for dim, k in (("track", s.track), ("app_domain", s.app_domain),
                       ("tier", tier_of(s.id))):
            if k:
                real.setdefault(dim, {})
                real[dim][k] = real[dim].get(k, 0) + 1

    for dim in ("track", "app_domain", "tier"):
        got = facets.get(dim) or {}
        want = real.get(dim) or {}
        if got != want:
            diff = {k: (got.get(k), want.get(k)) for k in set(got) | set(want)
                    if got.get(k) != want.get(k)}
            out.append(f"{dim} 计数不符(实得/应为)：{diff}")
        if sum(got.values()) != len(shelf):
            out.append(f"{dim} 计数合计 {sum(got.values())} ≠ 货架数 {len(shelf)}")

    # facet 里出现的 key 必须有中文标签（否则前端只能显示英文 key）
    lab_map = {"track": labels.get("track") or SHELF_TRACKS,
               "app_domain": labels.get("app_domain") or {},
               "tier": labels.get("tier") or {}}
    for dim, lm in lab_map.items():
        nolabel = sorted(k for k in (facets.get(dim) or {}) if k not in lm)
        if nolabel:
            out.append(f"{dim} 缺中文标签：{nolabel}")
    # 每条货架的标签 key 也必须在 labels 里（前端渲染卡片标签要用）
    for s in shelf:
        if s.track and s.track not in (labels.get("track") or {}):
            out.append(f"{s.id}.track={s.track} 无中文标签")
        if s.app_domain and s.app_domain not in (labels.get("app_domain") or {}):
            out.append(f"{s.id}.app_domain={s.app_domain} 无中文标签")
    return out


def _prose_app_domain_numbers(text: str) -> List[int]:
    """从散文里抽取「N 应用域」形式写出的数字。

    用途：README / CHANGELOG 是**对外账本**，里面的数字若描述代码实体，
    就会随代码演进而静默失真（本轮实测：文档写「20 应用域」，实际 24 个）。
    """
    return [int(m) for m in re.findall(r"(\d+)\s*应用域", text or "")]


def _prose_mismatch(shelf) -> List[str]:
    """⑪ 返回对外文档里与代码不符的「N 应用域」数字。"""
    want = sum(len(v) for v in SHELF_APP_DOMAINS.values())
    out: List[str] = []
    for f in (_README, _CHANGELOG):
        if not os.path.exists(f):
            out.append(f"{os.path.basename(f)} 不存在")
            continue
        nums = _prose_app_domain_numbers(open(f, encoding="utf-8").read())
        bad = [n for n in nums if n != want]
        if bad:
            out.append(f"{os.path.basename(f)} 写 {bad}，代码实际 {want}")
        elif not nums:
            out.append(f"{os.path.basename(f)} 未出现「N 应用域」（应写明以便核对）")
    return out


def main() -> int:
    rc = 0
    shelf = DEFAULT_SHELF
    print("=" * 74)
    print("创新超市分类体系护栏（v0.9.42）")
    print("=" * 74)
    print(f"货架总数：{len(shelf)}\n")

    # ① 全覆盖
    miss = _missing_labels(shelf)
    rc |= not check("① 分类标签全覆盖（track + app_domain 均非空）",
                    not miss, f"缺标签 {len(miss)} 条：{miss[:5]}")

    # ② 枚举闭合
    bad = _illegal_combos(shelf)
    rc |= not check("② 枚举闭合（track∈SHELF_TRACKS，app_domain 属本赛道）",
                    not bad, f"非法组合 {len(bad)} 条：{bad[:5]}")

    # ③ 应用域 key 全局唯一
    dup = _dup_domain_keys()
    rc |= not check("③ app_domain key 跨赛道全局唯一（防 facets 计数合并失真）",
                    not dup, f"重复 key：{dup}")

    # ④ 派生表同步
    jm = _json_mismatch(shelf)
    rc |= not check("④ innovation_market.json 与 .py 逐条一致（派生表）",
                    not jm, f"不一致 {len(jm)} 条：{jm[:3]}")

    # ⑤ 方向映射
    from lda_webui.store import CUSTOM_DIRECTION_SHELVES  # noqa: E402
    dprob = _direction_problems(shelf, CUSTOM_DIRECTION_SHELVES)
    rc |= not check("⑤ 定制需求方向映射覆盖全量且无脏 ID",
                    not dprob, f"{dprob[:3]}")

    # ⑥ 前端防回潮
    hc = _html_hardcode()
    rc |= not check("⑥ store.html 不再硬编码 DIR_SHELVES/DIR_LABELS（防回潮）",
                    not hc, f"回潮痕迹：{hc}")

    # ⑦ facets 计数一致
    fm = _facet_mismatch(shelf)
    rc |= not check("⑦ facets 计数与实数据一致且均有中文标签",
                    not fm, f"{fm[:3]}")

    # ⑪ 对外文档里的数字（散文里的数字会随代码演进静默失真）
    pm = _prose_mismatch(shelf)
    n_dom = sum(len(v) for v in SHELF_APP_DOMAINS.values())
    rc |= not check(f"⑪ 对外文档「N 应用域」与代码一致（代码实际 {n_dom} 个）",
                    not pm, f"{pm}")

    # ⑫ 反向测试 D：文档写错数字 ⇒ ⑪ 必须报
    fake = f"超市按 999 应用域分类（错写）"
    n_fake = _prose_app_domain_numbers(fake)
    rc |= not check("⑫ 反向测试 D：文档写错「N 应用域」⇒ ⑪ 必须报",
                    n_fake == [999] and 999 != n_dom, f"抽到 {n_fake}")

    # ⑧ 反向测试 A：注入无 track 货架
    from dataclasses import replace as _replace
    ghost = _replace(shelf[0], id="IM-GHOST-NO-TRACK", track="", app_domain="")
    m2 = _missing_labels(list(shelf) + [ghost])
    rc |= not check("⑧ 反向测试 A：注入无 track 货架 ⇒ ① 必须报缺口",
                    "IM-GHOST-NO-TRACK" in m2, f"报出 {len(m2)} 条")

    # ⑨ 反向测试 B：注入跨赛道 app_domain
    cross = _replace(shelf[0], id="IM-GHOST-CROSS", track="datacom",
                     app_domain="cpo_engine")
    b2 = _illegal_combos(list(shelf) + [cross])
    rc |= not check("⑨ 反向测试 B：注入跨赛道 app_domain ⇒ ② 必须报非法",
                    "IM-GHOST-CROSS" in b2, f"报出 {len(b2)} 条")

    # ⑩ 反向测试 C：方向映射注入脏 ID
    dirty = {k: list(v) for k, v in CUSTOM_DIRECTION_SHELVES.items()}
    k0 = next(iter(dirty))
    dirty[k0] = dirty[k0] + ["IM-NOT-EXIST"]
    p3 = _direction_problems(shelf, dirty)
    rc |= not check("⑩ 反向测试 C：方向映射注入脏 ID ⇒ ⑤ 必须报脏",
                    any("IM-NOT-EXIST" in x for x in p3), f"报出 {len(p3)} 项")

    n_pass = sum(1 for c in CHECKS if c["ok"])
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(CHECKS) - n_pass} FAIL / 共 {len(CHECKS)} 项")
    if rc == 0:
        print("ALL PASS — 分类体系无漏标、派生表无漂移、前端无回潮、护栏会响")
    else:
        print("FAIL — 分类体系存在缺口，请按上方 FAIL 项修复")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
