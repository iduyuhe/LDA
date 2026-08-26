#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2.2 多用户数据层冒烟（内存后端，零外部依赖）。

验收：注册/登录/建项目/存设计结果/多用户隔离/API Key 认证/用量计量 全 PASS。
运行：python lda/run_data_layer_smoke.py
"""
import sys
import os

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_data.backend import MemoryBackend, get_backend
from lda_data.service import DataLayer
from lda_data.auth import verify_api_key


def main() -> int:
    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    print("=== P2.2 数据层冒烟（MemoryBackend）===")
    dl = DataLayer(MemoryBackend())

    # 1. 注册两个用户（分属两个组织）
    u1 = dl.register_user("alice@lda.dev", "StrongPass#1")
    u2 = dl.register_user("bob@lda.dev", "StrongPass#2")
    check("注册两个用户，id 不同", u1 != u2 and u1 > 0 and u2 > 0)

    # 2. 登录校验（正确/错误密码）
    check("alice 正确密码登录", dl.verify_user("alice@lda.dev", "StrongPass#1") is not None)
    check("alice 错误密码拒绝", dl.verify_user("alice@lda.dev", "wrong") is None)
    check("邮箱大小写归一", dl.verify_user("ALICE@LDA.DEV", "StrongPass#1") is not None)

    # 3. 组织与成员关系
    org_a = dl.create_org("Acme")
    org_b = dl.create_org("BetaCorp")
    dl.add_member(u1, org_a, role="owner")
    dl.add_member(u2, org_b, role="owner")
    check("alice 属 org_a", dl.is_member(u1, org_a))
    check("alice 不属 org_b（隔离）", not dl.is_member(u1, org_b))
    check("user_orgs 返回正确", [o.id for o in dl.user_orgs(u1)] == [org_a])

    # 4. 项目 + 设计结果持久化
    p1 = dl.create_project(org_a, "ring-filter", meta={"goal": "add-drop"})
    dr_id = dl.save_design_result(
        org_a, p1, device_type="RingResonator",
        params={"radius_um": 5.0}, dual_verify_report={"passed": True},
        layout_json={"gds": "..."})
    check("设计结果已存，返回 id", dr_id > 0)
    got = dl.get_project(org_a, p1)
    check("项目可取且 meta 还原", got is not None and got.meta == {"goal": "add-drop"})

    # 5. 租户隔离：org_b 看不到 org_a 的设计，也不能越权写
    check("org_b 列出设计为空（隔离）", dl.list_design_results(org_b) == [])
    check("org_b 取 org_a 项目返回 None", dl.get_project(org_b, p1) is None)
    try:
        dl.save_design_result(org_b, p1, device_type="x")  # p1 不属于 org_b
        check("org_b 越权写被拒（异常）", False)
    except ValueError:
        check("org_b 越权写被拒（异常）", True)

    # cross-org：bob 在自己的 org 存设计，alice 那边列表不受影响
    p2 = dl.create_project(org_b, "bob-proj")
    dl.save_design_result(org_b, p2, device_type="Waveguide")
    check("org_a 设计数仍为 1（不被污染）", dl.count_designs(org_a) == 1)
    check("org_b 设计数为 1", dl.count_designs(org_b) == 1)

    # 6. API Key 认证
    plain, kid = dl.create_api_key(u1, scopes=["design:read"])
    check("API Key 创建返回明文", plain.startswith("sk-") and len(plain) > 10)
    auth_uid = dl.authenticate_api_key(plain)
    check("正确 Key 解析出 user_id", auth_uid == u1)
    check("错误 Key 拒绝", dl.authenticate_api_key("sk-bogus") is None)
    check("哈希校验一致（auth 模块）",
          verify_api_key(plain, dl.list_api_keys(u1)[0].key_hash))

    # 7. 用量计量
    dl.record_run(org_a, p1, "fdtd3d", 12.5, "ok")
    dl.record_run(org_a, p1, "fdtd3d", 8.0, "ok")
    usage = dl.get_usage(org_a)
    check("org_a 用量：2 次运行/20.5s", usage["runs"] == 2 and abs(usage["run_seconds"] - 20.5) < 1e-6)
    check("org_b 用量为 0（隔离）", dl.get_usage(org_b)["runs"] == 0)

    dl.close()

    # 8. get_backend 解析（sqlite 文件 / 内存 / 未配置默认内存）
    check("未配置 LDA_DB_URL → 内存后端", isinstance(get_backend(None), MemoryBackend))
    check("sqlite:// 文件后端可解析",
          isinstance(get_backend("sqlite:////tmp/lda_test.db"), __import__("lda_data.backend", fromlist=["SqliteFileBackend"]).SqliteFileBackend))
    try:
        get_backend("postgresql://u:p@h/db")
        check("Postgres 路径显式不支持", False)
    except NotImplementedError:
        check("Postgres 路径显式不支持", True)

    print(f"\n=== P2.2 冒烟结果：PASS={passed}  FAIL={failed} ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
