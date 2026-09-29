# -*- coding: utf-8 -*-
"""光量子计算芯片案例卡（WebUI 只读端点数据源）· D-131。

定位：把「量子征程（吃狗粮）」九步成果在 **WebUI 中以只读案例** 呈现。
本模块是 A 档接入的数据源，不做任何版图生成 / 仿真。

════════════════════════════ 三条纪律（不可破）════════════════════════════
① **零重计算**：全部数字 = **闭式现算**（深度 / 损耗 / 参数 / 维数），微秒级；
   不跑 P&R、不 import 求解器 ⇒ 该 GET 端点无 DoS 面，也不消耗 CPU。
   （站内同类先例：`/api/verification_ledger`、`/api/benchmarks` 都是免登录只读 GET。）
② **不伪装实测**：所有损耗 / 效率均为**设计预算口径**，返回体自带 `honest_note`，
   且 `verdict` 明标 `DESIGN_BUDGET` —— **不用 ACCEPT/PASS 冒充实测签核**。
③ **LLM 不进判决**：本模块纯算术 + 静态文案，无任何模型调用、无网络。

数值真源（本模块**只复述闭式**，不重造物理）：
  · 元件数 N(N−1)/2 —— Clements 必要性定理
  · 三角 Reck 深度 2N−3 —— `lda_qeda.temporal_mesh` 浅调度实测（N≤64）与闭式一致
  · 矩形 Clements 深度 N —— `lda_qeda.rect_mesh`(D-122) 紧界可达
  · per_mzi 2.4 dB / per_step 2.6 dB —— `lda_qeda.loss_budget`(D-123) 设计预算
门禁 `run_qchip_case_smoke.py` 做**跨源一致性断言**（本模块现算值 vs report JSON /
平台模块常量），防文案与工程漂移。
"""

from __future__ import annotations

import math
import os

__all__ = [
    "CASE_ID",
    "PER_MZI_LOSS_DB",
    "PER_STEP_LOSS_DB",
    "MILESTONES",
    "FINDINGS",
    "GAPS",
    "QCHIP_HONEST_NOTE",
    "mesh_depth_closed_form",
    "loss_account_closed_form",
    "hilbert_log2_dim",
    "case_card",
    "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-Q · 光量子计算芯片（LOQC 通用处理器）"

#: 单个 MZI 插损（dB）· 来源 `lda_qeda/loss_budget.py`（D-123）设计预算口径
PER_MZI_LOSS_DB = 2.4
#: 时间复用每步插损（dB，含延迟环/开关）· 同上（D-123）
PER_STEP_LOSS_DB = 2.6
#: 旗舰规模（对标 Xanadu Borealis 同规模）
FLAGSHIP_N = 216

QCHIP_HONEST_NOTE = (
    "① 本案例是**设计 + 数值正确性证明**（数学 + 构造性数值 + 版图签核流程），"
    "**非流片后实测**；② 损耗 / 效率均为**设计预算口径**（per_mzi 2.4 dB、"
    "per_step 2.6 dB），**非实测 PDK**（属 D5 外部依赖）；③ 与 Borealis 只比"
    "**规模 / 架构 / 参数计数**，**不比数值**（CV Gaussian Boson Sampling vs "
    "DV 被动 LOQC，物理模型不同）；④ 「综合对标分」是平台自定义量，**非国际公认"
    "指标**；⑤ 最优性证据限 N ≤ 8 / D ≤ 6 搜索空间（N=4 穷举）⇒ 不宣称全局最优证明；"
    "⑥ 每模口径**不含波导交叉损耗**，属**下界**。"
)

# ═══════════════════════ 九步征程（静态事实 · 可回溯 report）═══════════════════
MILESTONES = [
    {"id": "M1", "code": "LDA-Q1", "title": "4 模硬编码网格 · 全链路签核",
     "result": "真实 GDS + DRC PASS + LVS ACCEPT + 酉重构保真度 1.0（12 交叉对全解）"},
    {"id": "M2", "code": "LDA-Q2", "title": "参数化 N×N P&R 生成器",
     "result": "N=4/8/16/32/64 全 DRC PASS + LVS ACCEPT + 保真 1.0 + 0 波导交叉"},
    {"id": "M3", "code": "LDA-Q3", "title": "量子态层（Fock / 符合计数 / HOM）",
     "result": "从经典酉矩阵跃到量子态演化；HOM 闭式 ⇄ 数值一致"},
    {"id": "M3b", "code": "LDA-Q3b", "title": "真实源 + 探测器 + 开放系统",
     "result": "SPDC 单光子源 / SNSPD / 多模 Lindblad 损耗通道 · 三法独立互证"},
    {"id": "M3c", "code": "LDA-Q3c", "title": "全链路量子签核",
     "result": "量子 DRC ACCEPT（9 规则）· 量子 LVS ACCEPT（保真度 0.999788 ≥ 0.999）"},
    {"id": "M4", "code": "LDA-Q4", "title": "规模对标（100+ / 216 模）",
     "result": "规模律 + 瓶颈诊断；签核 @N=4 ACCEPT / @N=216 REJECT（诚实暴露规模墙）"},
    {"id": "M4b", "code": "LDA-Q4b", "title": "时间复用 + 深度最优性",
     "result": "1 片 MZI 可实现任意酉（fid 1.0）；深度三口径：参数界 215（非紧）≤ 紧界 216 ≤ Reck 最优 429"},
    {"id": "M5", "code": "LDA-Q5", "title": "矩形 Clements 网格 · 坐实紧界可达",
     "result": "深度 = N = 紧下界（紧界可达）· 省 213 层 · 装配保真度 1.0 · 三方一致"},
    {"id": "M5b", "code": "LDA-Q5b", "title": "真实损耗预算（每模口径）",
     "result": "三角 1029.6 → 矩形 518.4 dB（省 511.2）· 浅电路越墙但非通用"},
]

# ═════════════════════════ 四条硬结论（静态文案）═════════════════════════
FINDINGS = [
    {"tag": "紧界可达", "text":
     "通用 N 模酉的相邻耦合紧下界 = N；矩形 Clements 网格深度恰 = N（每层真匹配）"
     "⇒ 紧界可达，且元件数不增（仍 N(N−1)/2）。对照平台三角 Reck 最优 2N−3，"
     "深度减半（N=216：429 → 216）。"},
    {"tag": "参数计数会骗人", "text":
     "「可及参数 ≈ ⌊N/2⌋·D」是上界。实测可达子流形维数后：全最大匹配序列门数线性增"
     "而可达维数恒为 2N（与深度无关）；最优浅电路是交替砖墙；参数计数下界 N−1 不可达。"},
    {"tag": "通用与省损不可兼得", "text":
     "损耗墙本质是深度墙，深度下界 Ω(N) 由参数计数钉死。时间复用把元件数从 O(N²) 降到"
     "O(1)，但每模损耗反而更贵；只有放弃通用性的浅电路才越墙（非通用）。"},
    {"tag": "约定须精确到块级恒等式", "text":
     "平台 mzi_unit_cell 与主权矩形分解的相位臂相反：裸替换在 2×2 只差一个标量，"
     "但嵌入 N×N 后变成逐模相位注入且与邻门不对易 ⇒ 整网格 ≠ U（连全局相位都不是）。"},
]

# ══════════════════ 平台能力缺口 G_Q1–G_Q9（吃狗粮反向长出）══════════════════
GAPS = [
    {"id": "G_Q1", "what": "单光子源 / SNSPD 探测器模型", "closed": True, "by": "D-114 / D-115"},
    {"id": "G_Q2", "what": "Fock / Wigner 量子态仿真器", "closed": True, "by": "D-113"},
    {"id": "G_Q3", "what": "量子过程保真度（开放系统）", "closed": True, "by": "D-116"},
    {"id": "G_Q4", "what": "HOM 双光子干涉可见度", "closed": True, "by": "D-113"},
    {"id": "G_Q5", "what": "L3 标定闭环", "closed": True, "by": "D-117"},
    {"id": "G_Q6", "what": "N×N 可扩 P&R 生成器", "closed": True, "by": "M2"},
    {"id": "G_Q7", "what": "量子器件 DRC / LVS 规则", "closed": True, "by": "D-118"},
    {"id": "G_Q8", "what": "量子基准", "closed": True, "by": "D-119"},
    {"id": "G_Q9", "what": "结构代理无法表示平凡 MZI（Lc=0 塌缩）",
     "closed": False, "by": "M2 用布局最小长度守卫绕过"},
]

#: 产出物探测目录（相对仓库根）——生产部署若无该目录则优雅降级
_ARTIFACT_DIRS = ("examples",)


# ═══════════════════════════ 闭式现算（纯 math）═══════════════════════════
def mesh_depth_closed_form(n_modes: int) -> dict:
    """闭式：元件数 / 三角 Reck 深度 / 矩形 Clements 深度 / 省层数 / 三口径。

    🔴 全是 int —— 判决位无浮点、无模型。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    n_mzi = n * (n - 1) // 2
    d_reck = 2 * n - 3 if n >= 2 else 0
    d_rect = n
    return {
        "n_modes": n,
        "n_mzi": int(n_mzi),
        "depth_triangular_reck": int(d_reck),
        "depth_rectangular_clements": int(d_rect),
        "depth_saving_vs_reck": int(d_reck - d_rect),
        "tight_adjacency_bound": int(n),
        "parameter_count_bound": int(math.ceil(n_mzi / max(1, n // 2))),
        "tight_bound_reachable": bool(d_rect == n),
    }


def loss_account_closed_form(n_modes: int,
                             per_mzi_db: float = PER_MZI_LOSS_DB,
                             per_step_db: float = PER_STEP_LOSS_DB) -> dict:
    """闭式：各架构**每模**插损账（dB）· 口径分离（列口径 vs 每模口径）。

    · 三角静态（邻耦合，每模深度 2N−3）：`(2N−3)·per_mzi`
    · 矩形静态（每模深度 N）：`N·per_mzi`
    · 时间复用（矩形调度，深度 N）：`N·per_step`
    · 时间复用（Reck 调度，深度 2N−3）：`(2N−3)·per_step`
    · 列口径参考（D-120 旧口径，**低估**）：`(N−1)·per_mzi`
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    d = mesh_depth_closed_form(n)
    tri = d["depth_triangular_reck"] * float(per_mzi_db)
    rect = d["depth_rectangular_clements"] * float(per_mzi_db)
    tmx_rect = d["depth_rectangular_clements"] * float(per_step_db)
    tmx_reck = d["depth_triangular_reck"] * float(per_step_db)
    col = (n - 1) * float(per_mzi_db)
    return {
        "n_modes": n,
        "per_mzi_loss_db": float(per_mzi_db),
        "per_step_loss_db": float(per_step_db),
        "column_basis_db": float(col),
        "triangular_static_db": float(tri),
        "rectangular_static_db": float(rect),
        "temporal_rect_schedule_db": float(tmx_rect),
        "temporal_reck_schedule_db": float(tmx_reck),
        "rect_saving_vs_triangular_db": float(tri - rect),
        "temporal_penalty_vs_rect_static_db": float(tmx_rect - rect),
        "rect_eta": float(10.0 ** (-rect / 10.0)),
        "universality_floor_db": float(rect),
        "universality_floor_kind": "rect_static",
        "column_basis_underestimates_by_db": float(tri - col),
    }


def hilbert_log2_dim(n_modes: int, n_photons: int = 125) -> float:
    """玻色采样输出态空间的 log2 维数 = log2 C(N+n−1, n)（闭式，用 lgamma）。"""
    n, k = int(n_modes) + int(n_photons) - 1, int(n_photons)
    lg = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))
    return float(lg / math.log(2.0))


# ═══════════════════════════ 产出物探测（只读元信息）═══════════════════════
def _artifact_manifest(repo_root: str | None = None) -> dict:
    """探测 `examples/` 下的量子芯片产出物**元信息**（文件名 + 字节数）。

    🔴 只 `stat`，不读内容、不解析 GDS ⇒ 微秒级；`examples/` 不存在的
    （如生产部署只装 `lda/`）则优雅降级为 `available=False`。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    items = []
    found_dir = None
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if os.path.isdir(p):
            found_dir = p
            break
    if found_dir is None:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [], "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    try:
        names = sorted(os.listdir(found_dir))
    except OSError:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [], "note": "产出物目录不可读"}
    for nm in names:
        if not (nm.startswith("lda_qchip_") or nm.startswith("lda_q")):
            continue
        if nm.endswith(".py"):
            continue
        fp = os.path.join(found_dir, nm)
        try:
            if os.path.isfile(fp):
                items.append({"name": nm, "bytes": int(os.path.getsize(fp))})
        except OSError:
            continue
    return {"available": True, "root_hint": _ARTIFACT_DIRS[0],
            "count": len(items), "items": items,
            "note": "只读元信息（文件名 + 字节数）；在线生成请走源码仓的 examples/ 脚本"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(n_modes: int = FLAGSHIP_N, repo_root: str | None = None) -> dict:
    """组装 WebUI 案例卡（只读 · 闭式现算 · 秒回）。"""
    n = int(n_modes)
    if not (2 <= n <= 4096):
        raise ValueError("n_modes 须在 2..4096")
    depth = mesh_depth_closed_form(n)
    loss = loss_account_closed_form(n)
    return {
        "endpoint": "/api/qchip_demo",
        "case_id": CASE_ID,
        "claim": "任意 N×N 酉变换可在片上可编程实现（LOQC 通用处理器 = 可编程 MZI 干涉仪网格）",
        "identity": {
            "physics": "LOQC（线性光量子计算）· 离散变量 Fock 基",
            "device": "集成光子芯片：波导 + 定向耦合器 + 相移器",
            "unit": "MZI 单元 = 一个分束器 θ + 一个相移器 φ（2×2 酉）",
            "route_note": "LDA 唯一能出真实 GDS 并走完全链路签核的量子路线（超导 transmon 仅有理论锚）",
        },
        "spec": {
            "n_modes": depth["n_modes"],
            "n_mzi": depth["n_mzi"],
            "topology": "矩形（Clements）网格 · 交替砖墙层",
            "depth": depth["depth_rectangular_clements"],
            "depth_tight_bound": depth["tight_adjacency_bound"],
            "tight_bound_reachable": depth["tight_bound_reachable"],
            "depth_vs_reck_saving": depth["depth_saving_vs_reck"],
            "per_mode_loss_db": loss["rectangular_static_db"],
            "recon_fidelity": 1.0,
            "hilbert_log2_dim": round(hilbert_log2_dim(n), 2),
        },
        "depth_scan": [
            dict(mesh_depth_closed_form(k),
                 rectangular_static_db=loss_account_closed_form(k)["rectangular_static_db"],
                 triangular_static_db=loss_account_closed_form(k)["triangular_static_db"])
            for k in (4, 8, 16, 32, 64, 128, 216)
        ],
        "loss_account": loss,
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_closed": sum(1 for g in GAPS if g["closed"]),
        "gaps_total": len(GAPS),
        "artifacts": _artifact_manifest(repo_root),
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算口径（非实测签核）",
        "honest_note": QCHIP_HONEST_NOTE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。全部为闭式断言 + 红线断言。"""
    res = {}

    # ① 旗舰规模闭式
    d = mesh_depth_closed_form(216)
    res["① N=216：元件数 23220 · Reck 429 · 矩形 216 · 省 213 · 紧界可达"] = (
        d["n_mzi"] == 23220 and d["depth_triangular_reck"] == 429
        and d["depth_rectangular_clements"] == 216
        and d["depth_saving_vs_reck"] == 213 and d["tight_bound_reachable"] is True)

    # ② 矩形深度 == 紧界 == N（紧界可达）
    res["② 矩形深度 ≡ 紧下界 ≡ N（对 N=3..128 逐点）"] = all(
        (lambda m: m["depth_rectangular_clements"] == m["n_modes"]
         == m["tight_adjacency_bound"])(mesh_depth_closed_form(k))
        for k in (3, 4, 5, 8, 16, 32, 64, 128))

    # ③ 参数计数下界 ≤ 紧界 ≤ Reck 最优（三口径）
    res["③ 三口径偏序：参数界 ≤ 紧界 N ≤ Reck 2N−3"] = all(
        (lambda m: (m["parameter_count_bound"] <= m["tight_adjacency_bound"]
                    <= m["depth_triangular_reck"]))(mesh_depth_closed_form(k))
        for k in (4, 8, 216))

    # ④ 损耗账（N=216 逐项）
    L = loss_account_closed_form(216)
    res["④ N=216 损耗账：三角 1029.6 / 矩形 518.4 / 省 511.2 / 列口径 516.0"] = (
        abs(L["triangular_static_db"] - 1029.6) < 1e-9
        and abs(L["rectangular_static_db"] - 518.4) < 1e-9
        and abs(L["rect_saving_vs_triangular_db"] - 511.2) < 1e-9
        and abs(L["column_basis_db"] - 516.0) < 1e-9)

    # ⑤ 列口径低估真账（口径分离）
    res["⑤ 列口径低估每模真账（N=216 差 513.6 dB > 0）"] = (
        abs(L["column_basis_underestimates_by_db"] - 513.6) < 1e-9
        and L["column_basis_underestimates_by_db"] > 0)

    # ⑥ 时间复用贵于矩形静态（通用与省损不可兼得）
    res["⑥ 时间复用（矩形调度）贵于矩形静态 43.2 dB（= N·延迟）"] = (
        abs(L["temporal_penalty_vs_rect_static_db"] - 43.2) < 1e-9
        and L["temporal_penalty_vs_rect_static_db"] > 0)

    # ⑦ 通用性损耗地板 = 矩形静态（最省的可达通用架构）
    res["⑦ 通用性每模损耗地板 = rect_static（518.4 dB）"] = (
        L["universality_floor_kind"] == "rect_static"
        and abs(L["universality_floor_db"] - L["rectangular_static_db"]) < 1e-12)

    # ⑧ η 闭式
    res["⑧ 透射率闭式 η = 10^(−dB/10)：矩形 N=216 ⇒ 1.445e−52"] = (
        abs(L["rect_eta"] - 10.0 ** (-518.4 / 10.0)) < 1e-60 * max(1.0, 1.0)
        and 1.0e-53 < L["rect_eta"] < 1.0e-51)

    # ⑨ 输出空间维数（Borealis 量级）
    res["⑨ log2 C(216+124,125) ≈ 318.13 bit"] = (
        abs(hilbert_log2_dim(216, 125) - 318.13) < 0.02)

    # ⑩ 护栏：非法 N 抛错
    guard = False
    try:
        mesh_depth_closed_form(1)
    except ValueError:
        guard = True
    try:
        loss_account_closed_form(0)
    except ValueError:
        pass
    else:
        guard = False
    res["⑩ 护栏：N < 2 抛 ValueError"] = guard

    # ⑪ 案例卡组装 + 红线（verdict 非 PASS/ACCEPT）
    card = case_card(216, repo_root="__nonexistent_root__")
    res["⑪ 案例卡组装：九步 + 四条结论 + 缺口 9 项 + 产出物优雅降级"] = (
        len(card["milestones"]) == 9 and len(card["findings"]) == 4
        and card["gaps_total"] == 9 and card["gaps_closed"] == 8
        and card["artifacts"]["available"] is False)

    # ⑫ 🔴 不伪装实测：verdict 明标 DESIGN_BUDGET，且诚实边界齐全
    res["⑫ 不伪装实测：verdict=DESIGN_BUDGET · honest_note 含「非流片后实测」与「设计预算」"] = (
        card["verdict"] == "DESIGN_BUDGET"
        and card["verdict"] not in ("PASS", "ACCEPT")
        and "非流片后实测" in card["honest_note"]
        and "设计预算" in card["honest_note"])

    # ⑬ 🔴 LLM 不进判决：本模块零模型依赖（AST 精确解析，不看 docstring 文本）
    import ast as _ast
    _tree = _ast.parse(open(os.path.abspath(__file__), encoding="utf-8").read())
    _imported = set()
    for _node in _ast.walk(_tree):
        if isinstance(_node, _ast.Import):
            for _a in _node.names:
                _imported.add((_a.asname or _a.name).split(".")[0])
        elif isinstance(_node, _ast.ImportFrom):
            for _a in _node.names:
                _imported.add(_a.asname or _a.name)
    _banned = {"openai", "anthropic", "requests", "urllib", "http", "socket",
               "httpx", "aiohttp", "transformers", "torch", "numpy"}
    res["⑬ LLM 不进判决：模块实际 import 无 LLM/网络/数值库"] = not (_imported & _banned)

    # ⑭ 纯闭式：**模块顶层**只绑定 math / os（GET 端点微秒级，零重依赖）
    _top = set()
    for _node in _tree.body:
        if isinstance(_node, _ast.Import):
            for _a in _node.names:
                _top.add((_a.asname or _a.name).split(".")[0])
        elif isinstance(_node, _ast.ImportFrom):
            for _a in _node.names:
                _top.add(_a.asname or _a.name)
    res["⑭ 纯闭式零重依赖：顶层仅 math / os / __future__"] = _top <= {
        "math", "os", "__future__", "annotations"}

    if verbose:
        for k, v in res.items():
            print("[%s] %s" % ("PASS" if v else "FAIL", k))
    return bool(all(res.values()))


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print("qchip_case 自检：%s" % ("PASS" if ok else "FAIL"))
    raise SystemExit(0 if ok else 1)
