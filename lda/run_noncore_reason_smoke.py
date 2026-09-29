"""豁免表理由防腐化 smoke（v0.9.46 · N-2 驱动；v0.9.144 · D-147 扩到真值维度）。

防什么
------
NON_CORE_SMOKES（非 core 豁免登记表）的**理由**是派生数据：写着「实测 Xs」，
但代码不跑、CI 不查，数字就会烂在注释里。N-2 复测（2026-09-06，18/18 逐条
重跑）抓到两条失真：`run_sparams_3d_smoke.py` 与 `run_sparams_loop_smoke.py`
旧注均称「实测 >60s 超时」，实测分别 **47.2s / 64.3s 完成（rc=0）**——「超时」
描述的是某次审计工具的 60s 截断，不是脚本的真相。豁免理由失真 = 下一轮审计
还要再踩一遍。

血案脉络
--------
v0.9.41：wdm_coupler 文件头旧注称「重 FDTD」→ 实测 0.30s（已捞回 core）。
v0.9.46：sparams_3d / sparams_loop 旧注称「>60s 超时」→ 实测均能完成。
共同点：**豁免理由没有判据守护 ⇒ 写什么全凭良心**。

🔴 v0.9.144（D-147）补的第二层缺口
----------------------------------
上节判据①②守护的是理由的**格式**（须含『实测 Ns』∈[5,330]、不得写「超时」），
但**没有**任何东西保证：
  ① 那些数字**现在**还准（理由是快照，代码在动）；
  ② 这些 smoke **现在**还能跑通（豁免表 ≠ 执行：2026-09-06 复测后直到
     2026-09-29 的 23 天里，18 项**没有一次自动执行**）。
这正是 v0.9.41 血案（`run_production_smoke.py` 从未进任何回归集）的弱化版：
**「进了豁免表」被默认等同于「没事了」**。补法 = **受跟踪的复测台账**
（`lda/noncore_replay_ledger.json`，由 `scripts/noncore_replay.py` 写）
+ 本节判据⑪~⑯。台账 `last_green` 只在复测为绿时前移 ⇒ 红了就停在旧日期，
时效判据自然变红 —— 把「永不执行」变成「有期限、有真值的豁免」。

判据（死标量，LLM 不进判决路径）
--------------------------------
  ① 每条理由必须含机器可查的实测耗时 `实测 <数字>s`（禁止只写「超时」了事）
  ② 声称耗时必须 ∈ [5, 330]s：<5s 违反准入准则（须进 core），>330s 超出复测上限
  ③ 理由不得含「超时」字样（豁免口径只能是「慢但能完成」，不能是「没跑完」）
  ④ CORE_SMOKES 与 NON_CORE_SMOKES 不得双登记（口径冲突）
  ⑤ NON_CORE 条目必须真实存在于磁盘（防 ghost 豁免）
  ⑥ 反向：注入无实测数字的理由 ⇒ 判据①必须报
  ⑦ 反向：注入「实测 3s」的低于阈值理由 ⇒ 判据②必须报
  ⑧ 反向：双登记一条 ⇒ 判据④必须报
  ⑪ 复测台账覆盖 == 豁免表（无缺 = 每项都复测过 · 无 ghost）
  ⑫ 台账每项：`last_green` 合法 · `elapsed_s` 正 · `samples_s` 非空
  ⑬ **时效**：`last_green` ≤ 90 天（超期 ⇒ 绿不可信 ⇒ 复测）
  ⑭ **真值一致**：台账实测 elapsed vs 理由『实测 Ns』偏差 ≤ 20%（理由失真即红）
  ⑮ 反向：`last_green` 推到 2020 ⇒ 判据⑬必须报
  ⑯ 反向：台账 elapsed 偏离理由 10× ⇒ 判据⑭必须报
  ⑰ **预算守口**：非 core 项不在 `_BUILTIN_TIMEOUT_OVERRIDE` ⇒ B5~B10 管不到 ⇒ 本表断言
     「**生效预算 / 实测上界 ≥ 3×**」（对齐 core 目标档；生效预算 =
     `run_ci_regression.NON_CORE_TIMEOUT_OVERRIDE.get(s, 全局默认 300s)`）
  ⑱ 反向：实测上界抬到 999s ⇒ 判据⑰必须报
  ⑲ 反向：拿掉 `run_wdm_splitter_smoke.py` 的专属预算（回落 300s ⇒ 1.83×）⇒ 判据⑰必须报
     ⇒ **证明 `NON_CORE_TIMEOUT_OVERRIDE` 不是装饰**
  ⑨ 反向测试后状态复原（不污染真判据）· ⑩ 判据执行自身无异常

复测入口（写台账）：`python scripts/noncore_replay.py`（串行 + 项间冷却防掉电）
台账体检（秒级）    ：`python scripts/noncore_replay.py --check`

运行：python lda/run_noncore_reason_smoke.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from typing import Any, Dict, List

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

import run_ci_regression as R  # noqa: E402

_SELF = "run_noncore_reason_smoke.py"
_SEC_RE = re.compile(r"实测\s*(\d+(?:\.\d+)?)s")

# 🔴 D-147（2026-09-29）：豁免的**真值**维度（此前只有理由的**格式**维度）。
LEDGER_PATH = os.path.join(_LDA, "noncore_replay_ledger.json")
MAX_AGE_DAYS = 90.0      # last_green 超过此天数未刷新 ⇒ 红（逼复测）
TRUTH_TOL = 0.20         # 台账 elapsed 与理由「实测 Ns」相对偏差上限
# 非 core 项不在 `_BUILTIN_TIMEOUT_OVERRIDE` ⇒ B5~B10 管不到 ⇒ 由本 smoke 的 ⑰ 管。
# 生效预算 = `run_ci_regression.NON_CORE_TIMEOUT_OVERRIDE.get(s, 全局默认 300s)`。
NON_CORE_DEFAULT_BUDGET_S = 300.0   # = run_ci_regression() 的默认 timeout（全局兜底）
NON_CORE_TARGET_X = 3.0             # 对齐 run_timeout_budget_ratchet 的 TARGET_X（3×）


def _reason_gaps(table) -> List[str]:
    """①③ 返回理由缺实测数字或含「超时」的条目。"""
    out = []
    for f, why in table.items():
        if not _SEC_RE.search(why or ""):
            out.append(f"{f}: 缺『实测 Ns』数字")
        elif "超时" in (why or ""):
            out.append(f"{f}: 理由含『超时』（豁免口径只能是慢但能完成）")
    return out


def _range_violations(table, lo: float = 5.0, hi: float = 330.0) -> List[str]:
    """② 声称耗时越界（<5s 无权豁免；>330s 超出复测上限）。"""
    out = []
    for f, why in table.items():
        m = _SEC_RE.search(why or "")
        if m and not (lo <= float(m.group(1)) <= hi):
            out.append(f"{f}: 实测 {m.group(1)}s 越界 [{lo:.0f},{hi:.0f}]")
    return out


def _dup_registrations() -> List[str]:
    """④ core 与豁免表双登记。"""
    return sorted(set(R.CORE_SMOKES) & set(R.NON_CORE_SMOKES))


def _ghost_entries() -> List[str]:
    """⑤ 豁免表内不存在于磁盘的条目。"""
    return sorted(f for f in R.NON_CORE_SMOKES
                  if not os.path.exists(os.path.join(_LDA, f)))


# ───────────────────────── 台账（真值维度 · D-147）纯函数 ─────────────────────────
def _ledger_load(path: str = LEDGER_PATH) -> Dict[str, Any]:
    """台账不可读 ⇒ 返回空 dict（下游判据会红，不静默放行）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _ledger_cover(want: List[str], rows: Dict[str, Any]) -> List[str]:
    """⑪ 台账与豁免表**键集必须一致**（缺 = 从没复测过；多 = ghost 台账行）。"""
    return ([f"缺台账行：{f}" for f in sorted(set(want) - set(rows))]
            + [f"ghost 台账行：{f}" for f in sorted(set(rows) - set(want))])


def _ledger_shape(rows: Dict[str, Any]) -> List[str]:
    """⑫ 每条：last_green 合法 YYYY-MM-DD · elapsed_s 正数 · samples 非空。"""
    out = []
    for f, e in sorted(rows.items()):
        e = e or {}
        lg = str(e.get("last_green") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lg):
            out.append(f"{f}: last_green 非法（{lg!r}）")
            continue
        try:
            if float(e.get("elapsed_s")) <= 0:
                out.append(f"{f}: elapsed_s 非正")
        except (TypeError, ValueError):
            out.append(f"{f}: elapsed_s 缺失或非数")
            continue
        if not (e.get("samples_s") or []):
            out.append(f"{f}: samples_s 为空（无实测样本）")
    return out


def _age_days(stamp: str, today: date) -> float:
    y, m, d = (int(x) for x in stamp.split("-"))
    return (today - date(y, m, d)).days


def _ledger_stale(rows: Dict[str, Any], today: date,
                  max_age: float = MAX_AGE_DAYS) -> List[str]:
    """⑬ 时效：last_green 超过 max_age 天 ⇒ 该豁免项的「绿」已不可信。"""
    out = []
    for f, e in sorted(rows.items()):
        lg = str((e or {}).get("last_green") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lg):
            continue                      # 格式问题由 ⑫ 报，此处不重复
        age = _age_days(lg, today)
        if age > max_age:
            out.append(f"{f}: last_green {lg}（{age} 天 > {max_age:.0f} 天）")
    return out


def _ledger_untruthful(rows: Dict[str, Any], table: Dict[str, str],
                       tol: float = TRUTH_TOL) -> List[str]:
    """⑭ 真值一致：台账实测 elapsed 与理由里写的「实测 Ns」偏差 > tol ⇒ 理由已失真。"""
    out = []
    for f, why in sorted(table.items()):
        m = _SEC_RE.search(why or "")
        e = rows.get(f) or {}
        try:
            claimed = float(m.group(1)) if m else None
            actual = float(e.get("elapsed_s"))
        except (TypeError, ValueError):
            continue                      # 缺数字由 ① / ⑫ 报
        if claimed is None:
            continue
        rel = abs(actual - claimed) / claimed
        if rel > tol:
            out.append(f"{f}: 理由 {claimed:.1f}s vs 台账 {actual:.1f}s（偏差 {rel * 100:.0f}%）")
    return out


def _over_default_budget(rows: Dict[str, Any],
                         noncore_override: Dict[str, float] | None = None,
                         target: float = NON_CORE_TARGET_X) -> List[str]:
    """⑰ 非 core 项的**生效预算 / 实测上界** 必须 ≥ `target`（对齐 core 的目标档 3×）。

    生效预算 = `NON_CORE_TIMEOUT_OVERRIDE.get(s, 300.0)`（非 core 项不在
    `_BUILTIN_TIMEOUT_OVERRIDE` 里 ⇒ B5~B10 管不到，故单立本条）。
    🔴 实测动机（D-147）：`run_wdm_splitter_smoke` 实测上界 **163.86s**、走全局 300s
    ⇒ **1.83× < 2× 硬闸**（换台慢机器跑 `--tag all` 就假红），故给它 600s。
    """
    nco = dict(noncore_override or {})
    out = []
    for f, e in sorted(rows.items()):
        try:
            mx = float((e or {}).get("elapsed_max_s"))
        except (TypeError, ValueError):
            continue
        if mx <= 0:
            continue
        b = float(nco.get(f, NON_CORE_DEFAULT_BUDGET_S))
        if b / mx < target:
            out.append(f"{f}: 生效预算 {b:.0f}s / 实测上界 {mx:.1f}s = "
                       f"{b / mx:.2f}× < {target:.1f}×")
    return out


def main() -> int:

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rc = 0
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append(ok)
        line = f"{'PASS' if ok else 'FAIL'} | {name}"
        if detail:
            line += f" | {detail}"
        print(line)
        return ok

    try:
        # ---- 正向判据 ----
        g = _reason_gaps(R.NON_CORE_SMOKES)
        rc |= not check(f"① 全部 {len(R.NON_CORE_SMOKES)} 条理由含『实测 Ns』且不含「超时」",
                        not g, "; ".join(g[:3]))
        v = _range_violations(R.NON_CORE_SMOKES)
        rc |= not check("② 声称耗时全部 ∈ [5,330]s", not v, "; ".join(v[:3]))
        d = _dup_registrations()
        rc |= not check("④ 无 core/豁免双登记", not d, str(d))
        gh = _ghost_entries()
        rc |= not check("⑤ 无 ghost 豁免条目", not gh, str(gh))

        # ---- 真值维度（D-147）：台账覆盖 / 形状 / 时效 / 与理由一致 ----
        led = _ledger_load()
        lrows = dict(led.get("rows") or {})
        want = sorted(R.NON_CORE_SMOKES)
        cov = _ledger_cover(want, lrows)
        rc |= not check(f"⑪ 复测台账覆盖 == 豁免表 {len(want)} 项（无缺 · 无 ghost）",
                        not cov,
                        "; ".join(cov[:3]) or f"台账 {len(lrows)} 条 · 更新 {led.get('updated')}")
        shp = _ledger_shape(lrows)
        rc |= not check("⑫ 台账每项：last_green 合法 · elapsed_s 正 · samples 非空",
                        not shp, "; ".join(shp[:3]))
        stl = _ledger_stale(lrows, date.today())
        rc |= not check(f"⑬ 时效：last_green ≤ {MAX_AGE_DAYS:.0f} 天（超期 ⇒ 复测）",
                        not stl, "; ".join(stl[:3]))
        unf = _ledger_untruthful(lrows, R.NON_CORE_SMOKES)
        rc |= not check(f"⑭ 真值一致：台账实测 vs 理由『实测 Ns』偏差 ≤ {TRUTH_TOL * 100:.0f}%",
                        not unf, "; ".join(unf[:3]))
        nco = dict(getattr(R, "NON_CORE_TIMEOUT_OVERRIDE", {}) or {})
        ovr = _over_default_budget(lrows, nco)
        rc |= not check(f"⑰ 非 core 项：生效预算/实测上界 ≥ {NON_CORE_TARGET_X:.1f}×"
                        f"（对齐 core 目标档 · 超 ⇒ 配预算）",
                        not ovr, "; ".join(ovr[:3]))
        ghost_b = sorted(set(nco) - set(R.NON_CORE_SMOKES))
        rc |= not check("⑳ 预算表无 ghost 条目（每项都落在豁免表内）",
                        not ghost_b, str(ghost_b[:3]))

        # ---- 反向测试（护栏必须会响）----
        saved = dict(R.NON_CORE_SMOKES)
        saved_core = list(R.CORE_SMOKES)
        try:
            t1 = dict(saved)
            t1["_fake_no_number.py"] = "重仿真：跑得慢"
            g1 = _reason_gaps(t1)
            rc |= not check("⑥ 反向：无实测数字的理由 ⇒ 判据①必须报",
                            any("_fake_no_number" in x for x in g1), str(g1[:2]))

            t2 = dict(saved)
            t2["_fake_fast.py"] = "跑得快，实测 3s"
            v2 = _range_violations(t2)
            rc |= not check("⑦ 反向：声称 3s（<5s 准入线）⇒ 判据②必须报",
                            any("_fake_fast" in x for x in v2), str(v2[:2]))

            R.CORE_SMOKES = list(saved_core) + ["run_ir_smoke.py"]  # core 里已有它 ⇒ 制造双登记
            d2 = _dup_registrations()
            rc |= not check("⑧ 反向：双登记 ⇒ 判据④必须报",
                            "run_ir_smoke.py" in d2, str(d2))

            # ⑮ 反向：把某条 last_green 推到 200 天前 ⇒ 判据⑬ 必报（护栏会响）
            victim = want[0] if want else "run_ir_smoke.py"
            t3 = {k: dict(v or {}) for k, v in lrows.items()}
            t3.setdefault(victim, {})["last_green"] = "2020-01-01"
            s3 = _ledger_stale(t3, date.today())
            rc |= not check("⑮ 反向：last_green 推到 2020 ⇒ 判据⑬必须报",
                            any(victim in x for x in s3), str(s3[:2]))

            # ⑯ 反向：把某条 elapsed 改成与理由矛盾（10×）⇒ 判据⑭ 必报
            t4 = {k: dict(v or {}) for k, v in lrows.items()}
            m4 = _SEC_RE.search(R.NON_CORE_SMOKES.get(victim, ""))
            if m4:
                t4.setdefault(victim, {})["elapsed_s"] = float(m4.group(1)) * 10.0
                u4 = _ledger_untruthful(t4, dict(R.NON_CORE_SMOKES))
                rc |= not check("⑯ 反向：台账 elapsed 偏离理由 10× ⇒ 判据⑭必须报",
                                any(victim in x for x in u4), str(u4[:2]))
            else:
                rc |= not check("⑯ 反向：基准项理由含实测数字", False, victim)

            # ⑱ 反向：把某条 elapsed_max_s 抬到超预算 ⇒ 判据⑰ 必报
            t5 = {k: dict(v or {}) for k, v in lrows.items()}
            t5.setdefault(victim, {})["elapsed_max_s"] = 999.0
            o5 = _over_default_budget(t5, nco)
            rc |= not check("⑱ 反向：实测上界抬到 999s ⇒ 判据⑰必须报",
                            any(victim in x for x in o5), str(o5[:2]))

            # ⑲ 反向：拿掉 wdm_splitter 的专属预算（回落到全局 300s）⇒ 判据⑰ 必报
            #     —— 这条同时**证明 NON_CORE_TIMEOUT_OVERRIDE 不是装饰**（拿掉即红）。
            heavy = "run_wdm_splitter_smoke.py"
            if heavy in lrows and heavy in nco:
                o6 = _over_default_budget(lrows, {k: v for k, v in nco.items()
                                                  if k != heavy})
                rc |= not check("⑲ 反向：拿掉 wdm 专属预算 ⇒ 判据⑰必须报（证明该表必需）",
                                any(heavy in x for x in o6), str(o6[:1]))
            else:
                rc |= not check("⑲ 反向：基准项（wdm/预算）存在", False,
                                f"{heavy} in ledger={heavy in lrows} · in nco={heavy in nco}")
        finally:
            R.NON_CORE_SMOKES.clear()
            R.NON_CORE_SMOKES.update(saved)
            R.CORE_SMOKES = saved_core

        # 收尾：复原后必须重新全绿（测试不污染真实判据）
        g3 = _reason_gaps(R.NON_CORE_SMOKES)
        rc |= not check("⑨ 反向测试后状态复原", not g3 and not _dup_registrations(), "")
    except Exception as exc:  # noqa: BLE001 —— 判据自身跑挂 ⇒ 必须红，不能裸退假绿
        rc |= not check("⑩ 判据执行自身无异常", False, repr(exc))

    n_pass = sum(1 for c in checks if c)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(checks) - n_pass} FAIL / 共 {len(checks)} 项")
    if rc == 0:
        print("ALL PASS — 豁免理由含真实实测耗时、台账真值一致且在时效内，护栏会响")
    else:
        print("FAIL — 豁免理由/台账腐化，请跑 "
              "`python scripts/noncore_replay.py` 复测后刷新台账与理由")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
