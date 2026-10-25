# -*- coding: utf-8 -*-
"""缺口台账并账生成器（N4 · v0.9.283）。

把 18 张案例卡的 `case_card()["gaps"]` 并成**一张可机核的表**：

    docs/GAP_SETTLEMENT.md    人读（markdown 表）
    docs/gap_settlement.json  机读（含棘轮）

═══ 为什么需要它（N4 的核心发现）═══
审计 v3 写「94 条缺口」，现算 **112** —— 漏了 **18 条**：
`j1`(2) / `j3`(4) / `oi`(7) / `accel`(5)。前两者模块级无 `GAPS` 常量，后两者只在
`case_card()` 里返回；而审计只扫了模块级常量 ⇒ 结构性漏计。

🔴 **更严重的是第二个发现**：112 条里 **58 条根本没有闭合状态标记**
（超导 5 + 电子 20 + 光子 14 + 量子 19 全无状态）。原因不是"没人标"，
是**台账有 6 种形态**：

    gaps_closed 字段 / 元素 closed 键 / 元素 status 键 / 元素 state 键 /
    纯字符串（无状态） / 元素无状态字段

⇒ **任何单一的「已闭合 X 条」数字都取决于口径。** 本生成器**不猜**：
无可靠状态源的一律计入 `unmarked`，并**逐卡登记它的状态来源**。

═══ 纪律 ===═
· 纯 stdlib、无时间戳、无随机 ⇒ 两次运行逐字节相同
· `--check` 只比对不写盘（供门禁守「文档与代码同源」）
· 不改任何卡、不产生任何新物理量
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "lda"))

#: 卡 → 域。d1/d2/d4 是**量子域蓝图 v2**（光-量异质集成 / QEC 码族 / 域扩展），
#: 🔴 审计 v3 把它们算进"光子 36 条" ⇒ 域归属错误，本表修正。
DOMAIN = {
    "pchip": "光子", "pm": "光子", "soc": "光子", "oi": "光子",
    "accel": "光子", "sensor": "光子",
    "qchip": "量子", "qs": "量子", "j1": "量子", "j2": "量子", "j3": "量子",
    "j4": "量子", "j5": "量子", "d1": "量子", "d2": "量子", "d4": "量子",
    "schip": "超导", "ecore": "电子",
}
#: 模块名不规整者单列
MODULE = {"d4": "d4case"}
#: qchip 的 case_card 默认 n_modes=216（flagship），这里统一用 12 保持快且稳定
ARGS = {"qchip": (12,)}

#: 棘轮（各自方向由 `_RATCHET` 声明）。**必须机器守**，否则只是注释。
UNMARKED_MAX = 0       # 待补状态的缺口数（只降）—— v0.9.286 已达 0：112/112 全部可机核
OPEN_MAX = 15          # 🔴 **未闭合 = 真欠债**（只降）—— v0.9.299 schip G-E 闭合后 16→15
CLOSED_MIN = 56        # 已闭合（只升）—— v0.9.299 schip G-E（TSV / 倒装焊 / 低温衰减链）
SETTLED_MIN = 11       # 已结算（只升）—— v0.9.289 qchip G_Q9（M2 布局最小长度守卫绕过）
BOUNDARY_MIN = 34      # 边界声明（只升）—— v0.9.299 schip G-Eb（整阵列集体耦合/装配公差/衰减器频响）
                       #   （参考设计的范围/模型边界原先被 closed=False 记成欠债）

# ── 状态词表（**唯一权威** · v0.9.286 四值口径）──────────────────────────
# 🔴 **为什么是四值而不是二值**（用户定调 A 案）：`gaps` 里混了不同性质的东西，
#    压进「已闭/未闭」二元必然压扁（同 N3-b 把「限制」写成「深度变浅」）：
#      ① 已闭合：工作做完，证据链可查（soc G1–G6、j3 M0–M4、ecore G-J/G-K）
#      ② 已结算：问题有裁决、**不再挂账**，但**能力/证据未必具备**
#         （判为不可锚 / 派生量 / 净增 0 / 明确决定不修，如 ecore G-N 极性缺陷「不改 mna + B14 锁死」）
#      ③ 未闭合：确认仍未做 —— 这才是**欠债**
#      ④ 边界声明：永久能力边界，**本来就不以「做完」为目标**（非流片、零能效纪律、理想化模型）
#    ⇒ 把 ②③ 塞进「已闭」= 又一次概念压扁；把 ④ 当「未闭」= 把诚实边界记成欠债。
GAP_CLOSED = "已闭合"
GAP_SETTLED = "已结算"
GAP_OPEN = "未闭合"
GAP_BOUNDARY = "边界声明"
GAP_STATES = (GAP_CLOSED, GAP_SETTLED, GAP_OPEN, GAP_BOUNDARY)

# 历史遗留写法 → 四值（**只做显式映射，不猜散文**）。键为小写子串。
_LEGACY_MAP = (
    ("未闭合", GAP_OPEN), ("非闭合", GAP_OPEN), ("开放", GAP_OPEN),
    ("未开工", GAP_OPEN), ("未实现", GAP_OPEN), ("未修", GAP_OPEN),
    ("净增 0", GAP_SETTLED), ("净增0", GAP_SETTLED), ("裁决净增", GAP_SETTLED),
    ("已结算", GAP_SETTLED), ("结算", GAP_SETTLED),
    ("边界", GAP_BOUNDARY),
    ("已闭合", GAP_CLOSED), ("闭合", GAP_CLOSED), ("closed", GAP_CLOSED),
)


def _state_of(status):
    """状态串 → 四值之一，或 None（无可信状态源）。

    🔴 **先判「未」再判「已」**（`未闭合` 含 `闭合`）；判定顺序即 `_LEGACY_MAP` 的顺序。
    """
    t = str(status).strip().lower()
    if not t:
        return None
    # 标准四值优先（前缀精确匹配，避免「未闭合」被当「闭合」）
    for st in GAP_STATES:
        if t.startswith(st):
            return st
    for tok, st in _LEGACY_MAP:
        if tok in t:
            return st
    return None


#: 分类器自测（**四值全覆 + 两侧都验**）。任一失败 ⇒ 生成器拒跑。
_TEST_CASES = (
    ("CLOSED（S5-ext）", GAP_CLOSED),          # soc 真实取值（旧实现漏判的那条）
    ("CLOSED（机制 · 真值未持有）", GAP_CLOSED),
    ("已闭合（M0–M4）", GAP_CLOSED),
    ("闭合（B515）", GAP_CLOSED),
    ("未闭合", GAP_OPEN),                      # j2
    ("开放", GAP_OPEN),                        # sensor
    ("未开工", GAP_OPEN),
    ("已结算（E13 已补 DD；残余见 G-L）", GAP_SETTLED),
    ("能力层已建 · 锚净增 0（四重避让）", GAP_SETTLED),   # j4：裁决不新增锚 ≠ 闭合
    ("裁决净增 0", GAP_SETTLED),
    ("边界声明（非流片实测）", GAP_BOUNDARY),
    ("随便写点什么", None),
    ("", None),
)


def _selftest():
    """返回失败项列表（空 = 全过）。"""
    return [(s, e, _state_of(s)) for s, e in _TEST_CASES if _state_of(s) != e]




FIELDS = ("closed", "settled", "open", "boundary", "unmarked")


def _zero():
    return {f: 0 for f in FIELDS}


def _counts_from(states):
    c = _zero()
    for s in states:
        if s == GAP_CLOSED:
            c["closed"] += 1
        elif s == GAP_SETTLED:
            c["settled"] += 1
        elif s == GAP_OPEN:
            c["open"] += 1
        elif s == GAP_BOUNDARY:
            c["boundary"] += 1
        else:                      # None = 无可信状态源
            c["unmarked"] += 1
    return c


def _classify(card):
    """返回 (缺口数, 状态来源, 四值计数 or None)。None = 整卡无可信状态源。"""
    g = card.get("gaps") or []
    n = len(g)
    if not g:
        return 0, "无缺口", _zero()
    # ① 显式 `gaps_status`（与 gaps 逐条对齐）—— 字符串型 gaps 的卡用这个，
    #    好处是**不动 gaps 形状**（前端仍按字符串渲染），状态又能机核。
    gs = card.get("gaps_status")
    if isinstance(gs, (list, tuple)) and len(gs) == n:
        return n, "gaps_status 列表", _counts_from([_state_of(x) for x in gs])
    # ② dict 元素自带 status / state / closed
    if isinstance(g[0], dict):
        head = g[0]
        for key in ("status", "state"):
            if key in head:
                return n, "元素 %s 键" % key, _counts_from([_state_of(x.get(key)) for x in g])
        if "closed" in head:
            return (n, "元素 closed 键",
                    _counts_from([GAP_CLOSED if x.get("closed") is True else GAP_OPEN for x in g]))
    # ③ 标量 `gaps_closed`（旧口径：只区分闭/未闭，不细分结算与边界）
    gc, gt = card.get("gaps_closed"), card.get("gaps_total")
    if isinstance(gc, int) and isinstance(gt, int) and gt == n:
        return (n, "gaps_closed 字段",
                _counts_from([GAP_CLOSED] * gc + [GAP_OPEN] * (n - gc)))
    return n, ("纯字符串（无状态）" if not isinstance(g[0], dict) else "元素无状态字段"), None


def collect():
    """现算全表（确定性）。"""
    cards = {}
    for k in sorted(DOMAIN):
        mod = MODULE.get(k, k + "_case")
        M = importlib.import_module("lda_webui." + mod)
        card = M.case_card(*ARGS.get(k, ()))
        n, src, cnt = _classify(card)
        if cnt is None:
            cnt = _zero()
            cnt["unmarked"] = n
        cards[k] = {"domain": DOMAIN[k], "gaps": n, "status_source": src,
                    "machine_checkable": src not in ("纯字符串（无状态）", "元素无状态字段"),
                    "counts": cnt,
                    "closed": cnt["closed"], "settled": cnt["settled"],
                    "open": cnt["open"], "boundary": cnt["boundary"],
                    "unmarked": cnt["unmarked"]}
    agg = {}
    for k in sorted(cards):
        d = cards[k]["domain"]
        a = agg.setdefault(d, {"gaps": 0, **{f: 0 for f in FIELDS}})
        a["gaps"] += cards[k]["gaps"]
        for f in FIELDS:
            a[f] += cards[k][f]
    total = {"gaps": sum(agg[d]["gaps"] for d in agg)}
    for f in FIELDS:
        total[f] = sum(agg[d][f] for d in agg)
    return {"schema": "lda_gap_settlement_v2", "cards": cards,
            "by_domain": agg, "total": total,
            "ratchet": {"unmarked_max": UNMARKED_MAX, "closed_min": CLOSED_MIN,
                        "settled_min": SETTLED_MIN, "boundary_min": BOUNDARY_MIN,
                        "open_max": OPEN_MAX}}



def render_md(ref) -> str:
    """渲染 markdown（确定性；仅由 ref 决定）。"""
    c, agg, tot = ref["cards"], ref["by_domain"], ref["total"]
    out = [
        "# 缺口台账并账（N4 · v0.9.286 四值口径）",
        "",
        "> **本文件由 `scripts/gen_gap_settlement.py` 生成，请勿手改** ——",
        "> 门禁 `run_p2_usability_smoke` 会重跑生成器比对，零漂移才通过。",
        "> 数据源：18 张案例卡的 `case_card()[\"gaps\"]` + `gaps_status`／元素 `status` 现算",
        "> （纯 stdlib · 无时间戳）。",
        "",
        "## 1. 四值口径（**为什么不是二值**）",
        "",
        "| 状态 | 含义 | 是否欠债 |",
        "|---|---|---|",
        "| **已闭合** | 工作做完，证据链可查（如 `soc` G1–G6、`j3` M0–M4） | 否 |",
        "| **已结算** | 问题有裁决、不再挂账，但**能力/证据未必具备**"
        "（判不可锚／派生量／净增 0／决定不修，如 `ecore` G-N 极性缺陷「不改 mna + B14 锁死」） | 否 |",
        "| **未闭合** | 确认仍未做 —— **这才是欠债** | **是** |",
        "| **边界声明** | 永久能力边界，本来就不以「做完」为目标（非流片实测／零能效纪律／理想化模型） | 否 |",
        "",
        "> 🔴 把「已结算」塞进「已闭合」= 又一次**概念压扁**（同 N3-b 把「限制」写成「深度变浅」）；",
        "> 把「边界声明」当「未闭合」= **把诚实边界记成欠债**，会诱导以后删掉边界声明。",
        "",
        "## 2. 逐卡并账",
        "",
        "| 域 | 卡 | 缺口数 | 状态来源 | 已闭合 | 已结算 | 未闭合 | 边界声明 | 未标 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for k in sorted(c):
        r = c[k]
        out.append("| %s | `%s` | %d | %s | %d | %d | %d | %d | %s |"
                   % (r["domain"], k, r["gaps"], r["status_source"],
                      r["closed"], r["settled"], r["open"], r["boundary"],
                      ("**%d**" % r["unmarked"]) if r["unmarked"] else "0"))
    out += [
        "",
        "## 3. 按域汇总",
        "",
        "| 域 | 缺口 | 已闭合 | 已结算 | 未闭合 | 边界声明 | 未标状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in ("光子", "量子", "超导", "电子"):
        if d in agg:
            a = agg[d]
            out.append("| %s | %d | %d | %d | %d | %d | **%d** |"
                       % (d, a["gaps"], a["closed"], a["settled"], a["open"],
                          a["boundary"], a["unmarked"]))
    out += [
        "| **合计** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** |"
        % (tot["gaps"], tot["closed"], tot["settled"], tot["open"],
           tot["boundary"], tot["unmarked"]),
        "",
        "## 4. 结论（比数字更重要）",
        "",
        "1. 🔴 **总数是 %d，不是 94**。审计 v3 漏了 **18 条**：`j1`(2) / `j3`(4) /"
        " `oi`(7) / `accel`(5) —— 前两者模块级无 `GAPS` 常量、后两者只在 `case_card()`"
        " 里返回，而审计只扫了模块级常量。" % tot["gaps"],
        "2. 🔴 **域归属修正**：`d1`/`d2`/`d4` 是**量子域蓝图 v2**，审计 v3 把它们算进"
        "「光子 36 条」⇒ 光子/量子的真实构成与旧表**不同数**（旧光子 36 = pchip+sensor"
        "+pm+soc+d1+d2+d4；新光子 36 = pchip+pm+soc+oi+accel+sensor）。"
        "**同数不同构成 —— 聚合数字又一次掩盖了结构。**",
        "3. 🔴🔴 **v0.9.286 修正分类器漏判**：`soc` 的 6 条状态字面写着 `CLOSED（…）`，"
        "旧实现只在状态串里找中文「闭合」二字 ⇒ 全部漏判成未闭，台账对外报「已闭 0」。"
        "改为**显式词表 + 12 条自测**（四值全覆盖），自测不过生成器拒跑。",
        "4. **真正的欠债只有「未闭合」一列 = %d 条**（不是历史上被当作欠债的 %d 条）；"
        "另有 %d 条是**永久边界**、%d 条是**已裁决不再挂账**。"
        "⇒ 对外说「%d 条缺口」时**必须带分布**，否则会把边界声明读成欠债。"
        % (tot["open"], tot["gaps"] - tot["closed"] - tot["settled"], tot["boundary"], tot["settled"], tot["gaps"]),
        "5. ⚠️ **%d 条仍未标**：给 `case_card()` 补 `gaps_status`（字符串型 gaps）或元素 `status`"
        "（dict 型 gaps）即可机核。**本表拒绝从散文里猜状态**。" % tot["unmarked"],
        "",
        "## 5. 棘轮（**全部机器守**，退步即拒跑）",
        "",
        "| 指标 | 当前 | 方向 | 含义 |",
        "|---|---|---|---|",
        "| `unmarked` | **%d** | 只降不升 | 待补状态源的缺口数 |" % tot["unmarked"],
        "| `closed` | **%d** | 只升不降 | 已闭合（证据链可查） |" % tot["closed"],
        "| `settled` | **%d** | 只升不降 | 已结算（裁决不再挂账） |" % tot["settled"],
        "| `boundary` | **%d** | 只升不降 | 永久边界声明 |" % tot["boundary"],
        "| 🔴 `open` | **%d** | **只降不升** | **未闭合 = 真欠债**（唯一应当递减的列） |"
        % tot["open"],
        "",
        "> 五列各自单向：**新加缺口必须带状态源**（否则 `unmarked` 涨 ⇒ 红）；",
        "> 已闭合/已结算/边界不得回退成未标（否则对应下界被击穿 ⇒ 红）；",
        "> **`open` 是唯一应当递减的列** —— 它涨说明新增了欠债，也判红（v0.9.289 新增）。",
        "",
    ]
    return "\n".join(out)



def _atomic_write(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="缺口台账并账（N4）")
    ap.add_argument("--check", action="store_true", help="只比对不写盘（供门禁）")
    a = ap.parse_args(argv)

    # 🔴 分类器自测先跑：状态词表改坏 ⇒ 立刻拒跑（不写盘、不当成功）
    bad = _selftest()
    if bad:
        print("FAIL: 状态分类器自测未过 %s" % (bad,), file=sys.stderr)
        return 2

    ref = collect()
    # 🔴 棘轮**必须机器守**（v0.9.286）：这些常量原先只写进 JSON 供人看，
    #    没有任何一处拒绝退步 ⇒ 那不是棘轮，是声明。回归会**静默通过**。
    #    此处四列各按自己的方向显式拒跑。
    t = ref["total"]
    breach = []
    if t["closed"] < CLOSED_MIN:
        breach.append("closed %d < %d" % (t["closed"], CLOSED_MIN))
    if t["settled"] < SETTLED_MIN:
        breach.append("settled %d < %d" % (t["settled"], SETTLED_MIN))
    if t["boundary"] < BOUNDARY_MIN:
        breach.append("boundary %d < %d" % (t["boundary"], BOUNDARY_MIN))
    if t["unmarked"] > UNMARKED_MAX:
        breach.append("unmarked %d > %d" % (t["unmarked"], UNMARKED_MAX))
    if t["open"] > OPEN_MAX:          # 🔴 真欠债只能减，不能增
        breach.append("open %d > %d" % (t["open"], OPEN_MAX))
    if breach:
        print("FAIL: 棘轮退步 —— %s" % " / ".join(breach), file=sys.stderr)
        return 3

    md = render_md(ref)
    js = json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    pm = os.path.join(ROOT, "docs", "GAP_SETTLEMENT.md")
    pj = os.path.join(ROOT, "docs", "gap_settlement.json")

    if a.check:
        bad = []
        for path, want in ((pm, md), (pj, js)):
            if not os.path.isfile(path):
                bad.append("%s 缺" % os.path.basename(path))
                continue
            with open(path, "rb") as f:
                got = f.read().decode("utf-8")
            if got != want:
                bad.append("%s 漂移" % os.path.basename(path))
        if bad:
            print("FAIL: " + " / ".join(bad), file=sys.stderr)
            return 1
        t = ref["total"]
        print("OK: 并账与代码一致（%d 缺口 · 已闭合 %d / 已结算 %d / 未闭合 %d / 边界 %d / 未标 %d）"
              % (t["gaps"], t["closed"], t["settled"], t["open"], t["boundary"], t["unmarked"]))
        return 0

    _atomic_write(pm, md)
    _atomic_write(pj, js)
    t = ref["total"]
    print("已生成 docs/GAP_SETTLEMENT.md / docs/gap_settlement.json")
    print("  缺口 %d（光子 %d / 量子 %d / 超导 %d / 电子 %d）"
          % (t["gaps"], ref["by_domain"]["光子"]["gaps"], ref["by_domain"]["量子"]["gaps"],
             ref["by_domain"]["超导"]["gaps"], ref["by_domain"]["电子"]["gaps"]))
    print("  已闭合 %d · 已结算 %d · 未闭合 %d · 边界声明 %d · 未标 %d"
          % (t["closed"], t["settled"], t["open"], t["boundary"], t["unmarked"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
