#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""插件注册（P2.3 · 开放扩展缝）。

扩展点 = ext_oracle（已有 Meep ORACLE 桥）与 lda_plugins 命名空间。
安全白名单：entry 模块必须落在 ALLOWED_BASES 内，防止任意代码加载。
加载器调用模块的 `lda_plugin_register(ctx)`（若存在）完成自注册。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

REGISTRY: Dict[str, "PluginManifest"] = {}

ALLOWED_BASES = ("ext_oracle", "lda_plugins")


@dataclass
class PluginManifest:
    name: str
    version: str
    entry: str           # 模块路径，如 "ext_oracle.meep_oracle"
    scopes: list = field(default_factory=list)
    sandbox: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PluginManifest":
        return cls(
            name=d.get("name", ""),
            version=d.get("version", "0.0.0"),
            entry=d.get("entry", ""),
            scopes=d.get("scopes", []),
            sandbox=bool(d.get("sandbox", True)),
        )


def validate_manifest(m: PluginManifest) -> Optional[str]:
    if not m.name or not m.version or not m.entry:
        return "name / version / entry 均为必填"
    base = m.entry.split(".")[0]
    if base not in ALLOWED_BASES:
        return f"entry 必须落在白名单命名空间 {ALLOWED_BASES} 内"
    return None


def register_plugin(m: PluginManifest) -> Dict[str, Any]:
    err = validate_manifest(m)
    if err:
        return {"ok": False, "error": err}
    try:
        mod = importlib.import_module(m.entry)
        fn = getattr(mod, "lda_plugin_register", None)
        if callable(fn):
            fn({"name": m.name, "scopes": m.scopes,
                "sandbox": m.sandbox})
        REGISTRY[m.name] = m
        return {"ok": True, "name": m.name, "entry": m.entry,
                "sandbox": m.sandbox}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"插件加载失败: {e}"}


def list_plugins() -> list:
    return [
        {"name": m.name, "version": m.version, "entry": m.entry,
         "scopes": m.scopes, "sandbox": m.sandbox}
        for m in REGISTRY.values()
    ]
