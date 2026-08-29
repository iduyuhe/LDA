"""D-XXX · 商务闭环 smoke —— 创新超市商业化链路回归守护。

覆盖 2026-08-29 商业化准备线的核心商务流（函数级直调，不起 HTTP 服务，CI 友好）：
  1. 注册 / 登录 / 身份折扣 / 反枚举 / 限流
  2. 下单 → 上传凭证 → 审批 → 兑换码 → 下载（限次 #1 成 #2 拒）
  3. 对公申请 → 管理员列表 → 审批出码 → 拒绝流（app.py 函数级）
  4. 定制需求全状态机：提交 → 接单 → 加交付物 → 交付 → 客户下载 → 验收
  5. 「我的」模块：概览 / 许可证资产 / 改资料 / 改密令牌轮换
  6. 账号重置闭环：管理员重置 → 临时密码登录 → 强制改密 → 解除
  7. 意见收集：提交 / 公开脱敏列表 / 管理员聚合（app.py 函数级）

验收（死标量）：全部断言 PASS → 绿；LLM 不进判决路径。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_webui"))
sys.path.insert(0, os.path.join(_HERE, "lda_l2"))

import store  # noqa: E402
from lda_l2 import ship_package as sp  # noqa: E402
from lda_l2.innovation_market import DEFAULT_SHELF  # noqa: E402
from lda_l2.ship_package import is_download_open  # noqa: E402

ADMIN = "smoke-admin-token"


def _real_open_shelf() -> str:
    for s in DEFAULT_SHELF:
        if is_download_open(s.id):
            return s.id
    raise AssertionError("无开放货架")


class StoreFlowSmoke(unittest.TestCase):
    """商务闭环函数级回归（临时路径隔离，不碰生产/本地数据）。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="lda_store_smoke_")
        store.STORE_PATH = os.path.join(cls._tmp, "store.json")
        sp.LICENSES_PATH = os.path.join(cls._tmp, "licenses.json")
        # app.py 侧依赖（对公申请 / 意见）
        import app as webapp
        cls.app = webapp
        webapp.PURCHASE_PATH = os.path.join(cls._tmp, "purchase_requests.json")
        webapp.OPINIONS_PATH = os.path.join(cls._tmp, "opinions.json")
        webapp.PROOF_DIR = os.path.join(cls._tmp, "proofs")
        os.environ["LDA_ADMIN_TOKEN"] = ADMIN

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_01_register_login_tier(self):
        email = "a1@smoke.com"
        r = store.register(email, "甲", "secret123", user_type="academic", organization="某高校")
        self.assertTrue(r["ok"], r)
        tok = r["token"]
        self.assertEqual(r["user"]["user_type"], "academic")
        # 重复注册拒绝
        self.assertFalse(store.register(email, "乙", "secret123")["ok"])
        # 登录 + 折扣（学术 6 折）
        r2 = store.login(email, "secret123")
        self.assertTrue(r2["ok"])
        shelf = _real_open_shelf()
        self.assertAlmostEqual(store.price_of(shelf, "academic"),
                               store.price_of(shelf, None) * 0.6, places=6)
        # 反枚举：两种失败消息一致
        e1 = store.login("ghost@smoke.com", "x1")["error"]
        e2 = store.login(email, "wrongpwd")["error"]
        self.assertEqual(e1, e2)

    def test_02_order_proof_approve_download_limit(self):
        store.register("a2@smoke.com", "乙", "secret123")
        tok = store.login("a2@smoke.com", "secret123")["token"]
        shelf = _real_open_shelf()
        od = store.create_order(tok, {"shelf_id": shelf, "type": "personal",
                                      "customer": {"name": "乙", "email": "a2@smoke.com"}})
        self.assertTrue(od["ok"], od)
        oid = od["order"]["id"]
        # 凭证
        self.assertTrue(store.submit_proof(oid, tok, "wx-001")["ok"])
        # 审批出码
        ap = store.admin_approve(oid, ADMIN)
        self.assertTrue(ap["ok"], ap)
        code = ap["order"]["license_code"]
        self.assertTrue(code)
        # 下载 #1 成功
        d1 = store.order_download(oid, tok)
        self.assertTrue(d1["ok"], d1)
        # 下载 #2 拒绝（限次）
        d2 = store.order_download(oid, tok)
        self.assertFalse(d2["ok"], "第二次下载应被限次拒绝")

    def test_03_purchase_request_flow(self):
        """对公申请：提交 → 管理员可见 → 审批出码 → 拒绝流。"""
        store.register("a3@smoke.com", "丙", "secret123")
        shelf = _real_open_shelf()
        st, obj = self.app.purchase_request_submit(
            {"company": "测试公司", "contact": "王五", "phone": "13800000000",
             "email": "c3@smoke.com", "shelf_id": shelf})
        self.assertEqual(st, 200, obj)
        rid = obj["request_id"]
        # 管理员列表
        st, lst = self.app.purchase_request_list({"Authorization": "Bearer " + ADMIN})
        self.assertEqual(st, 200)
        self.assertTrue(any(r["id"] == rid for r in lst["requests"]))
        # 审批
        st, ap = self.app.purchase_request_approve({}, {"Authorization": "Bearer " + ADMIN}, rid)
        self.assertEqual(st, 200)
        self.assertTrue(ap["license_code"])
        # 拒绝流
        st, obj2 = self.app.purchase_request_submit(
            {"company": "测试公司2", "contact": "赵六", "phone": "13900000000",
             "email": "c4@smoke.com", "shelf_id": shelf})
        st, rj = self.app.purchase_request_approve({"reject": True},
                                                   {"Authorization": "Bearer " + ADMIN},
                                                   obj2["request_id"])
        self.assertEqual(st, 200)
        self.assertTrue(rj["ok"])
        # 非管理员被拒
        st, r = self.app.purchase_request_list({"Authorization": "Bearer bad"})
        self.assertEqual(st, 401)

    def test_04_custom_full_state_machine(self):
        store.register("a5@smoke.com", "丁", "secret123")
        tok = store.login("a5@smoke.com", "secret123")["token"]
        od = store.create_order(tok, {"type": "custom", "title": "定制需求",
                                      "requirement": "希望优化版图",
                                      "direction": "wdm",
                                      "customer": {"name": "丁", "email": "a5@smoke.com"}})
        self.assertTrue(od["ok"], od)
        oid = od["order"]["id"]
        self.assertEqual(od["order"]["status"], "created")
        self.assertEqual(od["order"]["direction"], "wdm")
        # 接单 → developing
        r = store.custom_accept(oid, ADMIN, quote_cny=120000, eta_date="2026-09-15")
        self.assertEqual(r["order"]["status"], "developing")
        # 加交付物 ×2
        store.custom_add_deliverable(oid, ADMIN, "版图 GDS", "https://x.com/gds.zip")
        r = store.custom_add_deliverable(oid, ADMIN, "仿真报告", "https://x.com/report.pdf")
        self.assertEqual(len(r["order"]["deliverables"]), 2)
        # 交付 → delivered
        r = store.custom_deliver(oid, ADMIN)
        self.assertEqual(r["order"]["status"], "delivered")
        # 客户下载（拿交付物列表）
        d = store.order_download(oid, tok)
        self.assertTrue(d["ok"], d)
        self.assertEqual(len(d.get("deliverables", [])), 2)
        # 客户验收 → accepted
        r = store.custom_accept_delivery(oid, tok)
        self.assertEqual(r["order"]["status"], "accepted")
        # 重复验收拒绝
        self.assertFalse(store.custom_accept_delivery(oid, tok)["ok"])
        # 非法方向拒绝
        r = store.create_order(tok, {"type": "custom", "title": "x", "requirement": "y",
                                     "direction": "hack",
                                     "customer": {"name": "丁", "email": "a5@smoke.com"}})
        self.assertFalse(r["ok"])

    def test_05_my_module(self):
        store.register("a6@smoke.com", "戊", "secret123", user_type="institution", organization="某院")
        tok = store.login("a6@smoke.com", "secret123")["token"]
        s = store.my_summary(tok)
        self.assertTrue(s["ok"], s)
        self.assertEqual(s["tier_label"], "机构席位")
        # 改资料
        r = store.update_profile(tok, name="戊改", user_type="academic", organization="某高校")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["user"]["user_type"], "academic")
        # 机构席位无机构名拒绝
        store.register("a7@smoke.com", "己", "secret123")
        t7 = store.login("a7@smoke.com", "secret123")["token"]
        r = store.update_profile(t7, user_type="institution", organization="")
        self.assertFalse(r["ok"])
        # 改密 + 令牌轮换 + 旧令牌失效
        r = store.change_password(tok, "secret123", "newpass456")
        self.assertTrue(r["ok"], r)
        newtok = r["token"]
        self.assertNotEqual(newtok, tok)
        self.assertFalse(store.my_summary(tok)["ok"], "旧令牌应失效")
        self.assertTrue(store.my_summary(newtok)["ok"])
        # 许可证资产（空）
        lc = store.my_licenses(newtok)
        self.assertEqual(lc["count"], 0)

    def test_06_admin_reset_password_loop(self):
        store.register("a8@smoke.com", "庚", "secret123")
        tok = store.login("a8@smoke.com", "secret123")["token"]
        # 管理员重置
        r = store.admin_reset_password("a8@smoke.com", ADMIN)
        self.assertTrue(r["ok"], r)
        temp = r["temp_password"]
        self.assertEqual(len(temp), 12)
        self.assertTrue(r["must_change_password"])
        # 旧会话失效
        self.assertFalse(store.my_summary(tok)["ok"])
        # 临时密码登录 + 强制改密标记
        r = store.login("a8@smoke.com", temp)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r.get("must_change_password"))
        t2 = r["token"]
        # 改密解除标记
        r = store.change_password(t2, temp, "final789xyz")
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["must_change_password"])
        # 新密码可登录、无标记
        r = store.login("a8@smoke.com", "final789xyz")
        self.assertTrue(r["ok"])
        self.assertFalse(r.get("must_change_password"))
        # 非管理员重置被拒
        self.assertFalse(store.admin_reset_password("a8@smoke.com", "bad")["ok"])

    def test_07_opinion_collection(self):
        """意见：提交 / 公开脱敏 / 管理员聚合含联系方式。"""
        st, obj = self.app.opinion_submit(
            {"shelf_id": "IM-CPO-WDM5", "content": "希望出 8 通道版本",
             "contact": "eng@smoke.com"})
        self.assertEqual(st, 200, obj)
        # 公开列表脱敏
        st, lst = self.app.opinion_list("IM-CPO-WDM5")
        self.assertEqual(st, 200)
        self.assertTrue(lst["count"] >= 1)
        self.assertTrue(all("contact" not in o for o in lst["opinions"]))
        # 管理员聚合含联系方式
        st, agg = self.app.opinion_admin_all({"Authorization": "Bearer " + ADMIN})
        self.assertEqual(st, 200)
        self.assertTrue(any(o.get("contact") == "eng@smoke.com" for o in agg["opinions"]))
        # 非管理员 401
        st, _ = self.app.opinion_admin_all({"Authorization": "Bearer bad"})
        self.assertEqual(st, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
