#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""凭证处理（P2.2）：密码哈希 + API Key 生成/校验。

纪律：密码与 API Key 仅存哈希，绝不落明文。
- 优先 bcrypt（若环境装了）；否则退回标准库 pbkdf2_hmac（零额外依赖）。
- API Key：形如 sk-<64hex>，存储其 sha256 哈希；校验时对待校验串重算哈希比对。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets


def _have_bcrypt() -> bool:
    try:
        import bcrypt  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


# ---- 密码哈希 ----
def hash_password(password: str) -> str:
    """返回可存储的哈希串。bcrypt: '$2b$...'；否则 'pbkdf2_sha256$iter$salt$hash'。"""
    if _have_bcrypt():
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"),
                             bcrypt.gensalt()).decode("utf-8")
    salt = secrets.token_bytes(16)
    iter_ = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iter_)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iter_, salt.hex(), dk.hex())


def verify_password(password: str, pw_hash: str) -> bool:
    if pw_hash.startswith("$2b$") or pw_hash.startswith("$2a$"):
        import bcrypt
        try:
            return bcrypt.checkpw(password.encode("utf-8"),
                                  pw_hash.encode("utf-8"))
        except Exception:  # noqa: BLE001
            return False
    if pw_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iter_s, salt_s, hash_s = pw_hash.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_s), int(iter_s))
            return hmac.compare_digest(dk.hex(), hash_s)
        except Exception:  # noqa: BLE001
            return False
    return False


# ---- API Key ----
def gen_api_key() -> str:
    """生成形如 sk-<64hex> 的 API Key（仅此一次明文，调用方负责返回给用户）。"""
    return "sk-" + secrets.token_hex(32)


def hash_api_key(key: str) -> str:
    """API Key 的存储哈希（sha256）。校验用 constant-time 比对。"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_api_key(presented: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(presented), stored_hash)
