#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA v1 REST API（P2.3 · 开放部分）。

定位：把 P2.2 数据层经 HTTP 暴露为产品级接口，并叠加 API Key 认证与租户隔离。
- 认证：Authorization: Bearer sk-...（经 DataLayer.authenticate_api_key）。
- 租户隔离：所有组织作用域操作须携带 org_id 且调用方必须是成员，否则 403。
- 现有 57 面板端点（app.py 原 /api/*）保持开放单用户 demo 行为，不在此强制认证。
- license 校验见 lda_license（闭源签名逻辑在 lda-cloud，本仓库仅 seam）。

本模块被 app.py 的 _handle_v1 委托调用；返回 (http_code, dict)。
"""
from __future__ import annotations

import json
import re
import threading
from typing import Any, Optional, Tuple

from lda_data.backend import get_backend
from lda_data.service import DataLayer
from lda_license import check_license
from .plugins import register_plugin, list_plugins, PluginManifest

# 单例 DataLayer（进程内共享连接；backend 默认内存、或 LDA_DB_URL 文件型）
_DL: Optional[DataLayer] = None
_DL_LOCK = threading.Lock()


def get_data_layer() -> DataLayer:
    global _DL
    if _DL is None:
        with _DL_LOCK:
            if _DL is None:
                _DL = DataLayer(get_backend())
    return _DL


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------
def _bearer(headers: dict) -> Optional[str]:
    h = headers.get("Authorization", "")
    if h.startswith("Bearer "):
        return h[len("Bearer "):].strip()
    return None


def _auth_user(headers: dict) -> Optional[int]:
    key = _bearer(headers)
    if not key:
        return None
    return get_data_layer().authenticate_api_key(key)


def _member_or_403(dl: DataLayer, user_id: int, org_id) -> Tuple[int, Optional[dict]]:
    """校验 user 是 org 成员；返回 (code, error_or_None)。"""
    try:
        org_id = int(org_id)
    except (TypeError, ValueError):
        return 400, {"error": "org_id 非法"}
    if not dl.is_member(user_id, org_id):
        return 403, {"error": "非该组织成员（租户隔离）"}
    return 200, None


# ---------------------------------------------------------------------------
# 路由处理
# ---------------------------------------------------------------------------
def handle_v1(method: str, path: str, body: dict,
              headers: dict) -> Tuple[int, dict]:
    dl = get_data_layer()
    p = path[len("/api/v1"):]
    if p.startswith("/"):
        p = p[1:]

    # ---- 认证类（无需 Bearer）----
    if method == "POST" and p == "auth/register":
        return _register(dl, body)
    if method == "POST" and p == "auth/login":
        return _login(dl, body)
    # license 状态（开放 seam，公开可读）
    if method == "GET" and p == "license":
        lic = check_license()
        return 200, {"tier": lic.tier, "active": lic.active, "note": lic.note}

    # ---- 以下均需认证 ----
    uid = _auth_user(headers)
    if uid is None:
        return 401, {"error": "未认证：需 Authorization: Bearer <api_key>"}

    if method == "GET" and p == "me":
        u = dl.get_user_by_email(_email_of(dl, uid)) or None
        return 200, {"user_id": uid, "orgs": [o.id for o in dl.user_orgs(uid)]}

    if method == "GET" and p == "usage":
        org_id = body.get("org_id") or _q(headers, "org_id")
        code, err = _member_or_403(dl, uid, org_id)
        if err:
            return code, err
        return 200, dl.get_usage(int(org_id))

    if method == "GET" and p == "projects":
        org_id = body.get("org_id") or _q(headers, "org_id")
        code, err = _member_or_403(dl, uid, org_id)
        if err:
            return code, err
        rows = dl.conn.execute(
            "SELECT id, name, meta FROM projects WHERE org_id=? ORDER BY id DESC",
            (int(org_id),)).fetchall()
        return 200, {"projects": [
            {"id": r["id"], "name": r["name"],
             "meta": json.loads(r["meta"]) if r["meta"] else None}
            for r in rows]}

    if method == "POST" and p == "projects":
        org_id = body.get("org_id")
        code, err = _member_or_403(dl, uid, org_id)
        if err:
            return code, err
        name = (body.get("name") or "").strip()
        if not name:
            return 400, {"error": "name 必填"}
        pid = dl.create_project(int(org_id), name, body.get("meta"))
        return 200, {"project_id": pid, "org_id": int(org_id), "name": name}

    # /api/v1/projects/{id}/designs
    m = re.match(r"^projects/(\d+)/designs$", p)
    if m:
        proj_id = int(m.group(1))
        org_id = body.get("org_id") or _q(headers, "org_id")
        code, err = _member_or_403(dl, uid, org_id)
        if err:
            return code, err
        if method == "GET":
            rows = dl.list_design_results(int(org_id), project_id=proj_id)
            return 200, {"designs": [
                {"id": d.id, "device_type": d.device_type,
                 "params": d.params, "created_at": d.created_at}
                for d in rows]}
        if method == "POST":
            did = dl.save_design_result(
                int(org_id), proj_id, device_type=body.get("device_type"),
                params=body.get("params"),
                dual_verify_report=body.get("dual_verify_report"),
                layout_json=body.get("layout_json"))
            return 200, {"design_id": did}

    # ---- 插件（开放扩展缝）----
    if method == "GET" and p == "plugins":
        return 200, {"plugins": list_plugins()}
    if method == "POST" and p == "plugins":
        man = PluginManifest.from_dict(body.get("manifest", body))
        return 200, register_plugin(man)

    return 404, {"error": "not found"}


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _email_of(dl: DataLayer, uid: int) -> str:
    row = dl.conn.execute(
        "SELECT email FROM users WHERE id=?", (uid,)).fetchone()
    return row["email"] if row else ""


def _q(headers: dict, key: str) -> Optional[str]:
    # 简化：从 X-LDA-Org 头读取 org_id（GET 无 body 时）
    if key == "org_id":
        return headers.get("X-LDA-Org")
    return None


def _register(dl: DataLayer, body: dict) -> Tuple[int, dict]:
    email = (body.get("email") or "").strip()
    pw = body.get("password") or ""
    if not email or not pw:
        return 400, {"error": "email / password 必填"}
    if len(pw) < 8:
        return 400, {"error": "密码至少 8 位"}
    if dl.get_user_by_email(email):
        return 409, {"error": "邮箱已注册"}
    uid = dl.register_user(email, pw)
    # 个人组织（默认 workspace）
    org_id = dl.create_org("personal:" + email)
    dl.add_member(uid, org_id, role="owner")
    plain, _ = dl.create_api_key(uid, scopes=["design:read", "design:write"])
    return 200, {
        "user_id": uid, "org_id": org_id, "api_key": plain,
        "tier": check_license().tier,
    }


def _login(dl: DataLayer, body: dict) -> Tuple[int, dict]:
    email = (body.get("email") or "").strip()
    pw = body.get("password") or ""
    u = dl.verify_user(email, pw)
    if u is None:
        return 401, {"error": "邮箱或密码错误"}
    plain, _ = dl.create_api_key(u.id, scopes=["design:read", "design:write"])
    return 200, {"api_key": plain, "orgs": [o.id for o in dl.user_orgs(u.id)]}
