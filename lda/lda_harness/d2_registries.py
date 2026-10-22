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
    "D2_M1_ADJUDICATION",
    "d2_m1_unanchorable_classes",
    "d2_m1_sentinel_metrics",
    "d2_m1_reused_metrics",
    "selfcheck_d2_m1_adjudication",
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


# ══════════════════════════════════════════════════════════════════════════════
# D2-M1 裁决面（码族比较 / 开销 · G-V2-D2-3 + G-V2-D2-4）
# ══════════════════════════════════════════════════════════════════════════════
#: D2-M1 裁决面：**四类不可锚 · 净增 0 锚**
#:
#: 依据 `docs/LDA_V2-D2_QEC码族_M1短评估_码族比较与开销_2026-10-22.md`（先体检后动手）：
#: 码族「比较 / 开销」这一面**没有可锚物** —— 连续部分已被既有锚占满，非连续部分全是
#: 整数 / 拟合值 / 离散选择。四类各带 ≥3 条证据，哨兵指标名防「换名重立」。
D2_M1_ADJUDICATION: Dict[str, object] = {
    "verdict": "NOT_ANCHORABLE",
    "scope": "G-V2-D2-3 码族间资源-阈值折衷（同 p 下比较）+ G-V2-D2-4 逻辑门集合的可比性度量",
    "unanchorable_classes": {
        "exact_integer_overhead": {
            "anchorable": False,
            "reason": "码族开销面（空间开销 n/k、物理比特数 (2d−1)²、T 计数、门深度、"
                      "基态简并度、稳定子群阶、逻辑类数）全是精确整数或精确有理数：任何"
                      "「独立算法」都给出同一个数 ⇒ resid ≡ 0 ⇒ 触 BL 的「零残差」红线"
                      "（n_zero_resid 只许 =0）⇒ 不是「难锚」，是原理上不可锚。",
            "evidence": [
                "空间开销 n/k：[[5,1,3]]⇒5 · [[7,1,3]](Steane)⇒7 · [[9,1,3]](Shor)⇒9（精确整数，无截断项）",
                "表面码物理比特数 (2d−1)²：d=3/5/7 ⇒ 25/81/169（精确整数）",
                "拓扑/稳定子组合量：4^g(g=2)⇒16 · 2^(n−k)⇒64 · 2^(2k)⇒4 · Steane 松紧度 2^6/(1+7·3)=32/11（精确有理）",
                "T 计数 / 门深度为编译后精确整数计数，不存在随步长收敛的数值路径 ⇒ 残差恒 0",
            ],
            "sentinel_metrics": [
                "qec_code_space_overhead_ratio",
                "qec_surface_code_physical_qubit_count",
                "qec_logical_t_count",
                "qec_code_circuit_depth_count",
            ],
        },
        "fitted_threshold_parameters": {
            "anchorable": False,
            "reason": "跨族比较必须引入各族的阈值 p_th 与前置系数 A，这两个量来自文献拟合或"
                      "蒙特卡洛 + 有限尺寸标定 ⇒ 没有闭式 golden。若拿拟合值当 golden，"
                      "「golden ⇄ candidate」的方法学独立性被切断，只剩自己跟自己比 ⇒ 不可锚。",
            "evidence": [
                "LDPC / 色码 / 表面码的 p_th 与 A 均为拟合量（文献值随解码器与噪声模型漂移）",
                "同一 p_th 在两篇文献可相差数倍 ⇒ 不构成「可复现的死标量」",
                "仓库红线禁第三方 QEC SDK ⇒ 无法引入独立实现做交叉对照 ⇒ 缺第二个闭式",
            ],
            "sentinel_metrics": [
                "qec_code_cross_family_threshold_fit",
                "qec_color_code_threshold_scaling",
                "qec_family_fit_coefficient_a",
            ],
        },
        "discrete_argmin_comparison": {
            "anchorable": False,
            "reason": "「同 p 下哪个族更省」是比较的**结果**，本质是离散 argmin / 整数比较 "
                      "⇒ 与精确整数同类：任何实现都给同一个族名，没有连续残差可言。"
                      "而把 d* 再做代数合成（如 (2d*−1)²）只是既有闭式的单调变换 ⇒ 派生量。",
            "evidence": [
                "argmin 输出是族标签（离散），resid 无从定义 ⇒ 判据只能是「等于某个名字」",
                "d*=88.5400554685（既有闭式）⇒ (2d*−1)²=31004.205468、2d*²=15678.682845 均为纯代数合成",
                "可行性判定 p_phys ≥ p_th ⇒ d*<0（实测 −283.7152649994）也是符号比较，非新物理量",
            ],
            "sentinel_metrics": [
                "qec_code_family_argmin_choice",
                "qec_derived_physical_qubit_footprint",
                "qec_code_family_feasibility_flag",
            ],
        },
        "same_function_asymptotic_bound": {
            "anchorable": False,
            "reason": "码族比较的渐近速率口径（量子 Gilbert–Varshamov 界）与已落账本的退极化 "
                      "hashing 界是**同一个函数**：R_GV(δ)=1−H₂(δ)−δ·log₂3 ≡ I_c(p) 只换自变量名。"
                      "实测四点差恒 0.0（代数恒等签名，非 1e-16）⇒ 同式异写，换任何观测量都治不好。",
            "evidence": [
                "δ=0.05: 两式同得 0.63435491784798592（差 0.0）",
                "δ=0.11: 同得 0.32573816675614475 · δ=0.25: 同得 −0.20751874963942185（差均 0.0）",
                "δ=0.18929（穿零点）: 同得 −5.5511151231257827e-17 ⇒ 连穿零位置都一致",
                "数值格式也相同（熵→积分表示→复合 Simpson）⇒ 被测标量∧数值格式两处全同",
            ],
            "sentinel_metrics": [
                "qec_gilbert_varshamov_rate",
                "qec_asymptotic_code_rate_bound",
            ],
        },
    },
    #: 复核（非新锚）：M1 用到的连续标量已在既有锚内 —— 门禁按 **metric 名**取用，不写锚号
    "reused_anchor_metrics": {
        "qec_threshold_distance": "阈值标度律反解的最小距离 d*（既有的连续标量，跨族只换 (A,p_th) 参数）",
        "qec_depolarizing_hashing_bound": "退极化信道 hashing / coherent-information 界（与 GV 界同函数）",
    },
}


def d2_m1_unanchorable_classes() -> List[str]:
    """返回 D2-M1 全部「不可锚」类名。"""
    return sorted(D2_M1_ADJUDICATION["unanchorable_classes"])


def d2_m1_sentinel_metrics() -> List[str]:
    """返回 D2-M1 全部哨兵指标名（被任何锚采用 ⇒ 门禁必红）。"""
    out: List[str] = []
    for spec in D2_M1_ADJUDICATION["unanchorable_classes"].values():
        out.extend(spec["sentinel_metrics"])
    return sorted(out)


def d2_m1_reused_metrics() -> List[str]:
    """返回 D2-M1 判定「复用既有锚」的 metric 名（门禁据此取既有 golden）。"""
    return sorted(D2_M1_ADJUDICATION["reused_anchor_metrics"])


def d2_all_sentinel_metrics() -> List[str]:
    """M0 + M1 的哨兵并集（门禁一次性扫全）。"""
    return sorted(set(d2_sentinel_metrics()) | set(d2_m1_sentinel_metrics()))


def selfcheck_d2_m1_adjudication() -> Dict[str, bool]:
    """D2-M1 裁决面自洽自检（门禁 A 组会用 · 证据门槛 ≥3）。"""
    c: Dict[str, bool] = {}
    cls = D2_M1_ADJUDICATION["unanchorable_classes"]
    c["verdict_is_not_anchorable"] = D2_M1_ADJUDICATION.get("verdict") == "NOT_ANCHORABLE"
    c["four_classes"] = len(cls) == 4
    c["every_class_has_reason_30"] = all(
        isinstance(v.get("reason"), str) and len(v["reason"]) >= 30 for v in cls.values())
    c["every_class_has_three_evidence"] = all(
        isinstance(v.get("evidence"), list) and len(v["evidence"]) >= 3 for v in cls.values())
    c["every_class_has_sentinel"] = all(
        isinstance(v.get("sentinel_metrics"), list) and len(v["sentinel_metrics"]) >= 1
        for v in cls.values())
    c["sentinel_names_unique"] = len(set(d2_m1_sentinel_metrics())) == len(d2_m1_sentinel_metrics())
    c["no_sentinel_collides_with_reused"] = not (
        set(d2_m1_sentinel_metrics()) & set(d2_m1_reused_metrics()))
    c["reused_metrics_not_empty"] = len(d2_m1_reused_metrics()) >= 2
    return c


if __name__ == "__main__":
    print("可锚:", d2_anchorable_ids())
    print("不可锚类:", d2_unanchorable_classes())
    print("哨兵名 %d 个:" % len(d2_sentinel_metrics()), d2_sentinel_metrics())
    sc = selfcheck_d2_adjudication()
    bad = [k for k, v in sc.items() if not v]
    print("自检 %d 项：%s" % (len(sc), "ALL PASS" if not bad else "FAIL=%s" % bad))
    print("─" * 70)
    print("D2-M1 决:", D2_M1_ADJUDICATION["verdict"], "· 范围:", D2_M1_ADJUDICATION["scope"])
    print("D2-M1 不可锚类:", d2_m1_unanchorable_classes())
    print("D2-M1 哨兵名 %d 个:" % len(d2_m1_sentinel_metrics()), d2_m1_sentinel_metrics())
    print("D2-M1 复用既有 metric:", d2_m1_reused_metrics())
    sc1 = selfcheck_d2_m1_adjudication()
    bad1 = [k for k, v in sc1.items() if not v]
    print("D2-M1 自检 %d 项：%s" % (len(sc1), "ALL PASS" if not bad1 else "FAIL=%s" % bad1))
