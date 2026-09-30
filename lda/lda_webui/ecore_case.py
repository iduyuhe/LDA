"""电子计算芯片案例卡（WebUI 只读端点数据源）· D-155。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
电子计算征程「吃狗粮」E1…E5（D-150…D-154）的**只读案例**：用 LDA 亲手设计一颗
**电子计算芯片**（模拟计算核 = 模拟 MVM 交叉阵列，电子版的「光子 MZI 网格」），
走完 晶体管级模型 → 电路仿真 → 阵列 → 数据通路 → 规模对标 → 平台能力硬化 全链路。

与 `/api/qchip_demo`（光量子 LOQC）、`/api/schip_demo`（超导 transmon）、
`/api/pchip_demo`（硅光张量核）**并列**：四条物理/器件路线在 LDA 均已吃狗粮。
本卡回答的是**同一个平台问题**——「同一条链路，换一种器件（电子/CMOS），是否还站得住？」

🔴 **零重计算**：本模块**不跑电路仿真、不 import 求解器/numpy** —— 全部数字取自
① 静态里程碑/结论（人工登记、可回溯到门禁与 report）② **纯 math 闭式**现算
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。

🔴 **不伪装实测 / 不报 fabricated 能效**：`verdict` 恒为 `DESIGN_VERIFIED`
（**非** ACCEPT/PASS），返回体自带 `honest_note`；本卡**不报任何 TOPS/TOPS-W/fJ/op**。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "ECORE_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SCALE_TIERS", "MOSFET_FACTS", "KEY_METRICS", "LANDMARKS_BRIEF",
    "crossbar_capacity", "quant_error_rel_bound", "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-E · 电子计算芯片（模拟计算核 / MVM 交叉阵列）"

#: 长沟道 NMOS 模型参数（E1 · D-150 · `lda_l2.ecore.mosfet.NmosParams` 默认值；公开典型量级占位）
MOSFET_FACTS = {
    "kp_a_per_v2": 120e-6,        # 跨导参数 KP = µn·Cox（A/V²）
    "vth0_v": 0.4,                # 零偏阈值电压
    "lambda_per_v": 0.02,         # 沟道长度调制
    "w_over_l": 10.0,             # 宽长比（占位）
    "model": "长沟道平方律（截止/三极管/饱和三区 + gm/gds 解析）· Level-1/Shichman–Hodges",
}

#: 关键实测（门禁值 · 可回溯到 run_ecore_e*_smoke）
KEY_METRICS = {
    # E1 · MNA 电路仿真器精度（vs 闭式）
    "mna_rc_transient_err": 2e-4,        # RC 瞬态 vs 指数闭式
    "mna_ac_err": 1e-13,                 # RC 交流 vs 闭式转移函数
    # E2 · 交叉阵列（MNA vs 闭式 golden）
    "xbar_ideal_8x8_err": 2e-4,          # 理想 TIA 路径
    "xbar_transistor_4x4_err": 2.4e-4,   # NMOS 三极管权重路径
    "ota_gain_20k": 7.5, "ota_gain_30k": 10.4,   # 晶体管级 OTA 开环增益（∝ Rd）
    # E3 · MVM 数据通路（vs 全精度数字 golden）
    "datapath_single_8bit_err": 0.0122,
    "datapath_mlp_2layer_6bit_err": 0.044,
    "datapath_tiling_err": 0.0,
    # E4 · 规模律
    "scale_rel_err_32": 0.018, "scale_rel_err_256": 0.030,
    "scale_abs_err_32": 0.08, "scale_abs_err_256": 0.54,
    "max_synapses_tested": 65536,
}

#: 公开 landmark（A级公开来源·照录·未验证·仅背景坐标；不作 LDA 成就值）
LANDMARKS_BRIEF = [
    {"who": "Mythic AI", "item": "M1076 AMP：analog compute-in-memory MVM 交叉阵列"
                                 "（flash array + on-die ADC）· up to 25 TOPS · typ. 3–4 W · "
                                 "76 AMP tiles · up to 80M weights · INT4/INT8（厂商宣称）",
     "source": "https://mythic.ai/?p=134/"},
]

ECORE_HONEST_NOTE = (
    "① 本案例是**设计期验证**（晶体管级模型 + 电路仿真 + 阵列 + 数据通路 + 规模扫描），"
    "**非流片后实测**——无硅、无实测精度/良率/工艺、无 foundry 回片；"
    "② 晶体管模型为**公开典型量级占位参数**（非 PDK 标定、无实测锚）⇒ 不宣称器件性能；"
    "③ 数据通路主路径用**理想 TIA（放大器无限增益理想化）**；transistor 路径的列增益含"
    "**电阻负载因子**（golden 已计入）——二者均为建模口径，非实测；"
    "④ **不报任何 TOPS / TOPS-W / fJ/op 等能效或吞吐指标**（LDA 是设计&验证工具链，"
    "非流片芯片）；Mythic 等公开 landmark 仅作背景坐标，**不同台比较**；"
    "⑤ 电路级验证引擎是**设计验证引擎**，非签核级 SPICE（无温度/噪声/稀疏矩阵/收敛增强）；"
    "⑥ **LLM 不进判决路径**：判决为死标量比对（闭式物理律 golden）；"
    "全程零外部 SPICE 引擎——C 级自主（纯 numpy）。"
)

# ═══════════════════════ 五段征程（静态事实 · 可回溯门禁）═══════════════════
MILESTONES = [
    {"id": "E1", "code": "D-150", "title": "基座：晶体管模型 + 电路仿真器 + 最小计算单元",
     "gate": 6,
     "result": "补齐平台两块短板（此前**无晶体管级模型 / 无电路仿真器**）：长沟道平方律 "
               "NMOS（三区 + gm/gds）+ MNA 仿真器（DC 牛顿/瞬态后向欧拉/AC 复数）+ 反相求和 MAC；"
               "RC 瞬态 vs 指数 <2e-4、AC vs 闭式 <1e-13"},
    {"id": "E2", "code": "D-151", "title": "参数化 N×M 模拟 MVM 交叉阵列",
     "gate": 5,
     "result": "参数化阵列（ideal TIA / transistor 权重 双路径）+ 晶体管级 OTA 表征；"
               "理想 8×8 <2e-4、transistor 4×4 <2.4e-4、OTA 开环增益 ∝ Rd（20k→7.5 / 30k→10.4）"},
    {"id": "E3", "code": "D-152", "title": "MVM 数据通路（计算架构 + 端到端正确性）",
     "gate": 6,
     "result": "数字→DAC→交叉阵列→ADC→数字；带符号权重参考列法 + 多层级联(MLP+ReLU) + 分块；"
               "单层 8bit 误差 0.012 · 2 层 MLP 0.044 · 分块=全阵（精确）"},
    {"id": "E4", "code": "D-153", "title": "规模对标（诚实边界）",
     "gate": 6,
     "result": "规模扫描 32→256（65536 突触）+ 公开 landmark 诚实对标；规模律："
               "**相对误差有界（0.018→0.030）· 绝对误差 ∝ N（0.08→0.54）**；不报 fabricated 能效"},
    {"id": "E5", "code": "D-154", "title": "平台能力硬化（能力清单 + 守护门禁）",
     "gate": 5,
     "result": "ECORE_CAPABILITY_MANIFEST（单一真源）+ 常驻守护门禁（清单↔模块/符号**双向完备** + "
               "披露一致 + 诚实边界）⇒ 能力面不再静默失守"},
]

# ═══════════════════════ 关键结论（物理 + 方法学）═══════════════════════
FINDINGS = [
    {"title": "吃狗粮逼出并补齐平台四块真短板",
     "detail": "此前 LDA 电子域只到行为级——**无晶体管级模型 / 无电路仿真器 / 无模拟计算原语 / "
               "无规模定标与诚实护栏**。本征程新增 `lda_l2/ecore/` 包（7 模块）逐一补齐。"},
    {"title": "架构族同构：电子版「光子 MZI 网格」",
     "detail": "模拟 MVM 交叉阵列 = 行电压 × 交叉点电导 → 列电流求和 → TIA，正是电子域的"
               "矩阵-向量乘；与光子 MZI mesh、与商业模拟 AI 加速器（Mythic 类）**同族**。"},
    {"title": "方法学独立：闭式物理律 golden",
     "detail": "MOSFET 三区解析 ↔ 平方律闭式、RC 瞬态 ↔ 指数、AC ↔ 复导纳转移函数、"
               "分压/求和 ↔ 闭式——判决全为**死标量比对**，LLM 不进判决路径，零外部 SPICE。"},
    {"title": "规模律（诚实报告）：相对误差有界、绝对误差 ∝ N",
     "detail": "MVM 输出幅度随 N 增长；固定位数 ADC 下绝对 LSB 随之增大 ⇒ **须按层输出定标**"
               "（`out_norm`）；相对误差 ≈ 1/2^bits 与 N 无关。这是「规模墙」暴露的真实架构约束。"},
    {"title": "诚实对标：不报 fabricated 能效",
     "detail": "LDA 是设计&验证工具链（非流片芯片）⇒ **不报任何 TOPS/TOPS-W**；公开 landmark "
               "照录来源、仅作背景坐标、不作 LDA 成就值；护栏机器化（注入造假指标必红）。"},
]

# ═══════════════════════ 诚实边界（未闭合项 · 逐条登记）═══════════════════════
GAPS = [
    {"id": "G-A", "title": "无流片 / 无实测",
     "detail": "全部为设计期验证；无硅、无实测精度/良率、无 foundry 回片。"},
    {"id": "G-B", "title": "无 foundry PDK",
     "detail": "晶体管参数为公开典型量级占位（非 PDK 标定、无实测锚）。"},
    {"id": "G-C", "title": "理想 TIA 路径 / 非签核级 SPICE",
     "detail": "数据通路主路径用理想运放（无限增益）；电路引擎无温度/噪声/稀疏矩阵/收敛增强。"},
    {"id": "G-D", "title": "无实测能效 / 吞吐",
     "detail": "不报任何 TOPS / TOPS-W / fJ/op（无流片、无硅实测）。"},
    {"id": "G-E", "title": "transistor 路径列增益含电阻负载因子",
     "detail": "晶体管权重路径的列增益随该列总电导变化（电阻负载固有特性，golden 已计入）。"},
]

# ═══════════════════════ 规模档案（来自 E4 实测）═══════════════════════
SCALE_TIERS = [
    {"n": 32, "synapses": 1024, "rel_err": 0.018, "abs_err": 0.08},
    {"n": 64, "synapses": 4096, "rel_err": 0.027, "abs_err": 0.15},
    {"n": 128, "synapses": 16384, "rel_err": 0.024, "abs_err": 0.29},
    {"n": 256, "synapses": 65536, "rel_err": 0.030, "abs_err": 0.54},
]

_ARTIFACT_DIRS = ("examples", "lda/examples")


# ═══════════════════════════ 闭式（可反向测试 · 纯 math）═══════════════════════════
def crossbar_capacity(n_rows: int, n_cols: int) -> Dict[str, Any]:
    """模拟 MVM 交叉阵列容量闭式（纯计数）：突触数 = rows×cols。

    - 突触数（交叉点）= rows · cols
    - 数据列 = cols；参考列（承载带符号权重）= 1 ⇒ 物理列 = cols + 1
    - 每列输出 = −Rf · Σ_i g_ij·Vin_i（TIA 虚地电流求和）
    """
    r, c = int(n_rows), int(n_cols)
    if r < 1 or c < 1:
        raise ValueError("n_rows / n_cols 须 ≥ 1")
    return {
        "n_rows": r, "n_cols": c,
        "n_synapses": r * c,
        "n_data_cols": c,
        "n_phys_cols_incl_ref": c + 1,
        "fan_in_per_col": r,
    }


def quant_error_rel_bound(bits: int) -> float:
    """均匀量化（mid-tread）相对误差上界 ≈ 1/(2^bits − 1)（LSB/2 归一）。

    bits ≤ 0 视为理想（不量化）⇒ 返回 0.0。
    """
    b = int(bits)
    if b <= 0:
        return 0.0
    if b > 60:
        raise ValueError("bits 过大（>60）无意义")
    return 1.0 / (2 ** b - 1)


# ═══════════════════════════════ 产出物探测（只读元信息）═══════════════════════
def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 `examples/` 下 E 征程产出物**元信息**（文件名 + 字节数 · 只 stat）。

    🔴 **聚合扫描**：逐个候选目录扫描后**按文件名去重合并**（防「假空」）；
    目录都不存在则优雅降级 `available=False`。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d)
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith("lda_ecore") or nm.endswith(".py"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [], "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits, "root_hint": hits[0],
            "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数，已跨目录去重）"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装电子计算芯片案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_VERIFIED` —— **明标「设计期验证」而非实测**。
    """
    flag = crossbar_capacity(256, 256)
    gate_total = sum(m["gate"] for m in MILESTONES)
    return {
        "endpoint": "/api/ecore_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗电子计算芯片（模拟计算核 / MVM 交叉阵列）："
                 "晶体管级模型 + 电路仿真 + 参数化阵列 + 数据通路 + 规模扫描全链路验证",
        "verdict": "DESIGN_VERIFIED",
        "verdict_label": "设计期验证（非流片实测）",
        "identity": {
            "physics": "模拟 compute-in-memory（MVM 交叉阵列）· 电子/CMOS 电路级",
            "device": "NMOS 差分对 OTA / 交叉点电导 / TIA（大增益运放）",
            "unit": "模拟 MVM 砖 = 行电压 × 交叉点电导 → 列电流求和 → TIA 转电压",
            "route_note": "吃狗粮第四条路线（光子计算 / 光量子 LOQC / 超导 transmon 之后）；"
                          "与光子 MZI mesh 同构（电子版）",
            "zero_quantum_sdk": True,
            "zero_spice_engine": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": gate_total,
            "modules": 7,
            "modules_dir": "lda/lda_l2/ecore/",
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "flagship": {
            "kind": "N×M 模拟 MVM 交叉阵列",
            "n_rows": flag["n_rows"], "n_cols": flag["n_cols"],
            "n_synapses": flag["n_synapses"],
            "n_phys_cols_incl_ref": flag["n_phys_cols_incl_ref"],
            "fan_in_per_col": flag["fan_in_per_col"],
        },
        "scale_tiers": {
            "tiers": SCALE_TIERS,
            "max_synapses_tested": KEY_METRICS["max_synapses_tested"],
            "note": "规模 = **可建模并可验证的交叉点容量**，非已流片器件数；"
                    "相对误差有界、绝对误差 ∝ N（固定位数 ADC 固有律）",
        },
        "physics": {
            "mosfet": MOSFET_FACTS,
            "metrics": KEY_METRICS,
            "scale_law": {
                "rel_err_bound_formula": "≈ 1/(2^bits − 1)",
                "rel_err_bound_8bit": quant_error_rel_bound(8),
                "abs_err_grows_with_N": True,
            },
        },
        "artifacts": _artifact_manifest(repo_root),
        "ui": {
            "found_in_ui": True,
            "entry": "验证实力（accept）→「电子计算芯片案例」卡",
            "scope_note": "UI 电子/CMOS 面板覆盖**电路级仿真**；本卡覆盖**芯片级模拟计算架构与验证**。",
        },
        "positioning": _positioning(),
        "honest_note": ECORE_HONEST_NOTE,
    }


def _positioning() -> Dict[str, Any]:
    """先进性定位（公开来源 · 只作背景，不与本案例同台比较）。"""
    return {
        "disclaimer": "下列为公开报道的**产业界/学术界模拟计算（compute-in-memory）**数字，"
                      "仅作背景坐标；本案例为**设计期验证**（无流片），两者**不同台比较**；"
                      "LDA **不报任何 TOPS / TOPS-W**。",
        "public_landscape": LANDMARKS_BRIEF + [
            {"who": "学术界", "item": "RRAM/ReRAM MVM 交叉阵列加速器提案"
                                     "（ISAAC / PUMA 系列，架构族参照）"},
        ],
        "what_is_different": [
            {"axis": "交付物", "industry": "流片硅产品 + 云访问（或有硅实测）",
             "lda": "**设计期验证**：可复现、可审计的工具链输出（无硅）"},
            {"axis": "工具链来源", "industry": "各自闭源 CAD/PDK + 商业 SPICE",
             "lda": "**开源（MIT）· Agent-native · 零外部 SPICE 引擎**：晶体管模型 + MNA "
                    "求解器自研（纯 numpy）"},
            {"axis": "判决路径", "industry": "通常为实测 + 数值仿真混合",
             "lda": "**LLM 不进判决路径**：判决为死标量比对；红线为物理定律锚"},
            {"axis": "架构族", "industry": "analog CIM MVM 交叉阵列",
             "lda": "**同族**：MVM 交叉阵列（电子版「光子 MZI 网格」）——同族维度可比"},
            {"axis": "能效口径", "industry": "有实测/宣称 TOPS 与 W",
             "lda": "**不报能效/吞吐**（无流片）——口径不同，不可比数"},
        ],
        "honest_limits": [
            "无数值/能效同台比较：LDA 不宣称在 TOPS/W 或吞吐上优于任何厂商。",
            "晶体管参数为公开典型量级占位（非 PDK、无实测锚）⇒ 不代表任何工艺实现。",
            "规模数字须按「可建模/可验证容量」解读，误读成「已流片芯片」即为失真。",
        ],
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器 / numpy）。"""
    import ast
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append(f"{'PASS' if cond else 'FAIL'} | {name}")

    # ① 交叉阵列容量闭式：256×256 ⇒ 65536 突触 · 257 物理列
    f = crossbar_capacity(256, 256)
    chk("① 256×256 容量闭式：65536 突触 · 257 物理列（含参考列）",
        f["n_synapses"] == 65536 and f["n_phys_cols_incl_ref"] == 257)

    # ② 容量闭式与逐点一致（N=2..10 方阵）
    ok = True
    for k in range(2, 11):
        ok = ok and crossbar_capacity(k, k)["n_synapses"] == k * k
    chk("② 方阵突触数 ≡ k²（k=2..10 逐点）", ok)

    # ③ 量化相对误差上界 = 1/(2^bits−1)
    chk("③ 量化相对误差上界：8bit ⇒ 1/255 ≈ 0.00392",
        abs(quant_error_rel_bound(8) - 1.0 / 255.0) < 1e-15)

    # ④ 案例卡组装：5 里程碑 · 5 结论 · 5 缺口 · 门禁判据合计 28
    card = case_card(repo_root="__nonexistent_root__")
    chk("④ 案例卡组装：5 里程碑 / 5 结论 / 5 缺口 / 门禁判据合计 28",
        len(card["milestones"]) == 5 and len(card["findings"]) == 5
        and card["gaps_total"] == 5 and card["span"]["gate_checks"] == 28)

    # ⑤ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    chk("⑤ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)

    # ⑥ 🔴 不伪装实测：verdict 恒 DESIGN_VERIFIED，且诚实边界齐全
    note = card["honest_note"]
    chk("⑥ 不伪装实测：verdict=DESIGN_VERIFIED · 诚实边界含「非流片后实测」/「非 PDK」/"
        "「不报任何 TOPS」",
        card["verdict"] == "DESIGN_VERIFIED"
        and "非流片后实测" in note and "非 PDK" in note and "不报任何 TOPS" in note)

    # ⑦ 🔴 不报 fabricated 能效：定位声明 + 3 条诚实限制
    pos = card["positioning"]
    chk("⑦ 先进性定位：含不同台比较声明 + 3 条诚实限制 + 「不报任何 TOPS/TOPS-W」",
        bool(pos["disclaimer"]) and len(pos["honest_limits"]) == 3
        and "不报任何 TOPS / TOPS-W" in pos["disclaimer"])

    # ⑧ 🔴 规模口径明标「可建模/可验证容量」
    chk("⑧ 规模口径明标「可建模并可验证的交叉点容量」",
        "可建模并可验证的交叉点容量" in card["scale_tiers"]["note"])

    # ⑨ 🔴 零外部框架：**ast 遍历真实 import**（不用源码字符串 in）⇒ 无 numpy/scipy/SPICE
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    mods: List[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.append(node.module.split(".")[0])
    banned = {"numpy", "scipy", "ahkab", "PySpice", "ngspice", "pyspice"}
    hit = sorted(set(mods) & banned)
    chk("⑨ 零重计算/零外部框架：本模块不 import numpy/scipy/SPICE（ast 判定）", not hit)

    # ⑩ 护栏：非法输入抛错（0 行列 / bits 过大）
    guard = 0
    for bad in (lambda: crossbar_capacity(0, 4),
                lambda: crossbar_capacity(4, 0),
                lambda: quant_error_rel_bound(61)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑩ 护栏：非法 rows/cols · bits>60 均抛 ValueError", guard == 3)

    # ⑪ 每里程碑都有门禁数与结果文本（防空洞）
    chk("⑪ 里程碑完整：每段含 gate 数 + 结果文本",
        all(m.get("gate", 0) > 0 and m.get("result") for m in MILESTONES))

    # ⑫ landmark 登记含来源（A 级公开·未验证）
    chk("⑫ landmark 登记含 source（Mythic · mythic.ai）",
        bool(LANDMARKS_BRIEF) and all(e.get("source") for e in LANDMARKS_BRIEF))

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("电子计算芯片案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
