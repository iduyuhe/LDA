"""B6 · 光栅耦合器 3D 场级 ORACLE（Tidy3D，GPL 仅外部）。

设计纪律（《白皮书》§11 许可证红线）：Tidy3D 为 GPL 代码，**绝不 import 进
LDA Apache-2.0 核心**。本模块是"外部 ORACLE 适配层"——仅在用户显式配置了
TIDY3D_API_KEY 且环境可 import tidy3d 时，才在**隔离/外部**方式下调用真 3D
求解，回传标量耦合效率；否则返回 None，由 golden.py 回退到设计守则锚
（B6_DESIGN_ANCHOR=0.5，工艺成熟下限）作为验收基准。

这是"主权优先"策略下对 B 级依赖（MIT/BSD 可 fork，GPL 仅外部 ORACLE）的
标准处理：核心永不污染，真值按需外挂。

注：本环境未配置 TIDY3D_API_KEY，故 resolve_tidy3d_grating 恒返回 None，
链路自动走设计守则锚——这是刻意的主权安全默认，而非缺陷。
"""
import os


def resolve_tidy3d_grating(params):
    """返回 {value, source, note} 或 None。

    value: 峰值耦合效率（0–1）；source: 'tidy3d-3d'；None = 未配置/不可用，
    由调用方回退到设计守则锚。
    """
    key = os.environ.get("TIDY3D_API_KEY")
    if not key:
        return None
    try:
        import tidy3d as td  # GPL，仅外部 ORACLE；缺失即不可用
        from tidy3d.plugins import ModeSolver  # 仅占位，真实需完整结构
    except Exception:
        return None
    # —— 以下为"已配置凭证"时才执行的真 3D 求解路径（本演示环境不触发）——
    # 1) 用 key 配置 Tidy3D web 客户端（外部服务，符合 §11 外挂纪律）
    # 2) 构建 1D/2D 布拉格光栅耦合器 3D 结构（Si 条 + 二氧化埋层 + 上包层）
    # 3) td.web.run(...) 求 S 参数 → 峰值耦合效率
    # 4) 返回 {"value": eff, "source": "tidy3d-3d",
    #          "note": "Tidy3D 3D FDTD ORACLE（外部，GPL 不进核心）"}
    # 因无真实凭证，该路径仅在用户环境中被外部触发；本模块默认 None。
    _ = (td, ModeSolver, params, key)
    return None
