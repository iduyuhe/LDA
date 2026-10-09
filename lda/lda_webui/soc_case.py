"""光子计算 SoC（PIC）案例卡（WebUI 只读端点数据源）· v0.9.213 接入。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
光子计算 SoC 征程（S0–S5-ext + G6）的**只读案例卡**：把 v0.9.212 已在后端 +
CI core 落地的「用 LDA 亲手设计一颗光子计算 SoC 整芯片」全链，在首页「★ 芯片案例直达」
露成独立只读案例卡。

与 `/api/pchip_demo`（硅光张量核 / 光计算芯片 · MZI mesh）、`/api/qchip_demo`（光量子 LOQC）、
`/api/schip_demo`（超导 transmon）、`/api/ecore_demo`（电子计算芯片）**并列**：
这是 LDA 三条物理路线之外、又一条「吃自己狗粮」征程的对外窗口。

🔴 **零重计算**：本模块**不跑仿真、不 import 求解器、不解析版图**——数字取自
① 静态里程碑/结论（可回溯到 S0–S5-ext + G6 门禁与 `docs/LDA_光子计算SOC征程_*.md`）
② **纯闭式**现算（MZI 计数 N(N−1)/2）③ 对产出物只 `stat` 的元信息。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/pchip_demo`、
`/api/qchip_demo`、`/api/verification_ledger` 同属「公开只读验货」类。

🔴 **不伪装实测 / 不报 fabricated 能效**：`verdict` 恒为 `DESIGN_SIGNOFF`
（**非** ACCEPT/PASS），返回体自带 `honest_note`；模块复用 `assert_no_energy_metrics`
纪律（源码级扫描：本文件不含任何外部光学 SDK / numpy / lda_l2 / 能效键）。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "SOC_HONEST_NOTE", "JOURNEY", "SUBSYSTEMS", "FINDINGS", "GAPS",
    "INTEGRATION_CRITERIA", "LEVERS", "VERIFIED_SIZES",
    "reck_mzi_count", "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与 S0–S5-ext+G6 实绩同源 · 静态登记）═════════════════════════════
CASE_ID = "LDA-SoC · 光子计算 SoC（PIC）· S0–S5-ext + G6 全链（多核 tiling + WDM/TDM + foundry 闭集 signoff + NDA deck 替换 + 多 foundry PDK）"

#: 三档经端到端验证的网格规模（N×N 主权 mesh）。MZI 数 = N(N−1)/2（闭式）。
VERIFIED_SIZES = [
    {"n": 16, "mzi": 120, "stage": "S3", "drc": "PASS", "lvs": "ACCEPT",
     "io_ports": 32, "grating_couplers": 2, "cpo_il_db": 10.63,
     "g5": "BYPASSABLE", "mvm_rel_err": 8.2e-3, "mvm_tol": 1.5e-2,
     "cls_acc": 1.0, "layers": "SI/METAL/HEATER"},
    {"n": 64, "mzi": 2016, "stage": "S4", "drc": "PASS", "lvs": "ACCEPT",
     "io_ports": 128, "grating_couplers": 2, "cpo_il_db": None,
     "g5": "BYPASSABLE", "mvm_rel_err": 3.75e-2, "mvm_tol": 6.14e-2,
     "cls_acc": 1.0, "layers": "SI/METAL/HEATER",
     "sovereign_gds_mb": 1.8, "gds_roundtrip": "IDENTICAL",
     "resonance_um": 1.5497, "threshold_gain_cm": 82.6, "threshold_gain_limit_cm": 150.0,
     "coupling_db": 1.5, "coupling_limit_db": 3.0},
    {"n": 128, "mzi": 8128, "stage": "S4 规模上限", "drc": "PASS", "lvs": "ACCEPT",
     "note": "主权 P&R + 集成度 + 端到端保真（单核规模爬升上限，非阵列）"},
]

#: 首期必须同片集成的五个子系统
SUBSYSTEMS = [
    {"id": "SUB1", "title": "光子计算核", "detail": "N×N MZI 网格（Clements 物理综合 + DRC/LVS 签核）"},
    {"id": "SUB2", "title": "电子外设", "detail": "per-MZI 驱动 DAC + TIA + 标定 FSM（功能级，G2）"},
    {"id": "SUB3", "title": "光 IO", "detail": "GratingCoupler 阵列 + 封装光源接口（G5 外置激光可绕）"},
    {"id": "SUB4", "title": "封装光源接口", "detail": "外部激光经 G5 合规接入（不破红线）"},
    {"id": "SUB5", "title": "标定环", "detail": "CalibrationStateMachine + 可辨识性验证 + 读回反估 Vπ"},
]

#: 征程阶段（静态事实 · 可回溯门禁）
JOURNEY = [
    {"id": "S0", "title": "可行性评估", "result": "锁定应用/对标轴/光源/流片边界；确认 SoC 首期范围"},
    {"id": "S1", "title": "架构定义 v1", "result": "芯片架构总览 + 五子系统接口契约 + 集成度判据 C1–C9 + G1–G6 缺口台账"},
    {"id": "S2", "title": "平台短板补齐（G2/G3/G5）", "result": "功能级 EIC（eic_functional）+ 多层光电 GDS 组装（soc_gds_assemble）+ 冷态标定环（soc_calibration）"},
    {"id": "S3", "title": "端到端设计 + 行为验证", "result": "整芯片设计包（soc_design_package）+ C1–C9 机器核验全绿（N=16）"},
    {"id": "S4", "title": "规模爬升 G6（N 16→32→64→128）", "result": "主权 P&R 爬升 + 规模债照妖镜（奇圈多色破解 / 可辨识性条件化）；C1–C9 全绿"},
    {"id": "S5", "title": "主权 GDS 真实导出 + DRC/LVS", "result": "真 GDS 落盘 + 往返 sha256 无损 + 含 M3 + 几何 DRC（N=64）"},
    {"id": "S5-ext", "title": "G1 单片激光 + G4 foundry PDK 对接", "result": "monolithic_laser（FP 解析模型）+ foundry_pdk（AIM 公开近似层映射 + DRC 签核）"},
    {"id": "G6", "title": "收官：多核 tiling + WDM/TDM + 闭集 signoff + NDA deck 替换 + 多 foundry PDK", "result": "三大杠杆 + foundry DRC 闭集（13 条）+ NDA deck 替换机制 + 多 foundry 注册表符合性校验"},
]

#: 关键结论（平台能力增量）
FINDINGS = [
    {"title": "整芯片集成度（C1–C9 全绿）",
     "detail": "光子核 + 电子外设 + 光 IO + 封装光源 + 标定环，在同一份主权 GDS 内协同集成，"
               "机器核验 C1–C9 全部通过（非模块级全绿 = 集成无债）。"},
    {"title": "主权 GDS 真导出 + 双闸签核",
     "detail": "S5 落盘 lda_soc_{N}x{N}.gds（含 SI/METAL/HEATER/M3），往返 sha256 无损、含 M3、几何 DRC PASS。"},
    {"title": "多核 array tiling（杠杆②）",
     "detail": "已验证主权 N×N 计算核按 pitch 平移复制成 M×M 阵列（N=8 M=4 = 16 核）：阵列 DRC 0 违规、"
               "16/16 核 MVM max_rel_err 4.62e-3、跨核 IO 256 端口。"},
    {"title": "WDM 多 λ 复用（杠杆①）",
     "detail": "主权 mesh 波长相关酉真算 + demux/mux GDS DRC；100GHz ITU 致密栅格（0.8nm）"
               "规避网格色散（10nm 离带 MVM 误差 ~21% 物理极限）。"},
    {"title": "TDM 时间复用调度（杠杆③）",
     "detail": "K 帧每帧随机 Haar 酉，reck 分解重建 ≈ 机器精度；TDMController.tick() 推进帧 + "
               "重配置相位变更计数（诚实度量非物理时延）。"},
    {"title": "foundry 闭集 signoff + NDA deck 替换",
     "detail": "foundry DRC 升级为显式闭集（13 条规则，公开近似 + 逐条规格锚）；"
               "FoundryDeck schema 支持签约 NDA deck 零改动替换闭集（provenance 护栏拒绝冒充）。"},
    {"title": "多 foundry PDK 对接机制",
     "detail": "foundry_pdk_registry 注册 AIM/Tower/GF/imec 四家公开近似 PDK + 符合性校验；"
               "真实 NDA PDK 按 schema 注入即零改动生效。"},
]

#: G1–G6 缺口（首期全部闭合 · 诚实登记 foundry 真值未持有）
GAPS = [
    {"id": "G1", "title": "单片集成激光器", "status": "CLOSED（S5-ext）",
     "detail": "monolithic_laser.py（Fabry-Perot 阈值增益/谐振/耦合解析判据）；首期光源仍走 G5 外置激光可绕。"},
    {"id": "G2", "title": "电子外设超越行为级", "status": "CLOSED（S2）",
     "detail": "eic_functional.py（理想 DAC/ADC + DriverFunctional/TiaFunctional + soc_calibration_fsm）；晶体管级仍红线外。"},
    {"id": "G3", "title": "多层光电 GDS + 全 LVS", "status": "CLOSED（S2/S5）",
     "detail": "soc_gds_assemble.py 复用既有层协同组装；跨层 netlist 级 LVS 留后续。"},
    {"id": "G4", "title": "真实 foundry PDK", "status": "CLOSED（机制 · 真值未持有）",
     "detail": "foundry_pdk.py（AIM 公开近似）+ foundry_pdk_registry.py（多 foundry 注册表 + 符合性校验）；"
               "真实 NDA PDK 须签约注入，本机不持有。"},
    {"id": "G5", "title": "热串扰/工艺角标定闭环", "status": "CLOSED（冷态部分）",
     "detail": "soc_calibration.py（eo_calibration_loop ↔ CalibrationStateMachine）；"
               "热串扰/工艺角模型仍留 S5-ext 或后续。"},
    {"id": "G6", "title": "规模爬升（多核/WDM/TDM + foundry 闭集 signoff + NDA deck 替换）",
     "status": "CLOSED",
     "detail": "单核 N=16→128 + 多核 tiling + WDM/TDM + 闭集 signoff + NDA deck 替换机制；"
               "signoff_ready/conformant 仅代表主权自洽可制造性就绪。"},
]

#: 集成度成功判据 C1–C9（S3 机器核验）
INTEGRATION_CRITERIA = [
    {"id": "C1", "title": "设计包含 N 个 MZI 且 DRC/LVS 全绿", "ok": True},
    {"id": "C2", "title": "≥ N 个 per-MZI 驱动器（DAC→相移器）", "ok": True},
    {"id": "C3", "title": "≥ N 个 TIA（PD 后跨阻）", "ok": True},
    {"id": "C4", "title": "光 IO GratingCoupler ≥ 2 且 cpo 指标有效", "ok": True},
    {"id": "C5", "title": "封装光源接口存在且 G5 可绕 PASS", "ok": True},
    {"id": "C6", "title": "标定环 CalibrationStateMachine + 可辨识性通过", "ok": True},
    {"id": "C7", "title": "端到端推理精度 vs golden 落差 = 0（< 量化容差）", "ok": True},
    {"id": "C8", "title": "整芯片同一份主权 GDS 含光子+电子+IO 层", "ok": True},
    {"id": "C9", "title": "所有 calibrated 声明绑定合格物理锚", "ok": True},
]

#: 三大杠杆（与 lda_l2 模块常量同源 · 闭式/实测登记）
LEVERS = {
    "tiling": {
        "name": "多核 array tiling（杠杆②）",
        "verified": "N=8 M=4（16 核）",
        "array_drc_violations": 0,
        "per_core_mvm_max_rel_err": 4.62e-3,
        "mvm_tol": 0.05,
        "cross_core_io_ports": 256,
        "note": "tiling = 主权核几何按 pitch 平移复制；跨核无 via，不重跑阵列级 LVS 引擎",
    },
    "wdm": {
        "name": "WDM 多 λ 复用（杠杆①）",
        "lambda0_um": 1.55,
        "channel_spacing_um": 0.0008,
        "spacing_note": "100GHz ITU 栅格 ≈ 0.8nm（真实致密 WDM）",
        "mvm_tol": 0.05,
        "verified": "N=8/W=4",
        "worst_mvm_err": 7.499e-3,
        "gds_drc": True,
        "dispersion_note": "网格色散敏感；10nm 离带 MVM 误差 ~21% 物理极限 ⇒ 须致密栅格",
    },
    "tdm": {
        "name": "TDM 时间复用调度（杠杆③）",
        "default_frames": 4,
        "mvm_tol": 0.05,
        "verified": "N=8/K=4",
        "worst_mvm_err": 6.083e-16,
        "reconfig_updates": 112,
        "note": "重配置开销 = 相位变更计数（诚实度量，非物理时延）",
    },
}

#: foundry signoff（闭集 · 公开近似）
FOUNDRY_SIGNOFF = {
    "closed_set_rules": 13,
    "signoff_ready": True,
    "note": "闭集规则数值 = 公开近似 + 逐条规格锚，非 foundry NDA 真值；"
            "signoff_ready 仅代表主权自洽可制造性就绪，非真实 tape-out 授权",
    "uncovered": "密度/天线/阱邻近/金属填充/封装余量等未列入闭集的规则显式标未覆盖",
    "multi_foundry": ["AIM Photonics", "Tower Semiconductor", "GlobalFoundries", "imec"],
}

SOC_HONEST_NOTE = (
    "① 本案例是**设计&验证能力证明**（整芯片 SoC 的可设计 + 可验证集成度闭环），"
    "**非流片后实测芯片**——无 foundry 回片、无光学校准实测、无 TOPS/W 实测；"
    "② 规模数字（16/64/128）是**可设计且可验证保真度**的网格规模，是**设计容量**"
    "而非已制备器件数——误读成「已制备 128×128 光子 SoC」即为失真；"
    "③ **不报任何 fabricated 能效数字**：公开基准的 TOPS/W 是「已交付芯片」的实测/厂商标称，"
    "LDA 作为设计工具链**不产出** pj/MAC、TOPS/W（那是制造与系统级，非本平台职责）；"
    "④ **foundry NDA 真值本机不持有、未伪造**：闭集规则与多 foundry 注册表均为「公开近似 + 逐条规格锚」；"
    "`signoff_ready=True` / `conformant=True` 仅代表**主权自洽可制造性就绪**，**非真实 foundry tape-out 授权**"
    "（真实授权须由 foundry 商务签约注入 NDA deck/PDK 替换闭集）；"
    "⑤ 对标按**集成度/规模/架构正确性**（C1–C9），**不按 die 级 benchmark 数字同台比较**；"
    "⑥ 集成债不可隐藏：模块级全绿 ≠ 集成无债；C1–C9 全 PASS 才算首期成功；"
    "⑦ 零外部光学 SDK：全程不依赖 Meep / Tidy3D / Lumerical 等，物理内核平台自研。"
)

_ARTIFACT_DIRS = ("examples/sovereign_evidence", "lda/examples/sovereign_evidence")


# ═══════════════════════════ 闭式（可反向测试 · 纯 python）═══════════════════════════
def reck_mzi_count(n: int) -> int:
    """N×N 三角 Reck 分解的 MZI 元件数 = N(N−1)/2（与 S3/S4 主权 P&R 同源闭式）。"""
    n = int(n)
    if n < 1:
        raise ValueError("n 须 ≥ 1")
    return n * (n - 1) // 2


def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 `examples/sovereign_evidence/` 下 SoC 主权 GDS 产出物**元信息**（文件名 + 字节数）。

    只 `stat`，不读内容、不解析 GDS ⇒ 微秒级；目录不在本部署内则优雅降级为 `available=False`。
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
            if not nm.startswith("lda_soc_") or not nm.endswith(".gds"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [],
                "note": "主权 GDS 产出物目录不在本部署内（源码仓才含 examples/sovereign_evidence/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits,
            "root_hint": hits[0], "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数）；完整 GDS 由对应门禁落盘"}


# ═════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装光子计算 SoC 案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_SIGNOFF` —— **明标「设计&验证能力证明」而非流片实测**。
    """
    return {
        "endpoint": "/api/soc_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗光子计算 SoC 整芯片：光子核 + 电子外设 + 光 IO + "
                 "封装光源 + 标定环，同一份主权 GDS 内协同集成，机器核验集成度 C1–C9 全绿",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计&验证能力证明（非流片实测）",
        "identity": {
            "physics": "硅光子计算（N×N MZI mesh 干涉 · 相干光学线性代数）",
            "device": "任意酉矩阵（Clements 物理综合）+ 对角衰减 ⇒ 任意实/复矩阵；"
                      "DAC 下发 + TIA 读回闭环标定",
            "unit": "MZI 单元 = 相位/耦合分束器 + 可调相移器（Vπ）",
            "subsystems": "5（光子核/电子外设/光 IO/封装光源/标定环）",
            "zero_optical_sdk": True,
            "level": "系统级 SoC（区别于 /api/pchip_demo 的器件/张量核级 MZI mesh）",
        },
        "span": {
            "journey_stages": len(JOURNEY),
            "subsystems": len(SUBSYSTEMS),
            "modules": 11,
            "modules_list": [
                "eic_functional", "foundry_pdk", "foundry_pdk_registry",
                "monolithic_laser", "soc_array_tiling", "soc_calibration",
                "soc_design_package", "soc_gds_assemble", "soc_tapeout_signoff",
                "soc_tdm", "soc_wdm",
            ],
            "new_ci_gates": 11,
            "ci_core_before": 296,
            "ci_core_after": 307,
            "integration_criteria": len(INTEGRATION_CRITERIA),
        },
        "journey": JOURNEY,
        "subsystems": SUBSYSTEMS,
        "verified_sizes": VERIFIED_SIZES,
        "levers": LEVERS,
        "foundry_signoff": FOUNDRY_SIGNOFF,
        "integration_criteria": INTEGRATION_CRITERIA,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "artifacts": _artifact_manifest(repo_root),
        "honest_note": SOC_HONEST_NOTE,
    }


# ═════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器 / lda_l2）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append(f"{'PASS' if cond else 'FAIL'} | {name}")

    # ① 闭式：N=16 ⇒ 120 MZI（=16*15/2）
    chk("① reck_mzi_count(16) == 120（=N(N−1)/2）", reck_mzi_count(16) == 120)
    # ② 闭式与逐点枚举一致（N=2..128）
    ok = True
    for k in list(range(2, 129)):
        ok = ok and reck_mzi_count(k) == k * (k - 1) // 2
    chk("② reck_mzi_count(N) ≡ N(N−1)/2（N=2..128 逐点）", ok)
    # ③ 实测档 N=16/64/128 的 MZI 数 == 闭式
    chk("③ 实测档 MZI 数 ≡ 闭式（120 / 2016 / 8128）",
        VERIFIED_SIZES[0]["mzi"] == reck_mzi_count(16)
        and VERIFIED_SIZES[1]["mzi"] == reck_mzi_count(64)
        and VERIFIED_SIZES[2]["mzi"] == reck_mzi_count(128))
    # ④ 五子系统齐全
    chk("④ 五子系统齐全（光子核/电子外设/光 IO/封装光源/标定环）", len(SUBSYSTEMS) == 5)
    # ⑤ 集成度判据 C1–C9 全绿
    chk("⑤ 集成度判据 C1–C9 全 PASS",
        len(INTEGRATION_CRITERIA) == 9 and all(c["ok"] for c in INTEGRATION_CRITERIA))
    # ⑥ G1–G6 全部闭合登记
    chk("⑥ G1–G6 缺口全部登记且闭合",
        len(GAPS) == 6 and all(g["status"].startswith("CLOSED") for g in GAPS))
    # ⑦ foundry 闭集 signoff 13 条 + signoff_ready
    chk("⑦ foundry 闭集 signoff：13 条规则 + signoff_ready=True",
        FOUNDRY_SIGNOFF["closed_set_rules"] == 13 and FOUNDRY_SIGNOFF["signoff_ready"] is True)
    # ⑧ WDM/TDM 杠杆常量与 lda_l2 模块同源（跨源一致性 · 本判据内不引入 lda_l2 依赖，
    #    跨源对拍见 run_soc_ui_smoke.py 的 B 节）
    chk("⑧ WDM λ0=1.55µm · 栅格 0.8nm · tol 0.05；TDM 默认 4 帧 · tol 0.05",
        abs(LEVERS["wdm"]["lambda0_um"] - 1.55) < 1e-12
        and abs(LEVERS["wdm"]["channel_spacing_um"] - 0.0008) < 1e-15
        and abs(LEVERS["wdm"]["mvm_tol"] - 0.05) < 1e-12
        and LEVERS["tdm"]["default_frames"] == 4
        and abs(LEVERS["tdm"]["mvm_tol"] - 0.05) < 1e-12)
    # ⑨ tiling 杠杆实测（16 核 · 0 违规 · 4.62e-3）
    chk("⑨ tiling：N=8 M=4=16 核 · 阵列 DRC 0 违规 · per-core MVM 4.62e-3",
        LEVERS["tiling"]["cross_core_io_ports"] == 256
        and LEVERS["tiling"]["array_drc_violations"] == 0
        and abs(LEVERS["tiling"]["per_core_mvm_max_rel_err"] - 4.62e-3) < 1e-12)
    # ⑩ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    card = case_card(repo_root="__nonexistent_root__")
    chk("⑩ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)
    # ⑪ 🔴 不伪装实测 / 不报 fabricated 能效：verdict 恒 DESIGN_SIGNOFF + 诚实边界齐全
    note = card["honest_note"]
    chk("⑪ 不伪装实测：verdict=DESIGN_SIGNOFF · 诚实边界含「非流片后实测」/"
        "「不报任何 fabricated 能效」/「设计容量」/「NDA 真值本机不持有」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非流片后实测" in note and "不报任何 fabricated 能效" in note
        and "设计容量" in note and "NDA 真值本机不持有" in note)
    # ⑫ 🔴 零外部光学 SDK / 零 numpy / 零 lda_l2：只扫「import <name> / from <name> import」
    src = open(os.path.abspath(__file__), encoding="utf-8").read().lower()
    banned = ("numpy", "scipy", "meep", "tidy3d", "lumerical", "torch",
              "tensorflow", "jax", "lda_l2")
    hit = [b for b in banned if ("import " + b) in src or ("from " + b) in src]
    chk("⑫ 零外部光学 SDK / 零 numpy / 零 lda_l2：本模块无任何求解器/lda_l2 import", not hit)
    # ⑬ 🔴 不报 fabricated 能效数字：返回体不含任何能效键
    energy_keys = ("tops_w", "power_w", "pj_per_mac", "pj_per_bit",
                   "flops_per_watt", "top_s_w", "w_per_mac")
    flat = json.dumps(card).lower()
    hit_e = [k for k in energy_keys if k in flat]
    chk("⑬ 零能效数字：案例卡返回体不含任何能效键（tops_w/pj_per_mac/…）", not hit_e)
    # ⑭ 护栏：非法输入抛错（N < 1）
    guard = 0
    for bad in (lambda: reck_mzi_count(0), lambda: reck_mzi_count(-3)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑭ 护栏：N<1 抛 ValueError（reck_mzi_count）", guard == 2)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("光子计算 SoC 案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
