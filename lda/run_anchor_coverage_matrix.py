# -*- coding: utf-8 -*-
"""T-9 锚题覆盖矩阵生成器（33 类 × 48 锚）

用法（仓库根，CI 解释器）：
    python lda/run_anchor_coverage_matrix.py            # 写 docs/lda_anchor_coverage_matrix_2026-09-04.md

事实来源（全为权威单一来源，程序化读取）：
  * 48 锚列序/判据字段：lda_harness/benchmarks.py 的 BENCHMARK_ORDER / BENCHMARK_DEFS
  * 接线态三分类：spec['candidate'] ∈ BENCHMARK_CANDIDATES（verification_adapters.py）= 严格独立
                  （与 lda_harness/harness.py candidate_class() 同一判序）
  * 33 类（22 引擎 + 11 包）：lda_design/design_package.py 的 ENGINE_KINDS / PACKAGE_KINDS /
                  ENGINE_KIND_MAP / ENGINE_DOMAIN / _ENGINE_TITLE
  * 引擎 specs 显式锚引用：lda_design/design_engine.py _build_specs()（code 证据）

编辑性归属（本文件内 ANCHOR_HOSTS，人工维护，证据分级见证据标签）：
  code   = 引擎 specs 代码显式引用该锚（最权威）
  title  = 锚 title/metric/note 明写该器件品类（语义强对应）
  corpus = 该品类的引擎级判决锚在 48 集之外（语料锚），所列 48 锚仅为名义/物理邻居
  inferred = 编辑推断（组合/弱宿主）

重新生成 = 把 ANCHOR_HOSTS 改对后重跑本脚本即可（锚增删后统计自动重算）。
"""
from __future__ import annotations
import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # lda/
_LDA = os.path.dirname(_HERE)                                 # 仓库根
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.benchmarks import BENCHMARK_ORDER, BENCHMARK_DEFS  # noqa: E402
from lda_harness.verification_adapters import BENCHMARK_CANDIDATES  # noqa: E402
from lda_design.design_package import (                          # noqa: E402
    ENGINE_KINDS, PACKAGE_KINDS, ENGINE_KIND_MAP, ENGINE_DOMAIN, _ENGINE_TITLE,
)

DOC_PATH = os.path.join(_LDA, "docs", "lda_anchor_coverage_matrix_2026-09-04.md")

# 域顺序（光子在前、量子在后，引擎保持 ENGINE_KINDS 内部序分组展示）
_DOMAIN_ORDER = ["photon", "quantum"]

# 横向/系统层锚（不属于任何单一品类，单独成节）——伪宿主标签
PSEUDO = {
    "S1":  ("⟂系统层·光链路预算",   "纯算术 dB 级联判决；宿主=lda_chain 全部光链路设计（wdm/add_drop/耦合器/…），不细分品类"),
    "S2":  ("⟂系统层·WDM 信道规划", "信道间隔−滤波器带宽>0 纯算术；宿主=wdm 包信道规划（title 明示 WDM 信道）"),
    "S3":  ("⟂系统层·OSNR",         "ASE 级联解析；宿主=含放大光链路设计流"),
    "S4":  ("⟂系统层·量子保真度预算", "F_total=∏fᵢ 乘法级联；宿主=量子门序列/多比特系统设计流（quantum/multiqubit）"),
    "S5":  ("⟂系统层·最坏情况预算",  "工艺角最坏 margin；宿主=光链路设计流"),
    "S6":  ("⟂系统层·探测器灵敏度",  "P_rx−Sens margin；宿主=接收链路设计流"),
    "S7":  ("⟂系统层·统计预算 p5",   "MC 分布 p5（高斯闭式候选已接=严格独立）；宿主=光链路设计流"),
    "S8":  ("⟂系统层·OSNR 统计 p5",  "MC OSNR 分布 p5（已接=严格独立）；宿主=含放大链路设计流"),
    "S9":  ("⟂签核·LVS",             "版图-原理图一致性签核；宿主=全部含版图的品类（引擎/包通用，结构性不可接 C1+C3）"),
    "S10": ("⟂签核·多层 LVS",        "M1/VIA/M2 层叠签核；宿主=多层布线版图品类（结构性不可接 C1+C3）"),
    "S11": ("⟂签核·千器件规模",      "1000 器件全链路 ACCEPT；宿主=规模流水线（无独立品类）"),
    "S12": ("⟂统计·阵列分布",        "均值+下界+离群三锚 AND；宿主=WDM/CPO 多通道、量子多比特阵列（wdm/multiqubit/multiqubit_fidelity）"),
    "S13": ("⟂统计·设计良率 DFY",    "环形 FSR 光刻容差命中概率（已接=严格独立）；宿主=环类产品（add_drop/wdm）"),
    "B19": ("⟂物理·链路 passivity",  "max|T|≤1 无源链路守恒（已接=严格独立）；宿主=全部无源链路品类"),
    "B1":  ("⟂求解核·Mie 散射",      "散射效率 Q_scat（已接=严格独立）；33 类无散射体品类 ⇒ 求解核级锚（lda_solver/mie_solver）"),
    "B8":  ("⟂求解核·绝热锥度 EME",  "T→1 绝热极限（已接=严格独立）；33 类无锥度品类 ⇒ 求解核/互连级锚（EME 核，taper 内嵌于布局路由）"),
    "B17": ("⟂基础量·约瑟夫森 Ic",   "I_c=2e·E_J/ℏ；量子结参数基础量，33 类无独立宿主"),
}

# ---------------------------------------------------------------- 编辑性归属表
# key=锚 id；value=list[(宿主 kind, 证据标签, 备注)]
# 引擎宿主用 snake 键（engine_* / 包 snake 名），文档层转 CamelCase 展示。
ANCHOR_HOSTS: dict[str, list[tuple[str, str, str]]] = {
    # ---- 光子 B 锚 ----
    "B2":  [("engine_waveguide", "inferred", "EIM/slab 有效折射率；引擎 cheap=_slab_te_neff 同族（gapdoc: 波导）")],
    "B3":  [("engine_ringresonator", "inferred", "Airy 腔 FSR 无独立品类；FSR 口径方法学挂谐振腔家族（与 B4/B20 并列对照）")],
    "B4":  [("engine_ringresonator", "code", "引擎 FSR 解析锚 λ²/(n_g·2πR)，engine note 同式"),
            ("add_drop", "title", "锚对象即 add-drop 环形谐振器 drop 口传递函数")],
    "B5":  [("engine_ybranchloss", "corpus", "引擎真判决锚 E-YBRANCH-LOSS 在 48 集外；B5=理想 50/50 下限 3.0dB 守则桩（同器件名义覆盖）")],
    "B6":  [("engine_gratingeff", "corpus", "引擎真判决锚 E-GRATING-EFF 在 48 集外；B6=成熟工艺可达效率 0.5 守则桩（同器件名义覆盖）")],
    "B7":  [("engine_crossing", "title", "波导交叉串扰；引擎 IL+XT 双出口，E7=实测 XT 同器件（守则桩 vs 实证桩）")],
    "B11": [("engine_ringresonator", "title", "环形谐振器 drop 口透射谱谱形 L2（结构性不可接，见 T-4 侦察）")],
    "B14": [("engine_dcoupler", "code", "引擎 cheap=b14_dc_coupling_length，note 显式 B14"),
            ("coupler", "title", "包=方向耦合器设计闭环（D-55），锚=3dB 耦合长度")],
    "B15": [("engine_braggmirror", "inferred", "Bragg 条件 λ_B=2·n_eff·Λ；镜周期设计同族（gapdoc: Bragg）"),
            ("engine_gcoupler", "inferred", "λ_B=Λ·n_eff 同一阶相位匹配")],
    "B16": [("engine_mmi", "code", "引擎 note 显式 B16 锚（结构性不可接 C5+C3）")],
    "B20": [("engine_mzi", "inferred", "MZI FSR=λ²/(n_eff·ΔL) 同式（engine note 即 B20 物理）")],
    "B21": [("engine_phc", "code", "引擎 cheap=b21_phc_resonance，note 显式 B21（结构性不可接 C2）")],
    "B28": [("engine_mzimod", "inferred", "引擎目标 V_π（Pockels）与 B28 同物理量同闭式")],
    # ---- 量子 B 锚 ----
    "B9":  [("engine_transmon", "code", "引擎 cheap=koch_f01 即 B9 golden 同式"),
            ("quantum", "inferred", "量子逆设计包（Transmon）同物理")],
    "B10": [("quantum", "inferred", "单比特门退相干极限保真度；门层无独立引擎品类 ⇒ 量子系统/门层锚")],
    "B12": [("engine_qres", "inferred", "λ/4 超导谐振器通式（与 B22 CPW 具体化并列，同引擎宿主）")],
    "B13": [("quantum", "inferred", "双 transmon 电容耦合 J；无独立双比特引擎 ⇒ quantum 包（频率/耦合设计）"),
            ("multiqubit", "inferred", "N-qubit 频率复用读出依赖 J 间隔规划（弱）")],
    "B18": [("engine_readoutpair", "inferred", "腔 QED 增强因子 F_P=4g²/(κγ₁)；读出/比特配对物理（弱）"),
            ("readout_chain", "inferred", "色散读出链路（复用 D-88 参数，弱）")],
    "B22": [("engine_qres", "code", "引擎 cheap=b22_qres_frequency，note 显式 B22"),
            ("readout_chain", "inferred", "CPW λ/4 读出谐振器=readout 链核心元件")],
    "B23": [("engine_fluxonium", "code", "引擎 note 显式 B23 LC 极限边界校验")],
    "B24": [("engine_tcoup", "code", "引擎 cheap=b24_tcoup_geff，note 显式 B24")],
    "B25": [("engine_tuntransmon", "code", "引擎 cheap=b25_tunable_transmon_f01，note 显式 B25")],
    "B26": [("engine_readoutpair", "code", "引擎 cheap=b26_dispersive_shift，note 显式 B26"),
            ("readout_chain", "inferred", "色散位移 χ=readout 链核心设计量")],
    "B27": [("engine_czgate", "code", "引擎 cheap=b27_cz_gate_time，note 显式 B27")],
    # ---- 实证 E 锚 ----
    "E1":  [("engine_waveguide", "inferred", "SOI 波导群折射率实测 4.18±0.05（AMF racetrack 反演）；波导模式核（gapdoc）")],
    "E2":  [("engine_waveguide", "code", "候选 semivec_ng=半矢量求解核 vs 实测 n_g（SiN 300nm 平台）；引擎 cheap 同 slab 核"),
            ("engine_sinpl", "inferred", "同为 SiN 平台（但 E2=群折射率、E6=传播损耗，物理量不同）")],
    "E3":  [("engine_ringresonator", "title", "薄埋氧 SOI 微环 FSR 实测 10.44nm（结构性不可接 C4 循环）")],
    "E4":  [("engine_crossing", "corpus", "corpus E-SOI-CROSS-IL = 48 集 E4；crossing 插入损耗实测 0.18±0.03dB")],
    "E5":  [("engine_mmiel", "corpus", "corpus E-MMI-1X2-EL = 48 集 E5；MMI 过量损耗实测 0.05dB")],
    "E6":  [("engine_sinpl", "corpus", "corpus E-SIN-PL-800 = 48 集 E6；厚 SiN 传播损耗实测 0.087dB/cm")],
    "E7":  [("engine_crossing", "corpus", "corpus E-SOI-CROSS-XT = 48 集 E7；crossing 串扰实测 −41±2dB")],
    # ---- S 锚中落单品类的显式宿主 ----
    "S2":  [("wdm", "title", "信道间隔−滤波器带宽 无碰撞=wdm 信道规划判决")],
    "S4":  [("quantum", "inferred", "门序列保真度预算 ∏fᵢ"), ("multiqubit_fidelity", "inferred", "多比特保真度预算同族")],
    "S12": [("wdm", "title", "多实例 WDM/CPO 阵列分布判决"), ("multiqubit", "title", "量子多比特阵列分布判决"),
            ("multiqubit_fidelity", "title", "逐 qubit 保真度分布判决（均值+下界+离群三锚）")],
    "S13": [("add_drop", "inferred", "环形 FSR 光刻容差→命中规格概率"), ("wdm", "inferred", "多环产品良率延伸")],
}

# 0 宿主但物理上有弱归属的「孤儿锚」单独说明
ORPHAN_NOTES = {
    "B10": "单比特门退相干保真度：量子门层锚；品类宿主仅 quantum 包（○），主缺口=两比特门锚（gapdoc 钉子 C 候选）",
}


def strict_stub_sets() -> tuple[list[str], list[str]]:
    strict, stubs = [], []
    for b in BENCHMARK_ORDER:
        cand = str(BENCHMARK_DEFS[b].get("candidate", ""))
        (strict if cand and cand in BENCHMARK_CANDIDATES else stubs).append(b)
    return strict, stubs


def kind_display(kind: str) -> str:
    if kind.startswith("engine_"):
        return ENGINE_KIND_MAP[kind]
    return kind


def domain_of_kind(kind: str) -> str:
    if kind.startswith("engine_"):
        return ENGINE_DOMAIN[ENGINE_KIND_MAP[kind]]
    # 包 domain：由 design_package 构建器 kind 字段语义人工归类（add_drop/wdm/coupler=photon；
    # quantum/readout_fidelity/multiqubit_fidelity=quantum；readout_chain/multiqubit/mixed_system/
    # wdm_coupler/splitter_readout=hybrid → 归 quantum 展示组亦可，此处按光子/量子/hybrid 标注）
    _pkg_dom = {"add_drop": "photon", "wdm": "photon", "coupler": "photon",
                "wdm_coupler": "photon", "splitter_readout": "photon",
                "quantum": "quantum", "readout_fidelity": "quantum",
                "multiqubit_fidelity": "quantum", "readout_chain": "hybrid",
                "multiqubit": "hybrid", "mixed_system": "hybrid"}
    return _pkg_dom.get(kind, "hybrid")


def main() -> None:
    strict, stubs = strict_stub_sets()
    STATE = {}
    for b in BENCHMARK_ORDER:
        STATE[b] = "strict" if b in strict else "stub"

    # 行序：photon 引擎 → quantum 引擎 → 包
    eng_rows = []
    for dom in _DOMAIN_ORDER:
        for k in ENGINE_KINDS:
            if ENGINE_DOMAIN[ENGINE_KIND_MAP[k]] == dom:
                eng_rows.append(k)
    pkg_rows = [k for k in PACKAGE_KINDS]
    rows = [(k, "engine") for k in eng_rows] + [(k, "package") for k in pkg_rows]

    # kind → hosts anchors（含证据）
    kind_anchors: dict[str, dict[str, list[str]]] = {}   # kind -> aid -> evidence tags
    for aid, hostlist in ANCHOR_HOSTS.items():
        for host in hostlist:
            kind, ev = host[0], host[1]
            note = host[2] if len(host) > 2 else ""
            if kind in PSEUDO:
                continue
            kind_anchors.setdefault(kind, {})[aid] = kind_anchors.get(kind, {}).get(aid, []) + [ev]

    # 锚 → hosts（含伪宿主）
    anchor_kinds: dict[str, list[tuple[str, str, str]]] = {a: list(ANCHOR_HOSTS.get(a, [])) for a in BENCHMARK_ORDER}
    for a, (lab, note) in PSEUDO.items():
        anchor_kinds.setdefault(a, []).insert(0, (lab, "pseudo", note))

    sym = {"strict": "●", "stub": "◐"}
    ev_badge = {"code": "C", "title": "T", "corpus": "K", "inferred": "i", "pseudo": "P"}

    out = io.open(DOC_PATH, "w", encoding="utf-8")
    W = out.write
    W("# LDA 锚题覆盖矩阵（33 类 × 48 锚 · T-9）\n\n")
    W("> 生成：2026-09-04 · 生成器 `lda/run_anchor_coverage_matrix.py`（可复现：改归属表后重跑）\n")
    W("> 口径：**品类×锚覆盖** = 该锚的物理对象/判决对象落在该设计品类上。覆盖 ≠ 已接独立候选；"
      "●=严格独立已接、◐=自证桩（名义覆盖）。证据分级：**C**=引擎 specs 代码显式引用（最权威）"
      "· **T**=锚 title/metric 明写该品类 · **K**=引擎真判决锚在 48 集外（语料锚），所列 48 锚仅为名义邻居"
      "· **i**=编辑推断 · **P**=横向/系统层。\n\n")

    # ---------- 摘要 ----------
    n_eng_hit = sum(1 for k, kt in rows if kt == "engine" and k in kind_anchors and kind_anchors[k])
    n_pkg_hit = sum(1 for k in pkg_rows if k in kind_anchors and kind_anchors[k])
    pseudo_only = [a for a in BENCHMARK_ORDER if anchor_kinds.get(a) and all(ev == "pseudo" for _, ev, _ in anchor_kinds[a])]
    no_host = [a for a in BENCHMARK_ORDER if not anchor_kinds.get(a)]
    W("## 0 · 摘要\n\n")
    W(f"- 33 类 = 22 引擎（光子 15 + 量子 7）+ 11 包；48 锚（B28 + E7 + S13）；严格独立 **{len(strict)}** / 自证桩 **{len(stubs)}**\n")
    W(f"- 有 ≥1 锚宿主（48 集内）：引擎 **{n_eng_hit}/22**、包 **{n_pkg_hit}/11**\n")
    W(f"- 横向/系统层锚（无单一品类宿主）**{len(pseudo_only)}**：{', '.join(pseudo_only)}\n")
    W(f"- 零覆盖品类与接线建议见 §3；完整归属见 §2。\n\n")

    # ---------- 矩阵：按行（品类） ----------
    W("## 1 · 品类 → 锚覆盖矩阵（33 行）\n\n")
    W("每类一行：命中锚序列 `锚id(符号·证据)`；**空 = 48 集内零覆盖**。\n\n")
    W("| # | 品类（域） | 48 集覆盖锚 | 覆盖数 |\n|---|---|---|---|\n")
    idx = 0
    for kind, kt in rows:
        idx += 1
        if kt == "engine":
            name = f"**{kind_display(kind)}**（引擎）"
        else:
            name = f"**{kind}**（包）"
        hits = kind_anchors.get(kind, {})
        if hits:
            # 按 BENCHMARK_ORDER 排锚序
            cells = []
            for aid in BENCHMARK_ORDER:
                if aid in hits:
                    st = sym[STATE[aid]]
                    evs = "".join(ev_badge[e] for e in sorted(set(hits[aid])))
                    cells.append(f"{aid}{st}{evs}")
            cov = f"{' · '.join(cells)}"
        else:
            cov = "🚫 **零覆盖**"
        W(f"| {idx} | {name} | {cov} | {len(hits)} |\n")

    # ---------- 矩阵：横向/系统层 ----------
    W("\n**横向/系统层锚**（不归属单一品类，按适用层列出）：\n\n")
    W("| 锚 | 分类 | 适用层 / 宿主 | 态 |\n|---|---|---|---|\n")
    for aid in BENCHMARK_ORDER:
        if aid not in PSEUDO:
            continue
        lab, note = PSEUDO[aid][0], PSEUDO[aid][1]
        W(f"| {aid} | {lab} | {note} | {sym[STATE[aid]]} |\n")

    # ---------- 锚宿主表 ----------
    W("\n## 2 · 锚 → 归属明细（48 行）\n\n")
    W("| 锚 | 判据态 | oracle | 宿主（品类 / 横向层） | 证据 |\n|---|---|---|---|---|\n")
    for aid in BENCHMARK_ORDER:
        d = BENCHMARK_DEFS[aid]
        st = "严格独立" if STATE[aid] == "strict" else "自证桩"
        hostcells = []
        for (kind, ev, note) in anchor_kinds.get(aid, []):
            if ev == "pseudo":
                hostcells.append(kind)
            else:
                hostcells.append(f"{kind_display(kind)}")
        host_s = "、".join(hostcells) if hostcells else "🚫 **零宿主**"
        notes = []
        for (kind, ev, note) in anchor_kinds.get(aid, []):
            if note:
                notes.append(f"{kind_display(kind)}: {note}")
        if aid in ORPHAN_NOTES:
            notes.append(ORPHAN_NOTES[aid])
        evs = "".join(sorted({ev_badge[e] for (_, e, _) in anchor_kinds.get(aid, [])}))
        extra = " ｜ " + "；".join(notes) if notes else ""
        W(f"| {aid} | {st} | {str(d.get('oracle',''))} | {host_s} | {evs or '—'}{extra} |\n")

    # ---------- 零覆盖区 ----------
    W("\n## 3 · 零覆盖区与缺口清单\n\n")
    W("### 3.1 品类零覆盖（48 集内无任何锚宿主）\n\n")
    zero_rows = [(k, kt) for (k, kt) in rows if not kind_anchors.get(k)]
    if zero_rows:
        W("| 品类 | 类型 | 缺口说明 |\n|---|---|---|\n")
        for (k, kt) in zero_rows:
            note = ""
            if k == "engine_phaseshifter":
                note = ("热光相移器：唯一零覆盖引擎。引擎自锚 D-73（相移效率 deg/mW）在 48 集外；"
                        "48 集最近邻 B28 为电光 Pockels（机制不同，不可顶替）⇒ 建议新锚 B29（热光相位效率，D-73 升格）")
            elif k == "readout_fidelity":
                note = "单发读出保真度预算：48 集无读出 SNR/保真度物理锚（gapdoc 08-29 已列缺口「钉子 E 读出 SNR 锚」）"
            elif k == "mixed_system":
                note = "多环 WDM × 量子读出混合巨型系统：组合系统无直接锚；组成器件锚在宿主品类，整系统验收走 GC-*（48 外）"
            elif k == "wdm_coupler":
                note = "耦合器×WDM 组合（FDTD 标定 gap）：复合弱；组成锚 B14（DC）与 B4（环）在其宿主品类"
            elif k == "splitter_readout":
                note = "方向耦合器×量子读出（分束供电控制）：复合弱；组成锚 B14/B22 在宿主品类"
            W(f"| {k}（{kind_display(k) if k.startswith('engine_') else k}） | {'引擎' if kt=='engine' else '包'} | {note} |\n")
    else:
        W("（无）\n")
    W("\n### 3.2 仅名义覆盖（宿主锚全为自证桩 / corpus 判决锚在 48 外）\n\n")
    W("| 品类 | 名义锚 | 判据态 | 说明 |\n|---|---|---|---|\n")
    rows_nominal = []
    for (k, kt) in rows:
        hits = kind_anchors.get(k, {})
        if hits and all(STATE[a] == "stub" for a in hits):
            rows_nominal.append((k, kt, hits))
    if rows_nominal:
        for (k, kt, hits) in rows_nominal:
            aids = ", ".join(sorted(hits))
            notes = []
            for a in hits:
                for (kind2, ev, note) in ANCHOR_HOSTS.get(a, []):
                    if kind2 == k and note:
                        notes.append(note)
            W(f"| {kind_display(k) if k.startswith('engine_') else k} | {aids} | 全桩 | {'；'.join(notes)[:200]} |\n")
    else:
        W("（无）\n")
    W("\n### 3.3 横向/无载体锚（不归属单一品类）\n\n")
    W("| 锚 | 判据态 | 说明 |\n|---|---|---|\n")
    for a in pseudo_only + no_host:
        st = sym[STATE[a]]
        note = ""
        for (kind, ev, n2) in anchor_kinds.get(a, []):
            if ev == "pseudo":
                note = n2
        if a in ORPHAN_NOTES:
            note += ("；" if note else "") + ORPHAN_NOTES[a]
        W(f"| {a} | {st} | {note} |\n")

    W("\n### 3.4 接线优先级建议\n\n")
    W("1. **热光相移器零锚 → 新锚 B29**（D-73 升格进 48 集）：唯一零覆盖引擎，工作量小；与 B28 电光并列构成有源调制双锚。\n")
    W("2. **readout_fidelity 零锚 → 读出 SNR 锚**（gapdoc 钉子 E）：单发读出保真度是量子读出货架卖点，缺物理 ground。\n")
    W("3. **B5/B6/B7 守则桩**：非接线问题而是 ORACLE 缺口（Meep/Tidy3D 场级，C 期锁）；解锁后 YbranchLoss/GratingEff/Crossing "
      "引擎获得集内真锚。\n")
    W("4. **引擎真判决锚入集**：E-YBRANCH-LOSS / E-GRATING-EFF / D-73 三处引擎级判决锚在 48 集外 ⇒ 建议评估升格，"
      "否则 48 锚口径对 YbranchLoss / GratingEff / PhaseShifter 三类覆盖失真（矩阵 K 证据即此）。\n")
    W("5. taper（B8）与散射（B1）两无载体锚指向品类缺口：无「锥度/散射体」设计引擎 ⇒ 可评估新增品类，或明示 B8 归互连级。\n")

    # ---------- 口径与方法 ----------
    W("\n## 4 · 口径、方法与诚实边界\n\n")
    W("- **数据源**：BENCHMARK_ORDER/DEFS（benchmarks.py）、BENCHMARK_CANDIDATES（verification_adapters.py）、"
      "ENGINE_KINDS/PACKAGE_KINDS/ENGINE_DOMAIN/_ENGINE_TITLE（design_package.py）、引擎 specs（design_engine.py）。"
      "接线态判序与 `harness.candidate_class()` 同源：`spec.candidate ∈ 登记表 ⇒ strict`。\n")
    W("- **包级品类注意**：包是装配级设计流，其整包验收门 = S 层系统/统计/签核锚 + GC-* 整芯片对标（29 条，48 集外）"
      "；本矩阵只标「组成器件的物理锚」→ 包行稀疏是预期的，不直接等于「包不可验货」。\n")
    W("- **K 证据含义**：corpus 类引擎（YbranchLoss/GratingEff 等）的引擎级判决锚（E-YBRANCH-LOSS/E-GRATING-EFF）"
      "不在 48 锚集内 ⇒ 表中宿主为名义/物理邻居（B5/B6），勿误读为「该品类已被 48 锚严格覆盖」。\n")
    W("- **推断标记**：所有 `i`（inferred）归属为编辑判断，供评审；`T/C` 为代码/标题直接证据。"
      "修正归属 = 改 `run_anchor_coverage_matrix.py` 的 ANCHOR_HOSTS 后重跑。\n")
    W("- 结构性不可接桩依据：`docs/anchor_wiring_survey_2026-09-03.md`（S9/S10 违 C1+C3、E3 违 C4、B21 违 C2、B16 违 C5+C3、B11 C1/C2/C4）。\n")
    W("- 无载体锚 B1/B8/B17 虽零品类宿主，但 B1/B8 为严格独立（求解核级验证）、B17 为确定性基础量 —— 属「能力有、品类载体缺」，非验证缺口。\n")
    out.close()
    print(f"OK strict={len(strict)} stubs={len(stubs)} → {DOC_PATH}")


if __name__ == "__main__":
    main()
