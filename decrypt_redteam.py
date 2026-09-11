#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地还原 redteam 待处理缺陷原始数据（仅本机使用，不依赖网络）。

密文与密钥均位于 .secrets/（已被 .gitignore 排除，绝不进版本库）。
用法：
    python decrypt_redteam.py
还原后输出到 lda/redteam_anchor_fuzz_defects_pending.json 原有位置。
"""
import os
from cryptography.fernet import Fernet

BASE = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE, ".secrets", "redteam_fernet.key")
ENC_PATH = os.path.join(BASE, ".secrets", "redteam_anchor_fuzz_defects_pending.json.enc")
OUT_PATH = os.path.join(BASE, "lda", "redteam_anchor_fuzz_defects_pending.json")


def main() -> None:
    if not os.path.exists(KEY_PATH) or not os.path.exists(ENC_PATH):
        raise SystemExit("缺少密钥或密文：请确认 .secrets/ 目录完整（未误删、未遗漏复制）。")
    with open(KEY_PATH, "rb") as f:
        key = f.read()
    with open(ENC_PATH, "rb") as f:
        ct = f.read()
    data = Fernet(key).decrypt(ct)
    with open(OUT_PATH, "wb") as f:
        f.write(data)
    print(f"decrypted -> {OUT_PATH}  ({len(data)} bytes)")


if __name__ == "__main__":
    main()
