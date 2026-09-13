# -*- coding: utf-8 -*-
"""P1(b) 结构断言 smoke：守护 `agent_verify` ↔ `link_physics_harness` 字典契约。

背景（见 `LDA_lda_agent_code_review_2026-09-14.md` P1）：
- 生产者 `lda_chain/link_harness.py::link_physics_harness` 返回一个 dict。
- 消费者 `lda_agent/agent_verify.py:96,105-108` **按 dict key** 取
  `status` / `b19` / `energy_conservation` / `no_missing_models` / `routing_complete`。
- 任一侧改名 / 删 key → 运行时 `KeyError`（仅端到端才暴露）。

本 smoke 在 **单元层** 断言：生产者返回 dict 必须 ⊇ 消费者消费的 key 集
（且类型符合消费者预期）。任一侧破坏契约 → 本 smoke FAIL，无需跑全链路即可报警。

🔴 维护约束：若 `agent_verify.py` 新增/改了 `harness_res[...]` 的 key 消费，
必须同步更新本文件的 `CONSUMER_KEYS`（否则本 smoke 会漏检消费者侧漂移）。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# 使 `lda_chain` / `lda_harness` 作为顶层包可导入（二者均位于 `lda/` 下）。
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_chain.link_harness import link_physics_harness  # noqa: E402

# 消费者 `agent_verify.py` 实际读取的 key 集（来源行号见文件头 docstring）。
# 顺序无关，集合语义。
CONSUMER_KEYS = ("status", "b19", "energy_conservation",
                 "no_missing_models", "routing_complete")

# 消费者对各 key 的预期类型（来自 agent_verify.py 使用方式）。
EXPECTED_TYPES = {
    "status": str,
    "b19": dict,
    "energy_conservation": dict,
    "no_missing_models": bool,
    "routing_complete": bool,
}


def _build_minimal_sim():
    """最小可跑 sim：仅含 `link_physics_harness` 实际读取的字段。

    `link` 参数当前在 harness 内部未被使用（见 link_harness.py:98-149），
    传 None 即可；若未来 harness 开始消费 link，本 smoke 将如实 FAIL（契约变更信号）。
    """
    return {
        # transfer key 须含 "->"（link_harness._per_source_power_balance 按 "->" 拆分）
        "transfers": {"in0->out0": [0.5, 0.48, 0.51],
                      "in0->out1": [0.49, 0.5, 0.47]},
        "wavelengths_um": [1.54, 1.55, 1.56],
        "missing_models": [],
    }


def main():
    checks = []
    res = link_physics_harness(None, _build_minimal_sim(), [])

    # ① 生产者必须提供消费者消费的全部 key
    produced = set(res.keys())
    missing = [k for k in CONSUMER_KEYS if k not in produced]
    checks.append({
        "name": "producer_supplies_consumer_keys",
        "passed": not missing,
        "detail": ("缺失 key: " + ", ".join(missing)) if missing
                  else f"生产者提供 {sorted(produced)} ⊇ 消费者 {list(CONSUMER_KEYS)}",
    })

    # ② 各 key 类型须符合消费者预期
    for k in CONSUMER_KEYS:
        if k not in produced:
            continue
        ok = isinstance(res[k], EXPECTED_TYPES[k])
        checks.append({
            "name": f"type[{k}]=={EXPECTED_TYPES[k].__name__}",
            "passed": ok,
            "detail": f"{k}={res[k]!r}" if not ok else f"{k} 类型 OK",
        })

    # ③ status 取值域约束（消费者 `status == "ok"/"fail"` 分支）
    status_ok = res.get("status") in ("ok", "fail")
    checks.append({
        "name": "status_in_ok_fail",
        "passed": status_ok,
        "detail": f"status={res.get('status')!r}",
    })

    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    verdict = {
        "name": "agent_verify<->link_physics_harness contract",
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "checks": checks,
    }
    return verdict


if __name__ == "__main__":
    v = main()
    for c in v["checks"]:
        mark = "✅" if c["passed"] else "❌"
        print(f"  {mark} {c['name']}: {c['detail']}")
    print(f"[contract] {v['passed']}/{v['total']} PASS -> "
          f"{'OK' if v['ok'] else 'FAIL'}")
    sys.exit(0 if v["ok"] else 1)
