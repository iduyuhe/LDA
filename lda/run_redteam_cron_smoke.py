# -*- coding: utf-8 -*-
"""红队 cron 告警定级护栏（CORE）：classify() 必须「反向测试会响」。

纯函数无网络，直接 import scripts/redteam_cron.classify 验证：
- 漏过>0 / hit_rate>0  → CRITICAL（回归引入漏洞，必须立即告警）
- status=error / skipped → WARN（监控盲区/探针故障）
- attack_ratio<0.3 / coverage<2 → WARN（红队退化，非管线漏洞但需察觉）
- 健康响应 → OK
不验证「会响」的告警门 = 没门禁。本 smoke 即该门禁。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import redteam_cron as rc  # noqa: E402


def _resp(status, ds=None, detail=None):
    r = {"status": status, "dead_scalars": ds or {}}
    if detail is not None:
        r["detail"] = detail
    return r


def main():
    checks = []
    errs = []

    def check(name, cond, info=""):
        checks.append((name, bool(cond)))
        if not cond:
            errs.append("%s | %s" % (name, info))

    # ① CRITICAL：确认缺陷漏过（回归信号，最致命）
    lvl, msg = rc.classify(_resp("ok", {"confirmed_defects": 1, "hit_rate": 0.25,
                                        "attack_ratio": 1.0, "coverage": 4}))
    check("漏过>0 ⇒ CRITICAL", lvl == "CRITICAL", "got %s" % lvl)

    # ② CRITICAL：hit_rate>0（即便 confirmed 字段缺失）
    lvl, msg = rc.classify(_resp("ok", {"hit_rate": 0.1, "attack_ratio": 1.0, "coverage": 4}))
    check("hit_rate>0 ⇒ CRITICAL", lvl == "CRITICAL", "got %s" % lvl)

    # ③ WARN：探针执行出错
    lvl, msg = rc.classify(_resp("error", detail="timeout"))
    check("status=error ⇒ WARN", lvl == "WARN", "got %s" % lvl)

    # ④ WARN：红队未配置（监控盲区）
    lvl, msg = rc.classify(_resp("skipped"))
    check("status=skipped ⇒ WARN", lvl == "WARN", "got %s" % lvl)

    # ⑤ WARN：攻击强度退化（非漏洞但红队变弱）
    lvl, msg = rc.classify(_resp("ok", {"hit_rate": 0.0, "attack_ratio": 0.1, "coverage": 4}))
    check("attack_ratio<0.3 ⇒ WARN", lvl == "WARN", "got %s" % lvl)

    # ⑥ WARN：覆盖角度不足
    lvl, msg = rc.classify(_resp("ok", {"hit_rate": 0.0, "attack_ratio": 1.0, "coverage": 1}))
    check("coverage<2 ⇒ WARN", lvl == "WARN", "got %s" % lvl)

    # ⑦ OK：完全健康
    lvl, msg = rc.classify(_resp("ok", {"hit_rate": 0.0, "attack_ratio": 1.0, "coverage": 4}))
    check("健康响应 ⇒ OK", lvl == "OK", "got %s" % lvl)

    print("红队 cron 告警定级护栏  (checks=%d)" % len(checks))
    for n, ok in checks:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", n))
    if errs:
        print("FAIL_SUMMARY:")
        for e in errs:
            print("  - %s" % e)
        print("\nRESULT: FAIL (%d/%d)" % (sum(1 for _, o in checks if o), len(checks)))
        sys.exit(1)
    print("\nRESULT: PASS (%d/%d)" % (len(checks), len(checks)))
    sys.exit(0)


if __name__ == "__main__":
    main()
