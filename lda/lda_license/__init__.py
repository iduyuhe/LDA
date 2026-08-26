#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""License 校验集成缝（P2.3 · 开放 seam）。

分层开源纪律：本模块是**开放接口缝**，不是闭源校验实现本身。
- 开源版（无 LICENSE_KEY）：全功能、无限额，永远免费（MIT）。
- 商业版（有 LICENSE_KEY）：需离线签名校验；**真正的密码学校验实现在闭源
  lda-cloud 仓库**（守护城河）。本模块提供 set_verifier() 注入点，lda-cloud
  在启动时注入真实校验器；默认内置 verifier 仅做「格式合法即放行」的占位，
  绝不假装安全——缺省部署无 key，等同开源版。

设计：LicenseChecker 不决定功能开关，只回答「当前 tier / 是否超额」。
配额/治理的强制力由 lda-cloud 在应用层叠加，本仓库不绑架内核。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class LicenseInfo:
    tier: str          # "oss" | "cloud"
    seats: int = 0     # 0 = 无限（oss）
    active: bool = True
    note: str = ""


# 注入点：闭源 lda-cloud 调用 set_verifier 提供真实离线校验
_VERIFIER: Optional[Callable[[str], Optional[LicenseInfo]]] = None


def set_verifier(fn: Callable[[str], Optional[LicenseInfo]]) -> None:
    """lda-cloud 注入真实签名校验器（签名合法→返回 LicenseInfo，否则 None）。"""
    global _VERIFIER
    _VERIFIER = fn


def _default_verifier(key: str) -> Optional[LicenseInfo]:
    """占位 verifier：仅校验格式（`lda-` 前缀 + 足够长度），不做密码学。
    真实校验由 lda-cloud 覆盖。"""
    if key.startswith("lda-") and len(key) >= 16:
        return LicenseInfo(tier="cloud", seats=0, active=True,
                           note="占位校验（真实签名校验在 lda-cloud）")
    return None


def check_license(key: Optional[str] = None) -> LicenseInfo:
    """返回当前许可信息。无 key → 开源版（无限）。"""
    if key is None:
        key = os.environ.get("LDA_LICENSE_KEY", "").strip()
    if not key:
        return LicenseInfo(tier="oss", seats=0, active=True,
                           note="开源版：全功能、无限额、永久免费（MIT）")
    verifier = _VERIFIER or _default_verifier
    info = verifier(key)
    if info is None:
        # 校验失败 → 诚实降级为开源功能集（不谎报商业能力）
        return LicenseInfo(tier="oss", seats=0, active=True,
                           note="license 校验失败 → 降级开源版")
    return info


def is_oss() -> bool:
    return check_license().tier == "oss"
