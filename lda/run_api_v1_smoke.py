#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2.3 v1 API 冒烟（直接调用 api_v1.handle_v1，MemoryBackend）。

验收：注册/登录/认证/建项目/存设计/租户隔离/用量/插件安全/license seam 全 PASS。
运行：python lda/run_api_v1_smoke.py
"""
import sys
import os

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_webui import api_v1


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

    print("=== P2.3 v1 API 冒烟 ===")
    H = api_v1.handle_v1

    # 1. 注册 → 拿到 api_key + 个人 org
    c, o = H("POST", "/api/v1/auth/register",
             {"email": "a@lda.dev", "password": "password123"}, {})
    check("注册成功 200", c == 200, o)
    key_a = o.get("api_key")
    org_a = o.get("org_id")
    check("返回 api_key", bool(key_a) and key_a.startswith("sk-"))
    check("返回个人 org", isinstance(org_a, int))

    # 弱密码被拒
    c, o = H("POST", "/api/v1/auth/register",
             {"email": "weak@lda.dev", "password": "short"}, {})
    check("弱密码(>=8)被拒 400", c == 400)

    # 2. 未认证访问受保护接口 → 401
    c, o = H("GET", "/api/v1/me", {}, {})
    check("未认证 /me → 401", c == 401)

    # 3. 登录 → 新 api_key
    c, o = H("POST", "/api/v1/auth/login",
             {"email": "a@lda.dev", "password": "password123"}, {})
    check("登录成功 200", c == 200, o)
    key_login = o.get("api_key")
    check("登录返回 api_key", bool(key_login))

    AUTH = {"Authorization": "Bearer " + key_a}

    # 4. /me
    c, o = H("GET", "/api/v1/me", {}, AUTH)
    check("/me 返回 user + orgs", c == 200 and org_a in o.get("orgs", []))

    # 5. 建项目（带 org_id，且为成员）
    c, o = H("POST", "/api/v1/projects",
             {"org_id": org_a, "name": "ring", "meta": {"g": 1}}, AUTH)
    check("建项目 200", c == 200, o)
    proj = o.get("project_id")
    check("返回 project_id", isinstance(proj, int))

    # 6. 存设计（org 作用域）
    c, o = H("POST", f"/api/v1/projects/{proj}/designs",
             {"org_id": org_a, "device_type": "RingResonator",
              "params": {"r": 5.0}, "dual_verify_report": {"passed": True}}, AUTH)
    check("存设计 200", c == 200, o)
    did = o.get("design_id")

    # 7. 列出设计（GET 经 query/body 传 org_id）
    c, o = H("GET", f"/api/v1/projects/{proj}/designs", {"org_id": org_a}, AUTH)
    check("列设计含 1 条", c == 200 and len(o.get("designs", [])) == 1, o)

    # 8. 用量
    c, o = H("GET", "/api/v1/usage", {"org_id": org_a}, AUTH)
    check("用量返回 designs=1", c == 200 and o.get("designs") == 1)

    # 9. 租户隔离：第二用户无法访问 org_a
    c2, o2 = H("POST", "/api/v1/auth/register",
               {"email": "b@lda.dev", "password": "password123"}, {})
    key_b = o2.get("api_key")
    B = {"Authorization": "Bearer " + key_b}
    c, o = H("GET", "/api/v1/projects", {"org_id": org_a}, B)
    check("b 访问 a 的 org → 403", c == 403, o)
    c, o = H("POST", f"/api/v1/projects/{proj}/designs",
             {"org_id": org_a, "device_type": "x"}, B)
    check("b 越权写 a 的项目 → 403/400", c in (400, 403), o)

    # 10. 插件安全：白名单外 entry 被拒
    c, o = H("POST", "/api/v1/plugins",
             {"manifest": {"name": "evil", "version": "1.0",
                           "entry": "os.path"}}, AUTH)
    check("插件白名单外被拒", c == 200 and o.get("ok") is False, o)
    # 白名单内但模块不存在 → 加载失败（不崩溃）
    c, o = H("POST", "/api/v1/plugins",
             {"manifest": {"name": "missing", "version": "1.0",
                           "entry": "ext_oracle.nope"}}, AUTH)
    check("插件缺失模块→ok:False 不崩", c == 200 and o.get("ok") is False, o)
    # 列表插件
    c, o = H("GET", "/api/v1/plugins", {}, AUTH)
    check("插件列表可返回", c == 200 and isinstance(o.get("plugins"), list))

    # 11. license seam：无 key → oss
    c, o = H("GET", "/api/v1/license", {}, AUTH)
    check("license 默认 oss", c == 200 and o.get("tier") == "oss", o)

    print(f"\n=== P2.3 冒烟结果：PASS={passed}  FAIL={failed} ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
