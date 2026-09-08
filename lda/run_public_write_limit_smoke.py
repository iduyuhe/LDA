# -*- coding: utf-8 -*-
"""P3 · 公开写端点 IP 限流护栏（v0.9.6x · 权限审计 2026-09-09）。

🔴 防什么
---------
获客/生态投稿端点（opinion/submit、purchase/request、ecosystem/submit、
store/guide）**故意无鉴权**（公开促进转化/播种），但审计实测匿名连打
20~30 次全 200——无任何限流，垃圾投稿/询价可无限堆，管理员后台被淹。
→ 复用找回申请同款 IP 限流（10 次/10 分钟，store.public_write_guard）。

判据（死标量 + 行为真跑，LLM 不进判决路径）
--------------------------------------------
C1 接线（生产代码对象，非副本）：routes.PUBLIC_RATE_PATHS 恰 4 端点、全部
    ∈ POST_ROUTES 注册、且与 HEAVY_POST_PATHS（登录闸门）无交集。
C2 行为：同 scope+同 IP 连调 10 次放行、第 11 次拒绝（429 消息）。
C3 独立计数：不同 scope 或不同 IP 互不影响（各自窗口）。
C4 语义：client_ip 为空（单测直调/无对端）跳过限流恒放行。
C5 窗口过期：小窗口打满后 sleep 过期 ⇒ 恢复放行（滑动窗口自清理）。
C6 反向（防假绿）：limit=1 ⇒ 第 2 次必拒（证明窗口判据真会响）。
C7 端到端接线：经 routes._public_write_guard 真转发——前 10 次 200、第 11
    次 429、换 IP 恢复 200（_dispatch → _public_write_guard 分支的同一函数）。

🔴 store 隔离：本 smoke 在 import lda_webui.* 之前先把 store.STORE_PATH
   指向临时目录，全程不碰 dev store（防 2026-09-08 dist/store.json 清空
   事故重演——任何写库路径都必须先隔离）。

运行：python run_public_write_limit_smoke.py   （<5s，无重依赖）
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 🔴 先隔离 store，再 import 任何 lda_webui 模块（防 import 副作用写 dev 库）
_tmp = tempfile.mkdtemp(prefix="pub_rl_smoke_")
from lda_webui import store as _store_mod  # noqa: E402
_store_mod.STORE_PATH = os.path.join(_tmp, "store.json")

from lda_webui import app as A  # noqa: E402
from lda_webui import routes as R  # noqa: E402

IP_A = "203.0.113.9"
IP_B = "203.0.113.88"


class _FakeH:
    """最小 handler 替身：_client_ip 只读 client_address + headers。"""

    def __init__(self, ip):
        self.client_address = (ip, 4321)
        self.headers = {}


def _via_guard(endpoint, ip, payload=None):
    """经 routes._public_write_guard 打一发（转发 lambda handler）。"""
    h = _FakeH(ip)
    fn = lambda self, p, q, path: (200, {"ok": True, "echo": (p or {}).get("x")})
    return R._public_write_guard(endpoint, payload or {}, fn, h, {}, endpoint)


def main() -> int:
    passed = failed = 0

    def check(name, cond, extra=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {extra}")

    print("=== P3 公开写端点 IP 限流 ===")
    # C1 静态接线（生产代码对象）
    rate = set(R.PUBLIC_RATE_PATHS)
    posts = set(R.POST_ROUTES)
    heavy = set(R.HEAVY_POST_PATHS)
    expect = {"/api/opinion/submit", "/api/purchase/request",
              "/api/ecosystem/submit", "/api/store/guide"}
    check("C1 PUBLIC_RATE_PATHS 恰为 4 个审计端点", rate == expect,
          f"实际: {sorted(rate)}")
    check("C1b 全部 ∈ POST_ROUTES 注册", not (rate - posts),
          f"未注册: {sorted(rate - posts)}")
    check("C1c 与 HEAVY_POST_PATHS 无交集", not (rate & heavy),
          f"重叠: {sorted(rate & heavy)}")
    # C2 行为：10 放行 / 第 11 拒
    g = _store_mod.public_write_guard
    ok_n = sum(1 for _ in range(10) if g("C2:scope", IP_A) is None)
    r11 = g("C2:scope", IP_A)
    check("C2 同 scope+IP 10 放行/第 11 拒", ok_n == 10 and r11 is not None,
          f"放行={ok_n} 第11={r11!r}")
    # C3 独立计数
    r_other_scope = g("C3:other", IP_A)
    r_other_ip = g("C2:scope", IP_B)
    check("C3 不同 scope/IP 独立计数", r_other_scope is None and r_other_ip is None,
          f"other_scope={r_other_scope!r} other_ip={r_other_ip!r}")
    # C4 空 ip 恒放行
    c4 = all(g("C4:scope", "") is None for _ in range(30))
    check("C4 client_ip 空 ⇒ 恒放行（兼容单测直调）", c4)
    # C5 窗口过期恢复
    g5 = _store_mod.public_write_guard
    for _ in range(2):
        g5("C5:scope", IP_A, limit=2, window=0.1)
    r5_3rd = g5("C5:scope", IP_A, limit=2, window=0.1)
    time.sleep(0.15)
    r5_after = g5("C5:scope", IP_A, limit=2, window=0.1)
    check("C5 窗口过期恢复放行", r5_3rd is not None and r5_after is None,
          f"第3={r5_3rd!r} 过期后={r5_after!r}")
    # C6 反向：limit=1 第 2 次必拒（判据会响）
    g6 = _store_mod.public_write_guard
    first = g6("C6:scope", IP_B, limit=1, window=60)
    second = g6("C6:scope", IP_B, limit=1, window=60)
    check("C6 反向 limit=1 ⇒ 第 2 次必拒", first is None and second is not None,
          f"first={first!r} second={second!r}")
    # C7 端到端：_public_write_guard 真转发（真实 scope /api/opinion/submit）
    codes = []
    for i in range(11):
        c, _b = _via_guard("/api/opinion/submit", IP_A, {"x": i})
        codes.append(c)
    c_other_ip = _via_guard("/api/opinion/submit", IP_B, {"x": 99})[0]
    check("C7 端到端 10×200 + 第11×429 + 换IP恢复200",
          codes[:10] == [200] * 10 and codes[10] == 429 and c_other_ip == 200,
          f"codes={codes} other_ip={c_other_ip}")

    print("-" * 50)
    print(f"P3 结果：PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
