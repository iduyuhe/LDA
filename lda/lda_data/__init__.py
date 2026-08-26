#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA 多用户数据层（P2.2 · 开源基础设施）。

设计纪律：
- 净增、不绑架内核：本包为可选依赖层，内核（L0/L1/L3/harness）零依赖可独立跑。
- 主权可控：默认 SQLite 起步（零运维），通过 StorageBackend 抽象兼容
  Cloudflare D1（同源 SQLite 方言）与 Postgres（未来子类）。
- 凭证隔离：密码 / API Key / license 仅存哈希，绝不落明文（复用智衍纪律）。
- 租户隔离：所有读写强制按 org_id 作用域，跨组织不可见（见 service.DataLayer）。
"""
from .backend import (
    StorageBackend, SqliteFileBackend, MemoryBackend, get_backend,
)
from .models import User, Organization, Project, DesignResult, ApiKey
from .auth import hash_password, verify_password, gen_api_key, hash_api_key
from .service import DataLayer

__all__ = [
    "StorageBackend", "SqliteFileBackend", "MemoryBackend", "get_backend",
    "User", "Organization", "Project", "DesignResult", "ApiKey",
    "hash_password", "verify_password", "gen_api_key", "hash_api_key",
    "DataLayer",
]
