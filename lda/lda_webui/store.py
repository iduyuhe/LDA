"""LDA 创新超市 · 商业闭环核心（会员 + 统一订单 + 微信个人收款 + 自动交付）。

设计纪律（与 LDA 主权/红线一致）：
- 零外部依赖（仅标准库），离线可跑、数据落盘于 dist/（gitignored，绝不入库）。
- 复用 ship_package 的 mint_license / verify_license / generate_package 完成交付。
- 个人支付采用「微信个人收款码 + 支付凭证」模式（非商户 API），诚实标注：
  小额个人收款无法服务端自动核验，需管理员一键确认收货——但已把「确认收款 + 自动发货」
  合并为单次操作，最大限度减少人工。

数据持久化（dist/store.json）：
{
  "users":  {uid: {id,email,name,phone,password_hash,salt,created_at,is_admin}},
  "orders": [ {id, user_id, type, shelf_id, amount_cny, pay_method, status,
               customer:{name,company,phone,email}, proof, license_code,
               created_at, paid_at, approved_at, note, reject_reason} ],
  "config": {wechat:{payee,qr,amount_note}, prices:{shelf_id:amount}, auto_confirm}
}
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in __import__("sys").path:
    __import__("sys").path.insert(0, _LDA)

ROOT = os.path.dirname(_LDA)                      # 仓库根（lda/ 上一级）
STORE_PATH = os.path.join(ROOT, "dist", "store.json")
_LOCK = threading.Lock()

# 默认单价（¥，可被 config.prices 按货架覆盖）。开放货架众多，默认统一价即可。
DEFAULT_PRICE_CNY = 1999

# 计费身份分层（Track 0 · 学术/机构身份 + 定价分层）
# standard  → 标准个人（零售原价）
# academic  → 学术个人（公益教育价，默认 6 折）
# institution → 机构席位（协议价，默认 8.5 折，支持按需席位授权）
USER_TYPES = ("standard", "academic", "institution")
USER_TYPE_LABELS = {"standard": "标准个人", "academic": "学术个人",
                    "institution": "机构席位"}
TIER_DISCOUNT = {"standard": 1.0, "academic": 0.6, "institution": 0.85}
DEFAULT_TIER = "standard"

# 订单状态机：
#   created        → 已创建，待支付
#   paid_unverified → 已提交支付凭证，待管理员确认收款
#   approved       → 已确认收款并生成兑换码（待下载/已交付）
#   rejected       → 已拒绝
STATUS_FLOW = ("created", "paid_unverified", "approved", "rejected")


# --------------------------------------------------------------------------
# 持久化
# --------------------------------------------------------------------------
def _ensure_dir():
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if not os.path.exists(STORE_PATH):
        return {"users": {}, "orders": [], "config": {
            "wechat": {"payee": "", "qr": "", "amount_note": ""},
            "prices": {}, "auto_confirm": False}}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("users", {})
        data.setdefault("orders", [])
        data.setdefault("config", {})
        data["config"].setdefault("wechat", {"payee": "", "qr": "", "amount_note": ""})
        data["config"].setdefault("prices", {})
        data["config"].setdefault("auto_confirm", False)
        return data
    except Exception:  # noqa: BLE001
        return {"users": {}, "orders": [], "config": {
            "wechat": {"payee": "", "qr": "", "amount_note": ""},
            "prices": {}, "auto_confirm": False}}


def _save(data: dict) -> None:
    _ensure_dir()
    with _LOCK:
        with open(STORE_PATH, "w",  encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# 会员（注册 / 登录 / 会话）
# --------------------------------------------------------------------------
def _hash_pwd(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt.encode("utf-8"), 100_000).hex()


def register(email: str, name: str, password: str, phone: str = "",
             user_type: str = "standard", organization: str = "") -> dict:
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"ok": False, "error": "email 格式不合法"}
    if len(password or "") < 6:
        return {"ok": False, "error": "密码至少 6 位"}
    if user_type not in USER_TYPES:
        user_type = DEFAULT_TIER
    if user_type == "institution" and not (organization or "").strip():
        return {"ok": False, "error": "机构席位需填写机构/单位名称"}
    data = _load()
    if any(u.get("email") == email for u in data["users"].values()):
        return {"ok": False, "error": "该邮箱已注册，请直接登录"}
    salt = secrets.token_hex(8)
    uid = "u-" + uuid.uuid4().hex[:10]
    token = secrets.token_urlsafe(24)
    data["users"][uid] = {
        "id": uid, "email": email, "name": (name or "").strip()[:40],
        "phone": (phone or "").strip()[:40],
        "user_type": user_type,
        "organization": (organization or "").strip()[:120],
        "password_hash": _hash_pwd(password, salt), "salt": salt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_admin": False, "token": token,
    }
    _save(data)
    return {"ok": True, "token": token, "user": _public_user(data["users"][uid])}


def login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    data = _load()
    user = next((u for u in data["users"].values() if u.get("email") == email), None)
    if user is None:
        return {"ok": False, "error": "账号不存在，请先注册"}
    if _hash_pwd(password, user.get("salt", "")) != user.get("password_hash"):
        return {"ok": False, "error": "密码错误"}
    # 刷新会话令牌
    token = secrets.token_urlsafe(24)
    user["token"] = token
    _save(data)
    return {"ok": True, "token": token, "user": _public_user(user)}


def user_by_token(token: str) -> dict | None:
    if not token:
        return None
    data = _load()
    return next((u for u in data["users"].values() if u.get("token") == token), None)


def _public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u.get("name", ""),
            "phone": u.get("phone", ""), "is_admin": u.get("is_admin", False),
            "created_at": u.get("created_at", ""),
            "user_type": u.get("user_type", DEFAULT_TIER),
            "organization": u.get("organization", "")}


def is_admin(token: str) -> bool:
    # 站点管理员：环境变量 LDA_ADMIN_TOKEN（生产必设）或 store 中 is_admin 用户。
    env_tok = os.environ.get("LDA_ADMIN_TOKEN", "")
    if env_tok and token and token == env_tok:
        return True
    u = user_by_token(token)
    return bool(u and u.get("is_admin"))


# --------------------------------------------------------------------------
# 配置（微信收款 / 价格）
# --------------------------------------------------------------------------
def get_config() -> dict:
    return _load()["config"]


def set_config(config: dict, token: str) -> dict:
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized"}
    data = _load()
    # 仅接受已知字段
    wc = config.get("wechat") or {}
    if isinstance(wc, dict):
        data["config"]["wechat"]["payee"] = str(wc.get("payee", ""))[:60]
        data["config"]["wechat"]["qr"] = str(wc.get("qr", ""))[:2000]
        data["config"]["wechat"]["amount_note"] = str(wc.get("amount_note", ""))[:200]
    if isinstance(config.get("prices"), dict):
        data["config"]["prices"].update({str(k): float(v)
                                         for k, v in config["prices"].items()})
    if isinstance(config.get("tiers"), dict):
        new_tiers = {}
        for k, v in config["tiers"].items():
            if k in USER_TYPES:
                try:
                    new_tiers[k] = float(v)
                except (TypeError, ValueError):
                    pass
        if new_tiers:
            data["config"]["tiers"] = new_tiers
    if "auto_confirm" in config:
        data["config"]["auto_confirm"] = bool(config["auto_confirm"])
    _save(data)
    return {"ok": True, "config": data["config"]}


def tier_discount(user_type: str | None = None) -> float:
    """返回身份折扣系数（≤1.0）。优先用管理员在 config.tiers 的配置，否则用内置默认。"""
    if user_type not in USER_TYPES:
        return 1.0
    data = _load()
    tiers = data["config"].get("tiers", {}) or {}
    if user_type in tiers:
        try:
            return float(tiers[user_type])
        except (TypeError, ValueError):
            pass
    return TIER_DISCOUNT[user_type]


def price_of(shelf_id: str, user_type: str | None = None) -> float:
    """货架实付价：基准单价 × 身份折扣（可被 config.tiers 覆盖折扣）。"""
    data = _load()
    base = float(data["config"].get("prices", {}).get(shelf_id, DEFAULT_PRICE_CNY))
    return round(base * tier_discount(user_type), 2)


# --------------------------------------------------------------------------
# 订单（统一 个人/企业）
# --------------------------------------------------------------------------
def create_order(user_token: str, payload: dict) -> dict:
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    p = payload or {}
    otype = str(p.get("type") or "personal")  # personal | business | custom
    if otype not in ("personal", "business", "custom"):
        return {"ok": False, "error": "type 必须是 personal/business/custom"}

    customer = p.get("customer") or {}
    name = str(customer.get("name") or u.get("name") or "").strip()[:60]
    company = str(customer.get("company") or "").strip()[:120]
    phone = str(customer.get("phone") or u.get("phone") or "").strip()[:40]
    email = str(customer.get("email") or u.get("email") or "").strip()[:120]
    if not name or not email:
        return {"ok": False, "error": "姓名与邮箱为必填"}

    tier = u.get("user_type", DEFAULT_TIER)

    if otype == "custom":
        title = str(p.get("title") or "").strip()[:120]
        requirement = str(p.get("requirement") or "").strip()[:2000]
        if not title or not requirement:
            return {"ok": False, "error": "定制需求需填写标题与需求描述"}
        target_spec = str(p.get("target_spec") or "").strip()[:2000]
        budget = str(p.get("budget") or "").strip()[:200]
        shelf_id = ""
        amount_cny = 0
    else:
        from lda_l2.ship_package import is_download_open, shelf_by_id
        shelf_id = str(p.get("shelf_id") or "").strip()
        if not shelf_by_id(shelf_id) or not is_download_open(shelf_id):
            return {"ok": False, "error": f"货架 {shelf_id} 不存在或未开放下载"}
        title = str(p.get("title") or shelf_id)[:120]
        target_spec = ""
        budget = ""
        amount_cny = price_of(shelf_id, tier)

    order = {
        "id": "ord-" + uuid.uuid4().hex[:12],
        "user_id": u["id"],
        "type": otype,
        "shelf_id": shelf_id,
        "title": title,
        "amount_cny": amount_cny,
        "tier": tier,
        "pay_method": "wechat_personal" if otype == "personal" else ("bank_corp" if otype == "business" else "quote_later"),
        "status": "created",
        "customer": {"name": name, "company": company, "phone": phone, "email": email},
        "requirement": requirement if otype == "custom" else "",
        "target_spec": target_spec,
        "budget": budget,
        "proof": "",
        "license_code": None,
        "deliverable_url": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paid_at": None, "approved_at": None, "note": "",
        "reject_reason": "",
    }
    data = _load()
    data["orders"].insert(0, order)
    _save(data)
    return {"ok": True, "order": _public_order(order)}


def submit_proof(order_id: str, user_token: str, proof: str) -> dict:
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    data = _load()
    order = _find_order(data, order_id)
    if order is None:
        return {"ok": False, "error": "订单不存在"}
    if order["user_id"] != u["id"] and not u.get("is_admin"):
        return {"ok": False, "error": "无权操作该订单"}
    if order["status"] not in ("created", "paid_unverified"):
        return {"ok": False, "error": "该订单状态不可提交凭证"}
    order["proof"] = (proof or "").strip()[:500]
    order["status"] = "paid_unverified"
    order["paid_at"] = datetime.now(timezone.utc).isoformat()
    if data["config"].get("auto_confirm") and order["type"] == "personal":
        _deliver(order, data)
    _save(data)
    return {"ok": True, "order": _public_order(order)}


def admin_approve(order_id: str, token: str, deliverable_url: str = "") -> dict:
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    data = _load()
    order = _find_order(data, order_id)
    if order is None:
        return {"ok": False, "error": "订单不存在"}
    if order["status"] in ("approved", "rejected"):
        return {"ok": False, "error": "订单已处理", "license_code": order.get("license_code")}
    if order["type"] == "custom":
        order["status"] = "approved"
        order["approved_at"] = datetime.now(timezone.utc).isoformat()
        if deliverable_url:
            order["deliverable_url"] = str(deliverable_url).strip()[:500]
    else:
        _deliver(order, data, deliverable_url)
    _save(data)
    return {"ok": True, "order": _public_order(order)}


def admin_reject(order_id: str, token: str, reason: str = "") -> dict:
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    data = _load()
    order = _find_order(data, order_id)
    if order is None:
        return {"ok": False, "error": "订单不存在"}
    order["status"] = "rejected"
    order["reject_reason"] = (reason or "").strip()[:200]
    _save(data)
    return {"ok": True, "order": _public_order(order)}


def _deliver(order: dict, data: dict, deliverable_url: str = "") -> None:
    """确认收款并自动发货：生成兑换码 + 写入授权表（复用 ship_package）。"""
    from lda_l2.ship_package import mint_license
    if order.get("license_code") is None:
        order["license_code"] = mint_license(order["shelf_id"],
                                            email=order["customer"].get("email", ""),
                                            max_uses=1)
    order["status"] = "approved"
    order["approved_at"] = datetime.now(timezone.utc).isoformat()
    if deliverable_url:
        order["deliverable_url"] = str(deliverable_url).strip()[:500]


def _find_order(data: dict, order_id: str) -> dict | None:
    return next((o for o in data["orders"] if o.get("id") == order_id), None)


def _public_order(o: dict) -> dict:
    return {
        "id": o["id"], "user_id": o["user_id"], "type": o["type"],
        "shelf_id": o["shelf_id"], "title": o.get("title", ""),
        "amount_cny": o["amount_cny"], "tier": o.get("tier", "standard"),
        "pay_method": o["pay_method"],
        "status": o["status"], "customer": o["customer"],
        "requirement": o.get("requirement", ""), "target_spec": o.get("target_spec", ""),
        "budget": o.get("budget", ""), "proof": o.get("proof", ""),
        "license_code": o.get("license_code"), "deliverable_url": o.get("deliverable_url", ""),
        "created_at": o["created_at"], "paid_at": o.get("paid_at"),
        "approved_at": o.get("approved_at"),
        "reject_reason": o.get("reject_reason", ""),
    }


def list_orders(token: str, scope: str = "mine") -> dict:
    data = _load()
    u = user_by_token(token)
    if scope == "all":
        if not is_admin(token):
            return {"ok": False, "error":  "unauthorized", "code": 401}
        rows = [o for o in data["orders"]]
    else:
        if u is None:
            return {"ok": False, "error": "请先登录", "code": 401}
        rows = [o for o in data["orders"] if o["user_id"] == u["id"]]
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"ok": True, "orders": [_public_order(o) for o in rows],
            "count": len(rows)}


def public_config() -> dict:
    """给前台：微信收款码（脱敏）+ 单价 + 身份分层，不含管理员信息。"""
    data = _load()
    wc = data["config"]["wechat"]
    tiers = {}
    for t in USER_TYPES:
        tiers[t] = {"label": USER_TYPE_LABELS[t], "discount": tier_discount(t)}
    return {"payee": wc.get("payee", ""), "qr": wc.get("qr", ""),
            "amount_note": wc.get("amount_note", ""),
            "tiers": tiers, "default_tier": DEFAULT_TIER}


def order_download(order_id: str, token: str) -> dict:
    """会员自助下载：校验订单归属 + 已交付，生成/返回包（复用 ship_package）。"""
    u = user_by_token(token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    data = _load()
    order = _find_order(data, order_id)
    if order is None:
        return {"ok": False, "error": "订单不存在"}
    if order["user_id"] != u["id"] and not is_admin(token):
        return {"ok": False, "error": "无权下载该订单"}
    if order["type"] == "custom":
        if order.get("status") != "approved":
            return {"ok": False, "error": "订单尚未接单/交付"}
        if order.get("deliverable_url"):
            return {"ok": True, "deliverable_url": order["deliverable_url"],
                    "license_code": order.get("license_code")}
        return {"ok": False, "error": "交付文件待上传，请联系管理员"}
    if order.get("status") != "approved" or not order.get("license_code"):
        return {"ok": False, "error": "订单尚未交付，无法下载"}
    from lda_l2.ship_package import generate_package, consume_license
    r = generate_package(order["shelf_id"])
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "生成失败")}
    consume_license(order["license_code"])
    return {"ok": True, "zip_path": r["zip_path"],
            "license_code": order["license_code"], "shelf_id": order["shelf_id"]}
