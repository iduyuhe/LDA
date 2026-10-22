# -*- coding: utf-8 -*-
"""蓝图 v2 · **D2 QEC 码族** 的「不可锚」登记面（**非门禁模块**）。

🔴 **本模块不是门禁**，只存裁决面与哨兵名。锚号/指标名**只写在这里**，门禁通过 import 读取，
   以免 K4 的文本代理把「在门禁里提了一句」算成「有专属判据」（该病理已命中 5 次）。

## 为什么需要这个模块

D2 立项时的判断是「B 平台级」，理由写在章程
`docs/LDA_V2-D2_QEC码族_可行性评估_架构定义_蓝图补丁_2026-10-22.md`。落档前的可锚性体检把
「为什么不可锚」量化成了三类，本模块把它们**逐条登记并让门禁锁死**：

1. **精确组合量**（整数 / 有理数）⇒ 任何"独立"算法都得到同一个值 ⇒ `resid ≡ 0`
   ⇒ 触 BL 的「零残差」红线（`n_zero_resid` 只许 =0）⇒ **原理上不可锚**。
2. **闭式直接求值当候选**（两条路径都调同一批 libm）⇒ `resid` 只在 0~几 ulp 摆动
   ⇒ 平台间不可复现 ⇒ 触 BL-M2c 的「`resid ≥ 1e4·ulp`」脆弱判据 ⇒ **不可锚**。
3. **阈值密度演化 / 有限尺寸标定**（LDPC、色码）⇒ **没有闭式 golden**，标定值来自 MC 仿真
   ⇒ 「仿真值当 golden」会切断 `golden ⇄ candidate` 的方法学独立性 ⇒ **不可锚**。

唯一可锚的是 **退极化信道 hashing 界**（闭式 + 对数积分表示求积），落为 B525。

## 纪律

- 本表**只减不增**：日后若某类找到合规出口（如找到真闭式 + 真截断候选），必须先把该条
  **删除**并把新锚登记进账本，门禁的双向锁会自动要求同步。
- 哨兵指标名一旦被任何锚采用 ⇒ 门禁必红（防「换名重立同一物理量」）。
"""

from __future__ import annotations

from typing import Dict, List

__all__ = [
    "D2_ADJUDICATION",
    "d2_unanchorable_classes",
    "d2_sentinel_metrics",
    "d2_anchorable_ids",
    "selfcheck_d2_adjudication",
]

#: D2 裁决面：三类不可锚 + 唯一可锚
D2_ADJUDICATION: Dict[str, object] = {
    "verdict": "PARTIALLY_ANCHORABLE",
    "anchorable": {
        "B525": "退极化信道 hashing 界 I_c(p)=1−H₂(p)−p·log₂3（bit）—— 闭式 ⇄ 对数积分表示+复合 Simpson，"
                "残差 2.869e-11（余量 1.08e9×）· 相邻比趋近 16=2⁴ ⇒ O(h⁴) 真截断 ⇒ 可锚",
    },
    "unanchorable_classes": {
        "exact_combinatorial": {
            "reason": "精确组合量（整数/有理数）：任何独立算法都得到同一个值 ⇒ resid ≡ 0 ⇒ 触 BL 的"
                      "「零残差」红线（n_zero_resid 只许 =0）。不存在能产生截断误差的数值路径，"
                      "故不是「难锚」而是「原理上不可锚」。",
            "evidence": [
                "Steane [[7,1,3]] 量子 Hamming 界松紧度 = 2^6/(1+7·3) = 64/22 = 32/11 = 2.909090…（精确有理）",
                "Toric code 基态简并 = 4^g（g=1 ⇒ 4；g=2 ⇒ 16）—— 精确整数",
                "稳定子群阶 2^(n−k)（Steane ⇒ 64）· 逻辑 Pauli 类数 2^(2k)（⇒ 4）—— 精确整数",
            ],
            "sentinel_metrics": [
                "qec_steane_hamming_slack",
                "qec_toric_ground_degeneracy",
                "qec_stabilizer_group_order",
                "qec_logical_class_count",
            ],
        },
        "closed_form_direct_candidate": {
            "reason": "把闭式直接再算一遍当候选：两条路径都落在同一批 libm 调用上 ⇒ resid 只在 0~几 ulp 间"
                      "摆动 ⇒ 跨平台不可复现（BL-M2c 要求 resid ≥ 1e4·ulp）⇒ 判据不可复现即不可锚。",
            "evidence": [
                "ulp(|I_c(0.1)|) = 8.27e-17，而 BL-M2c 要求 resid ≥ 1e4·ulp = 8.27e-13",
                "改走对数积分表示后 resid = 2.869e-11 ⇒ resid/ulp = 3.5e5（> 1e4）⇒ 这才是可锚的形态",
            ],
            "sentinel_metrics": [
                "qec_hashing_bound_direct_log",
                "qec_depolarizing_capacity_direct_eval",
            ],
        },
        "threshold_density_evolution": {
            "reason": "阈值密度演化 / 有限尺寸标定（LDPC、色码）：**没有闭式 golden**，标定值本身来自 MC 仿真"
                      "⇒ 若用仿真值当 golden，「golden ⇄ candidate」的方法学独立性被切断，只剩自己跟自己比。",
            "evidence": [
                "LDPC 码阈值靠密度演化 + 有限尺寸标定，输出是拟合参数而非闭式标量",
                "色码/拓扑码阈值同理；且解码器重，仓库禁第三方 QEC SDK ⇒ 无法引入独立实现做对照",
            ],
            "sentinel_metrics": [
                "qec_ldpc_de_threshold",
                "qec_color_code_threshold_fit",
                "qec_finite_size_scaling_threshold",
            ],
        },
    },
}


def d2_unanchorable_classes() -> List[str]:
    """返回全部「不可锚」类名（供门禁遍历）。"""
    return sorted(D2_ADJUDICATION["unanchorable_classes"])


def d2_sentinel_metrics() -> List[str]:
    """返回全部哨兵指标名（被任何锚采用 ⇒ 门禁必红）。"""
    out: List[str] = []
    for spec in D2_ADJUDICATION["unanchorable_classes"].values():
        out.extend(spec["sentinel_metrics"])
    return sorted(out)


def d2_anchorable_ids() -> List[str]:
    """返回可锚（已落账本）的锚号。"""
    return sorted(D2_ADJUDICATION["anchorable"])


def selfcheck_d2_adjudication() -> Dict[str, bool]:
    """裁决面自洽自检（门禁 G 组会用）。"""
    c: Dict[str, bool] = {}
    cls = D2_ADJUDICATION["unanchorable_classes"]
    c["schema_verdict"] = isinstance(D2_ADJUDICATION.get("verdict"), str)
    c["at_least_three_classes"] = len(cls) >= 3
    c["every_class_has_reason"] = all(
        isinstance(v.get("reason"), str) and len(v["reason"]) >= 30 for v in cls.values())
    c["every_class_has_two_evidence"] = all(
        isinstance(v.get("evidence"), list) and len(v["evidence"]) >= 2 for v in cls.values())
    c["every_class_has_sentinel"] = all(
        isinstance(v.get("sentinel_metrics"), list) and len(v["sentinel_metrics"]) >= 1
        for v in cls.values())
    c["sentinel_names_unique"] = len(set(d2_sentinel_metrics())) == len(d2_sentinel_metrics())
    c["anchorable_not_empty"] = bool(d2_anchorable_ids())
    c["anchorable_disjoint_from_sentinels"] = not (
        set(d2_anchorable_ids()) & set(d2_sentinel_metrics()))
    return c


if __name__ == "__main__":
    print("可锚:", d2_anchorable_ids())
    print("不可锚类:", d2_unanchorable_classes())
    print("哨兵名 %d 个:" % len(d2_sentinel_metrics()), d2_sentinel_metrics())
    sc = selfcheck_d2_adjudication()
    bad = [k for k, v in sc.items() if not v]
    print("自检 %d 项：%s" % (len(sc), "ALL PASS" if not bad else "FAIL=%s" % bad))
