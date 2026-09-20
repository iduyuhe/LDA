# -*- coding: utf-8 -*-
"""T1 红线单一来源（v0.9.113 · 波次 2 · 源自 2026-09-19 全面代码审计 F-07）。

为什么存在
----------
T1 数值内核的铁律：**T1 输出（数值解）永不作 ORACLE** —— 死标量判决必须落在
非 AI ground（物理定律闭式 / 公开文献 / foundry 实测）上。守卫
``guard_t1_not_oracle`` 原在 6 个 T1 内核中各复制一份：

    apd_avalanche_true · detector_bandwidth_true · drift_diffusion_1d ·
    drift_diffusion_2d · ge_pd_responsivity_true · mzm_vpi_depletion_true

审计判读：*「红线守卫被复制 6 处 ⇒ 改一处漏五处即削弱保护」*（F-07 / §3.5）。
本模块把**逻辑**收敛为**单一定义**（受 `run_pyflakes_ratchet_smoke` 的「助手重复棘轮」
守护：全仓 ``def guard_t1_not_oracle`` 的函数定义数必须 == 1）。各内核只保留两样
**数据**：① ``T1_OUTPUT_IS_ORACLE`` 铁律开关（值恒 ``False``；单一定义在此处，各内核
re-export）；② 本内核被守卫量的文案 ``subject``（错误信息里说明「哪个量仅作候选」）。

纪律
----
纯死标量、无 I/O、无 wall-clock、无随机；**不导入任何数值内核**（无环、无副作用）。
"""
from __future__ import annotations

from functools import partial

# 🔴 铁律开关：T1 输出是否可作 ORACLE —— **恒 False，任何内核不得改**。
T1_OUTPUT_IS_ORACLE = False

# 死标量判决的地面来源（非 AI ground）——各内核按自己的验证责任方选用
GROUND_PHYSICS = "物理定律闭式/文献/foundry 实测"
GROUND_ANCHOR = "物理定律锚/文献/foundry 实测"
GROUND_MEASURED = "实测语料/物理定律闭式"
GROUND_LITERATURE = "实测语料/文献闭式"
GROUND_DEFAULT = GROUND_PHYSICS


def guard_t1_not_oracle(solution, force_oracle=False,
                         subject="T1 数值解", ground=GROUND_DEFAULT):
    """🔴 T1 输出不作 ORACLE 守卫（**全仓单一定义**，见模块 docstring）。

    - 正常调用（``force_oracle=False``）：断言 ``solution['is_oracle']`` 非 True
      （输出是**候选**，不是真值）⇒ 返回 ``True``。
    - 反向测试（``force_oracle=True``：模拟「有人把 T1 数值解当 ORACLE 喂进判决
      回路」）：必须 ``raise RuntimeError``（守卫必响），否则破红线。
    - ``subject`` / ``ground``：仅用于错误文案（各内核自述被守卫量与地面来源）；
      各内核经 :func:`bind_guard` 绑定，故归一前后**错误文案逐字一致**。
    """
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：%s 仅作候选，死标量判决须由%s定。"
            % (subject, ground))
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


def bind_guard(subject, ground=GROUND_DEFAULT):
    """按本内核的被守卫量绑定守卫（返回同签名可调用）。

    逻辑仍**只有** :func:`guard_t1_not_oracle` 一处定义；各内核只是把
    ``subject``/``ground`` 这两项**数据**绑上去。签名与错误文案与归一前一致。
    """
    return partial(guard_t1_not_oracle, subject=subject, ground=ground)
