"""D-223 · **公开函数可达性**门禁（能力层 · 净增 0 锚）。

## 门禁守什么

v0.9.271 修的那个 bug（`resonator_freq_ghz` 偏 1e6 倍）能潜伏很久，根因不是缺门禁，
而是 **这个函数全仓零引用** ⇒ 没有任何判据能碰它。同族的 `resonator_length_um`
有 3 处调用、方向正确、没 bug；反向函数写完就没人用。

⇒ 本门禁不追求「消灭所有零引用函数」，而是**要求每一个都被有意识地裁决过一次**。

  R 组  **双向**集合判据（核心）
        · 新增零引用函数 ⇒ 红（必须先分类登记，或改成私有）
        · 修好了但没删登记 ⇒ **也红**（防「登记了就不管」，这是登记制最常见的腐烂方式）
  X 组  互补性 —— 与 `dead_assert_guard`（扫 probe 突变锚点）分工不重叠
  G 组  **判别力反向验证** —— 注入假死/假活函数，分析器必须分别抓到/放过；
        以及**锁定面契约完整性**（v0.9.279 · D-227 · F-10 正解）：
        G7 能力层模块 100% 至少一个入口被反向锁定 · G8 锁定面与死函数面无交集 ·
        G9 豁免面自洽 · **G10 双粒度反向**（清空锁定 ⇒ 全模块缺口；删单模块锁定 ⇒ 缺口恰为该模块）
  Z 组  零增量 + 统计区间

## F-10 的口径修正（v0.9.279）

审计第二轮写「反向锁定只覆盖 **17/95 = 17.9%**」。**这个分母是错的**：
95 是 `DEAD_BASELINE`（已知**死**函数基线），拿"锁活"去比"已知死"永远不可能接近 100%。
真正该问的是「**能力层模块有没有一个入口被锁**」——那才是"有机制防它腐烂"。

实测：10 个带 `ANCHORABLE =` 声明的模块里，有 4 个**零锁定**（`noise_aware_schedule` /
`code_family` / `reachability` / `reachability_registry`）。它们**当前零死函数**，
所以一直没红 —— 但「现在恰好都活着」≠「有机制防它变死」，v0.9.271 的 1e6 倍 bug
正是「无锁 ⇒ 自由腐烂」。故本版按模块补入口，把契约从「若干条精确键」升级为
「**模块级全覆盖 + 反向可证伪**」。

## 为什么用**精确集合**而不是通配正则

若登记表写成 `r"_golden$"` 这类规则，**新增一个 `xxx_golden` 会被规则一起吞掉** ⇒
判据失去判别力（这正是项目在 BL/D1/D2 三轮里反复吃的亏：覆盖率 ≠ 判别力）。
所以 `DEAD_BASELINE` 是 95 条**精确键**，任何增减都必须人工过一遍。

## 判据标签避开 B/E/S 前缀（锚号前缀，会被 K4 文本代理误判成覆盖）

纯 stdlib（ast/os/sys）· 不 import 被测业务模块（唯一例外 `lda_harness.benchmarks`，
只为读 `golden_fn` 的函数对象）· 零子进程 · 零落盘。
"""
from __future__ import annotations

import ast
import os
import sys

from lda_harness import reachability as R
from lda_harness import reachability_registry as REG
from lda_harness.smoke_kit import make_check

_CNT = {"PASS": 0, "FAIL": 0}
# 🔴 v0.9.275：本文件的 `check` 改用 `smoke_kit` 单一实现（`run_helper_dup_ratchet_smoke`
#   J3/J4 要求「不得再添本地 `def check`」—— 本版把 .271~.275 新增的 5 道门禁全部归一）。
check = make_check(_CNT, ok_key="PASS", bad_key="FAIL", indent="  ",
                   detail_fmt="  |  {d}", detail_on="both", return_ok=True)




def main() -> int:
    _CNT["PASS"] = _CNT["FAIL"] = 0
    print("公开函数可达性 门禁 smoke（D-223）")

    res = R.analyze()
    st = res["stats"]
    now = R.dead_set(res)
    base = set(REG.DEAD_BASELINE)
    print("\n现算：公开 %d · 可达 %d · 零引用 **%d**（%.2f%%）· 锚入口名 %d · golden_fn 对象 %d"
          % (st["public_total"], st["reachable_total"], st["dead_total"],
             st["dead_pct"], st["anchor_entry_names"], st["golden_fn_entries"]))

    # ---------------- R 组：双向集合判据 ----------------
    print("\n[R] 双向集合判据（新增红 + 修好未删登记也红）")

    added = sorted(now - base)
    gone = sorted(base - now)
    check("R1 零引用集合 == 登记基线（新增 %d / 消失 %d）"
          % (len(added), len(gone)), not added and not gone,
          ("新增：" + ", ".join(added[:5]) + ("…" if len(added) > 5 else "")) if added else
          ("消失（已修好请删登记）：" + ", ".join(gone[:5]) +
           ("…" if len(gone) > 5 else "")) if gone else
          "%d 条逐条对齐" % len(now))

    check("R2 基线计数 == 现算计数（%d == %d）" % (len(base), len(now)),
          len(base) == len(now))

    st_reg = REG.baseline_stats()
    check("R3 基线无「自造分类」（每类都在 DEAD_CLASSES 里登记过）",
          not st_reg["unknown_classes"], str(st_reg["unknown_classes"]))
    check("R4 分类分布自洽（各类之和 == 总数 %d）" % st_reg["total"],
          sum(st_reg["by_class"].values()) == st_reg["total"],
          str(st_reg["by_class"]))

    # ---------------- X 组：互补性 + 反向锁定 ----------------
    print("\n[X] 互补性与反向锁定")

    try:
        from run_ci_regression import CORE_SMOKES
        both = ("run_dead_assert_guard_smoke.py" in CORE_SMOKES
                and "run_reachability_smoke.py" in CORE_SMOKES)
        check("X1 与 dead_assert_guard 互补且都在 CI core（前者扫 probe 锚点，本门禁扫函数可达性）",
              both, "core = %d 条" % len(CORE_SMOKES))
    except Exception as e:                                     # noqa: BLE001
        check("X1 与 dead_assert_guard 互补且都在 CI core", False, "不可读：%s" % e)

    need = [k for k in REG.MUST_BE_REACHABLE if k in now]
    check("X2 MUST_BE_REACHABLE 全部可达（%d 条，含 v0.9.271 的 bug 函数）"
          % len(REG.MUST_BE_REACHABLE), not need,
          ("变死：" + ", ".join(need[:4])) if need else "17 条关键交付物全部在活代码路径上")

    # ---------------- G 组：判别力反向验证 ----------------
    print("\n[G] 判别力反向验证（注入样本，必须分别抓到/放过）")

    def _toy(src):
        return ast.parse(src)

    # G1：假死函数必须被抓
    src = ("def live_one(): pass\n"
           "def dead_one():\n"
           "    return 1\n"
           "LIVE = {'x': live_one}\n")
    tree = _toy(src)
    funcs = R.public_funcs(tree)
    mod_ids = R.module_level_ids(tree)
    edges = {g: {t for t in R.ids_in(n) if t in funcs and t != g} for g, n in funcs.items()}
    roots = {n for n in funcs if n in mod_ids}
    reach, stack = set(roots), list(roots)
    while stack:
        cur = stack.pop()
        for nxt in edges.get(cur, ()):
            if nxt not in reach:
                reach.add(nxt); stack.append(nxt)
    dead_toy = set(funcs) - reach
    check("G1 注入的假死函数必被抓（dead_one 在死集、live_one 不在）",
          dead_toy == {"dead_one"}, "dead=%s" % sorted(dead_toy))

    # G2：不带括号的函数对象传递必须算活（记忆里的回调表血案）
    src2 = ("def cb(): pass\n"
            "TABLE = [('G2', cb, 8)]\n")
    t2 = _toy(src2)
    f2 = R.public_funcs(t2)
    m2 = R.module_level_ids(t2)
    check("G2 回调表里的 `cb`（不带括号）被算作活（模块级引用入口）",
          "cb" in m2 and set(f2) <= m2, "mod_ids=%s" % sorted(m2))

    # G3：v0.9.271 的 bug 函数必须可达（单列，防复发）
    check("G3 `resonator_freq_ghz`（v0.9.271 的 1e6 倍 bug 函数）必须可达",
          "lda/lda_qeda/sc_readout_mux.py::resonator_freq_ghz" not in now,
          "它若变死 ⇒ selfchecks ⑦b / 专属门禁的接线被拆了")

    # 🔴 G6：**契约完整性** —— `MUST_BE_REACHABLE` 是一份契约，**删条目本身就要红**。
    #    血案：首版只有 G3（查「它现在可达」），于是把该函数从列表里删掉仍全绿 ——
    #    「状态」与「契约」是两件事，必须各有一条判据：G3 守状态、G6 守契约。
    CRITICAL = "lda/lda_qeda/sc_readout_mux.py::resonator_freq_ghz"
    check("G6 契约完整：MUST_BE_REACHABLE 必须含 v0.9.271 的 bug 函数（删条目也红）",
          CRITICAL in REG.MUST_BE_REACHABLE,
          "它一旦被移出契约，1e6 倍错就会重新无人看守")

    # G4：分析器与登记表自身自检
    check("G4 分析器自检 4/4（Attribute/模块级/传递闭包/golden_fn 对象）",
          R.run_selfchecks(verbose=False))
    check("G5 登记表自检 5/5（分类齐备/键格式/无交集/无自造分类）",
          REG.run_selfchecks(verbose=False))

    # ── G7~G10 · v0.9.279（D-227 · F-10 正解）：锁定面**契约完整性** ──
    # 🔴 F-10 的原始表述是「反向锁定只覆盖 17/95 = 17.9%」，但 **17/95 这个分母是错的**：
    #    95 是 `DEAD_BASELINE`（已知**死**函数基线），拿"锁活"去比"已知死"永远不可能接近
    #    100%。真正该问的是：**能力层模块有没有一个入口被锁** —— 那才是"有机制防它腐烂"。
    #    故本组把口径换成「按模块计量」，并要求两个方向都能证伪。
    ct = REG.lock_contract()
    check("G7 锁定契约完整：能力层模块 %d/%d 至少一个入口被反向锁定（零锁模块 %d）"
          % (ct["n_covered"], ct["n_modules"], ct["n_uncovered"]),
          ct["n_uncovered"] == 0 and ct["n_modules"] > 0,
          "未覆盖=%s" % ct["uncovered"])

    check("G8 锁定面与死函数面**无交集**（不许把已知死函数写成\"必须活\"）",
          not ct["contradiction"], "矛盾=%s" % ct["contradiction"])

    check("G9 豁免面自洽（豁免项须真在能力层模块集内 ∧ 不与已锁模块重叠）",
          not ct["exempt_not_capability"] and not ct["exempt_but_locked"],
          "非能力层=%s 既锁又豁免=%s" % (ct["exempt_not_capability"],
                                         ct["exempt_but_locked"]))

    # 🔴 G10 反向：**把锁定面清空 ⇒ G7 必红**。
    #    没有这条，「10/10 覆盖」可能只是"恰好都覆盖了"，删掉条目它照样绿 ——
    #    这正是登记制最典型的失效模式（覆盖率 ≠ 判别力）。
    _saved = list(REG.MUST_BE_REACHABLE)
    try:
        REG.MUST_BE_REACHABLE.clear()
        bad = REG.lock_contract()
    finally:
        REG.MUST_BE_REACHABLE[:] = _saved
    # 再做一个**单模块**粒度的反向：只删某一模块的全部锁定条目 ⇒ 缺口恰为该模块
    _victim = REG.capability_modules()[0] if REG.capability_modules() else None
    single_ok = False
    if _victim:
        keep = [k for k in _saved if k.split("::")[0] != _victim]
        try:
            REG.MUST_BE_REACHABLE[:] = keep
            one = REG.lock_contract()
        finally:
            REG.MUST_BE_REACHABLE[:] = _saved
        single_ok = (one["uncovered"] == [_victim])
    check("G10 🔴 反向：清空锁定面 ⇒ 全模块缺口；删单模块锁定 ⇒ 缺口恰为该模块",
          bad["n_uncovered"] == bad["n_modules"] > 0 and single_ok,
          "全清空缺口=%d/%d · 单模块(%s) %s" % (
              bad["n_uncovered"], bad["n_modules"], _victim,
              "恰命中" if single_ok else "未命中"))

    # ---------------- Z 组：零增量 + 统计 ----------------
    print("\n[Z] 零增量与统计区间")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from lda_harness.benchmarks import BENCHMARK_DEFS as D
        n = len(D)
        check("Z1 零增量：账本锚数 = %d（能力层，不加锚）" % n, n == 541)
    except Exception as e:                                     # noqa: BLE001
        check("Z1 零增量：账本锚数不变", False, "不可读：%s" % e)

    check("Z2 ANCHORABLE=False（本模块不新增锚）",
          R.ANCHORABLE is False and REG.ANCHORABLE is False)

    # 统计区间：零引用比例应在「不为 0（否则分析器恒空）」且「不失控」之间
    check("Z3 零引用比例 %.2f%% 落在 (0.5%%, 15%%) 合理区间（兼防恒空/失控）"
          % st["dead_pct"], 0.5 < st["dead_pct"] < 15.0)
    check("Z4 锚 golden_fn 对象入口 > 400（防「只扫字符串」把整批黄金实现判死）",
          st["golden_fn_entries"] > 400, "%d 个" % st["golden_fn_entries"])

    n_pass = _CNT["PASS"]
    print("\n门禁 smoke：%d PASS / %d FAIL（共 %d 项）"
          % (n_pass, _CNT["FAIL"], n_pass + _CNT["FAIL"]))
    return 0 if _CNT["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
