#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据层业务服务（P2.2）：用户/组织/项目/设计结果 + 租户隔离。

租户隔离铁律：所有跨组织数据访问方法都强制传入 org_id 作用域；
不存在「列出全部组织设计」之类越权接口。org_id 必须由已认证用户的
成员关系推导（见 is_member），绝不由客户端自由指定。

凭证纪律：密码/API Key 仅经 auth 模块存哈希；本层不接触明文密码落库。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from .auth import hash_password, verify_password, gen_api_key, hash_api_key, verify_api_key
from .backend import StorageBackend
from .models import User, Organization, Project, DesignResult, ApiKey


def _jdump(obj: Any) -> Optional[str]:
    return None if obj is None else json.dumps(obj, ensure_ascii=False)


def _jload(s: Optional[str]) -> Any:
    return None if not s else json.loads(s)


class DataLayer:
    def __init__(self, backend: StorageBackend):
        self.backend = backend
        self.conn: sqlite3.Connection = backend.connect()

    # ---- 用户 ----
    def register_user(self, email: str, password: str) -> int:
        email = email.strip().lower()
        pw_hash = hash_password(password)
        cur = self.conn.execute(
            "INSERT INTO users(email, pw_hash) VALUES(?, ?)", (email, pw_hash))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_user_by_email(self, email: str) -> Optional[User]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        ).fetchone()
        return User(**dict(row)) if row else None

    def verify_user(self, email: str, password: str) -> Optional[User]:
        u = self.get_user_by_email(email)
        if u and verify_password(password, u.pw_hash):
            return u
        return None

    # ---- 组织 ----
    def create_org(self, name: str, plan: str = "oss") -> int:
        cur = self.conn.execute(
            "INSERT INTO organizations(name, plan) VALUES(?, ?)", (name, plan))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_org(self, org_id: int) -> Optional[Organization]:
        row = self.conn.execute(
            "SELECT * FROM organizations WHERE id=?", (org_id,)).fetchone()
        return Organization(**dict(row)) if row else None

    def add_member(self, user_id: int, org_id: int, role: str = "member") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO memberships(user_id, org_id, role) "
            "VALUES(?, ?, ?)", (user_id, org_id, role))
        self.conn.commit()

    def is_member(self, user_id: int, org_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM memberships WHERE user_id=? AND org_id=?",
            (user_id, org_id)).fetchone()
        return row is not None

    def user_orgs(self, user_id: int) -> list[Organization]:
        rows = self.conn.execute(
            "SELECT o.* FROM organizations o "
            "JOIN memberships m ON m.org_id=o.id WHERE m.user_id=?",
            (user_id,)).fetchall()
        return [Organization(**dict(r)) for r in rows]

    # ---- 项目 ----
    def create_project(self, org_id: int, name: str, meta: Optional[dict] = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO projects(org_id, name, meta) VALUES(?, ?, ?)",
            (org_id, name, _jdump(meta)))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_project(self, org_id: int, project_id: int) -> Optional[Project]:
        # 强制 org 作用域：即便传入他人 project_id 也查不到
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id=? AND org_id=?",
            (project_id, org_id)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["meta"] = _jload(d["meta"])
        return Project(**d)

    # ---- 设计结果（租户隔离核心）----
    def save_design_result(self, org_id: int, project_id: int,
                           device_type: Optional[str] = None,
                           params: Optional[dict] = None,
                           dual_verify_report: Optional[dict] = None,
                           layout_json: Optional[dict] = None) -> int:
        # 先校验 project 确实属于该 org（防越权写入）
        proj = self.get_project(org_id, project_id)
        if proj is None:
            raise ValueError("project 不属于该 org 或不存在")
        cur = self.conn.execute(
            "INSERT INTO design_results("
            "project_id, org_id, device_type, params, dual_verify_report, layout_json) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (project_id, org_id, device_type, _jdump(params),
             _jdump(dual_verify_report), _jdump(layout_json)))
        self.conn.commit()
        return int(cur.lastrowid)

    def list_design_results(self, org_id: int,
                            project_id: Optional[int] = None) -> list[DesignResult]:
        if project_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM design_results WHERE org_id=? AND project_id=? "
                "ORDER BY id DESC", (org_id, project_id)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM design_results WHERE org_id=? ORDER BY id DESC",
                (org_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["params"] = _jload(d["params"])
            d["dual_verify_report"] = _jload(d["dual_verify_report"])
            d["layout_json"] = _jload(d["layout_json"])
            out.append(DesignResult(**d))
        return out

    def count_designs(self, org_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM design_results WHERE org_id=?",
            (org_id,)).fetchone()
        return int(row["c"])

    # ---- API Key ----
    def create_api_key(self, user_id: int, scopes: Optional[list[str]] = None
                       ) -> tuple[str, int]:
        """返回 (明文 key, key_id)。明文仅此一次，调用方负责返回给用户。"""
        plain = gen_api_key()
        cur = self.conn.execute(
            "INSERT INTO api_keys(user_id, key_hash, scopes) VALUES(?, ?, ?)",
            (user_id, hash_api_key(plain),
             ",".join(scopes or [])))
        self.conn.commit()
        return plain, int(cur.lastrowid)

    def authenticate_api_key(self, presented: str) -> Optional[int]:
        row = self.conn.execute(
            "SELECT user_id FROM api_keys WHERE key_hash=?",
            (hash_api_key(presented),)).fetchone()
        if row is None:
            return None
        # 可选：此处可校验 key 是否被吊销（未来）
        return int(row["user_id"])

    def list_api_keys(self, user_id: int) -> list[ApiKey]:
        rows = self.conn.execute(
            "SELECT * FROM api_keys WHERE user_id=?", (user_id,)).fetchall()
        return [ApiKey.from_row(dict(r)) for r in rows]

    # ---- 运行日志 / 用量计量（P2.3 配额复用）----
    def record_run(self, org_id: int, project_id: Optional[int],
                   solver: str, duration_s: float, status: str) -> None:
        self.conn.execute(
            "INSERT INTO run_logs(project_id, org_id, solver, duration_s, status) "
            "VALUES(?, ?, ?, ?, ?)",
            (project_id, org_id, solver, duration_s, status))
        self.conn.commit()

    def get_usage(self, org_id: int) -> dict:
        designs = self.count_designs(org_id)
        runs = self.conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(duration_s),0) AS t "
            "FROM run_logs WHERE org_id=?", (org_id,)).fetchone()
        return {
            "org_id": org_id,
            "designs": designs,
            "runs": int(runs["c"]),
            "run_seconds": float(runs["t"]),
        }

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass
