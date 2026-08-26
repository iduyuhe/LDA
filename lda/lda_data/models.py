#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据层领域模型（P2.2，轻量 dataclass，便于 service 层构造与测试）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class User:
    id: int
    email: str
    pw_hash: str
    created_at: Optional[str] = None


@dataclass
class Organization:
    id: int
    name: str
    plan: str = "oss"
    license_key_hash: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Project:
    id: int
    org_id: int
    name: str
    meta: Optional[dict] = None
    created_at: Optional[str] = None


@dataclass
class DesignResult:
    id: int
    project_id: int
    org_id: int
    device_type: Optional[str] = None
    params: Optional[dict] = None
    dual_verify_report: Optional[dict] = None
    layout_json: Optional[dict] = None
    created_at: Optional[str] = None


@dataclass
class ApiKey:
    id: int
    user_id: int
    key_hash: str
    scopes: list[str] = field(default_factory=list)
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "ApiKey":
        scopes = []
        if row.get("scopes"):
            scopes = [s for s in row["scopes"].split(",") if s]
        return cls(
            id=row["id"], user_id=row["user_id"],
            key_hash=row["key_hash"], scopes=scopes,
            created_at=row.get("created_at"),
        )
