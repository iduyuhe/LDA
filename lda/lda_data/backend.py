#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""存储后端抽象（P2.2）。

StorageBackend 只负责「提供连接 + 建表 + 占位符方言」，业务 SQL 集中在
service.DataLayer。这样：
- SQLite 起步（SqliteFileBackend / MemoryBackend，均用标准库 sqlite3）；
- Cloudflare D1 同源 SQLite 方言，未来 D1Backend 仅需替换 connect()；
- Postgres 未来子类覆盖 placeholder()→'%s' 与 schema_sql()（SERIAL/now()）。

兼容性边界（诚实）：当前仅实装 SQLite/D1 方言；Postgres 路径在子类未实现时
显式抛 NotImplementedError，不假装支持。
"""
from __future__ import annotations

import os
import re
import sqlite3
from abc import ABC, abstractmethod


# ---- 表结构（SQLite / D1 方言）----
_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  email     TEXT UNIQUE NOT NULL,
  pw_hash   TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS organizations (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  name      TEXT UNIQUE NOT NULL,
  plan      TEXT NOT NULL DEFAULT 'oss',
  license_key_hash TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS memberships (
  user_id INTEGER NOT NULL,
  org_id  INTEGER NOT NULL,
  role    TEXT NOT NULL DEFAULT 'member',
  PRIMARY KEY (user_id, org_id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (org_id) REFERENCES organizations(id)
);
CREATE TABLE IF NOT EXISTS projects (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id    INTEGER NOT NULL,
  name      TEXT NOT NULL,
  meta      TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (org_id) REFERENCES organizations(id)
);
CREATE TABLE IF NOT EXISTS design_results (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  org_id    INTEGER NOT NULL,
  device_type TEXT,
  params    TEXT,
  dual_verify_report TEXT,
  layout_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (org_id) REFERENCES organizations(id)
);
CREATE TABLE IF NOT EXISTS run_logs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER,
  org_id    INTEGER,
  solver    TEXT,
  duration_s REAL,
  status    TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS api_keys (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id   INTEGER NOT NULL,
  key_hash  TEXT UNIQUE NOT NULL,
  scopes    TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS licenses (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id    INTEGER NOT NULL,
  tier      TEXT NOT NULL,
  seats     INTEGER,
  expires   TEXT,
  signature TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (org_id) REFERENCES organizations(id)
);
"""


class StorageBackend(ABC):
    @abstractmethod
    def connect(self):
        """返回一个 DB-API 连接（sqlite3 连接或被适配的 D1/PG 连接）。"""
        raise NotImplementedError

    def placeholder(self) -> str:
        """参数占位符方言。SQLite/D1 用 '?'；Postgres 子类覆盖为 '%s'。"""
        return "?"

    def schema_sql(self) -> str:
        """建表 DDL。SQLite/D1 方言；Postgres 子类覆盖。"""
        return _SCHEMA_SQLITE

    def init_db(self, conn) -> None:
        """在给定连接上执行建表（幂等 IF NOT EXISTS）。"""
        conn.executescript(self.schema_sql())
        conn.commit()


class _SqliteBase(StorageBackend):
    def _configure(self, conn):
        # WAL + 外键：单机/小团队读写更稳
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:  # noqa: BLE001
            pass
        self.init_db(conn)

    def init_db(self, conn) -> None:
        conn.executescript(self.schema_sql())
        conn.commit()

    def _connect(self, db_path: str):
        # 多线程 Web 服务（ThreadingHTTPServer）共享连接，需关闭线程检查 + 加锁超时
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        self._configure(conn)
        return conn


class SqliteFileBackend(_SqliteBase):
    """文件型 SQLite（自托管持久化）。url 形如 sqlite:////data/lda.db。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # 确保父目录存在
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def connect(self):
        return self._connect(self.db_path)


class MemoryBackend(_SqliteBase):
    """内存 SQLite（零持久化，单进程演示 / 测试用）。保留原内网 demo 行为。"""

    def connect(self):
        return self._connect(":memory:")


def get_backend(url: str | None = None) -> StorageBackend:
    """按 LDA_DB_URL 解析后端；未配置则默认内存后端（不破坏现有零依赖 demo）。

    - 未设置 / 'memory' / 'sqlite://:memory:' → MemoryBackend
    - 'sqlite:////abs/path.db' 或 'sqlite:///relative.db' → SqliteFileBackend
    - 其它（postgresql://...）→ 显式 NotImplementedError（未来子类支持）
    """
    if url is None:
        url = os.environ.get("LDA_DB_URL", "")
    url = (url or "").strip()
    if url == "" or url == "memory" or url.startswith("sqlite://:memory:"):
        return MemoryBackend()
    if url.startswith("sqlite:///"):
        # sqlite:////abs  → 去掉 9 字符前缀得 /abs/path.db
        # sqlite:///rel  → 去掉 9 字符前缀得 rel/path.db
        path = url[len("sqlite:///"):]
        if not path:
            return MemoryBackend()
        if not path.startswith("/") and re.match(r"^[a-zA-Z]:", path) is None:
            # 相对路径：相对 LDA_HOME 或当前工作目录
            home = os.environ.get("LDA_HOME", ".")
            path = os.path.join(home, path)
        return SqliteFileBackend(path)
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        raise NotImplementedError(
            "Postgres 后端尚未实装；当前仅支持 SQLite/D1 方言。"
            "请用 LDA_DB_URL=sqlite:////path/to/lda.db。"
        )
    raise ValueError(f"不支持的 LDA_DB_URL: {url!r}")
