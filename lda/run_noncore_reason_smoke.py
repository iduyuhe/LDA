"""豁免表理由防腐化 smoke（v0.9.46 · N-2 驱动）。

防什么
------
NON_CORE_SMOKES（非 core 豁免登记表）的理由是**派生数据**：写着「实测 Xs」，
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

运行：python lda/run_noncore_reason_smoke.py
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

import run_ci_regression as R  # noqa: E402

_SELF = "run_noncore_reason_smoke.py"
_SEC_RE = re.compile(r"实测\s*(\d+(?:\.\d+)?)s")


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


def main() -> int:
    import io
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
        finally:
            R.NON_CORE_SMOKES.clear()
            R.NON_CORE_SMOKES.update(saved)
            R.CORE_SMOKES = saved_core

        # 收尾：复原后必须重新全绿（测试不污染真判据）
        g3 = _reason_gaps(R.NON_CORE_SMOKES)
        rc |= not check("⑨ 反向测试后状态复原", not g3 and not _dup_registrations(), "")
    except Exception as exc:  # noqa: BLE001 —— 判据自身跑挂 ⇒ 必须红，不能裸退假绿
        rc |= not check("⑩ 判据执行自身无异常", False, repr(exc))

    n_pass = sum(1 for c in checks if c)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(checks) - n_pass} FAIL / 共 {len(checks)} 项")
    if rc == 0:
        print("ALL PASS — 豁免表理由全部含真实实测耗时，无「超时」式搪塞，护栏会响")
    else:
        print("FAIL — 豁免表理由腐化，请用 probe_noncore*.py 复测后回填真实耗时")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
