# -*- coding: utf-8 -*-
"""超时预算棘轮护栏（v0.9.118 · 波次 6 T6.1 · 源自 v0.9.112 / v0.9.116 两次同族复发）。

防什么（血案复盘 · 实证非推测）
------------------------------
「超时预算未随规模同步上调」这一类缺陷在本仓库**已复发两次**：

  ① v0.9.111 修了 `run_benchmark_falsifiability_smoke`（600s）/ `run_redteam_anchor_fuzz_smoke`
     （默认 300s）两项**假红 TIMEOUT**，**但只修了当时踩到的那两项，未做全表审计**；
  ② v0.9.112 全量回归再次假红（`run_d_criterion_smoke` 余量仅 1.03×）⇒ 全表审计 14 项
     才发现 **5 项余量不足**（含 ① 刚配的 1800/2000，余量只有 1.61× / 1.46×）；
  ③ v0.9.116 **同一项**（`run_fdtd2d_mmi_smoke`）**第三次**踩线（2.99→3.12→3.03→2.97→2.87×）。

根因恒定：**耗时随锚数/规模增长，预算未同步上调** ⇒ 余量被吃光 ⇒ 周期性
`TIMEOUT`（rc=0 功能全绿，只是超预算）被计入 FAIL ⇒ **假红**。危险的是它会把
后人引向"去改物理判据"这条失真通道 —— 本项目最忌讳的一条。

在此之前，"何时该重标定"**只存在于 `scripts/ci_core_batched.py` 跑完打印的体检报告里**
（`budget_audit`）——那只是**本地辅助脚本的输出，不是门禁**：没人看就等于不存在。
本 smoke 把它**升格为 CI 会红的机器纪律**。

做法（死标量 · LLM 不进判决路径）
----------------------------------
提交一份 `@10 线程` 实测基线表 `lda/timeout_budget_baseline.json`
（逐项 = **跨轮实测上界**，剔 TIMEOUT/CRASH 截断值），断言：

  B5 覆盖完备 —— `_BUILTIN_TIMEOUT_OVERRIDE` 每项都有基线行（新增覆盖项未登记 ⇒ 红）
  B6 无死行   —— 基线每行都属于覆盖表（残留行 ⇒ 红）
  B7 基线自洽 —— `samples_s` 非空 且 `max(samples) == elapsed_max_s`
  B8 **硬闸** —— 逐项 `budget / 跨轮实测上界 ≥ 2.0`（欠标定 ⇒ 红）
  B9 **目标棘轮** —— 低于 `3×` 的项数 `≤ ratchet`（**只降不升**，当前 0）
  B10 **预算一致性** —— 基线记的 `budget_s` 必须 == 覆盖表现值
       （🔴 这条是**刷新闭环的锁**：改了预算却不刷新基线 ⇒ 立刻红 ⇒ 被迫重跑重测，
        而不是让基线悄悄与代码脱钩。**它是精确判据，不产生假红**。）
  B11~B16 六条反向测试（证明上面的检测器**真会变红**，非假绿）
  B17 自食其规则（本 smoke 自分属 CORE_SMOKES）

刻意**不做**的（避免「狼来了」被关停 · 与 v0.9.112 的护栏教训一致）
--------------------------------------------------------------
锚数 / CI core 成员数漂移**只打印提示、不判红** —— 它们与"预算是否欠标定"没有
一一因果（14 项里只有 3 项耗时随锚数增长，其余参数固定），判红会制造**假红**，
而本仓库对假红的容忍度为零（假红会诱导后人去改物理判据）。真正的闸是 B8/B9
的**数字**：基线一旦刷新，数字说话。

刷新方式（闭环）
----------------
`python scripts/ci_core_batched.py --write-baseline`（跑完全量后把实测落成基线；
亦可 `--from-report <report.json>` 从既有报告刷新）。若预算上调，**只改
`_BUILTIN_TIMEOUT_OVERRIDE` 的耗时上限**——属**单调放宽**（放宽上限不可能使已
PASS 项变 FAIL），不含任何判据放宽。

🔴 本护栏**不放宽任何判据**：它管的是"耗时余量"，`TIMEOUT` 与 `FAIL` 是两种状态。
运行：python run_timeout_budget_ratchet_smoke.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

_SELF = "run_timeout_budget_ratchet_smoke.py"
_BASELINE = os.path.join(_HERE, "timeout_budget_baseline.json")
_SCHEMA = "lda.timeout_budget_baseline/1"
_CALIB_THREADS = 10          # 内置超时预算的标定线程数（见 run_ci_regression 文件头）
HARD_FLOOR_X = 2.0           # 硬闸：低于此即"欠标定"
TARGET_X = 3.0               # 目标档

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   detail_fmt=" —— {d}", detail_on="both", return_ok=True)


# ---------------------------------------------------------------- 纯函数（可反向测试）
def evaluate(override, rows, *, hard_floor=HARD_FLOOR_X, target=TARGET_X):
    """给定超时覆盖表 + 基线行 ⇒ 五类发现。纯函数：无 I/O、无全局态。

    返回 dict：
      missing         覆盖表有、基线无（新增覆盖项未登记基线）
      dead            基线有、覆盖表无（残留行）
      below_hard      余量 < hard_floor（欠标定 ⇒ 硬闸红灯）
      below_target    hard_floor ≤ 余量 < target（达标但未到目标档 ⇒ 棘轮计数）
      budget_mismatch 基线记的预算 ≠ 覆盖表现值（基线未随预算刷新）
      inconsistent    基线行自身不自洽（字段缺失 / 非正 / samples 与上界不符）
    """
    ov = {k: float(v) for k, v in dict(override or {}).items()}
    by = {}
    inconsistent = []
    budget_mismatch = []
    for r in (rows or []):
        s = (r or {}).get("script")
        if not s:
            inconsistent.append(("<无 script>", "行缺 script 键"))
            continue
        if s in by:
            inconsistent.append((s, "基线存在重复行"))
        else:
            by[s] = r

    missing = sorted(set(ov) - set(by))
    dead = sorted(set(by) - set(ov))
    below_hard, below_target = [], []

    for s in sorted(set(ov) & set(by)):
        r = by[s]
        try:
            budget = float(ov[s])
            mx = float(r["elapsed_max_s"])
        except (KeyError, TypeError, ValueError) as e:
            inconsistent.append((s, "budget/elapsed_max_s 缺失或非数：%s" % e))
            continue
        try:
            b_rec = float(r["budget_s"])
        except (KeyError, TypeError, ValueError) as e:
            inconsistent.append((s, "budget_s 缺失或非数：%s" % e))
            continue
        if b_rec != budget:
            budget_mismatch.append((s, b_rec, budget))
        if mx <= 0:
            inconsistent.append((s, "elapsed_max_s 非正（%r）" % mx))
            continue
        ss = r.get("samples_s") or []
        if not ss:
            inconsistent.append((s, "samples_s 为空（无实测样本，余量无从校验）"))
            continue
        try:
            hi = max(float(x) for x in ss)
        except (TypeError, ValueError) as e:
            inconsistent.append((s, "samples_s 含非数：%s" % e))
            continue
        if abs(hi - mx) > 1e-6:
            inconsistent.append((s, "samples 上界 %.2f != elapsed_max_s %.2f"
                                 % (hi, mx)))
            continue
        margin = budget / mx
        if margin < hard_floor:
            below_hard.append((s, round(margin, 3), budget, mx))
        elif margin < target:
            below_target.append((s, round(margin, 3), budget, mx))

    return {"missing": missing, "dead": dead, "below_hard": below_hard,
            "below_target": below_target, "budget_mismatch": budget_mismatch,
            "inconsistent": inconsistent}


def _load_baseline(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------ main
def main() -> int:
    rc = 0
    print("=" * 78)
    print("超时预算棘轮护栏（T6.1 · 把「何时该重标定」变成 CI 会红的机器纪律）")
    print("=" * 78)

    try:
        import run_ci_regression as R
        override = dict(R._BUILTIN_TIMEOUT_OVERRIDE)
        core_smokes = list(R.CORE_SMOKES)
    except Exception as e:                                        # noqa: BLE001
        print("FAIL —— 无法导入 run_ci_regression（门禁依赖缺失=红，不静默跳过）：%s" % e)
        return 1

    # ---- B1 基线文件可解析 ----
    base, load_err = None, ""
    try:
        base = _load_baseline(_BASELINE)
    except Exception as e:                                        # noqa: BLE001
        load_err = "%s" % e
    rc |= not check("B1 基线表存在且可解析（%s）" % os.path.basename(_BASELINE),
                    base is not None, load_err or "解析成功")
    if base is None:
        print("FAIL —— 基线表不可用，后续判据无法执行")
        print("汇总：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, PASS + FAIL))
        return 1

    sch = base.get("schema")
    rc |= not check("B2 基线 schema 正确（%s）" % _SCHEMA, sch == _SCHEMA,
                    "实际 %r" % sch)

    rows = base.get("rows") or []
    rc |= not check("B3 基线行非空（防空集上「空洞为真」）", len(rows) > 0,
                    "rows=%d" % len(rows))

    thr = base.get("threads")
    rc |= not check("B4 标定线程口径一致（@%d 线程）" % _CALIB_THREADS,
                    thr == _CALIB_THREADS,
                    "基线记 %r —— 非同口径的实测不可比（线程数改小 ⇒ 变慢）" % thr)

    res = evaluate(override, rows)
    n_below_target = len(res["below_target"])

    # ---- B5 覆盖完备 ----
    rc |= not check("B5 覆盖完备：超时覆盖表每项都有基线行（新增项未登记 ⇒ 红）",
                    not res["missing"],
                    "缺基线行 %s" % res["missing"])

    # ---- B6 无死行 ----
    rc |= not check("B6 无死行：基线每行都属于当前超时覆盖表",
                    not res["dead"],
                    "残留行 %s（覆盖表已删项 ⇒ 基线须同步刷新）" % res["dead"])

    # ---- B7 基线自洽 ----
    rc |= not check("B7 基线自洽：样本非空 且 max(samples) == elapsed_max_s",
                    not res["inconsistent"],
                    "不自洽 %s" % res["inconsistent"][:5])

    # ---- B8 硬闸（余量 ≥ 2×） ----
    rc |= not check("B8 硬闸：逐项 budget / 跨轮实测上界 ≥ %.1f×（欠标定 ⇒ 红）"
                    % HARD_FLOOR_X,
                    not res["below_hard"],
                    "欠标定 %s" % [("%s %.3f× (budget=%.0f 实测=%.1f)"
                                    % (s, m, b, x))
                                   for s, m, b, x in res["below_hard"]])

    # ---- B9 目标棘轮（低于 3× 的项数只降不升） ----
    ratchet = int(base.get("ratchet_below_target", 0))
    rc |= not check("B9 目标棘轮：低于 %.1f× 的项数 %d ≤ 棘轮 %d（只降不升）"
                    % (TARGET_X, n_below_target, ratchet),
                    n_below_target <= ratchet,
                    "贴线项 %s ⇒ 须重测并上调预算（只改耗时上限 · 属单调放宽）"
                    % [("%s %.3f×" % (s, m)) for s, m, b, x in res["below_target"]])

    # ---- B10 预算一致性（刷新闭环的锁） ----
    rc |= not check("B10 预算一致性：基线记的 budget_s == 覆盖表现值"
                    "（改预算必刷新基线）",
                    not res["budget_mismatch"],
                    "不一致 %s ⇒ 重跑全量并 --write-baseline 刷新（不要手改数字）"
                    % [("%s 基线 %.0f → 现值 %.0f" % (s, a, b))
                       for s, a, b in res["budget_mismatch"]])

    # ---- ⚠️ 提示（刻意不判红：与"预算欠标定"无一一直因果，判红即制造假红） ----
    try:
        from lda_harness.benchmarks import BENCHMARK_ORDER
        anchors_now = len(BENCHMARK_ORDER)
    except Exception as e:                                        # noqa: BLE001
        anchors_now = -1
        print("    （无法读取 BENCHMARK_ORDER：%s）" % e)
    anchors_base = base.get("anchors_at_measurement")
    if anchors_base != anchors_now:
        print("  ⚠️ 锚数漂移：基线 %s → 当前 %s —— 耗时随锚数增长的 3 项"
              "（d_criterion / falsifiability / fuzz）实测可能已过期，建议重跑刷新基线"
              % (anchors_base, anchors_now))
    core_base = base.get("core_smokes_at_measurement")
    if core_base != len(core_smokes):
        print("  ⚠️ CI core 成员数漂移：基线 %s → 当前 %d —— 批构成已变，建议重跑刷新基线"
              % (core_base, len(core_smokes)))

    # ---- 反向测试 A：逐项压到自身实测上界的 1.5× ⇒ 硬闸必报满 ----
    mx_by = {r["script"]: float(r["elapsed_max_s"]) for r in rows
             if r.get("script") and r.get("elapsed_max_s") is not None}
    probe_ov = {s: mx_by[s] * 1.5 for s in override if s in mx_by}
    pr = evaluate(probe_ov, rows)
    rc |= not check("B11 反向 A：逐项压到 1.5× 实测上界 ⇒ 硬闸必报满（非假绿）",
                    len(probe_ov) > 0 and len(pr["below_hard"]) == len(probe_ov),
                    "报出 %d 项（应 %d 项）" % (len(pr["below_hard"]), len(probe_ov)))

    # ---- 反向测试 B：覆盖表新增一项而基线没有 ⇒ 必报 ----
    probe_ov = dict(override)
    probe_ov["run_this_script_does_not_exist_smoke.py"] = 999.0
    pr = evaluate(probe_ov, rows)
    rc |= not check("B12 反向 B：覆盖表多一项而基线无 ⇒ 覆盖检测器必报",
                    "run_this_script_does_not_exist_smoke.py" in pr["missing"],
                    "missing=%s" % pr["missing"][:3])

    # ---- 反向测试 C：基线多一行 ⇒ 死行检测器必报 ----
    probe_rows = list(rows) + [{"script": "run_ghost_smoke.py", "budget_s": 60.0,
                                "elapsed_max_s": 1.0, "samples_s": [1.0]}]
    pr = evaluate(override, probe_rows)
    rc |= not check("B13 反向 C：基线多一行 ⇒ 死行检测器必报",
                    "run_ghost_smoke.py" in pr["dead"], "dead=%s" % pr["dead"][:3])

    # ---- 反向测试 D：空集 ⇒ 必报（防空集上「空洞为真」） ----
    pr_empty_ov = evaluate({}, rows)
    pr_empty_rows = evaluate(override, [])
    rc |= not check("B14 反向 D：空覆盖表 / 空基线 ⇒ 检测器必报（防空集空洞为真）",
                    bool(pr_empty_ov["dead"]) and bool(pr_empty_rows["missing"]),
                    "空覆盖表 dead=%d · 空基线 missing=%d"
                    % (len(pr_empty_ov["dead"]), len(pr_empty_rows["missing"])))

    # ---- 反向测试 E：样本与上界不符 ⇒ 自洽检测器必报 ----
    probe_rows = [dict(r) for r in rows]
    probe_rows[0]["samples_s"] = [1.0, 2.0]
    pr = evaluate(override, probe_rows)
    rc |= not check("B15 反向 E：样本上界与 elapsed_max_s 不符 ⇒ 自洽检测器必报",
                    bool(pr["inconsistent"]), "inconsistent=%s" % pr["inconsistent"][:2])

    # ---- 反向测试 F：基线预算与现值不符 ⇒ 一致性检测器必报 ----
    probe_rows = [dict(r) for r in rows]
    probe_rows[0]["budget_s"] = float(probe_rows[0]["budget_s"]) * 2.0
    pr = evaluate(override, probe_rows)
    rc |= not check("B16 反向 F：基线预算与现值不符 ⇒ 一致性检测器必报",
                    bool(pr["budget_mismatch"]),
                    "budget_mismatch=%s" % pr["budget_mismatch"][:2])

    # ---- B17 自食其规则 ----
    in_core = _SELF in core_smokes
    rc |= not check("B17 本 smoke 自身在 CORE_SMOKES 内（自食其规则）",
                    in_core, "" if in_core else "门禁自己被漏接！")

    # ---- 汇总 ----
    print("-" * 78)
    margins = sorted(
        ((float(override[r["script"]]) / float(r["elapsed_max_s"]), r["script"])
         for r in rows if r.get("script") in override), key=lambda x: x[0])
    print("  覆盖项 %d · 基线行 %d · 硬闸下限 %.1f× · 目标档 %.1f×"
          % (len(list(override)), len(rows), HARD_FLOOR_X, TARGET_X))
    for m, s in margins[:5]:
        print("    最低档 %-44s %7.3f×" % (s, m))
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, PASS + FAIL))
    if rc == 0:
        print("ALL PASS — 超时预算与跨轮实测上界对齐（最低 %.3f×，目标 ≥%.1f×）"
              % (margins[0][0] if margins else 0.0, TARGET_X))
    else:
        print("FAIL — 超时预算欠标定，或基线陈旧/与预算脱钩：先重跑全量拿实测，"
              "再按「≥3 × 跨轮实测上界」上调 _BUILTIN_TIMEOUT_OVERRIDE 的耗时上限，"
              "然后 --write-baseline 刷新基线。**不要改物理判据。**")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
