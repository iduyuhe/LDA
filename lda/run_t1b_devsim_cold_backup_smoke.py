"""T1-B-W1 · DEVSIM 主权镜像冷备 CI 门禁（离线构建证据）。

判据（core 160→161）：
  ① 镜像存在：vendor/devsim_mirror/ 存在 → 否则 FAIL（冷备缺失）
  ② 提交锁定：git rev-parse HEAD == PINNED_COMMIT → 否则 FAIL
  ③ 许可证：镜像内含 LICENSE（Apache-2.0）→ 否则 FAIL
  ④ 可选 import 标量隔离：若 devsim 可用，运行最小 p-n 跨校验，
     断言返回为标量 dict（非对象）；不可用时 SKIP（不破坏 CI）

闭合 T1-B-W3 收尾「离线构建证据 CI 门禁」缺口：源码提交锁定 + 许可证 + 隔离纪律
三位一体证据链。rc=0 PASS / ≠0 FAIL。

🔴 EAR 744.23：本门禁只验证冷备完整性，不授权先进节点用途；用途声明见
docs/lda_t1b_ear74423_compliance.md。
"""
from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = os.path.join(REPO_ROOT, "vendor", "devsim_mirror")
PINNED_COMMIT = "43b41ca845184c47e22b72d144db7e7db8509377"

sys.path.insert(0, REPO_ROOT)
from lda_solver.devsim_bridge import devsim_available, devsim_pn_junction_scalar_crosscheck  # noqa: E402


def _check_mirror_present() -> bool:
    return os.path.isdir(MIRROR)


def _check_pinned_commit() -> str | None:
    if not _check_mirror_present():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", MIRROR, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _check_license() -> bool:
    lic = os.path.join(MIRROR, "LICENSE")
    if not os.path.isfile(lic):
        return False
    try:
        with open(lic, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4096).lower()
        return "apache" in head
    except Exception:
        return False


def main() -> int:
    fails = []

    if not _check_mirror_present():
        fails.append("镜像缺失 vendor/devsim_mirror（DEVSIM 冷备未建立）")
    else:
        commit = _check_pinned_commit()
        if commit != PINNED_COMMIT:
            fails.append(f"提交未锁定：得 {commit!r} 期望 {PINNED_COMMIT!r}")
        if not _check_license():
            fails.append("镜像 LICENSE 缺失或非 Apache-2.0")

    # ④ 可选 import 标量隔离（不破坏 CI）
    iso_note = "SKIP（devsim 未安装，走自研 C 级候选）"
    if devsim_available():
        x = devsim_pn_junction_scalar_crosscheck(1e17, 1e17, 10.0, 5.0)
        if x is None:
            iso_note = "devsim 可用但跨校验返回 None（隔离回退 OK）"
        elif isinstance(x, dict) and isinstance(x.get("N_at_probe"), float):
            iso_note = f"隔离 OK（标量回传 {x['N_at_probe']:.3e}）"
        else:
            fails.append("devsim 跨校验未回标量 dict（隔离契约违反）")

    if fails:
        for f in fails:
            print(f"FAIL · T1-B-W1 DEVSIM 冷备门禁：{f}")
        return 1

    print("PASS · T1-B-W1 DEVSIM 主权镜像冷备门禁：镜像存在 + 提交锁定 "
          f"{PINNED_COMMIT[:10]} + LICENSE(Apache-2.0) + 隔离纪律 OK | {iso_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
