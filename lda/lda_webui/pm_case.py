# -*- coding: utf-8 -*-
"""光子存储阵列案例卡（WebUI 只读端点数据源）· PM 征程 M0–M5。

定位
----
光子存储征程 PM-M0…M6 的**只读案例**：用 LDA 亲手设计一条**非易失光子存储
单元 → 阵列 → 外设与系统 → 国际对标收官**（Si 波导 + GST 相变段 + 双侧微加热器
+ 电极 pad），走完 **P&R → 布线路由 → 几何 DRC/LVS → 独立 GDS 字节复核 →
设计预算 → 读出/写驱动行为级 → 系统误码预算 → 2.5D 装配签核 → 规格锚逐条
对拍** 全链路，并出**真 GDSII**。

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不跑
P&R、不 import 求解器、不解析 GDS** —— 全部数字取自
① 静态里程碑/结论（人工登记，可回溯到门禁与 report）
② **预生成报告 JSON**（`examples/photo_memory/lda_pm_m3_report.json` 与
   `lda_pm_m4_report.json`，由货架脚本 `build_pm_m3.py` / `build_pm_m4.py` 产出；
   本模块只 `json.load` + `stat`）。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_SIGNOFF`（**非** ACCEPT/PASS），
返回体自带 `honest_note`；DRC 限值为**自建设计规则**（非 foundry PDK deck）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "PM_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "STATIC_SNAPSHOT", "case_card", "run_selfchecks",
]

CASE_ID = "LDA-PM · 非易失光子存储阵列版图（GST 相变 · 电辅助写）"

#: 单元/阵列的**版图契约**（与 `lda_l2.primitives` / `gds_export` 同源）
PCM_LAYERS = {"SI": 1, "PCM": 5, "HEATER": 6}
PCM_PORTS = ["in", "out", "h1", "h2", "h3", "h4"]

PM_HONEST_NOTE = (
    "① 本案例是**设计期签核**（版图 + 几何 DRC + LVS + 设计预算），**非流片、非实测**"
    "——无实测开关比/保持时间/循环寿命，无 foundry 回片；"
    "② DRC 限值是**自建设计规则**（公开工艺近似 + 探针接触常识），"
    "**非任何 foundry 的 PDK deck**；"
    "③ 单元插损含 **Γ（模场重叠）**——v0.9.198 起 **Γ 已有自研场求解标定**"
    "（`pm_gamma`：半矢量场法 + 全矢量**独立离散** ⇒ 主账 ≈0.084、方法学区间 "
    "[0.077, 0.093]；🔴 计算值**不作 golden**，缺口 PM-G2 已结算）；"
    "本卡版图数字仍按**假设 Γ=0.05** 出图 ⇒ 🔴 **两口径并报**：`L ∝ 1/Γ` ⇒ 按标定 Γ "
    "重标定为 **6.556 µm / pitch 13.586 µm**（现值 11.015 / 18.045 µm），且**现役设计点越出"
    "标定口径可行窗上界**（+15.3% ⇒ 读出饿死）= 缺口 **PM-G11 开放**；"
    "**每 π 损耗与 M1 可行性判据 r 与 Γ 无关**（Γ、L 同时约掉，门禁现算互等证明）；"
    "跨来源材料常数离散度 >1 个数量级 ⇒ **任何单值结论都是伪精度**；"
    "④ 单元间距由 **k_iso × L_max** 给出，`k_iso` 是**设计选择**（不是物理常数）"
    "——本卡并报 L_max 的两个口径（扩散 / 集总 RC），不假装它是真值；"
    "⑤ 阵列总插损是**串行累加**（N × 单元），**不含**单元间连接波导的传播损耗"
    "（该损耗无本项目锚 ⇒ 不编数）；"
    "⑥ **无电学/热学联仿**：微加热器的电压/电流/焦耳热分布、热-光耦合动力学"
    "不在本档（属器件级 T1 与电路级 T2 锁死区）；"
    "⑦ 规模数字是**版图容量**（可排布且可签核的单元数），**非**已制备器件数；"
    "⑧ **不报 pJ/bit、fJ/op、TOPS、TOPS-W 类能效指标**（红线）；"
    "⑨ 全程零外部 EDA/光学框架（C 级自主，numpy/标准库自研），"
    "判决为死标量比对，**LLM 不进判决路径**；"
    "⑩ M4 外设为**行为级**：读出链的 PD 响应度 / 加热器方阻取**公开工程典型区间**"
    "（非实测、非逐条 DOI），读出速率 / 输入光功率 / 驱动摆幅 / EIC 通道 pitch 为"
    "**设计假设** ⇒ 只报区间与恒等式，**不报器件级真值**；焦耳热分布 / 热-光耦合"
    "属 T1/T2 锁死区；"
    "⑪ 系统误码预算的 drift 段（v0.9.193 起）主账算自**光学域实测上界锚**（Cheng 2019 "
    "Sci. Adv. eaau5759：器件级 10⁴ s 无可测透射漂移 + 编程 SD 0.35% 检测下限 ⇒ "
    "ν_T ≤ 3.80e-4，纯算术推导）；ν_T 是**上界**非点值 ⇒ 保持时间结论是**下界**语义；"
    "漂移函数形式 ΔT/T ≈ ν·ln(t) 仍是模型假设（锚只钉住速率上界）。M4 原电学域跨域"
    "代理口径（ν≈0.12）**并报可查**（`drift_proxy` 字段）：该口径下瓶颈=drift、"
    "16 电平保持 ~1.7 秒 —— 两口径差 315.8×，判结论前必须先选对口径。"
)

# ═══════════════════════ 四段征程（静态事实 · 可回溯门禁）════════════════════
# 🔴 口径（v0.9.191 修正）：`gate` = 该档**后端门禁判据数**，须与对应 smoke 实跑的
#   `[PASS]` 计数逐档相等（可人工复核 `grep -c '\[PASS\]'`）：
#   M0 `run_pm_m0_smoke`=33 · M1 `run_pm_m1_smoke`=24 · M2 `run_pm_m2_smoke`=40 ·
#   M3 `run_pm_m3_smoke`=22 · M4 `run_pm_m4_smoke`=25 · M4b `run_pm_g7_settlement_smoke`=20 ·
#   M5 `run_pm_m5_smoke`=21 · M6 `run_pm_m6_smoke`=33 · M6b `run_pm_g2_smoke`=28。
#   🔴 v0.9.194 起**不再靠人工复核**：`run_webui_pm_render_path_smoke` 的 **W8** 会实跑
#      上表 8 个门禁并数**行首** `[PASS]` 行，与卡内 `gate` 逐档对照（缺映射即红）；
#      **W9** 再把 `run_ci_regression.py` 注释里手写的「N 判据」也实跑对照
#      —— 治「同一份数字手写三处、只锁住一处」的漂移。
#   🔴 前端渲染门禁 `run_webui_pm_render_path_smoke`(=29) 是**另一个门禁**，不并入本表
#      —— 各档没有对应前端门禁，混口径会让跨档数字不可比。
#   🔴 血案：M3 曾误登记 `gate=62`（把「后端判据 + 前端判据 + 案例卡自检 + 探针」混成
#      一个数），与 M0/M1/M2 口径不一致 ⇒ 本版修正为 22（= smoke 实跑值）。
MILESTONES = [
    {"id": "M0", "code": "v0.9.187", "title": "单元闭式基线 + 相变材料锚库",
     "gate": 33,
     "result": "🔴 核心闭式律：每 π 损耗 IL_π ≡ (10/ln10)·2πk/Δn —— **Γ 与器件长度"
               "同时约掉**；单元双态对比度 28.2–489.4 dB（跨 4 个独立来源，"
               "离散 15.2×）⇒ 一律区间口径"},
    {"id": "M1", "code": "v0.9.188", "title": "多电平设计层（JMAK 晶化动力学）",
     "gate": 24,
     "result": "几何无关可行性判据 r = k_a/(k_c−k_a) ≤ 0.198（**Γ 与 L 同约掉**）；"
               "GST 4/5 来源可行 ⇒ 设计点 L = 11.01 µm · 级间距 6.57% · "
               "worst BER 4.78e-14；4 bit/单元（16 电平）"},
    {"id": "M2", "code": "v0.9.189", "title": "热-可靠性层（瞬态热 + 非晶 drift）",
     "gate": 40,
     "result": "可非晶化最大膜厚 L_max **双口径**（扩散 768–879 nm / 集总 RC 240–272 nm）；"
               "冷却时间 τ_cool ≈ 1.3 ns ≪ 脉冲 ⇒ 冷却不是瓶颈；电学域保持窗口 "
               "34/199/1162 s（log_range 2/3/4 decade）；🔴 光学域 drift **无直接锚**"
               "⇒ 派生缺口 PM-G7 如实开放"},
    {"id": "M3", "code": "v0.9.191", "title": "阵列版图（真 GDS + DRC/LVS + 独立复核）",
     "gate": 22,
     "result": "新器件原语 **PCMCell**（五处契约同步）；单元间距 = max(k_iso×L_max, "
               "工艺间隙) ⇒ pitch 18.05 µm；1×N 与 R×C 两种阵列；"
               "**从最终 GDS 字节独立解码复核**（层 5 = 单元数、层 6 = 6×单元数）；"
               "规模档 4/8/16/32 单元 + 4×8 全部 **DRC PASS + LVS ACCEPT(0 违规)**"},
    {"id": "M4", "code": "v0.9.192", "title": "外设与系统（读出链 + 写驱动 + 系统预算 + 2.5D）",
     "gate": 25,
     "result": "读出链 `T→I_pd→V_TIA→判决→BER`（行为级）：存储读出**低频高灵敏** ⇒ "
               "TIA 反馈电阻可取带宽上界 ⇒ 灵敏度 −39.8 dBm、余量 **9495×**"
               "（读出不是瓶颈）；写驱动行为级 `R_h` 183.6–917.9 Ω、与 M1 脉宽动态范围"
               "对齐；🔴 **系统瓶颈 = drift**（当时代理口径：ε_drift 2.07 ≫ ε_write "
               "0.029 ≫ ε_read 3.1e-5）⇒ 若与电学域同阶，16 电平保持仅 **1.7 秒**"
               "（PM-G7 由「缺口」升级为「系统级阻塞项」）；2.5D 装配签核 ⇒ "
               "**EIC 通道 pitch(50 µm) > PIC 单元 pitch(18.05 µm) ⇒ 密度瓶颈在电域**"},
    {"id": "M4b", "code": "v0.9.193", "title": "PM-G7 结算（光学域 drift 实测锚 → 主账口径翻转）",
     "gate": 20,
     "result": "三条 DOI 级**实测锚**落库（Cheng 2019 Sci. Adv. eaau5759 器件级 10⁴ s "
               "无可测透射漂移 / Kalb 2003 JAP 4908 双分子弛豫 E_iso=1.76 eV / "
               "Ríos 2015 Nat. Photon. 8 电平「数十年」声明）⇒ ν_T 上界 **3.80e-4**"
               "（0.35% 检测下限 + 纯算术推导，锚内字段重算守卫）；M4 系统预算主账 "
               "drift 段改算自光学域锚 ⇒ **口径翻转**：1 年保持瓶颈 drift→**write**、"
               "系统 BER 0.4047→**3.98e-62**（all_ok 翻绿）、保持下界 ~10^74 s；"
               "旧电学代理口径**并报可查**（两域差 **315.8×**）"},
    {"id": "M5", "code": "v0.9.194", "title": "国际对标收官（规格锚逐条对拍表 + 缺口台账终态）",
     "gate": 21,
     "result": "对拍表 **7 行**：电平数 16 vs 文献实测最大 13（比值 1.23 · **设计目标，"
               "非流片实测**）· 写脉冲能量与光写入同量级（比值 3.39 · 🔴 电辅助 vs "
               "光写入**口径差**显式）· 胞长 11.01 vs 2–5 µm · 二元对比度 0.70 vs "
               "1.02 dB（保守侧）· drift 行=**自洽检查**非独立对标（上界推导自同一来源）· "
               "🔴 **endurance 行=不可判**（无模型 ∧ 无器件级循环数锚 ⇒ **PM-G10**）· "
               "密度行=无同口径文献锚（不比）。**收官口径：知道自己每项站在哪，"
               "不是「全面领先」**"},
    {"id": "M6", "code": "v0.9.195", "title": "相位域（干涉/谐振）多电平口径（PM-G6 结算）",
     "gate": 33,
     "result": "🔴 与 M1 振幅域**镜像**的核心律：相位域多电平可行 ⇔ IL_π ≤ IL_budget "
               "⇔ **FOM = Δn/(8.6859k) ≥ π/IL_budget**（Γ 与 L 同时约掉 ⇒ 材料定能力、"
               "几何只定窗口位置）；MZI 读出用**等强度间距**精确反演 φ=2·arccos(√I)"
               "（cos² 非线性 ⇒ 最小相位间距落在正交点）；材料 FOM 8.83e4 rad/dB vs "
               "器件锚 Delaney 2020 **29 rad/dB** ⇒ 差 **3045×**（器件损耗几乎全来自"
               "非材料项，两条锚族并报不可互换）；位深 **4.31 bit**（同源 9 fJ · "
               "BER 1e-12）⟷ 器件实测 **6-bit**（逆解需 **100.7 fJ** ⇒ 11.2×，"
               "能量-位深 trade-off 显式）；🔴 **残余边界**：相位漂移无独立定量锚 ⇒ "
               "定量保持性仍开放（与 PM-G7 的分野）"},
    {"id": "M6b", "code": "v0.9.198", "title": "PM-G2 结算（Γ 场求解标定 ⇒ 抓出跨档断口 PM-G11）",
     "gate": 28,
     "result": "Γ 从**假设值**升级为**自研标定**：四条**方法学独立**路径 —— 半矢量 collocated "
               "场法（主账 **0.08401**）/ 全矢量 staggered（**独立离散**）0.08240（rel 1.9% ⇒ "
               "「换一套离散、值不变」）/ 微扰法 0.07708 / 1D 平板（独立维度）0.09269 ⇒ "
               "区间 **[0.077, 0.093]**；网格收敛 1.55%、窗口不变性 1.4e-05；"
               "n_pcm 现算多源均值 3.290；🔴 `claim_kind=simulation` ⇒ **计算值永不作 golden**。"
               "🔴 **结算即抓出跨档断口**：`L ∝ 1/Γ` ⇒ 按标定 Γ 可行窗 [3.559, 9.553] µm、"
               "设计点应为 6.556 µm，而现役版图 11.015 µm **越窗上界 +15.3% ⇒ 读出饿死** ⇒ "
               "登记 **PM-G11（开放）**、两口径**并报**；Γ-无关量（IL_π / M1 判据 r / 相位域 FOM）"
               "**现算互等**不受影响"},
]

# 各档**后端**突变探针数（与各 smoke 输出的 `[PASS] P*` 计数一致；派生用，勿写死合计）
MILESTONE_PROBES = {"M0": 6, "M1": 5, "M2": 7, "M3": 5, "M4": 5, "M4b": 3, "M5": 4,
                    "M6": 7, "M6b": 8}

FINDINGS = [
    {"title": "热串扰间距是版图的**物理约束**（不是随意留白）",
     "detail": "相邻单元间距 = `k_iso × L_max`，`L_max` 取自 M2 的热扩散口径上界"
               "（0.8788 µm）⇒ 8 个扩散长度 = 7.03 µm，**大于**工艺间隙（6.0 µm）"
               "而成为 binding 约束 ⇒ 单元 pitch 18.05 µm。若热学给不出更小的 "
               "L_max，版图密度就上不去 —— 这是「材料/热学结论直接改版图」的实证。"},
    {"title": "光学 IO 必须**引出**，否则光栅与电极 pad 几何打架",
     "detail": "GratingCoupler 的齿区沿 y 伸出约 10 µm，而 PCM 单元的电极 pad 就在"
               "光端口旁（y = ±1.1 µm）⇒ 直接放光栅会与 pad 重叠。设计上在总线两端加"
               "**引出波导**（20 µm），把光栅推到远离 pad 处；多总线阵列的行间距"
               "（16 µm）亦由「光栅高度 + pad 半高」定出。"},
    {"title": "端口归属的**容差纪律**决定了器件几何",
     "detail": "LVS 以 1.0 µm 容差把布线端点归到最近端口。若电极 pad 中心离波导端点"
               "在容差内，端点会退化为「靠更近取胜」的脆弱判定 ⇒ 设计上把 "
               "`heat_gap` 取 0.35 µm（电极中心 y = 1.10 µm > 容差）使归属**无歧义**。"},
    {"title": "签核判决不读生成端结论：从**最终字节**独立解码复核",
     "detail": "阵列以 flat 导出（不做 AREF 压缩），由自写的最小 GDSII 记录流解析器"
               "（**刻意不复用** `gds_export` 解码器）从字节解出层分布："
               "层 5 元素数必须**恰等于**单元数、层 6 必须**恰等于** 6× 单元数，"
               "且必须真的走到 ENDLIB（截断即拒）。这与「声明闭合 ⇔ 证据机器可查」"
               "同一条纪律。"},
    {"title": "吃狗粮抓出的**框架级真缺陷**：端口锚点缓存被 id 复用毒化",
     "detail": "本档首次在同一进程内多次构建阵列时暴露：`placement.port_abs` 的组件"
               "索引缓存**仅以 `id()` 为键**，上一批对象被 GC 后新对象复用同一 id ⇒ "
               "命中陈旧索引 ⇒ 端口偏移静默退回器件原点 ⇒ 51 处 LVS 假红。已修："
               "缓存值**持有对象引用 + 身份校验 + 组件数版本**；并把 `port_abs` 的"
               "「实例不在 link ⇒ 静默返回器件原点」改为 **raise**。"},
    {"title": "存储读出与通信链路**口径本质不同**：低频 ⇒ 大转阻换灵敏度",
     "detail": "光子存储是**存储读**（kHz~MHz），不是 GBd 通信链。TIA 带宽 "
               "`f_3dB = 1/(2π R_f C_f)` ⇒ 读出速率越低，允许的 `R_f` 越大；而热噪声 "
               "`σ_th·|Z| ∝ √R_f` 使 `SNR ∝ √R_f`（热噪声主导）⇒ **在带宽可行域内"
               "取最大 R_f**。本档 R_f 设计点 20 kΩ（带宽上界 79.6 MΩ）⇒ 读出灵敏度 "
               "−39.8 dBm、对 1 mW 读光的余量 **9495×** ⇒ **读出电路不是系统瓶颈**。"},
    {"title": "🔴 系统瓶颈是 drift（M4 主账 = **电学域跨域代理**口径）—— 把 PM-G7 升级为「阻塞项」",
     "detail": "三段等效电平误差：ε_write 0.029（驱动时序量化）· ε_read 3.1e-5（读出"
               "电路）· **ε_drift 2.07**（保持 1 年 · 电学域 ν 上界代理）。前两者都远小于 1，"
               "唯独 drift 段远超间距 ⇒ 系统 BER 0.40，逆解 16 电平保持仅 **1.7 秒**。"
               "⇒ 光学域 drift 锚（PM-G7）不闭合则寿命结论不可给。（M4 结算前口径；"
               "结算后的主账翻转见下条）"},
    {"title": "🔴 PM-G7 结算 ⇒ **口径翻转**：主账瓶颈 drift → **write**（旧口径并报不删）",
     "detail": "Cheng 2019（Sci. Adv. eaau5759）器件级实测「10⁴ s 无可测透射漂移」"
               "（13 电平 · probe 0.1 mW）+ 编程 SD 0.35% 检测下限 ⇒ ν_T ≤ 3.80e-4"
               "（上界 · 纯算术推导）。主账 drift 段 ε 从 2.072（电学代理）降到 0.00656 "
               "⇒ 1 年保持系统 BER 从 0.4047（all_ok=false）翻到 **3.98e-62"
               "（all_ok=true）**，瓶颈翻转为**写量化**（占 97.6%）；保持下界 ~10^74 s。"
               "两域 ν 相差 **315.8×** —— 跨域代理会把光学域判决带偏 316 倍，"
               "这正是缺口要逐条结算的原因。"},
    {"title": "2.5D 集成密度瓶颈在**电域**（EIC 通道 pitch > PIC 单元 pitch）",
     "detail": "PIC 单元 pitch 18.05 µm（M3 由热串扰咬合定出）；本档 2.5D 装配假设 EIC "
               "通道 pitch 50 µm ⇒ EIC die（400 µm 宽）比 PIC die（197 µm 宽）还宽 ⇒ "
               "**系统密度受 EIC 约束**。临界值 = PIC pitch ⇒ **EIC 通道 pitch 须 ≤ "
               "18.05 µm 才不成为瓶颈**（这是给电路设计方的硬指标）。"},
    {"title": "🔴 国际对标收官口径：**知道自己每一项站在哪**（M5 · 不是「全面领先」）",
     "detail": "逐条对拍 7 行：LDA 全部数字是**闭式/行为级设计值**（无流片实测），"
               "文献值全部 **DOI 级器件实测**；比值仅判量级（三带规则 0.5–2 / 2–5）。"
               "两个「不可判」如实登记：endurance 无模型（**PM-G10**）、密度无同口径"
               "文献锚（单胞演示无阵列）。drift 行是**自洽检查**（上界推导自同一来源），"
               "不是独立对标——真正独立对标需第二来源实测。"},
    {"title": "🔴 Γ 标定暴露跨档断口：**按假设出的设计点，在标定口径下读不出来**（PM-G11）",
     "detail": "PM-G2 把 Γ 从「假设 0.05」升级为「自研标定 0.084 ±10%」——但这不是换个数就完事："
               "M1 可行窗两端与设计点均 `L ∝ 1/Γ`（dB 预算固定、每 µm 损耗 ∝ Γ）⇒ "
               "**1/Γ 律**给出按标定 Γ 的窗 [3.559, 9.553] µm 与设计点 6.556 µm。"
               "结论：现役版图（设计点 11.015 µm，按 0.05 出图）**越出标定窗上界 15.3%** ⇒ "
               "在该口径下非晶态透射率跌破读出门限（**读出饿死**）。"
               "两条方法论教训：① **「用的假设更小」≠「更保守」** —— 长度方向确实偏大（对面积保守），"
               "但可行窗同步缩 ⇒ 设计点反而**不保守**；② **能约掉 Γ 的结论才是稳的** —— "
               "IL_π / 可行性判据 r / 相位域 FOM 三条门禁现算互等（rel 2e-16）⇒ 材料定能力的主结论"
               "不受此断口影响，受影响的只有**几何绝对值**。已登记 PM-G11 并两口径并报。"},
]

GAPS = [
    {"id": "PM-G2", "title": "模场重叠因子 Γ 的场求解标定 —— **已结算（v0.9.198 · 证据链机器可查）**",
     "detail": "结算前：Γ 为**纯假设参数**（0.05），单元绝对插损/长度结论对它线性敏感"
               "（每 π 损耗与 Γ 无关，闭式已证）。"
               "结算证据链（`pm_gamma` 四条**方法学独立**路径 + 门禁 `run_pm_g2_smoke` "
               "28 判据/8 探针 + `pm_m0._ev_g2` 读**现算**判定，不读字面量）："
               "① **半矢量 collocated 本征模场法**（主账）= 0.08401；"
               "② **微扰法**（同一求解器两次本征值，Δn_eff/Δn_bulk）= 0.07708（rel 8.2%）；"
               "③ **全矢量 staggered Yee（独立离散）** = 0.08240 —— 🔴 **换一套离散、值不变**"
               "（rel 1.9%）⇒ 「实现无关」的强证据；④ **1D 垂直平板（独立维度）** = 0.09269。"
               "方法学区间 **[0.07708, 0.09269]**；收敛证据：网格 h 0.02→0.01 漂移 1.55%（半矢量）"
               "/2.68%（全矢量）、窗口 L=3↔4 相对差 1.4e-05。对照（三带规则）：vs 假设 0.05 "
               "比值 1.680（same_order，**假设偏低**）· vs 文献器件隐含 0.0922 比值 0.911"
               "（same_order · 不同几何/材料，仅交叉参照）。n_pcm 由 `pm_matlib.nk()` "
               "**现算**多源均值（=3.290）而非字面量。🔴 `claim_kind=simulation`"
               "（计算值**永不作 golden**）；零外部 EMC 框架（纯 numpy，无 Meep/Tidy3D）。"
               "**残余边界（如实开放）**：Γ 是**仿真值**、无本项目/文献对**同一几何**的实测锚 "
               "⇒ 只作设计取值依据与区间，绝对插损结论仍是**设计值**（非实测，见 PM-G9/PM-G8 "
               "的同类锁死）；由它**派生**的版图重标定登记为 **PM-G11（开放）**。"},
    {"id": "PM-G11", "title": "Γ 标定后的全链设计点/版图重标定 —— **开放（v0.9.198 新登记）**",
     "detail": "🔴 **Γ 标定 ⇒ 吃狗粮抓出的跨档断口**（不是新增功能，是**已有数字的口径不一致**）："
               "M1 振幅域可行窗两端与设计点均 `∝ 1/Γ`（每 µm 损耗 ∝ Γ、dB 预算固定）⇒ "
               "**L_mid(Γ_cal) = L_mid(Γ_as)·Γ_as/Γ_cal**（1/Γ 律，门禁 rel=1.4e-16 复核）。"
               "按假设 Γ=0.05：窗 [5.979, 16.050] µm、设计点 **11.015 µm**、pitch 18.045 µm；"
               "按标定 Γ=0.084：窗 [3.559, 9.553] µm、设计点应为 **6.556 µm**、pitch ≈13.586 µm。"
               "⇒ 🔴 **现役设计点 11.015 µm 越出标定口径窗上界 9.553 µm（+15.3%）**，"
               "在标定口径下**非晶态透射率跌破读出门限（读出饿死）** ⇒ M3 版图 / M4 系统预算 / "
               "M5 对拍表的**绝对**长度类数字须重标定（GDS 字节、pitch、密度、胞长行）。"
               "**为什么仍算「已发现而非已修复」**：重标定会改全部受跟踪 GDS 与报告快照 "
               "⇒ 属独立施工批次，本版只做**如实登记 + 两口径并报**（M5 胞长/密度两行已带 "
               "`gamma_sensitivity` 并报，不选择性披露）。"
               "**Γ-无关量不受影响**（门禁 `run_pm_g2_smoke` C16 以两档 Γ **现算互等**证明）："
               "每 π 损耗 IL_π、M1 可行性判据 r=k_a/(k_c−k_a)、相位域 FOM=Δn/(8.6859k)。"},
    {"id": "PM-G6", "title": "相位域（谐振/干涉）多电平读出与漂移口径 —— **已结算（v0.9.195 · 证据链机器可查）**",
     "detail": "结算前：本卡只走振幅域（波导直通 + 相变吸收调制），相位域口径未建。"
               "结算证据链（`pm_matlib.PHASE_DOMAIN_ANCHORS` 6 条 = 5 measured + 1 simulation · "
               "`pm_m6.phase_domain_status` 机器判定 + FOM 闭式现算）：① Delaney et al., "
               "Adv. Funct. Mater. 30(36):2002447 (2020) doi:10.1002/adfm.202002447 —— Sb₂Se₃ "
               "Δn=0.77、k<1e-5、**器件 FOM = 29 rad/dB**、耐久>4000；② PhotoniX 3:18 (2022) "
               "doi:10.1186/s43074-022-00070-4 —— Δn_eff≈0.071、L_π=11 µm、"
               "**每 π 损耗 0.2 dB（含 0.1 散射）的唯一拆分锚**；③ Adv. Opt. Mater. (2025) "
               "doi:10.1002/adom.202503295 —— MZI 消光比 28 dB、V_πL=0.56 V·cm；"
               "④ Adv. Funct. Mater. (2023) doi:10.1002/adfm.202304601 —— **6-bit 多电平"
               "**开关态、>10⁴ 周期；⑤ Blundell et al. 2025 —— 23 nm 膜 >10⁶ 周期"
               "（Dwivedi APL 2025 的 HMI 14 dB 为**仿真** ⇒ ⛔ 永不作 golden）。"
               "**口径**：可行 ⇔ IL_π ≤ IL_budget ⇔ FOM ≥ π/IL_budget（**Γ、L 同约掉**）。"
               "🔴 **残余边界（如实开放）**：相位**漂移**无独立定量实测锚（现有光学锚全是"
               "**透射**漂移）⇒ 只给观测方程 + 差分共模抑制机制，**不给定量保持时间**"
               "（与 PM-G7 的分野：G7 有实测上界锚可定量，G6 没有）。"},
    {"id": "PM-G7", "title": "光学域 drift 定量锚（透射电平漂移）—— **已结算（v0.9.193 · 证据链机器可查）**",
     "detail": "结算前：光学域无直接锚，M4 升级为系统级阻塞项（若与电学域同阶，16 电平保持"
               "仅 ~1.7 秒）。结算证据链（`pm_matlib.OPTICAL_DRIFT_ANCHORS` 非空 + "
               "`pm_m2.optical_drift_status` 机器判定 + `nu_optical_bound` 重算守卫）："
               "① Cheng et al., Sci. Adv. 5, eaau5759 (2019) doi:10.1126/sciadv.aau5759 —— "
               "2 µm GST 波导存储胞 13 电平、probe 0.1 mW ON 下 10⁴ s **无可测透射漂移**"
               "（实测事实）⇒ 取编程 SD 0.35% 作检测下限（显式假设）⇒ ν_T ≤ 3.80e-4（上界）；"
               "② Kalb et al., J. Appl. Phys. 94, 4908 (2003) doi:10.1063/1.1610775 —— "
               "a-GST 粘度随时间线性增长（双分子结构弛豫 · E_iso=1.76 eV，实测）；"
               "③ Ríos et al., Nat. Photon. 9, 725 (2015) doi:10.1038/nphoton.2015.182 —— "
               "集成 8 电平保持「数十年」声明（定性）。**口径翻转**：主账 drift 段改算自"
               "光学域上界锚 ⇒ 1 年保持瓶颈翻转为 **write**、系统 BER 3.98e-62 全绿、"
               "保持下界 ~10^74 s（旧电学代理口径**并报**：瓶颈=drift、BER 0.4047 —— "
               "两口径差 315.8×）。**残余边界**：ν_T 是上界非点值（检测下限假设支配）；"
               "漂移函数形式 ln(t) 仍是模型假设 ⇒ 长寿命结论是**下界**语义。"},
    {"id": "PM-G8", "title": "加热器电-热联仿与 T1 器件级真值（M4 部分结算：行为级已交付 · 器件级仍锁死）",
     "detail": "M4 交付**行为级**外设（`R_h = R_sheet·(L_h/w_h)`、`P = V²/R`、`E = P·t`）"
               "并与 M1 的脉冲阶梯动态范围对齐；但焦耳热分布、热-光耦合动力学、开关能耗"
               "**真值**仍属**器件级 T1 / 电路级 T2 锁死区**（无 PDK ⇒ 不报）。"},
    {"id": "PM-G9", "title": "外设参数缺本项目实测锚（M4 新增登记）",
     "detail": "PD 响应度（A/W）/ 加热器薄膜方阻（Ω/sq）取**公开工程典型区间**（非实测、"
               "非逐条 DOI 复核）；读出速率 / 输入光功率 / 驱动摆幅 / EIC 通道 pitch 为"
               "**设计假设** ⇒ 外设结论只给**区间 + 恒等式 + 单调性**，无绝对真值。"},
    {"id": "PM-G10", "title": "写读耐久（endurance）模型与锚（M5 对拍判定「不可判」）",
     "detail": "征程内**无 endurance 模型**；文献检索未取得光子 GST 器件级循环数"
               "实测锚（Ríos 2015 原文未报循环数）⇒ 对拍表该行 verdict=not_modeled。"
               "🔴 不引用电学 PCM 的 10⁶–10⁹ 量级作粉饰（器件口径不同）。"},
]

#: 报告 JSON 不在本部署时的**内置快照**（2026-10-04 实测 · 仅供降级展示）。
#: 🔴 **schema 必须与 `examples/photo_memory/lda_pm_m3_report.json` 逐块同构** ——
#: 由 `run_pm_m3_smoke.py` 的「快照 == 仓库当前状态」判据常驻守（铁律：入库生成物
#: 必须配快照一致性判据，否则每加一批锚就多一份静默失真）。
STATIC_SNAPSHOT: Dict[str, Any] = {
    "array_8x1": {
        "kind": "1 bus × 8 cells",
        "stats": {"n_devices": 10, "n_nets": 11, "n_elements": 109,
                  "area_um2": 1223.44, "width_um": 197.33, "height_um": 6.2,
                  "bbox_um": [-40.0, -3.1, 157.33, 3.1], "gds_bytes": 6224,
                  "multilayer": False, "n_io": 2, "n_structures": 1},
        "drc": {"all_pass": True, "n_checked": 10, "n_pass": 10},
        "lvs": {"verdict": "ACCEPT", "n_violations": 0},
        "independent_scan": {
            "n_structures": 1, "n_elements": 109,
            "layers": {"1": 53, "5": 8, "6": 48},
            "by_kind": {"aref": 0, "boundary": 72, "path": 37, "sref": 0},
            "n_sref": 0, "n_aref": 0, "total_length_um": 379.57},
        "expected": {"PCM": 8, "HEATER": 48, "SI_devices": 10, "SI_routes": 9,
                     "layers_expected": {"5": 8, "6": 48},
                     "n_devices": 10, "n_nets": 9},
        "gds": {"bytes": 6224,
                "sha256": "（快照未含 sha；请以仓库 examples 报告为准）"},
    },
    "array_4x8": {
        "kind": "4 buses × 8 cells",
        "stats": {"n_devices": 40, "n_nets": 44, "n_elements": 436,
                  "area_um2": 10695.27, "width_um": 197.33, "height_um": 54.2,
                  "bbox_um": [-40.0, -3.1, 157.33, 51.1], "gds_bytes": 24710,
                  "multilayer": False, "n_io": 8, "n_structures": 1},
        "independent_scan": {
            "layers": {"1": 212, "5": 32, "6": 192},
            "by_kind": {"aref": 0, "boundary": 288, "path": 148, "sref": 0},
            "n_elements": 436, "n_sref": 0, "n_aref": 0,
            "n_structures": 1, "total_length_um": 1518.28},
        "drc_all_pass": True, "lvs_verdict": "ACCEPT", "lvs_n_violations": 0,
    },
    "pitch": {"l_cell_um": 11.0146, "gap_um": 7.0304, "gap_thermal_um": 7.0304,
              "gap_process_um": 6.0, "binding": "thermal", "pad_um": 4.0,
              "pitch_um": 18.045,
              "thermal": {"material": "GST", "k_iso": 8.0,
                          "l_max_diff_um": 0.8788, "l_max_rc_um": 0.2723,
                          "min_gap_um": 7.0304, "min_gap_um_rc_basis": 2.1787,
                          "literature_l_ref_um": 0.15,
                          "basis": "k_iso × L_max（热扩散口径上界）· k_iso 为设计选择"}},
    "budget": {"material": "GST", "n_cells_total": 8, "n_levels": 16,
               "bits_per_cell": 4, "l_cell_um": 11.0146,
               "array_states": 128, "array_bits": 32, "n_electrode_pads": 32,
               "n_heater_lines": 16,
               "single_cell_il_db": {"amorphous": [0.3878, 3.1026],
                                     "crystalline": [1.9391, 30.0561]},
               "single_cell_contrast_db": [1.5513, 26.9536],
               "array_il_db": {"amorphous": [3.1026, 24.8205],
                               "crystalline": [15.5128, 240.4490]},
               "il_model": "serial_sum(N × single_cell_il)；不含单元间连接波导传播损耗（无锚）",
               "gamma_note": "单元 IL 含 Γ **假设 0.05**（Γ 已有自研场求解标定 pm_gamma≈0.084 ⇒ PM-G2 v0.9.198 结算）；🔴 L ∝ 1/Γ ⇒ 本档版图按假设出图，标定口径下设计点**越窗**须重标定（PM-G11 开放 · 两口径并报）⇒ 一律**区间**口径，非单值",
               "contrast_reuse_note": "contrast 与 IL 来自同一 M0 双层调用（避免二次来源）"},
    "scale_tiers": [
        {"bus_x_cells": "1x4", "n_buses": 1, "n_cells_per_bus": 4, "n_cells_total": 4,
         "n_devices": 6, "n_nets": 7, "n_elements": 73, "gds_bytes": 4272,
         "area_um2": 775.93, "width_um": 125.15, "height_um": 6.2,
         "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 4, "got_pcm": 4},
        {"bus_x_cells": "1x8", "n_buses": 1, "n_cells_per_bus": 8, "n_cells_total": 8,
         "n_devices": 10, "n_nets": 11, "n_elements": 109, "gds_bytes": 6224,
         "area_um2": 1223.44, "width_um": 197.33, "height_um": 6.2,
         "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 8, "got_pcm": 8},
        {"bus_x_cells": "1x16", "n_buses": 1, "n_cells_per_bus": 16,
         "n_cells_total": 16, "n_devices": 18, "n_nets": 19, "n_elements": 181,
         "gds_bytes": 10128, "area_um2": 2118.48, "width_um": 341.72,
         "height_um": 6.2, "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 16, "got_pcm": 16},
        {"bus_x_cells": "1x32", "n_buses": 1, "n_cells_per_bus": 32,
         "n_cells_total": 32, "n_devices": 34, "n_nets": 35, "n_elements": 325,
         "gds_bytes": 17936, "area_um2": 3908.54, "width_um": 630.51,
         "height_um": 6.2, "drc_pass": True, "lvs": "ACCEPT", "lvs_violations": 0,
         "independent_ok": True, "expected_pcm": 32, "got_pcm": 32},
        {"bus_x_cells": "4x8", "n_buses": 4, "n_cells_per_bus": 8,
         "n_cells_total": 32, "n_devices": 40, "n_nets": 44, "n_elements": 436,
         "gds_bytes": 24710, "area_um2": 10695.27, "width_um": 197.33,
         "height_um": 54.2, "drc_pass": True, "lvs": "ACCEPT",
         "lvs_violations": 0, "independent_ok": True, "expected_pcm": 32,
         "got_pcm": 32},
    ],
    "upstream": {
        "cell_length": {"l_um": 11.0146, "spacing_frac": 0.0657,
                        "spacing_ok": True, "worst_ber": 4.78e-14,
                        "source": "ACS Photonics 2025 / arXiv 2512.23559"
                                  "（椭偏 · Cody-Lorentz 拟合 · 30nm 膜）"},
        "levels": {"n_levels": 16, "bits_per_cell": 4},
        "thermal": {"material": "GST", "k_iso": 8.0, "l_max_diff_um": 0.8788,
                    "l_max_rc_um": 0.2723, "min_gap_um": 7.0304,
                    "min_gap_um_rc_basis": 2.1787, "literature_l_ref_um": 0.15,
                    "basis": "k_iso × L_max（热扩散口径上界）· k_iso 为设计选择"},
    },
    "signoff_checks": {"drc_all_pass": True, "lvs_accept": True,
                       "pcm_layer_exact": True, "heater_layer_exact": True,
                       "si_layer_at_least_devices": True,
                       "no_hierarchy_refs": True, "single_structure": True},
    # ── M4 外设与系统（2026-10-04 实测 · 与 lda_pm_m4_report.json 逐块同构）────────
    "m4":     {
        "assembly_2p5d": {
            "density_bottleneck": "eic",
            "drc_all_pass": True,
            "eic_die_um": [
                400.0,
                6.2
            ],
            "eic_pitch_um": 50.0,
            "gds_bytes_len": 4852,
            "gds_sha256": "4191e8b8255e98078add7886c35b982e7b5bb8bc6c2880db618b84fa12955bdf",
            "interposer_um": [
                408.0,
                24.4
            ],
            "layers_decoded": {
                "1": 10,
                "5": 8,
                "6": 48,
                "64": 2,
                "65": 16,
                "66": 1
            },
            "lvs_verdict": "ACCEPT",
            "n_channels": 8,
            "pic_die_um": [
                197.33,
                6.2
            ],
            "pic_pitch_um": 18.045024706557335
        },
        "readout": {
            "all_ok": True,
            "f_3db_hz": 397887357.7297383,
            "f_read_hz": 100000.0,
            "n_levels": 16,
            "p_in_w": 0.001,
            "p_min_dbm": -39.77515569742968,
            "p_min_w": 1.0531359308367793e-07,
            "r_f_max_ohm": 79577471.54594769,
            "r_f_ohm": 20000.0,
            "resp_a_per_w": 0.8,
            "sensitivity_margin_x": 9495.450404065508,
            "shot_dominant": True,
            "source": "ACS Photonics 2025 / arXiv 2512.23559（椭偏 · Cody-Lorentz 拟合 · 30nm 膜）",
            "worst_ber": 0.0,
            "worst_snr": 32382.63468487792,
            "z_mag_ohm": 19999.999368345347
        },
        "rf_tradeoff": {
            "design_r_f_ohm": 20000.0,
            "n_points": 24,
            "optimal_r_f_ohm": 79577471.54594769,
            "optimal_worst_ber": 0.0,
            "optimal_worst_snr": 37021.25838766379,
            "r_f_max_ohm": 79577471.54594769,
            "snr_monotone_nondecreasing": True
        },
        "system_budget": {
            "all_ok": True,
            "ber_target": 1e-12,
            "ber_total": 3.975659327580069e-62,
            "bottleneck": "write",
            "drift_anchor": {
                "derivation": "ν_T ≤ 检测下限 / ln(t_meas/t₀)（纯算术，检测下限假设显式披露）",
                "is_main_account": True,
                "is_upper_bound_semantics": True,
                "n_bound_anchors": 1,
                "note": "主账 drift 段 = 器件级实测锚（Cheng 2019 · doi:10.1126/sciadv.aau5759）；漂移函数形式 ΔT/T ≈ ν_T·ln(t/t₀) 仍是模型假设（锚只钉住速率上界）。",
                "nu_t_ub": 0.0003800076716653453,
                "per_anchor": [
                    {
                        "detection_floor_rel": 0.0035,
                        "nu_ub": 0.0003800076716653453,
                        "source": "Cheng, Ríos, Wright, Bhaskaran, Pernice et al., 《In-memory computing on a photonic platform》, Sci. Adv. 5, eaau5759 (2019) · doi:10.1126/sciadv.aau5759",
                        "t_meas_s": 10000.0
                    }
                ],
                "retention_semantics": "ν_T 为**上界** ⇒ max_t_hold 是**下界**（真保持 ≥ 报告值）；报告值受检测下限假设（0.35% SD）支配"
            },
            "drift_proxy": {
                "ber_total": 0.40466976317426545,
                "bottleneck": "drift",
                "eps_drift_at_t_hold": 2.0720881264730338,
                "eps_total": 2.0722968553581462,
                "is_cross_domain_proxy": True,
                "is_main_account": False,
                "note": "🔴 **旧 M4 主账口径并报**（电学域 ν 上界跨域代理，「若两域同阶」的后果）：该口径下瓶颈=drift、系统 BER ≈0.40、16 电平保持 ~1.7 s —— 即 PM-G7 结算前的结论，保留可查（口径翻转须并报，不选择性披露）。光学域实测上界比电学代理小 ~316×。",
                "nu_max_electrical": 0.12,
                "nu_min_electrical": 0.07,
                "nu_upper_bound_electrical": 0.18,
                "per_proxy": [
                    {
                        "nu_proxy": 0.07,
                        "t_erode_human": "2.4 秒",
                        "t_erode_s": 2.35641844238366
                    },
                    {
                        "nu_proxy": 0.12,
                        "t_erode_human": "1.6 秒",
                        "t_erode_s": 1.6487212707001282
                    }
                ]
            },
            "eps": {
                "drift": 0.00656174487022021,
                "read": 3.0880748578094574e-05,
                "write": 0.029411764705882353
            },
            "eps_total": 0.030134852786709958,
            "max_t_hold_human": "2837091245631522701244189319585739242049827558573865514564172382208.00 年",
            "max_t_hold_s_for_target": 8.94705095222357e+73,
            "share": {
                "drift": 0.217746040329557,
                "read": 0.0010247519308179123,
                "write": 0.9760049240676397
            },
            "snr_total": 16.592083709149875,
            "t_hold_s": 31560000.0,
            "t_hold_table": [
                {
                    "ber": 4.106652565053581e-65,
                    "bottleneck": "write",
                    "eps_drift": 0.0,
                    "eps_total": 0.029411780917428642,
                    "t_hold_s": 1.0
                },
                {
                    "ber": 6.154828416330524e-65,
                    "bottleneck": "write",
                    "eps_drift": 0.001555882344085688,
                    "eps_total": 0.02945290523197087,
                    "t_hold_s": 60.0
                },
                {
                    "ber": 2.0444384733039977e-64,
                    "bottleneck": "write",
                    "eps_drift": 0.003111764688171376,
                    "eps_total": 0.029575935085967613,
                    "t_hold_s": 3600.0
                },
                {
                    "ber": 8.770748952642746e-64,
                    "bottleneck": "write",
                    "eps_drift": 0.004319449524669031,
                    "eps_total": 0.029727268642291763,
                    "t_hold_s": 86400.0
                },
                {
                    "ber": 3.975659327580069e-62,
                    "bottleneck": "write",
                    "eps_drift": 0.00656174487022021,
                    "eps_total": 0.030134852786709958,
                    "t_hold_s": 31560000.0
                }
            ]
        },
        "upstream": {
            "levels": {
                "l_um": 11.014603130717049,
                "n_levels": 16,
                "source": "ACS Photonics 2025 / arXiv 2512.23559（椭偏 · Cody-Lorentz 拟合 · 30nm 膜）",
                "spacing_frac": 0.06570779838443097
            },
            "pic_pitch_um": 18.045024706557335
        },
        "write_driver": {
            "driver_bits": 8,
            "e_hi_j": 2.966062382119907e-09,
            "e_lo_j": 5.932124764239814e-10,
            "eps_write": 0.029411764705882353,
            "p_hi_w": 0.05932124764239814,
            "p_lo_w": 0.011864249528479628,
            "pulse_dynamic_range_ok": True,
            "pulse_ladder_ratio": 4.6748631345508755,
            "r_hi_ohm": 917.8835942264208,
            "r_lo_ohm": 183.57671884528415,
            "t_pulse_s": 5e-08,
            "v_drv": 3.3
        }
    },
    "m5": {
        "disclosure": {
            "all_lda_values_computed": True,
            "no_fabricated_efficiency_claims": True,
            "no_fabrication_of_measurability": True
        },
        "gaps_closed": 7,
        "gaps_final": [
            {
                "closed": True,
                "id": "PM-G1",
                "title": "相变材料光学常数锚库（n,k @λ,相态）"
            },
            {
                "closed": True,
                "id": "PM-G2",
                "title": "模场重叠因子 Γ 的场求解标定（v0.9.198 结算：半矢量场法 + 全矢量**独立离散** + 微扰法 + 1D 平板；🔴 计算值不作 golden）"
            },
            {
                "closed": True,
                "id": "PM-G3",
                "title": "瞬态热模型（冷却时间 = set/reset 周期下限）"
            },
            {
                "closed": True,
                "id": "PM-G4",
                "title": "晶化动力学（JMAK/Avrami）"
            },
            {
                "closed": True,
                "id": "PM-G5",
                "title": "非晶 drift（物理来源 + 电学域锚 + 光学域适用性判定）"
            },
            {
                "closed": True,
                "id": "PM-G6",
                "title": "相位域（谐振/干涉）多电平读出与漂移口径（v0.9.195 结算：口径 + DOI 锚；相位漂移定量仍开放）"
            },
            {
                "closed": True,
                "id": "PM-G7",
                "title": "光学域 drift 定量锚（透射电平漂移 · v0.9.193 结算：实测上界锚 + 检测下限假设显式披露）"
            },
            {
                "closed": False,
                "id": "PM-G10",
                "title": "写读耐久（endurance）模型与锚 —— M5 对拍表判定「不可判」（开放）"
            },
            {
                "closed": False,
                "id": "PM-G11",
                "title": "Γ 标定后的全链设计点/版图重标定（v0.9.198 新登记 · 开放：L ∝ 1/Γ ⇒ 按假设 Γ=0.05 出的设计点越出标定口径可行窗上界）"
            }
        ],
        "gaps_total": 9,
        "generated_by": "examples/photo_memory/build_pm_m5.py",
        "honest_note": "本表不产生任何「实测」声明：LDA 全部数字为闭式/行为级设计值；文献值全部 DOI 级器件实测；比值仅判量级（三带规则）。",
        "material": "GST",
        "milestone": "PM-M5",
        "rows": [
            {
                "design_only": True,
                "lda_source": "pm_m1.level_design（M1 主账）",
                "lda_value": 16,
                "lit_sources": [
                    "Ríos, Stegmaier, Hosseini, Wright, Bhaskaran & Pernice, 《Integrated all-photonic non-volatile multi-level memory》, Nat. Photon. 9, 725–732 (2015) · doi:10.1038/nphoton.2015.182",
                    "Cheng, Ríos, Wright, Bhaskaran, Pernice et al., 《In-memory computing on a photonic platform》, Sci. Adv. 5, eaau5759 (2019) · doi:10.1126/sciadv.aau5759"
                ],
                "lit_value": 13,
                "metric": "n_levels",
                "metric_cn": "存储电平数",
                "note": "🔴 LDA 是**设计目标**（无流片实测）；文献是器件级实测。「高于实测 23%」不构成实测声明。",
                "ratio": 1.2307692307692308,
                "verdict": "same_order"
            },
            {
                "cross_domain": True,
                "lda_source": "pm_m4.write_driver（M4 行为级 · 电辅助焦耳热）",
                "lda_value": {
                    "e_hi_j": 2.966062382119907e-09,
                    "e_lo_j": 5.932124764239814e-10,
                    "mid_j": 1.7796374292719442e-09
                },
                "lit_sources": [
                    "Ríos, Stegmaier, Hosseini, Wright, Bhaskaran & Pernice, 《Integrated all-photonic non-volatile multi-level memory》, Nat. Photon. 9, 725–732 (2015) · doi:10.1038/nphoton.2015.182"
                ],
                "lit_value": {
                    "e_switch_min_j": 1.34e-11,
                    "multi_mid_j": 5.25e-10
                },
                "metric": "write_pulse_energy_j",
                "metric_cn": "单次写脉冲能量",
                "note": "🔴 口径差：LDA = **电辅助**焦耳热（3.3 V × 加热线，行为级）；文献 = **光脉冲**写入（波导近场）。能量不可直接比优劣，只判量级；文献另报最低切换 13.4 pJ（二元优化点，非多电平工作点），不并入比值。",
                "ratio": 3.3897855795656078,
                "verdict": "within_5x"
            },
            {
                "gamma_sensitivity": {
                    "design_point_inside_calibrated_window": False,
                    "gamma_assumed": 0.05,
                    "gamma_calibrated": 0.0840054905578339,
                    "gap": "PM-G11",
                    "l_cell_now_um": 11.014603130717049,
                    "l_cell_rebaselined_um": 6.555882870021456,
                    "law_rel_dev": 1.3547807935397393e-16,
                    "length_scale": 0.5951991907669095,
                    "never_golden": True,
                    "note": "按标定 Γ=0.0840：可行窗 [3.559, 9.553] µm，设计点应为 6.556 µm；现值 11.015 µm（按假设 Γ=0.050 出图）**越出窗上界 9.553 µm（+15.3%）** ⇒ 读出饿死，须重标定（PM-G11）",
                    "scale_ratio": 0.5951991907669095,
                    "window_now_um": [
                        5.9792114645427,
                        16.049994796891397
                    ],
                    "window_rebaselined_um": [
                        3.558821825120043,
                        9.552943914922869
                    ]
                },
                "lda_source": "pm_m3.cell_length_um（M1 设计 L）",
                "lda_value": 11.014603130717049,
                "lit_sources": [
                    "Ríos, Stegmaier, Hosseini, Wright, Bhaskaran & Pernice, 《Integrated all-photonic non-volatile multi-level memory》, Nat. Photon. 9, 725–732 (2015) · doi:10.1038/nphoton.2015.182"
                ],
                "lit_value": 5.0,
                "metric": "cell_length_um",
                "metric_cn": "GST 相变段长度",
                "note": "胞长越长插入损耗越高（M0 闭式律 ∝L），但设计点由 M1 可行性判据定，非自由选择。🔴 **Γ 口径敏感（PM-G2 标定 · PM-G11 开放 · 并报）**：L ∝ 1/Γ ⇒ 按标定 Γ=0.0840 重标定为 **6.556 µm**（本行现值 11.015 µm 按假设 Γ=0.050 出图；1/Γ 律 rel=1.4e-16）。两口径并报，不选择性披露。",
                "ratio": 2.2029206261434098,
                "verdict": "within_5x"
            },
            {
                "lda_source": "pm_m0.contrast_vs_length（M0 闭式律 · Γ 抵消）",
                "lda_value": {
                    "at_l_um": 5.0,
                    "contrast_max_db": 12.235375044130057,
                    "contrast_min_db": 0.7041942471441752
                },
                "lit_note": "21% 透射变化 ⇒ 10·log10(1/0.79) = 1.024 dB（换算可见）",
                "lit_sources": [
                    "Ríos, Stegmaier, Hosseini, Wright, Bhaskaran & Pernice, 《Integrated all-photonic non-volatile multi-level memory》, Nat. Photon. 9, 725–732 (2015) · doi:10.1038/nphoton.2015.182"
                ],
                "lit_value": 1.0237290870955853,
                "metric": "readout_contrast_db",
                "metric_cn": "二元读出对比度",
                "note": "取 LDA **最小**对比度（k 源展布保守侧）与文献单值比。",
                "ratio": 0.6878716801356498,
                "verdict": "same_order"
            },
            {
                "lda_source": "pm_m2.nu_optical_bound（G7 结算 · 上界推导）",
                "lda_value": {
                    "nu_ub": 0.0003800076716653453,
                    "semantics": "upper_bound"
                },
                "lit_sources": [
                    "Cheng, Ríos, Wright, Bhaskaran, Pernice et al., 《In-memory computing on a photonic platform》, Sci. Adv. 5, eaau5759 (2019) · doi:10.1126/sciadv.aau5759"
                ],
                "lit_value": {
                    "kind": "no_detectable_drift_1e4_s"
                },
                "metric": "drift_index_nu",
                "metric_cn": "透射漂移指数 ν_T",
                "note": "🔴 LDA 上界ν_T ≤ 检测下限/ln(10⁴) **推导自** Cheng 2019 的同一实测事实⇒ 本行是**自洽性检查**（推导链可复核），不是独立对标；真正独立对标需第二来源的器件级 drift 实测（尚无）。",
                "self_consistency_only": True,
                "verdict": "derived_from_same_source"
            },
            {
                "gap_id": "PM-G10",
                "lda_source": None,
                "lda_value": None,
                "lit_sources": [],
                "lit_value": None,
                "metric": "endurance",
                "metric_cn": "写读循环耐久",
                "note": "🔴 征程内**无 endurance 模型**；文献检索未取得光子 GST 器件级循环数实测锚（Ríos 2015 原文未报循环数）⇒ **不可判**。不引用电学 PCM 的 10⁶–10⁹ 量级作粉饰（器件口径不同）。",
                "verdict": "not_modeled"
            },
            {
                "gamma_sensitivity": {
                    "design_point_inside_calibrated_window": False,
                    "gamma_assumed": 0.05,
                    "gamma_calibrated": 0.0840054905578339,
                    "gap": "PM-G11",
                    "l_cell_now_um": 11.014603130717049,
                    "l_cell_rebaselined_um": 6.555882870021456,
                    "law_rel_dev": 1.3547807935397393e-16,
                    "length_scale": 0.5951991907669095,
                    "never_golden": True,
                    "note": "按标定 Γ=0.0840：可行窗 [3.559, 9.553] µm，设计点应为 6.556 µm；现值 11.015 µm（按假设 Γ=0.050 出图）**越出窗上界 9.553 µm（+15.3%）** ⇒ 读出饿死，须重标定（PM-G11）",
                    "scale_ratio": 0.5951991907669095,
                    "window_now_um": [
                        5.9792114645427,
                        16.049994796891397
                    ],
                    "window_rebaselined_um": [
                        3.558821825120043,
                        9.552943914922869
                    ]
                },
                "lda_source": "pm_m3.cell_pitch_um × die 高（M4 2.5D）· 算出来的",
                "lda_value": {
                    "bits_per_cell": 4.0,
                    "die_h_um": 6.2,
                    "pic_side": 35752.86267622216,
                    "pic_side_rebaselined": 47486.14996030731,
                    "pitch_rebaselined_um": 13.586304445861742,
                    "pitch_um": 18.045024706557335,
                    "system_side_eic_bottleneck": 12903.22580645161
                },
                "lit_sources": [],
                "lit_value": None,
                "metric": "areal_density",
                "metric_cn": "集成密度（bits/mm²）",
                "note": "文献均为**单胞演示**（Ríos 5 µm / Cheng 2 µm），无同口径阵列密度实测锚⇒ 不比。LDA 侧两口径并报：PIC 版图口径 vs 2.5D 系统口径（EIC 瓶颈）。🔴 **Γ 口径敏感（PM-G2 标定 · PM-G11 开放 · 并报）**：pitch = L + gap ⇒ 按标定 Γ=0.0840 重标定 pitch=13.586 µm、PIC 密度 4.749e+04 bits/mm²（本行现值 pitch=18.045 µm / 3.575e+04 bits/mm² 按假设 Γ=0.050 出图）。",
                "verdict": "no_anchor"
            }
        ],
        "summary_note": "收官口径：对拍 7 行 —— same_order/within_5x 均为**量级**结论（LDA 无流片实测，全部 design_only）；drift 行是自洽检查非独立对标；endurance 与密度两行**不可判**（如实登记 PM-G10 / 无锚）。国际对标收官 = 「知道自己每一项站在哪」，不是「全面领先」。",
        "verdict_counts": {
            "derived_from_same_source": 1,
            "no_anchor": 1,
            "not_modeled": 1,
            "same_order": 2,
            "within_5x": 2
        }
    },
}

_ARTIFACT_DIRS = (
    os.path.join("examples", "photo_memory"),
    os.path.join("lda", "examples", "photo_memory"),
)
_REPORT_NAME = "lda_pm_m3_report.json"
_M4_REPORT_NAME = "lda_pm_m4_report.json"
_M5_REPORT_NAME = "lda_pm_m5_report.json"
_ARTIFACT_PREFIXES = ("lda_pm_m3", "lda_pm_m4", "lda_pm_m5")


# ═══════════════════════════ 产出物探测（只读）═══════════════════════════
def _repo_root(repo_root: Optional[str]) -> str:
    if repo_root is not None:
        return repo_root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_named_report(name: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读**指定文件名**的预生成报告 JSON（只 `json.load` + 目录扫描，绝不重算）。

    🔴 **聚合扫描**：源码仓产物在 `examples/photo_memory/`，部署形态可能在
    `lda/examples/photo_memory/` ⇒ 逐个候选目录扫描，取首个命中（同一份数据）。
    读不到 ⇒ 返回 `{}`（调用方回落 `STATIC_SNAPSHOT`，优雅降级）。
    """
    root = _repo_root(repo_root)
    for d in _ARTIFACT_DIRS:
        fp = os.path.join(root, d, name)
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    data["_source"] = d.replace(os.sep, "/") + "/" + name
                    return data
            except (OSError, ValueError):
                return {}
    return {}


def _load_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读 M3 阵列报告 JSON（薄委托 `_load_named_report`）。"""
    return _load_named_report(_REPORT_NAME, repo_root)


def _load_m4_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读 M4 外设与系统报告 JSON（薄委托 `_load_named_report`）。"""
    return _load_named_report(_M4_REPORT_NAME, repo_root)


def _load_m5_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """读 M5 国际对标收官报告 JSON（薄委托 `_load_named_report`）。"""
    return _load_named_report(_M5_REPORT_NAME, repo_root)


def _manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """产出物元信息（文件名 + 字节数）· 只 `stat`。"""
    root = _repo_root(repo_root)
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d.replace(os.sep, "/"))
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith(_ARTIFACT_PREFIXES) or nm.endswith(".py"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "dirs_scanned": [],
                "root_hint": _ARTIFACT_DIRS[0].replace(os.sep, "/"),
                "count": 0, "items": [],
                "note": "产出物目录不在本部署内（源码仓才含 examples/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits,
            "root_hint": _ARTIFACT_DIRS[0].replace(os.sep, "/"),
            "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数，已跨目录去重）；"
                    "在线生成请走源码仓的 examples/photo_memory/build_pm_m3.py"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def _phase_domain_case() -> Dict[str, Any]:
    """相位域（干涉/谐振）多电平口径摘要 —— **纯解析现算**（`pm_m6` · 无文件 IO / 无 FDTD）。

    🔴 与 `m3`/`m4`/`m5` 的「报告 JSON 快照」不同：相位域口径全是解析闭式（<50 ms），
    **无入库生成物** ⇒ 直接现算，从根上避免「快照与写入器漂移」那类风险
    （同族铁律：入库生成物必须配「快照 == 仓库当前状态」判据 —— 这里没有生成物 ⇒ 不需要）。
    """
    from lda_l2 import pm_m6 as M6
    return M6.phase_case_summary("Sb2Se3")


def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装光子存储阵列案例卡（只读 · 零重计算 · 免登录）。"""
    rep = _load_report(repo_root)
    src = rep.get("_source")
    rep4 = _load_m4_report(repo_root)
    src4 = rep4.get("_source")
    rep5 = _load_m5_report(repo_root)
    src5 = rep5.get("_source")
    snap = STATIC_SNAPSHOT
    snap4 = snap["m4"]
    snap5 = snap["m5"]
    a8 = rep.get("array_8x1") or snap["array_8x1"]
    a32 = rep.get("array_4x8") or snap["array_4x8"]
    pitch = rep.get("pitch") or snap["pitch"]
    bud = rep.get("budget") or snap["budget"]
    tiers = rep.get("scale_tiers") or snap["scale_tiers"]
    ups = rep.get("upstream") or snap["upstream"]
    checks = rep.get("signoff_checks") or snap["signoff_checks"]
    m4_up = rep4.get("upstream") or snap4["upstream"]
    m4_ro = rep4.get("readout") or snap4["readout"]
    m4_rf = rep4.get("rf_tradeoff") or snap4["rf_tradeoff"]
    m4_wd = rep4.get("write_driver") or snap4["write_driver"]
    m4_sb = rep4.get("system_budget") or snap4["system_budget"]
    m4_asm = rep4.get("assembly_2p5d") or snap4["assembly_2p5d"]

    gate_total = sum(m["gate"] for m in MILESTONES)
    return {
        "endpoint": "/api/pm_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一条非易失光子存储单元 → 阵列 → 外设与系统"
                 "（Si 波导 + GST 相变段 + 双侧微加热器 + 电极 pad）：P&R → 路由 → "
                 "几何 DRC/LVS → **从最终 GDS 字节独立解码复核** → 设计预算 → "
                 "读出/写驱动行为级 → 系统误码预算 → 2.5D 装配签核，出真 GDSII",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计期签核（非流片实测）",
        "identity": {
            "physics": "Si 波导 + GST 相变材料（电辅助写）· 振幅域多电平存储",
            "device": "PCM 单元 = Si 直波导 + GST 覆盖段 + 双侧微加热线 + 4 电极 pad",
            "route_note": "光学 IO 经**引出波导**接光栅耦合器（避免光栅齿区与电极 pad 打架）；"
                          "阵列 = 串行总线（1×N）或多总线（R×C）；外设 = 读出 TIA + "
                          "写驱动（行为级）",
            "layers": PCM_LAYERS,
            "ports": PCM_PORTS,
            "zero_external_eda": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": gate_total,
            "modules": len(MILESTONES),
            "probe_mutations": sum(MILESTONE_PROBES.values()),
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "device": {"kind": "PCMCell", "layers": PCM_LAYERS, "ports": PCM_PORTS,
                   "drc_rules": ["min_width", "min_space", "min_pad"]},
        "pitch": pitch,
        "upstream": ups,
        "array": {
            "main": {"kind": a8.get("kind"), "stats": a8.get("stats"),
                     "drc": a8.get("drc"), "lvs": a8.get("lvs")},
            "independent_scan": a8.get("independent_scan"),
            "expected_layers": a8.get("expected"),
            "gds_bytes": (a8.get("gds") or {}).get("bytes"),
            "gds_sha256": (a8.get("gds") or {}).get("sha256"),
            "wide": {"kind": a32.get("kind"), "stats": a32.get("stats"),
                     "drc_all_pass": a32.get("drc_all_pass"),
                     "lvs_verdict": a32.get("lvs_verdict"),
                     "lvs_n_violations": a32.get("lvs_n_violations")},
        },
        "signoff_checks": checks,
        "budget": bud,
        "scale_tiers": tiers,
        "m4": {
            "readout": m4_ro,
            "rf_tradeoff": m4_rf,
            "write_driver": m4_wd,
            "system_budget": m4_sb,
            "assembly_2p5d": m4_asm,
            "upstream": m4_up,
            "data_source": src4 or "内置快照（2026-10-04 实测；本部署内无 M4 报告 JSON）",
        },
        "m5": {
            "rows": rep5.get("rows") or snap5["rows"],
            "verdict_counts": rep5.get("verdict_counts") or snap5["verdict_counts"],
            "gaps_final": rep5.get("gaps_final") or snap5["gaps_final"],
            "gaps_total": rep5.get("gaps_total", snap5["gaps_total"]),
            "gaps_closed": rep5.get("gaps_closed", snap5["gaps_closed"]),
            "summary_note": rep5.get("summary_note") or snap5["summary_note"],
            "honest_note": rep5.get("honest_note") or snap5["honest_note"],
            "disclosure": rep5.get("disclosure") or snap5["disclosure"],
            "data_source": src5 or "内置快照（2026-10-05 实测；本部署内无 M5 报告 JSON）",
        },
        "m6": _phase_domain_case(),
        "artifacts": _manifest(repo_root),
        "data_source": src or "内置快照（2026-10-04 实测；本部署内无报告 JSON）",
        "ui": {
            "found_in_ui": True,
            "entry": "验证实力（accept）→「光子存储阵列（PM-M0–M6）」卡",
            "related_panels": [],
            "scope_note": "本卡覆盖**单元/阵列版图/外设系统与签核/国际对标收官**；单元物理闭式见 "
                          "`lda_l2/pm_m0…pm_m5`，非 UI 可点面板。",
        },
        "honest_note": PM_HONEST_NOTE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。红线断言 + 零重算断言（不 import 求解器）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    card = case_card(repo_root="__nonexistent_root__")

    # ① 优雅降级：根不存在 ⇒ 回落内置快照，不抛错
    chk("① 无报告时优雅降级（回落内置快照 + data_source 标注）",
        card["array"]["main"]["stats"]["n_devices"] == 10
        and "内置快照" in card["data_source"]
        and card["artifacts"]["available"] is False)

    # ② 🔴 不伪装实测：verdict 恒 DESIGN_SIGNOFF + 诚实边界关键词齐全
    note = card["honest_note"]
    chk("② 不伪装实测：verdict=DESIGN_SIGNOFF · 边界含「非流片」/「非 PDK」/"
        "「不报能效」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非流片、非实测" in note and "非任何 foundry 的 PDK deck" in note
        and "不报 pJ/bit" in note)

    # ③ 🔴 零重计算：本模块不 import 求解器/P&R/EDA（**ast 扫真实 import**）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    import ast
    banned_mods = {"numpy", "scipy", "lda_l2.pm_m3", "lda_l2.pm_m2",
                   "lda_l2.pm_m1", "lda_l2.pm_m0", "lda_l2.chip_layout_export",
                   "lda_layout.placement", "lda_chain.link_model"}
    bad_imports = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            bad_imports += [a.name for a in node.names if a.name in banned_mods]
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in banned_mods:
                bad_imports.append(mod)
    chk("③ 零重计算：无 numpy / 求解器 / P&R 模块 import（ast 实证）"
        "· 仅 json/os/typing",
        not bad_imports)

    # ④ 层契约与版图同源：SI/PCM/HEATER = 1/5/6
    chk("④ 版图层契约 SI/PCM/HEATER = 1/5/6 · 端口 6 个",
        PCM_LAYERS == {"SI": 1, "PCM": 5, "HEATER": 6} and len(PCM_PORTS) == 6)

    # ⑤ 独立复核口径自洽：层 5 == 单元数、层 6 == 6× 单元数（快照与报告同规则）
    lay = card["array"]["independent_scan"]["layers"]
    l5 = lay.get("5") if isinstance(lay, dict) else None
    l6 = lay.get("6") if isinstance(lay, dict) else None
    chk("⑤ 独立解码口径：层 5 == 单元数 且 层 6 == 6 × 单元数",
        l5 == 8 and l6 == 48)

    # ⑥ 缺口如实开放（不粉饰）：7 条缺口 · 含 endurance 不可判与「无 PDK」
    chk("⑥ 缺口逐条登记（7 条）· 含「endurance 不可判」与「无 PDK」",
        card["gaps_total"] == 7
        and any("endurance" in g["title"] for g in card["gaps"])
        and any("T1" in g["detail"] for g in card["gaps"]))

    # ⑦ 里程碑计数与 span 一致（算出来的）
    chk("⑦ 里程碑数 == span.milestones 且门禁判据合计 == sum(gate)",
        len(card["milestones"]) == card["span"]["milestones"]
        and card["span"]["gate_checks"] == sum(m["gate"] for m in MILESTONES))

    # ⑧ 规模化口径明标「版图容量」（防误读为已制备器件数）
    chk("⑧ 规模口径明标「版图容量」（诚实边界内）", "版图容量" in card["honest_note"])

    # ⑨ 返回体无非有限 float（防标准 JSON 出口崩 —— v0.9.186 血案同族）
    bad_float = []

    def _scan(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                _scan(v, path + "/" + str(k))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                _scan(v, path + "/[%d]" % i)
        elif isinstance(o, float):
            if o != o or o in (float("inf"), float("-inf")):
                bad_float.append(path)
    _scan(card)
    chk("⑨ 返回体无非有限 float（±inf/NaN 会让前端 JSON.parse 崩）",
        not bad_float)

    # ⑩ M4 外设块齐备（六段 · 与 lda_pm_m4_report.json 同构的顶层键）
    m4 = card.get("m4") or {}
    _m4_keys = {"readout", "rf_tradeoff", "write_driver", "system_budget",
                "assembly_2p5d", "upstream", "data_source"}
    chk("⑩ M4 外设块齐备（读出/权衡/写驱动/系统预算/2.5D/上游 六段 + 数据源）",
        _m4_keys <= set(m4.keys())
        and m4.get("system_budget", {}).get("bottleneck") in ("write", "drift", "read")
        and m4.get("assembly_2p5d", {}).get("lvs_verdict") in ("ACCEPT", "REJECT"))

    # ⑪ M4 密度瓶颈判据**快照内自洽**（EIC pitch ↕ PIC pitch ⇒ bottleneck）
    _asm = m4.get("assembly_2p5d") or {}
    chk("⑪ M4 密度瓶颈判据自洽（EIC pitch ↕ PIC pitch ⇒ bottleneck 翻转）",
        _asm.get("density_bottleneck")
        == ("eic" if _asm.get("eic_pitch_um", 0.0) > _asm.get("pic_pitch_um", 0.0) else "pic"))

    # ⑫ 🔴 PM-G7 结算口径翻转**快照内自洽**：主账瓶颈=write ∧ 旧口径瓶颈=drift ∧
    #    ν_T 上界 < 电学代理/100（315.8×）
    _sb = m4.get("system_budget") or {}
    _da = _sb.get("drift_anchor") or {}
    _dp = _sb.get("drift_proxy") or {}
    chk("⑫ PM-G7 结算自洽：主账 bottleneck=write ∧ 旧口径=drift ∧ ν_T_ub ≪ 电学 ν（>100×）",
        _sb.get("bottleneck") == "write" and _sb.get("all_ok") is True
        and _dp.get("bottleneck") == "drift"
        and _da.get("nu_t_ub", 1.0) * 100.0 < _dp.get("nu_max_electrical", 0.0))

    # ⑬ M5 对拍块齐备：7 行 ∧ 不可判行如实 ∧ 缺口终态与台账同源
    m5 = card.get("m5") or {}
    _rows = {r.get("metric"): r for r in (m5.get("rows") or [])}
    _gids = {g.get("id"): g.get("closed") for g in (m5.get("gaps_final") or [])}
    chk("⑬ M5 对拍块齐备：7 行 ∧ endurance=not_modeled ∧ G7/G2 闭合 ∧ G10/G11 开放",
        len(_rows) == 7
        and _rows.get("endurance", {}).get("verdict") == "not_modeled"
        and _rows.get("drift_index_nu", {}).get("verdict") == "derived_from_same_source"
        and _gids.get("PM-G7") is True and _gids.get("PM-G2") is True
        and _gids.get("PM-G10") is False and _gids.get("PM-G11") is False
        and m5.get("gaps_closed") == 7 and m5.get("gaps_total") == 9
        and m5.get("data_source"))

    # ⑭ 🔴 Γ 口径两口径并报（PM-G2 结算 ⇒ PM-G11）：胞长/密度两行必须带
    #    `gamma_sensitivity` ∧ 越窗判定为真 ∧ 行注记含「并报」（防选择性披露）
    _gs = {k: _rows.get(k, {}).get("gamma_sensitivity")
           for k in ("cell_length_um", "areal_density")}
    chk("⑭ Γ 口径并报（PM-G2 ⇒ PM-G11）：两行带 gamma_sensitivity ∧ 越窗为真 ∧ 注记含并报",
        all(isinstance(v, dict) for v in _gs.values())
        and all(v["design_point_inside_calibrated_window"] is False for v in _gs.values())
        and all(("并报" in _rows[k]["note"] and "PM-G11" in _rows[k]["note"]) for k in _gs)
        and any(g["id"] == "PM-G11" for g in card["gaps"]))

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("光子存储案例卡自检：",
          "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
