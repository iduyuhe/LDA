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
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in __import__("sys").path:
    __import__("sys").path.insert(0, _LDA)

ROOT = os.path.dirname(_LDA)                      # 仓库根（lda/ 上一级）
STORE_PATH = os.path.join(ROOT, "dist", "store.json")
_LOCK = threading.RLock()    # 可重入：读-改-写全程互斥（含 _load 读），防并发丢写 + Windows rename 冲突

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
#   created        → 已创建，待支付（个人/企业货架）
#   paid_unverified → 已提交支付凭证，待管理员确认收款
#   approved       → 已确认收款并生成兑换码（货架类自动交付）
#   rejected       → 已拒绝
#   developing     → 定制需求已接单，开发中（管理员录入排期/报价/内部备注）
#   delivered      → 定制需求已交付（管理员上传交付物）
#   accepted       → 客户确认验收（定制需求闭环）
STATUS_FLOW = ("created", "paid_unverified", "approved", "rejected",
               "developing", "delivered", "accepted")
# 定制需求专用状态流转：created → developing → delivered → accepted（任一可 → rejected）
CUSTOM_STATUS_FLOW = ("created", "developing", "delivered", "accepted", "rejected")

# 定制需求方向枚举（白名单；用于定制表单 chips 导流 + 管理后台精准对接）
CUSTOM_DIRECTIONS = ("ai_io", "wdm", "sensing", "coherent", "quantum", "pon")
DIRECTION_LABELS = {
    "ai_io": "光互连 / AI 集群",
    "wdm": "WDM 波分复用",
    "sensing": "传感与检测",
    "coherent": "相干与调制",
    "quantum": "量子计算 / QKD",
    "pon": "接入网 / PON",
}

# —— 登录/注册安全基线（2026-08-29 审计后引入）——
# 邮箱：比旧的 `"@" in email` 严格，杜绝 `a@.b`、`@.` 之类的畸形值入库。
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MAX_PASSWORD_LEN = 200        # 上限防 pbkdf2 计算型 DoS（10 万字符密码实测可注册）
MIN_PASSWORD_LEN = 6
# 会话令牌有效期（天）。到期后需重新登录；存量无时间戳的令牌视为「自首次访问起计时」，
# 不会因本次升级把已登录用户立刻踢下线。
TOKEN_TTL_DAYS = 30
# 登录失败限流：单账号 + 单 IP 双维度，超过阈值后锁定时长（秒）
_LOGIN_MAX_FAILS = 5
_LOGIN_LOCK_SECONDS = 600

# 失败计数器（进程内存）。本服务为单进程 ThreadingHTTPServer，内存计数足够；
# 重启即清空，与“持久化不应记录失败口令”的安全取向一致。
_LOGIN_GUARD: dict = {}
_LOGIN_GUARD_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# 持久化
# --------------------------------------------------------------------------
def _ensure_dir():
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if not os.path.exists(STORE_PATH):
        return {"users": {}, "orders": [], "config": _default_config()}
    with _LOCK:
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("orders", [])
            data.setdefault("config", {})
            data["config"].setdefault("wechat", {"payee": "", "qr": "", "amount_note": ""})
            data["config"].setdefault("bank", _default_bank())
            data["config"].setdefault("prices", {})
            data["config"].setdefault("tiers", {})
            data["config"].setdefault("auto_confirm", False)
            return data
        except Exception:  # noqa: BLE001
            # 数据文件损坏：绝不静默清空覆盖——先备份再返回默认，保留恢复机会。
            try:
                import time as _t
                os.rename(STORE_PATH, STORE_PATH + ".corrupt-%d" % int(_t.time()))
            except Exception:  # noqa: BLE001
                pass
            return {"users": {}, "orders": [], "config": _default_config()}


def _default_bank() -> dict:
    return {
        "name": "上海杜特企业管理咨询有限公司",
        "branch": "上海农商银行陈行支行",
        "account": "32434508010036375",
        "tel": "13636690529 / 13311602075 / 13901700712",
        "contact": "13636690529 / 13311602075 杜先生 或 13901700712 范女士",
    }


def _default_config() -> dict:
    return {"wechat": {"payee": "", "qr": "", "amount_note": ""}, "bank": _default_bank(),
            "prices": {}, "tiers": {}, "auto_confirm": False}


def _save(data: dict) -> None:
    with _LOCK:
        _save_nolock(data)


def _locked() -> "_LockedCtx":
    """读-改-写全程互斥（ThreadingHTTPServer 并发下防丢写）。

    用法：with _locked() as data: ...修改... （退出时自动落盘）
    """
    return _LockedCtx()


class _LockedCtx:
    def __enter__(self):
        _LOCK.acquire()
        try:
            self._data = _load()
            return self._data
        except Exception:
            _LOCK.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                _save_nolock(self._data)
        finally:
            _LOCK.release()
        return False


def _save_nolock(data: dict) -> None:
    """原子写：先写临时文件再 rename，避免进程崩溃时留下半写坏文件。"""
    _ensure_dir()
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    # Windows 下目标可能被瞬时读句柄占用：小重试窗口
    for _try in range(5):
        try:
            os.replace(tmp, STORE_PATH)
            return
        except PermissionError:
            time.sleep(0.02)
    # 最后兜底：直接覆盖写（保留 .bak 防止坏文件）
    try:
        if os.path.exists(STORE_PATH):
            os.replace(STORE_PATH, STORE_PATH + ".bak")
    except Exception:  # noqa: BLE001
        pass
    os.replace(tmp, STORE_PATH)


# --------------------------------------------------------------------------
# 会员（注册 / 登录 / 会话）
# --------------------------------------------------------------------------
def _hash_pwd(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt.encode("utf-8"), 100_000).hex()


def register(email: str, name: str, password: str, phone: str = "",
             user_type: str = "standard", organization: str = "") -> dict:
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return {"ok": False, "error": "email 格式不合法"}
    password = password or ""
    if len(password) < 6:
        return {"ok": False, "error": "密码至少 6 位"}
    if len(password) > MAX_PASSWORD_LEN:
        return {"ok": False, "error": "密码过长（上限 %d 字符）" % MAX_PASSWORD_LEN}
    if not (name or "").strip():
        return {"ok": False, "error": "请填写姓名/称谓"}
    if user_type not in USER_TYPES:
        user_type = DEFAULT_TIER
    if user_type == "institution" and not (organization or "").strip():
        return {"ok": False, "error": "机构席位需填写机构/单位名称"}
    with _locked() as data:
        if any(u.get("email") == email for u in data["users"].values()):
            return {"ok": False, "error": "该邮箱已注册，请直接登录"}
        salt = secrets.token_hex(8)
        uid = "u-" + uuid.uuid4().hex[:10]
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc).isoformat()
        data["users"][uid] = {
            "id": uid, "email": email, "name": (name or "").strip()[:40],
            "phone": (phone or "").strip()[:40],
            "user_type": user_type,
            "organization": (organization or "").strip()[:120],
            "password_hash": _hash_pwd(password, salt), "salt": salt,
            "created_at": now,
            "token": token, "token_created_at": now,
            "is_admin": False,
        }
    return {"ok": True, "token": token, "user": _public_user(data["users"][uid])}


def login(email: str, password: str, client_ip: str = "") -> dict:
    """登录。安全基线（审计后）：

    - 反用户枚举：账号不存在 / 密码错误 / 锁定 一律返回同一句提示；
    - 失败限流：账号维度 + IP 维度双计数，超阈值锁定 _LOGIN_LOCK_SECONDS 秒；
    - 只做一次 pbkdf2（账号不存在时用固定 salt 空算，避免时序差暴露账号存在性）；
    - 记录 last_login_at / last_login_ip 供审计。
    """
    email = (email or "").strip().lower()
    generic_err = "邮箱或密码不正确"

    def _guard_keys():
        # 无 IP 时跳过 IP 维度（否则会退化成共享的 "ip:" 键，把无关请求锁在一起）
        keys = []
        if email:
            keys.append("acct:" + email)
        if client_ip:
            keys.append("ip:" + client_ip)
        return keys

    # ---- 限流前置检查（不消耗 pbkdf2，防计算型 DoS）----
    with _LOGIN_GUARD_LOCK:
        for key in _guard_keys():
            st = _LOGIN_GUARD.get(key)
            if st and time.time() < st["until"] and st["fails"] >= _LOGIN_MAX_FAILS:
                left = int(st["until"] - time.time())
                return {"ok": False,
                        "error": "尝试次数过多，请 %d 分钟后再试" % max(1, (left + 59) // 60)}

    def _note_fail():
        with _LOGIN_GUARD_LOCK:
            now = time.time()
            for key in _guard_keys():
                st = _LOGIN_GUARD.get(key) or {"fails": 0, "until": 0.0}
                st["fails"] += 1
                if st["fails"] >= _LOGIN_MAX_FAILS:
                    st["until"] = now + _LOGIN_LOCK_SECONDS
                _LOGIN_GUARD[key] = st

    def _clear_fail():
        with _LOGIN_GUARD_LOCK:
            for key in _guard_keys():
                _LOGIN_GUARD.pop(key, None)

    with _locked() as data:
        user = next((u for u in data["users"].values() if u.get("email") == email), None)
        if user is None:
            # 账号不存在：仍跑一次等价开销的哈希，消除时序侧信道
            _hash_pwd(password or "", "no-such-account")
            _note_fail()
            return {"ok": False, "error": generic_err}
        if _hash_pwd(password or "", user.get("salt", "")) != user.get("password_hash"):
            _note_fail()
            return {"ok": False, "error": generic_err}
        _clear_fail()
        # 刷新会话令牌（单设备语义：新登录会使旧令牌失效）
        token = secrets.token_urlsafe(24)
        user["token"] = token
        user["token_created_at"] = datetime.now(timezone.utc).isoformat()
        user["last_login_at"] = user["token_created_at"]
        user["last_login_ip"] = (client_ip or "")[:64]
        if not user.get("user_type"):
            user["user_type"] = DEFAULT_TIER   # 修复历史脏值 None
        must_change = bool(user.get("must_change_password"))
    return {"ok": True, "token": token, "user": _public_user(user),
            "must_change_password": must_change}


def user_by_token(token: str) -> dict | None:
    """按会话令牌取用户。令牌比较用恒定时间算法，并检查 TTL。"""
    if not token:
        return None
    data = _load()
    for u in data["users"].values():
        if secrets.compare_digest(str(u.get("token") or ""), str(token)):
            if _token_expired(u):
                return None
            return u
    return None


def _token_expired(u: dict) -> bool:
    """会话过期判定。存量令牌无 token_created_at 时不视为过期（平滑升级，不踢在线用户）。"""
    ts = u.get("token_created_at") or u.get("created_at")
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - t > timedelta(days=TOKEN_TTL_DAYS)


def _public_user(u: dict) -> dict:
    # 注意用 `or` 而非 .get(k, default)：键存在但值为 None 时 .get 会返回 None，
    # 导致身份折扣静默降级为原价（生产中真实出现过该脏值）。
    return {"id": u["id"], "email": u["email"], "name": u.get("name") or "",
            "phone": u.get("phone") or "", "is_admin": bool(u.get("is_admin")),
            "created_at": u.get("created_at", ""),
            "user_type": u.get("user_type") or DEFAULT_TIER,
            "organization": u.get("organization") or ""}


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
    with _locked() as data:
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
        if isinstance(config.get("bank"), dict):
            bank = config["bank"]
            cur = data["config"].setdefault("bank", _default_bank())
            for k in ("name", "branch", "account", "tel", "contact"):
                if k in bank:
                    cur[k] = str(bank.get(k) or "").strip()[:200]
        if "auto_confirm" in config:
            data["config"]["auto_confirm"] = bool(config["auto_confirm"])
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


_SHELF_PRICES_CACHE: dict | None = None


def _shelf_prices() -> dict:
    """代码内建三档定价表（懒加载 + 缓存）。

    分档依据见 `lda_webui/shelf_pricing.py`：开源可替代性（gdsfactory 现成
    标准件映射）× 技术复杂度（基元数/系统级）× 客户价值（市场规模）。
    """
    global _SHELF_PRICES_CACHE
    if _SHELF_PRICES_CACHE is None:
        try:
            from .shelf_pricing import build_price_map
            _SHELF_PRICES_CACHE = build_price_map()
        except Exception:
            _SHELF_PRICES_CACHE = {}
    return _SHELF_PRICES_CACHE


def base_price(shelf_id: str, data: dict | None = None) -> float:
    """基准单价（未打折）。优先级：

      ① 管理员配置 `config.prices[shelf_id]`（运营覆盖，最高优先）
      ② 代码内建三档定价表 `shelf_pricing.build_price_map()`（¥599/1999/4999）
      ③ `DEFAULT_PRICE_CNY` 兜底（新增货架尚未归档时）

    ② 让定价开箱即用且开源可见（透明定价），① 保留运营调价空间。
    """
    d = data if data is not None else _load()
    cfg = d["config"].get("prices", {}) or {}
    if shelf_id in cfg:
        try:
            return float(cfg[shelf_id])
        except (TypeError, ValueError):
            pass
    return float(_shelf_prices().get(shelf_id, DEFAULT_PRICE_CNY))


def price_of(shelf_id: str, user_type: str | None = None) -> float:
    """货架实付价：基准单价 × 身份折扣（config.tiers 可覆盖折扣系数）。"""
    data = _load()
    return round(base_price(shelf_id, data) * tier_discount(user_type), 2)


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
        # 需求方向（可选，白名单校验，用于管理后台精准对接）
        direction = str(p.get("direction") or "").strip()[:30]
        if direction and direction not in CUSTOM_DIRECTIONS:
            return {"ok": False, "error": "需求方向不合法"}
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
        "direction": direction if otype == "custom" else "",
        "proof": "",
        "license_code": None,
        "deliverable_url": "",
        "deliverables": [],
        "dev_note": "",
        "eta_date": "",
        "quote_cny": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paid_at": None, "approved_at": None, "accepted_at": None, "note": "",
        "reject_reason": "",
    }
    data = _load()
    with _locked() as wdata:
        wdata["orders"].insert(0, order)
    return {"ok": True, "order": _public_order(order)}


def submit_proof(order_id: str, user_token: str, proof: str) -> dict:
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    with _locked() as data:
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
    return {"ok": True, "order": _public_order(order)}


def admin_approve(order_id: str, token: str, deliverable_url: str = "") -> dict:
    """货架订单：收款确认+自动发货。定制订单：保留向后兼容的「接单+交付一步」入口（建议用 custom_accept/custom_deliver 分步）。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None:
            return {"ok": False, "error": "订单不存在"}
        if order["status"] in ("approved", "delivered", "accepted", "rejected"):
            return {"ok": False, "error": "订单已处理", "license_code": order.get("license_code")}
        if order["type"] == "custom":
            # 一步到位：created → delivered（兼容旧脚本）。新流程请走 custom_accept + custom_deliver。
            order["status"] = "delivered"
            order["approved_at"] = datetime.now(timezone.utc).isoformat()
            if deliverable_url:
                order["deliverables"] = order.get("deliverables") or []
                order["deliverables"].append({"name": "交付文件", "url": str(deliverable_url).strip()[:500]})
                order["deliverable_url"] = str(deliverable_url).strip()[:500]
        else:
            _deliver(order, data, deliverable_url)
    return {"ok": True, "order": _public_order(order, for_admin=True)}


def admin_reject(order_id: str, token: str, reason: str = "") -> dict:
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None:
            return {"ok": False, "error": "订单不存在"}
        order["status"] = "rejected"
        order["reject_reason"] = (reason or "").strip()[:200]
    return {"ok": True, "order": _public_order(order, for_admin=True)}


# --------------------------------------------------------------------------
# 定制需求全流程：created → developing → delivered → accepted
# --------------------------------------------------------------------------
def _is_custom(o: dict) -> bool:
    return o.get("type") == "custom"


def custom_accept(order_id: str, token: str, dev_note: str = "",
                  quote_cny=None, eta_date: str = "") -> dict:
    """定制需求接单：created → developing。可填报价、排期、内部备注。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None or not _is_custom(order):
            return {"ok": False, "error": "订单不存在或非定制需求"}
        if order["status"] != "created":
            return {"ok": False, "error": "仅待接单状态可接单（当前状态：" + str(order["status"]) + "）"}
        order["status"] = "developing"
        order["approved_at"] = datetime.now(timezone.utc).isoformat()
        if dev_note:
            order["dev_note"] = str(dev_note).strip()[:2000]
        if quote_cny is not None and str(quote_cny).strip() != "":
            try:
                order["quote_cny"] = round(float(quote_cny), 2)
            except (TypeError, ValueError):
                pass
        if eta_date:
            order["eta_date"] = str(eta_date).strip()[:40]
    return {"ok": True, "order": _public_order(order, for_admin=True)}


def custom_update_note(order_id: str, token: str, dev_note: str = "") -> dict:
    """更新内部备注（任意状态可调）。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None or not _is_custom(order):
            return {"ok": False, "error": "订单不存在或非定制需求"}
        order["dev_note"] = str(dev_note or "").strip()[:2000]
    return {"ok": True, "order": _public_order(order, for_admin=True)}


def custom_add_deliverable(order_id: str, token: str, name: str, url: str) -> dict:
    """添加交付物（任意非终态可调）。支持多次添加多文件。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    name = (name or "").strip()[:120]
    url = (url or "").strip()[:500]
    if not url:
        return {"ok": False, "error": "URL 不能为空"}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None or not _is_custom(order):
            return {"ok": False, "error": "订单不存在或非定制需求"}
        if order["status"] in ("rejected", "accepted"):
            return {"ok": False, "error": "订单已结束，不能再添加交付物"}
        order.setdefault("deliverables", []).append({"name": name or "交付文件", "url": url})
        # 保持旧字段同步指向最后一项（向后兼容）
        order["deliverable_url"] = url
    return {"ok": True, "order": _public_order(order, for_admin=True)}


def custom_deliver(order_id: str, token: str) -> dict:
    """标记已交付：developing → delivered。需要至少已有一个交付物。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None or not _is_custom(order):
            return {"ok": False, "error": "订单不存在或非定制需求"}
        if order["status"] != "developing":
            return {"ok": False, "error": "仅开发中状态可标记已交付（当前：" + str(order["status"]) + "）"}
        if not order.get("deliverables") and not order.get("deliverable_url"):
            return {"ok": False, "error": "请先添加至少一个交付物（文件链接）"}
        order["status"] = "delivered"
        if not order.get("approved_at"):
            order["approved_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": True, "order": _public_order(order, for_admin=True)}


def custom_accept_delivery(order_id: str, user_token: str) -> dict:
    """客户确认验收：delivered → accepted。"""
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    with _locked() as data:
        order = _find_order(data, order_id)
        if order is None or not _is_custom(order):
            return {"ok": False, "error": "订单不存在或非定制需求"}
        if order["user_id"] != u["id"]:
            return {"ok": False, "error": "无权操作该订单"}
        if order["status"] != "delivered":
            return {"ok": False, "error": "仅已交付状态可确认验收（当前：" + str(order["status"]) + "）"}
        order["status"] = "accepted"
        order["accepted_at"] = datetime.now(timezone.utc).isoformat()
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


def _public_order(o: dict, *, for_admin: bool = False) -> dict:
    out = {
        "id": o["id"], "user_id": o["user_id"], "type": o["type"],
        "shelf_id": o["shelf_id"], "title": o.get("title", ""),
        "amount_cny": o["amount_cny"], "tier": o.get("tier", "standard"),
        "pay_method": o["pay_method"],
        "status": o["status"], "customer": o["customer"],
        "requirement": o.get("requirement", ""), "target_spec": o.get("target_spec", ""),
        "budget": o.get("budget", ""), "direction": o.get("direction", ""),
        "proof": o.get("proof", ""),
        "license_code": o.get("license_code"), "deliverable_url": o.get("deliverable_url", ""),
        "deliverables": o.get("deliverables", []),
        "created_at": o["created_at"], "paid_at": o.get("paid_at"),
        "approved_at": o.get("approved_at"),
        "accepted_at": o.get("accepted_at"),
        "dev_note": o.get("dev_note", ""),
        "eta_date": o.get("eta_date", ""),
        "quote_cny": o.get("quote_cny", 0),
        "reject_reason": o.get("reject_reason", ""),
    }
    if not for_admin:
        out.pop("proof", None)  # 客户视图不泄露管理员录入的支付凭证
    return out


def list_orders(token: str, scope: str = "mine") -> dict:
    data = _load()
    u = user_by_token(token)
    for_admin = False
    if scope == "all":
        if not is_admin(token):
            return {"ok": False, "error":  "unauthorized", "code": 401}
        rows = [o for o in data["orders"]]
        for_admin = True
    else:
        if u is None:
            return {"ok": False, "error": "请先登录", "code": 401}
        rows = [o for o in data["orders"] if o["user_id"] == u["id"]]
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"ok": True, "orders": [_public_order(o, for_admin=for_admin) for o in rows],
            "count": len(rows)}


# ---------------------------------------------------------------------------
# 「我的」模块（用户自助）：资料维护 / 改密 / 许可证资产 / 消费概览
#
# 注：本层是「单租户 · 多用户 · 扁平池」——所有用户共享 store.json，无 tenant_id
# 隔离键；user_type 是「定价折扣维度」不是「租户归属」。若未来升级真多租户，
# 在此处按 organization 引入 tenant_id 即为天然 seam，无需推翻现有结构。
# ---------------------------------------------------------------------------

def update_profile(user_token: str, *, name: str | None = None,
                   phone: str | None = None, organization: str | None = None,
                   user_type: str | None = None) -> dict:
    """用户自助改资料。身份（user_type）可改，但机构席位必须填机构名。"""
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    if user_type is not None and user_type not in USER_TYPES:
        return {"ok": False, "error": "身份取值非法"}
    with _locked() as data:
        cur = data["users"].get(u["id"])
        if cur is None:
            return {"ok": False, "error": "账号不存在", "code": 401}
        if name is not None:
            cur["name"] = str(name).strip()[:40]
        if phone is not None:
            cur["phone"] = str(phone).strip()[:40]
        if organization is not None:
            cur["organization"] = str(organization).strip()[:120]
        if user_type is not None:
            if user_type == "institution" and not (cur.get("organization") or "").strip():
                return {"ok": False, "error": "机构席位需先填写机构/单位名称"}
            cur["user_type"] = user_type
        cur["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": True, "user": _public_user(cur)}


def change_password(user_token: str, old_password: str, new_password: str) -> dict:
    """改密：校验旧密码 → 换新 salt/hash → 轮换会话令牌（旧令牌立即失效）。"""
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    new_password = new_password or ""
    if len(new_password) < MIN_PASSWORD_LEN:
        return {"ok": False, "error": "新密码至少 %d 位" % MIN_PASSWORD_LEN}
    if len(new_password) > MAX_PASSWORD_LEN:
        return {"ok": False, "error": "新密码过长（上限 %d 字符）" % MAX_PASSWORD_LEN}
    with _locked() as data:
        cur = data["users"].get(u["id"])
        if cur is None:
            return {"ok": False, "error": "账号不存在", "code": 401}
        if not secrets.compare_digest(
                _hash_pwd(old_password or "", cur.get("salt", "")),
                str(cur.get("password_hash") or "")):
            return {"ok": False, "error": "原密码不正确"}
        cur["salt"] = secrets.token_hex(8)
        cur["password_hash"] = _hash_pwd(new_password, cur["salt"])
        # 令牌轮换：改密后其它设备上的旧会话立即失效
        token = secrets.token_urlsafe(24)
        cur["token"] = token
        cur["token_created_at"] = datetime.now(timezone.utc).isoformat()
        # 管理员代重置后的「必须改密」标记在此解除
        cur["must_change_password"] = False
    return {"ok": True, "token": token, "user": _public_user(cur),
            "must_change_password": False}


# ---------------------------------------------------------------------------
# 管理员代重置密码（找回密码兜底通路：未接 SMTP，无法邮件自助找回）
# ---------------------------------------------------------------------------
def _clear_login_locks(email: str = "", all_accounts: bool = False) -> None:
    """清除登录失败锁定。管理员重置密码/应急解锁时调用。

    - email 非空：清除该账号维度计数；
    - IP 维度无法归属到具体账号，管理员人工介入时一并清空（低频已鉴权操作，
      换取「用户被锁死管理员能解开」这一实际可用性）。
    - all_accounts=True：连全部账号维度一起清空（应急开关）。
    """
    with _LOGIN_GUARD_LOCK:
        if email:
            _LOGIN_GUARD.pop("acct:" + (email or "").strip().lower(), None)
        for k in list(_LOGIN_GUARD.keys()):
            if k.startswith("ip:") or (all_accounts and k.startswith("acct:")):
                _LOGIN_GUARD.pop(k, None)


def _gen_temp_password() -> str:
    """生成易口头传达的临时密码：12 位，去除易混字符 0/O/1/l/I。"""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def admin_list_users(token: str) -> dict:
    """管理员查看用户列表（脱敏：不含密码/令牌/哈希）。"""
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    data = _load()
    rows = []
    for u in data["users"].values():
        rows.append({
            "id": u["id"], "email": u.get("email", ""), "name": u.get("name") or "",
            "phone": u.get("phone") or "",
            "user_type": u.get("user_type") or DEFAULT_TIER,
            "organization": u.get("organization") or "",
            "is_admin": bool(u.get("is_admin")),
            "created_at": u.get("created_at", ""),
            "last_login_at": u.get("last_login_at", ""),
            "must_change_password": bool(u.get("must_change_password")),
        })
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"ok": True, "users": rows, "count": len(rows)}


def admin_reset_password(identifier: str, token: str,
                         temp_password: str = "") -> dict:
    """管理员重置某用户密码（找回密码兜底）。

    - identifier 可为邮箱或 user_id；
    - 未指定 temp_password 时自动生成 12 位临时密码；
    - 重置后：旧会话立即失效（令牌轮换为不可预测值），并置 must_change_password，
      用户下次登录成功后需先改密码——避免临时密码长期有效。
    """
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    ident = (identifier or "").strip()
    if not ident:
        return {"ok": False, "error": "请填写邮箱或用户 ID"}
    pwd = (temp_password or "").strip() or _gen_temp_password()
    if len(pwd) < MIN_PASSWORD_LEN or len(pwd) > MAX_PASSWORD_LEN:
        return {"ok": False,
                "error": "临时密码长度需在 %d–%d 之间" % (MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)}

    with _locked() as data:
        target = None
        low = ident.lower()
        for u in data["users"].values():
            if u.get("id") == ident or (u.get("email") or "").lower() == low:
                target = u
                break
        if target is None:
            return {"ok": False, "error": "未找到该用户（邮箱或 ID 不存在）"}
        target["salt"] = secrets.token_hex(8)
        target["password_hash"] = _hash_pwd(pwd, target["salt"])
        # 旧会话立即失效：换成随机值（不返回给任何人）
        target["token"] = secrets.token_urlsafe(24)
        target["token_created_at"] = None
        target["must_change_password"] = True
        target["password_reset_at"] = datetime.now(timezone.utc).isoformat()
        # 清除该账号的登录锁定（含 IP 维度）：避免用户因旧的错误尝试被锁着进不来
        _clear_login_locks(target.get("email", ""))
    return {"ok": True, "email": target.get("email", ""), "user_id": target["id"],
            "temp_password": pwd, "must_change_password": True,
            "note": "请将临时密码通过原沟通渠道（微信/邮件）告知用户；"
                    "用户下次登录需先改密码。该账号的登录失败锁定已一并清除。"}


def admin_unlock_login(token: str) -> dict:
    """管理员应急解锁：清空全部登录失败计数（账号 + IP 维度）。

    用于处理「用户并未忘记密码，只是被失败锁定挡住」的场景，无需重置密码。
    """
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    with _LOGIN_GUARD_LOCK:
        n = len(_LOGIN_GUARD)
        _LOGIN_GUARD.clear()
    return {"ok": True, "cleared": n,
            "note": "已清除 %d 条登录失败锁定记录（账号 + IP 维度）。" % n}


def my_licenses(user_token: str) -> dict:
    """我的许可证资产：已购货架包 + 剩余下载次数（只读，不消耗）。"""
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    data = _load()
    rows = [o for o in data["orders"]
            if o["user_id"] == u["id"] and o.get("license_code")]
    try:
        from lda_l2.ship_package import license_status
    except Exception:  # noqa: BLE001
        license_status = None

    items = []
    for o in rows:
        code = o["license_code"]
        st = license_status(code) if license_status else {}
        items.append({
            "order_id": o["id"],
            "shelf_id": o.get("shelf_id", ""),
            "title": o.get("title", ""),
            "license_code": code,
            "status": o.get("status", ""),
            "approved_at": o.get("approved_at", ""),
            "used": st.get("used", 0) if st.get("ok") else 0,
            "max_uses": st.get("max_uses", 1) if st.get("ok") else 1,
            "remaining": st.get("remaining", 0) if st.get("ok") else 0,
            "revoked": bool(st.get("revoked")) if st.get("ok") else False,
            "downloadable": bool(st.get("ok")) and st.get("remaining", 0) > 0,
        })
    items.sort(key=lambda x: x.get("approved_at", ""), reverse=True)
    return {"ok": True, "licenses": items, "count": len(items)}


def my_summary(user_token: str) -> dict:
    """我的概览：身份/折扣 + 订单计数 + 累计消费 + 许可证资产 + 定制进度。"""
    u = user_by_token(user_token)
    if u is None:
        return {"ok": False, "error": "请先登录", "code": 401}
    data = _load()
    uid = u["id"]
    orders = [o for o in data["orders"] if o["user_id"] == uid]
    paid_statuses = ("paid_unverified", "approved", "delivered", "accepted")
    paid = [o for o in orders if o.get("status") in paid_statuses]
    spent = round(sum(float(o.get("amount_cny", 0) or 0) for o in paid), 2)
    lic = my_licenses(user_token)
    licenses = lic.get("licenses", [])
    custom = [o for o in orders if o.get("type") == "custom"]
    return {
        "ok": True,
        "user": _public_user(u),
        "tier_label": USER_TYPE_LABELS.get(u.get("user_type", DEFAULT_TIER), "标准个人"),
        "discount": tier_discount(u.get("user_type")),
        "orders_total": len(orders),
        "orders_paid": len(paid),
        "spent_cny": spent,
        "licenses_total": len(licenses),
        "downloads_left": sum(int(x.get("remaining", 0)) for x in licenses),
        "custom_total": len(custom),
        "custom_active": sum(1 for o in custom
                             if o.get("status") in ("created", "developing", "delivered")),
        # 管理员代重置后的临时密码标记：前端据此强制引导改密
        "must_change_password": bool(u.get("must_change_password")),
    }


def _is_test_email(email: str) -> bool:
    """判别测试/冒烟账号（stats 聚合用）：smoke-*.@lda.local 或已知测试域名。

    仅作信号分类启发式，不用于任何权限/计费判定。
    """
    e = (email or "").lower()
    if not e:
        return True
    if re.match(r"^smoke-.*@lda\.local$", e):
        return True
    dom = e.rsplit("@", 1)[-1]
    return dom in _TEST_DOMAINS


def stats_summary(token: str) -> dict:
    """管理后台数据看板聚合（admin 专属）。

    设计取向：把「真实信号」与「测试残留」分开计数——当前诚实边界是
    「0 真实成交、不猜方向」，此端点让真实注册/订单到来时**立即可见**，
    而不是混在 smoke 测试账号里被淹没。不依赖任何外部资源。
    """
    if not is_admin(token):
        return {"ok": False, "error": "unauthorized", "code": 401}
    data = _load()
    users = list(data["users"].values())
    total = len(users)
    real = sum(1 for u in users if not _is_test_email(u.get("email", "")))
    test = total - real
    by_type = {t: 0 for t in USER_TYPES}
    for u in users:
        k = u.get("user_type") or DEFAULT_TIER
        by_type[k] = by_type.get(k, 0) + 1
    orders = data["orders"]
    ototal = len(orders)
    by_status: dict = {}
    for o in orders:
        s = o.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1
    by_type_o: dict = {}
    for o in orders:
        t = o.get("type", "?")
        by_type_o[t] = by_type_o.get(t, 0) + 1
    _paid = ("paid_unverified", "approved", "delivered", "accepted")
    gmv = round(sum(float(o.get("amount_cny", 0) or 0)
                    for o in orders if o.get("status") in _paid), 2)
    # 货架档位分布（轻量，纯常量模块，无重依赖）
    try:
        from .shelf_pricing import build_price_map
        _pm = build_price_map()
    except Exception:  # noqa: BLE001
        _pm = {}
    by_tier = {"basic": 0, "standard": 0, "premium": 0}
    for _price in _pm.values():
        if _price == 599.0:
            by_tier["basic"] += 1
        elif _price == 1999.0:
            by_tier["standard"] += 1
        elif _price == 4999.0:
            by_tier["premium"] += 1
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "users": {"total": total, "real": real, "test": test, "by_type": by_type},
        "orders": {"total": ototal, "by_status": by_status,
                   "by_type": by_type_o, "gmv_cny": gmv},
        "shelves": {"total": len(_pm), "by_tier": by_tier},
        "note": "real=排除 smoke-*.@lda.local 及测试域名；test 为已知冒烟/测试残留。"
    }


def public_config() -> dict:
    """给前台：微信收款码 + 对公账户 + 身份分层，不含管理员信息。"""
    data = _load()
    wc = data["config"]["wechat"]
    bank = data["config"].get("bank") or _default_bank()
    tiers = {}
    for t in USER_TYPES:
        tiers[t] = {"label": USER_TYPE_LABELS[t], "discount": tier_discount(t)}
    return {"payee": wc.get("payee", ""), "qr": wc.get("qr", ""),
            "amount_note": wc.get("amount_note", ""),
            "bank": bank,
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
        if order.get("status") not in ("delivered", "accepted", "approved"):
            return {"ok": False, "error": "订单尚未交付"}
        # 优先返回新结构的 deliverables 列表；旧数据回落到 deliverable_url
        if order.get("deliverables"):
            return {"ok": True, "deliverables": order["deliverables"],
                    "deliverable_url": order.get("deliverable_url", ""),
                    "license_code": order.get("license_code")}
        if order.get("deliverable_url"):
            return {"ok": True, "deliverable_url": order["deliverable_url"],
                    "license_code": order.get("license_code")}
        return {"ok": False, "error": "交付文件待上传，请联系管理员"}
    if order.get("status") != "approved" or not order.get("license_code"):
        return {"ok": False, "error": "订单尚未交付，无法下载"}
    from lda_l2.ship_package import generate_package, consume_license
    # 原子消耗：锁内验证+自增，通过才生成包（修复并发超额下载 TOCTOU）
    if not consume_license(order["license_code"]):
        return {"ok": False, "error": "下载次数已用完或授权失效，请联系管理员"}
    r = generate_package(order["shelf_id"])
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "生成失败")}
    return {"ok": True, "zip_path": r["zip_path"],
            "license_code": order["license_code"], "shelf_id": order["shelf_id"]}
