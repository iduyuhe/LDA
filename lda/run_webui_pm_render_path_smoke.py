# -*- coding: utf-8 -*-
"""WebUI 光子存储阵列（PM-M3 / PM-M4）案例卡前端**取值路径 + 反向完备 + onclick** 门禁（2026-10-04）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（血案 #32 同族 / 血案 #18·#19 机器化）
═══════════════════════════════════════════════════════════════════════════
后端侧门禁（`run_pm_m3_smoke` / 案例卡自检 / API 验收）**只保证 JSON 里有值**，
**不保证前端问对了地方**。本门禁把 `renderPm`（`sec-pm` 面板）的每条取值路径
逐条拿到真实 `pm_case.case_card()` JSON 上解析，并做**反向完备**——
把「后端加了字段、前端从不显示」的静默盲区钉死。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
  W1 onclick 接线（`$('runPm').onclick = runPm`）+ 面板 DOM 契约
     （`sec-pm` / `runPm` / `pmSummary` / `pmBody` / `pmConclusion` 齐备）
  W2 函数定义（runPm / renderPm 真在场，且 runPm 真调 apiGet('/api/pm_demo')）
  W3 🔴 **取值路径存在性**：renderPm 里每条 `X.a.b` 引用（别名**按位置**解出 base）
     在真实 JSON 上逐段解析 ⇒ 全部存在
  W4 🔴 **反向完备**：顶层键 + **全部**嵌套块 + **全部** `[]` 项目块（数量由 `len()` 现算，不写死），
     **每个字段都被前端引用**
  W5 路由接线（`/api/pm_demo` 登记 `GET_ROUTES` ∧ **不在** `HEAVY_POST_PATHS`）
  W6 🔴 突变探针（先证能变红）：改真实路径 / 抹掉别名绑定 / 往后端注入新字段 /
     改项目块字面量 ⇒ 对应判据必红；还原后复绿
  W8 🔴 里程碑 `gate` 数 == 对应后端门禁**实跑**行首 `[PASS]` 计数（逐档 + 缺映射即红）
     —— 治「卡内手写数字漂移」（血案：M3 gate 误登记 62；v0.9.194 M4b/M5 两处漏改）
  W9 🔴 `run_ci_regression.py` 注释声明的「N 判据」== 门禁实跑数（缺声明/漂移即红）
     —— 同一份判据数被手写在**三处**（门禁 docstring / `pm_case.gate` / CI 注释），
        W8 只锁住中间一处 ⇒ 本轮注释里 M0 31→33 / G7 15→20 / M5 16→18 /
        render_path 22→24 全部漂移（+ 规模数字 306→344 / 23→24 / 7→9）。
        🔴 附赠：W9 首次运行即抓出 `_pass_count` 自身口径错（`.count("[PASS]")`
        数出现次数 ⇒ 被 detail 文本里的 `[PASS]` 字面污染，偏 +1）——
        **度量工具自身也要有守卫**。
  W10 🔴 README「当前版本」行（**对外第一屏**）里的 `run_pm_*_smoke` 判据数 == 实跑数
     —— 同一份数字至此已手写在**四处**（门禁 docstring / `pm_case.gate` / CI 注释 / README），
        README 顶行写 `run_pm_m5_smoke` **16 判据` / `前端门禁 22/0` 全部落后（实为 18 / 26）。
        ⚠ 只覆盖能在实跑集里查到数的条目；`前端门禁 N/0`（= 本门禁自身）**不纳入**
        （避免自指），属**已知无机器守卫**的对外手写项。
        🔴 v0.9.197：对照面 = PM 门禁 ∪ **本版真改动的便宜门禁**（`_W10_EXTRA`）。
        W10b 反向完备（≥1 条可对照条目）在 v0.9.197 首跑即把「D-93 专项顶行**未提任何
        门禁**」判红（真问题，非空转）⇒ 本版改的是 `run_report_determinism_smoke`
        （不在 PM 门禁族）⇒ 对照面须覆盖它。**贵门禁不入**（`run_ecosystem_smoke`
        实测 ~207s，会拖垮本门禁预算）。
  W7 自入 CI core

🔴 **诚实边界**：本门禁是**静态**路径检查，不执行 JS、不看渲染好不好看；
值存在但口径漂移仍需 `run_pm_m3_smoke`（重算判据）守。二者互补：
**重算判据守「值对不对」，本门禁守「问对没问对」。**
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_harness.webui_js_ref import (  # noqa: E402
    render_body, alias_timeline, scan_refs, bad_refs, json_path_exists, js_ref_ok,
)

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")

#: 里程碑 ⇒ 后端门禁脚本。🔴 **反向完备**：卡内每档都必须有映射，新增档漏登记即红
#: （否则「卡内 gate 数」就成了一份没人对得上的手写数字）。
_GATE_SMOKE = {
    "M0": "run_pm_m0_smoke.py",
    "M1": "run_pm_m1_smoke.py",
    "M2": "run_pm_m2_smoke.py",
    "M3": "run_pm_m3_smoke.py",
    "M4": "run_pm_m4_smoke.py",
    "M4b": "run_pm_g7_settlement_smoke.py",
    "M5": "run_pm_m5_smoke.py",
    "M6": "run_pm_m6_smoke.py",
    "M6b": "run_pm_g2_smoke.py",
}


def _pass_count(sname):
    """实跑某后端门禁，数**行首** `[PASS]` 行 —— 即 pm_case 文档化的复核口径 `grep -c`。

    🔴 为什么值得进常驻门禁（v0.9.194）：`pm_case.MILESTONES[].gate` 是**手写**数字，
    曾因「M3 误登记 gate=62（混口径）」出过血案；本轮又出现 M4b 17→20 / M5 16→18
    两处同族漏改（判据加了，卡内数字没跟着走）——**手写数字 + 无机器对照 = 必漂**。

    🔴 v0.9.194 第二血案（W9 首次运行即抓到）：原实现用 `stdout.count("[PASS]")`
    （数**出现次数**）⇒ 任何 detail 文本里出现 `[PASS]` 字面就多算一条
    （`run_ci_gate_contract_smoke` 的 C1 detail 含 `输出='[PASS] 样例判据…'` ⇒ 偏 +1）。
    **度量工具自身口径错 = 漂移检测器自己漂**，且与它自称的 `grep -c`（按行）不符。
    改为按行首锚定 —— 口径 == 人工复核口径。
    """
    p = os.path.join(_HERE, sname)
    r = subprocess.run([sys.executable, p], cwd=_HERE, capture_output=True,
                       text=True, timeout=300)
    return sum(1 for ln in (r.stdout or "").splitlines()
               if ln.lstrip().startswith("[PASS"))


def _gate_drift(milestones, counts, mapping):
    """返回 `(缺映射的档, [(档, 卡内 gate, 实跑计数)])` —— 参数化以便探针喂变异体。"""
    have = {m["id"]: m for m in milestones}
    missing = sorted(set(have) - set(mapping))
    drift = []
    for mid, sname in sorted(mapping.items()):
        if mid in have and counts.get(sname) != have[mid]["gate"]:
            drift.append((mid, have[mid]["gate"], counts.get(sname)))
    return missing, drift


#: W9 目标：哪些门禁必须在 `run_ci_regression.py` 注释里**声明**判据数（↔ 反向完备）
#: 🔴 v0.9.198 试过把 `run_webui_pm_render_path_smoke.py`（**本门禁自身**）纳入目标集，
#:    结果 `_pass_count(自身)` ⇒ **子进程自递归** ⇒ 300s 超时（实测 rc=2）。⇒ 本门禁
#:    的判据数**结构上不可能**由它自己守（自指），只能由 `run_ci_regression` 注释 +
#:    CORE_SMOKES 注释两处人工对齐（本版把注释里长期漂移的 28 更正为实测 29）。
_GATE_DECL_TARGETS = sorted(set(_GATE_SMOKE.values()) | {"run_ci_gate_contract_smoke.py"})

#: W10 对照面**增量**：本版真改动、且**便宜可实跑**的门禁（**不扩** W8/W9 的目标范围）。
#: 🔴 v0.9.197：W10b 抓出「当前版本行无可对照条目」为**真问题**（非守卫空转）——
#: 本版改的是 `run_report_determinism_smoke`（不属 PM 门禁族）⇒ 对照面须覆盖它。
#: 贵门禁（`run_ecosystem_smoke` 实测 ~207s）**不入**此表 ⇒ 免拖垮本门禁预算；
#: 它自己的判据数由 `run_ecosystem_smoke` 内「报告快照 == 仓库现算」常驻判据守。
#: 🔴 v0.9.205：本版真改动 = PS-M0 自检判据接入 CORE（迁入 lda/ + 登记）。其**直接相关**
#:   的便宜门禁 = `run_ci_coverage_gate_smoke`（正是抓出「未接线缺口」的那道闸）⇒ 纳
#:   对照面，令其 README 判据数由机器守（非手写）。**不纳** `run_ps_m0_smoke` 本体：
#:   它实测 ~27s（主权流片链 DRC/LVS），会令本 smoke 从 ~45s 升至 ~75-95s、余量跌破
#:   3× 目标档甚至 2× 硬闸（B9 只降不升 ⇒ 必红）—— 违反本表「便宜可实跑」准入准则。
#: 🔴 v0.9.207：本版真改动 = PS-M7 WebUI 传感器面板。其**直接相关**的便宜门禁 =
#:   `run_sensor_panel_smoke`（实测 ~0.9s / 45 判据）⇒ 纳对照面，令 README 顶行
#:   （对外第一屏）的 PS-M7 判据数由机器守（非手写）；且它无自指、无递归风险。
#: 🔴 v0.9.208：本版真改动 = 入口可达性补漏（首屏案例条漏登 `sec-sensor` + 案例卡族
#:   「现算」化）。直接相关且**便宜**的门禁 = `run_webui_entry_smoke`（实测 ~0.1s ·
#:   纯文本解析零网络）⇒ 纳对照面，令其 README 顶行判据数（24）由机器守。
#:   附注：W10b 要求**顶行提到的每个 `run_*` 都在对照面内** —— 本版顶行同时提
#:   `run_webui_entry_smoke` / `run_sensor_panel_smoke` / `run_ci_coverage_gate_smoke`，
#:   三者现均在 `_counts10`，故 W10-W10b-W10-P1 形成闭环（漏一个即 W10b 当场红）。
#: 🔴 v0.9.209：本版真改动 = PS-M8（G2 几何半 + Q 增强 LOD）。其**直接相关**的便宜门禁 =
#:   `run_count_consistency_smoke`（实测 ~0.4s / 13 判据，纯读取 BENCHMARK_ORDER/DEFS +
#:   README/CONTRIBUTING 文本，零网络零子进程）⇒ 纳对照面，令其 README 顶行判据数由机器守。
#:   **不纳** `run_ps_m8_smoke`：实测 ~64s（FV 全矢量本征求解 ×3 几何 × golden/cand），
#:   超出本表「便宜可实跑」准入准则（会令本 smoke 从 ~45s 升至 ~110s、余量跌破 3× 目标档）。
#:   故顶行**只声明** `run_count_consistency_smoke` 判据数（`_readme_decl_drift` 对不在
#:   `counts` 内的条目不作守卫，属诚实边界；PS-M8 判据数由 `run_ci_coverage_gate_smoke`
#:   的 CORE 计数 + 本文件顶部 README 版本行一致性间接覆盖）。
#: 🔴 v0.9.210：本版真改动 = PS-M1/G4（传感窗口工艺层 + DRC 工艺例外 + PDK 器件）。
#:   直接相关且**便宜**的门禁 = `run_ps_m1_smoke`（实测 **~0.5 s** / **27 判据**，
#:   纯标准库 + lazy import lda_l2/lda_pdk）⇒ 纳对照面，令本版 README 顶行声明的
#:   27 判据由机器守（非手写）；它无自指、无递归、无重算风险。
#: 🔴 v0.9.211：本版真改动 = PS-M9（G2 器件本体）+ `resolve_specs(only=…)` 子集过滤。
#:   ⚠️ **不纳** `run_ps_m9_smoke`（实测 **26 s**）：本 smoke 宿主预算 **180 s**，纳入
#:   对照面会令其 48.6 s → ~75 s、余量跌至 **2.4×**（< 3× 目标档）—— 与 v0.9.209 对
#:   `run_ps_m8_smoke`（~64 s）的判定同族。故本版 README 顶行**不声明** PS-M9 判据数，
#:   改声明 `run_count_consistency_smoke` **13 判据**（0.4 s · 在对照面内）。
#:   🔴 **通则（v0.9.211 首轮全量 CI 当场抓出 · 已入 IRONLAWS）**：**README 顶行声明的
#:   每个 `run_*` 判据数都必须在 `_W10_EXTRA` 内** —— 声明了却不在对照面 ⇒
#:   `W10b`（条目须在对照面）+ `W10-P1`（README 旧值必红）**双红**，即守卫按设计顶回。
_W10_EXTRA = ("run_report_determinism_smoke.py", "run_ci_coverage_gate_smoke.py",
              "run_sensor_panel_smoke.py", "run_webui_entry_smoke.py",
              "run_count_consistency_smoke.py", "run_ps_m1_smoke.py")


def _declared_judge_counts(text):
    """从 `run_ci_regression.py` 文本抽出脚本条目**上方注释块**声明的判据数。

    覆盖两种条目写法：① `CORE_SMOKES` 列表项 `"run_x.py",`；② `_BUILTIN_TIMEOUT_OVERRIDE`
    字典项 `"run_x.py": 120.0,`。取注释块里**最后**一个 `N 判据`。行尾带注释或格式不符
    的条目 ⇒ 解析不到 ⇒ 计入「缺声明」（W9 判红），不给盲区。
    """
    out, buf = {}, []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            buf.append(s)
            continue
        m = re.match(r'^"(run_[A-Za-z0-9_]+\.py)"\s*[,:]', s)
        if m:
            nums = re.findall(r"(\d+)\s*判据", "\n".join(buf))
            if nums:
                out[m.group(1)] = int(nums[-1])
            buf = []
            continue
        buf = []
    return out


def _decl_drift(declared, counts, targets):
    """返回 `[(脚本, 注释声明, 实跑计数)]`，只列**不一致**者 —— 参数化以便探针喂变异体。"""
    return [(t, declared.get(t), counts.get(t)) for t in targets
            if declared.get(t) != counts.get(t)]


def _readme_decl_drift(text, counts):
    """从 README「当前版本」行抽 ``\\`run_x_smoke\\` **N 判据``，与实跑数对照（第四处手写面）。

    🔴 血案 v0.9.194：README 顶行（**对外第一屏**）写 ``run_pm_m5_smoke`` **16 判据`` /
    ``前端门禁 22/0``，全部落后于实跑（18 / 26）。README 是散文式超长行，
    **只覆盖能在 `counts` 里查到实跑数的条目**（避免自指）；查不到的条目返回空
    ⇒ 不误判，但也**不构成对它的守卫**（诚实边界）。

    🔴 坑中坑（W10-P1 当场抓出）：README 里脚本名**不带 `.py`**（`` `run_pm_m5_smoke` ``），
    而首版正则强制 `\\.py` ⇒ **恒不匹配 ⇒ W10 恒绿**（又一个假判据，且首跑就红）。
    正则改为 `.py` **可选**并归一化补全。
    """
    bad = []
    for m in re.finditer(r"`(run_[A-Za-z0-9_]+)(?:\.py)?`\s*\*\*(\d+)\s*判据", text):
        t, n = m.group(1) + ".py", int(m.group(2))
        if t in counts and counts[t] != n:
            bad.append((t, n, counts[t]))
    return bad


#: 顶层块反向完备：`(JSON 前缀元组, 说明)`
_BLOCKS = (
    (("identity",), "器件/物理识别"),
    (("identity", "layers"), "版图层号"),
    (("span",), "征程跨度"),
    (("pitch",), "单元 pitch"),
    (("upstream",), "上游汇总"),
    (("upstream", "cell_length"), "M1 单元长"),
    (("upstream", "levels"), "M1 电平数"),
    (("upstream", "thermal"), "M2 热隔离"),
    (("budget",), "设计预算"),
    (("budget", "single_cell_il_db"), "单元插损区间"),
    (("budget", "array_il_db"), "阵列总损区间"),
    (("array",), "阵列汇总"),
    (("array", "main"), "主阵列"),
    (("array", "main", "stats"), "主阵列版图统计"),
    (("array", "main", "drc"), "主阵列 DRC"),
    (("array", "main", "lvs"), "主阵列 LVS"),
    (("array", "independent_scan"), "独立解码复核"),
    (("array", "expected_layers"), "期望层计数"),
    (("array", "wide"), "宽阵列"),
    (("array", "wide", "stats"), "宽阵列版图统计"),
    (("device",), "实现器件"),
    (("ui",), "面板导航"),
    (("signoff_checks",), "签核断言"),
    (("artifacts",), "产出物元信息"),
    # ── M4 外设与系统（2026-10-04 新增 · 与 m4 报告块逐块同构）────────────────
    (("m4",), "M4 外设与系统汇总"),
    (("m4", "upstream"), "M4 上游汇总"),
    (("m4", "upstream", "levels"), "M4 上游电平设计"),
    (("m4", "readout"), "M4 读出链"),
    (("m4", "rf_tradeoff"), "M4 R_f 权衡"),
    (("m4", "write_driver"), "M4 写驱动"),
    (("m4", "system_budget"), "M4 系统误码预算"),
    (("m4", "system_budget", "drift_proxy"), "M4 drift 跨域代理"),
    (("m4", "system_budget", "eps"), "M4 等效误差分量"),
    (("m4", "system_budget", "share"), "M4 等效误差占比"),
    (("m4", "assembly_2p5d"), "M4 2.5D 装配"),
)

#: `[]` 项目块：`(JSON 前缀带 [] 路径, {js字面量: 相对字段})`
#: 🔴 前缀是**字符串**（点分 + 数组 `[]`）——由 `_block_keys` 归一后逐段解析。
_ITEM_BLOCKS = (
    ("scale_tiers[]", "规模档", {
        "t.bus_x_cells": "bus_x_cells", "t.n_cells_total": "n_cells_total",
        "t.n_devices": "n_devices", "t.n_nets": "n_nets",
        "t.n_elements": "n_elements", "t.gds_bytes": "gds_bytes",
        "t.area_um2": "area_um2", "t.lvs": "lvs",
        "t.lvs_violations": "lvs_violations", "t.independent_ok": "independent_ok",
        "t.n_buses": "n_buses", "t.n_cells_per_bus": "n_cells_per_bus",
        "t.drc_pass": "drc_pass", "t.expected_pcm": "expected_pcm",
        "t.got_pcm": "got_pcm", "t.width_um": "width_um", "t.height_um": "height_um",
    }),
    ("milestones[]", "里程碑", {
        "m.id": "id", "m.code": "code", "m.title": "title",
        "m.gate": "gate", "m.result": "result",
    }),
    ("findings[]", "设计洞察", {"f.title": "title", "f.detail": "detail"}),
    ("gaps[]", "缺口", {"g.id": "id", "g.title": "title", "g.detail": "detail"}),
    ("artifacts.items[]", "产出物清单", {"it.name": "name", "it.bytes": "bytes"}),
    ("m4.system_budget.t_hold_table[]", "M4 保持时间扫描", {
        "tt.t_hold_s": "t_hold_s", "tt.ber": "ber", "tt.eps_drift": "eps_drift",
        "tt.eps_total": "eps_total", "tt.bottleneck": "bottleneck",
    }),
    ("m4.system_budget.drift_proxy.per_proxy[]", "M4 drift 代理逐点", {
        "pp.nu_proxy": "nu_proxy", "pp.t_erode_s": "t_erode_s",
        "pp.t_erode_human": "t_erode_human",
    }),
    ("m5.rows[]", "M5 对拍行", {
        "r.metric": "metric", "r.metric_cn": "metric_cn",
        "r.ratio": "ratio", "r.verdict": "verdict",
        "r.lda_source": "lda_source", "r.lit_sources": "lit_sources",
        "r.note": "note", "r.lit_note": "lit_note",
        "r.design_only": "design_only", "r.cross_domain": "cross_domain",
        "r.self_consistency_only": "self_consistency_only", "r.gap_id": "gap_id",
        "r.lda_value": "lda_value", "r.lit_value": "lit_value",
        "r.gamma_sensitivity": "gamma_sensitivity",
    }),
    ("m5.gaps_final[]", "M5 缺口终态", {
        "g.id": "id", "g.closed": "closed", "g.title": "title",
    }),
)


#: 🔴 **显式豁免**（最后手段）：子键为**同源副本**，前端只渲染「真身」那一份。
#: 每条豁免都必须能通过「活性探针」（W4d）：该路径在本体里确实存在（不是死条款）。
_DUP_SUBTREES = {
    ("pitch", "thermal"): "与 upstream.thermal 同源副本（pitch 由 thermal 派生，前端只渲染上游那份）",
}


def _block_keys(card, prefix):
    """取 JSON 路径 `prefix` 处的键集（**列表取首元素**；支持 `a.b[]` 点分形式）。

    🔴 2026-10-04 修（本轮自查抓出的**假绿**）：原实现对字符串前缀 `for seg in prefix`
    会把 `"scale_tiers[]"` 当**字符序列**迭代 ⇒ 首字符 `'s'` 不在根字典里 ⇒ 立刻
    `return set()` ⇒ `W4c` 的「`[]` 项目块字段全覆盖」半边**恒真**（后端给项目块加了字段，
    前端从不渲染，门禁全绿）。修法 = 先把前缀归一成「段列表」（字符串按 `.` 切分），
    再对每段处理可选 `[]` 后缀。配反向探针 `W6-P6` 证明修完**真能变红**。
    """
    parts = prefix.split(".") if isinstance(prefix, str) else list(prefix)
    cur = card
    for part in parts:
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return set()
            cur = cur[key]
            if not isinstance(cur, list) or not cur:
                return set()
            cur = cur[0]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return set()
            cur = cur[part]
    if isinstance(cur, dict):
        return set(cur.keys())
    if isinstance(cur, list) and cur and isinstance(cur[0], dict):
        return set(cur[0].keys())
    return set()


def _ref_segs(refs, prefix):
    """由 refs 派生「在 `prefix` 这一层的被引用键名」。"""
    out = set()
    for _a, path, base in refs:
        full = tuple(base) + tuple(path.split("."))
        if len(full) > len(prefix) and full[:len(prefix)] == prefix:
            out.add(full[len(prefix)])
    return out


def _fulls(refs):
    return [tuple(base) + tuple(p.split(".")) for _a, p, base in refs]


def main() -> int:
    print("=" * 74)
    print("WebUI 光子存储阵列（PM-M3 / PM-M4）案例卡 前端取值路径 + 反向完备 + onclick 门禁")
    print("=" * 74)

    html = open(INDEX, encoding="utf-8").read()
    from lda_webui import pm_case as PC
    card = PC.case_card()

    rsrc = render_body(html, "renderPm")
    usrc = render_body(html, "runPm")

    # ── W1 onclick 接线 + 面板 DOM 契约 ─────────────────────────────────
    check("W1a onclick 接线：$('runPm').onclick = runPm 在场（防「能力上线却点不动」）",
          "$('runPm').onclick = runPm" in html)
    dom = all(('id="%s"' % i) in html for i in
              ("sec-pm", "runPm", "pmSummary", "pmBody", "pmConclusion"))
    check("W1b 面板 DOM 契约：sec-pm / runPm / pmSummary / pmBody / pmConclusion 齐备", dom)
    check("W1c 导航快捷链接 #sec-pm 在场（入口可达性）", 'href="#sec-pm"' in html)

    # ── W2 函数定义 ─────────────────────────────────────────────────────
    check("W2a runPm / renderPm 在 index.html 内定义（非空壳）",
          "function runPm(" in html and "function renderPm(" in html)
    check("W2b runPm 调 apiGet('/api/pm_demo') 并转交 renderPm",
          "/api/pm_demo" in usrc and "renderPm(" in usrc)
    heads = ("① 上游设计点", "② 单元间距", "③ 主阵列", "④ 独立解码复核", "⑤ 规模档",
             "⑥ 设计预算",
             "⑦ M4 读出链", "⑧ M4 读出灵敏度", "⑨ M4 写驱动", "⑩ M4 系统误码预算",
             "⑪ M4 2.5D 装配签核",
             "⑫ 征程里程碑", "⑬ 设计洞察", "⑭ 诚实缺口",
             "⑮ M5 国际对标收官", "⑯ 相位域", "⑰ 产出物")
    miss = [h for h in heads if h not in rsrc]
    check("W2c renderPm 真渲染 ①–⑰ 十七段（防「后端加了段、前端还是空壳」）", not miss,
          "缺段：%s" % miss)
    check("W2d 抽屉目录自动运行映射含 '#sec-pm': 'runPm'",
          '"#sec-pm": "runPm"' in html)

    # ── W3 取值路径存在性 ───────────────────────────────────────────────
    timeline, table = alias_timeline(rsrc)
    names = set(table.keys())
    refs = scan_refs(rsrc, names, timeline)
    bad = bad_refs(card, refs)
    check("W3 🔴 **取值路径存在性**：%d 条引用路径（%d 个别名）逐条在真实 `case_card()` JSON 上"
          "解析 ⇒ 全部存在（血案 #32 那一层）" % (len(refs), len(names) - 1),
          not bad, "坏路径 %d 条：%s" % (len(bad), bad[:4]))

    # ── W4 反向完备 ─────────────────────────────────────────────────────
    top_backend = set(card.keys())
    top_ref = {f[0] for f in _fulls(refs) if f}
    miss_top = sorted(top_backend - top_ref)
    check("W4a 反向完备（顶层）：`case_card()` 全部 %d 个顶层键都被前端引用" % len(top_backend),
          not miss_top, "未被引用：%s" % miss_top)

    miss_blocks = []
    for prefix, label in _BLOCKS:
        bk = {k for k in _block_keys(card, prefix)
              if (prefix + (k,)) not in _DUP_SUBTREES}          # 显式豁免（同源副本）
        rk = _ref_segs(refs, prefix)
        d = sorted(bk - rk)
        if d:
            miss_blocks.append("%s(%s)缺%s" % (".".join(prefix), label, d))
    check("W4b 反向完备（%d 个嵌套块）：每块每个字段都被前端引用" % len(_BLOCKS),
          not miss_blocks, "盲区：%s" % miss_blocks[:4])

    # W4d 豁免活性探针：豁免的路径必须在**本体**里真存在（防「写死豁免吞掉新成员」）
    dead = [".".join(p) for p in _DUP_SUBTREES
            if p[-1] not in _block_keys(card, p[:-1])]
    check("W4d 🔴 豁免活性：%d 条显式豁免的路径在 `case_card()` 里**确实存在**（非死条款）"
          % len(_DUP_SUBTREES), not dead, "失效豁免：%s" % dead)

    all_lits = []
    for _p, _l, m in _ITEM_BLOCKS:
        all_lits += list(m.keys())
    miss_items, bad_items = [], []
    for prefix, label, mapping in _ITEM_BLOCKS:
        bk = _block_keys(card, prefix)
        rk = set(mapping.values())
        d = sorted(bk - rk)
        if d:
            miss_items.append("%s(%s)缺%s" % (prefix, label, d))
        for lit, _rel in mapping.items():
            if not js_ref_ok(rsrc, lit, all_lits):
                bad_items.append(lit)
    check("W4c 反向完备（%d 个 `[]` 项目块）：字段全覆盖 ∧ 每条 JS 字面量真在场"
          % len(_ITEM_BLOCKS), not miss_items and not bad_items,
          "缺字段=%s 缺字面量=%s" % (miss_items[:3], bad_items[:3]))

    # ── W5 路由接线 ─────────────────────────────────────────────────────
    rt = open(ROUTES, encoding="utf-8").read()
    get_block = rt.split("GET_ROUTES = {")[1].split("\n}")[0] if "GET_ROUTES = {" in rt else ""
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("W5a `/api/pm_demo` 登记进 GET_ROUTES 且 handler = h_pm_demo",
          '"/api/pm_demo": h_pm_demo,' in get_block)
    check("W5b 🔴 `/api/pm_demo` **不在** HEAVY_POST_PATHS（零重计算 ⇒ 免登录、无 DoS 面）",
          "/api/pm_demo" not in heavy and "def h_pm_demo(" in rt)

    # ── W6 突变探针（先证能变红）────────────────────────────────────────
    def _bad_paths(body):
        tl, tb = alias_timeline(body)
        return [x.split(" → ")[0] for x in bad_refs(card, scan_refs(body, set(tb.keys()), tl))]

    assert _bad_paths(rsrc) == [], "前置：原体应无坏路径"

    p1 = _bad_paths(rsrc.replace("PI.pitch_um", "PI.pitch_um_typo", 1))
    check("W6-P1 把一条真实路径改成 `PI.pitch_um_typo` ⇒ W3 必红（模拟血案 #32）",
          len(p1) >= 1, "命中 %d 条：%s" % (len(p1), p1[:2]))

    # 抹掉别名绑定 ⇒ 该块「不再被引用」⇒ W4 必红
    assert ", UI=d.ui||{}" in rsrc, "前置：别名块含 UI=d.ui||{}（探针锚点）"
    body2 = rsrc.replace(", UI=d.ui||{}", "", 1)
    _tl2, _tb2 = alias_timeline(body2)
    _refs2 = scan_refs(body2, set(_tb2.keys()), _tl2)
    top2 = {f[0] for f in _fulls(_refs2) if f}
    check("W6-P2 抹掉 `UI=d.ui||{}` 绑定 ⇒ W4a 顶层反向完备必红（假盲区回归）",
          "ui" not in top2)

    # 后端注入新字段 ⇒ W4b 该块必红
    import copy as _copy
    card2 = _copy.deepcopy(card)
    card2["pitch"]["brand_new_field"] = 1
    bk2 = {k for k in _block_keys(card2, ("pitch",))
           if ("pitch", k) not in _DUP_SUBTREES}
    d = sorted(bk2 - _ref_segs(refs, ("pitch",)))
    check("W6-P3 后端往 `pitch` 注入新字段 ⇒ W4b 必红（防「后端加了、前端不显示」）",
          d == ["brand_new_field"], "命中：%s" % d)

    # 项目块字面量被改 ⇒ W4c 必红
    p4 = "t.independent_okX" if not js_ref_ok(rsrc, "t.independent_okX", all_lits) else None
    check("W6-P4 项目块 JS 字面量被改（`t.independent_ok` → `…okX`）⇒ W4c 必红",
          p4 is not None and "t.independent_ok" in rsrc)

    check("W6-P5 还原完整性：探针退出后复跑仍无坏路径 ∧ UI 绑定仍在",
          _bad_paths(rsrc) == [] and "UI=d.ui||{}" in rsrc and '"#sec-pm": "runPm"' in html)

    # 🔴 项目块「字段全覆盖」反向探针 —— 证明 `_block_keys` 的 `[]` 支持**真能变红**
    def _buggy_block_keys(c, prefix):
        """**修复前**实现的逐字复刻（`for seg in prefix` 逐字符）——仅用于证明假绿曾存在。"""
        cur = c
        for seg in prefix:
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return set()
        return set(cur.keys()) if isinstance(cur, dict) else set()

    card_i = _copy.deepcopy(card)
    card_i["scale_tiers"][0]["brand_new_item_field"] = 1
    card_i["m4"]["system_budget"]["t_hold_table"][0]["brand_new_item_field"] = 1
    dm = sorted(_block_keys(card_i, "scale_tiers[]")
                - set(_ITEM_BLOCKS[0][2].values()))
    dm2 = sorted(_block_keys(card_i, "m4.system_budget.t_hold_table[]")
                 - set(_ITEM_BLOCKS[5][2].values()))
    check("W6-P6 项目块字段覆盖能变红：向 `scale_tiers[0]` / `t_hold_table[0]` 注入新字段 "
          "⇒ W4c 必红（%s / %s）" % (dm, dm2),
          dm == ["brand_new_item_field"] and dm2 == ["brand_new_item_field"])
    check("W6-P6b 🔴 假绿复现：**修复前**实现 `_block_keys(card, \"scale_tiers[]\")` 恒为**空集**"
          "（⇒ W4c 字段覆盖半边恒绿）——这就是本轮被修掉的那个假判据",
          _buggy_block_keys(card_i, "scale_tiers[]") == set()
          and len(_block_keys(card_i, "scale_tiers[]")) >= 2)

    # ── W8 🔴 里程碑 gate 数 == 后端门禁实跑计数（对「手写数字」上机器对照）──
    _ci = os.path.join(_HERE, "run_ci_regression.py")
    _ck = open(_ci, encoding="utf-8").read() if os.path.exists(_ci) else ""
    _counts = {s: _pass_count(s) for s in _GATE_DECL_TARGETS}
    _missing, _drift = _gate_drift(PC.MILESTONES, _counts, _GATE_SMOKE)
    check("W8 🔴 里程碑 `gate` == 对应后端门禁实跑 `[PASS]` 计数（逐档 · 缺映射即红）",
          not _missing and not _drift,
          "缺映射=%s · 漂移=%s · 实跑=%s" % (_missing, _drift,
                                            {k: v for k, v in _counts.items()}))

    # W8-P1 变异探针：原样绿 ∧ 计数变 / 卡内 gate 变 / 缺映射 三改各自必红
    _c_bad = dict(_counts)
    _c_bad[sorted(_GATE_SMOKE.values())[-1]] += 1
    _ms_bad = [dict(m) for m in PC.MILESTONES]
    for _m in _ms_bad:
        if _m["id"] == "M5":
            _m["gate"] += 1
    _map_del = {k: v for k, v in _GATE_SMOKE.items() if k != "M5"}
    _p8 = [_gate_drift(PC.MILESTONES, _counts, _GATE_SMOKE) == ([], []),
           _gate_drift(PC.MILESTONES, _c_bad, _GATE_SMOKE)[1] != [],
           _gate_drift(_ms_bad, _counts, _GATE_SMOKE)[1] != [],
           _gate_drift(PC.MILESTONES, _counts, _map_del)[0] == ["M5"]]
    check("W8-P1 突变探针：原样绿 ∧ 实跑计数变 / 卡内 gate 变 / 缺映射 三改必红",
          all(_p8), "p8=%s" % _p8)

    # ── W9 🔴 `run_ci_regression.py` 注释里的「N 判据」== 门禁实跑数 ──────────
    # 血案 v0.9.194：同一份「判据数」被手写在**三处**（门禁 docstring / `pm_case.gate` /
    # `run_ci_regression` 注释），W8 只锁住了第二处 ⇒ 本轮全量 CI 后复核发现注释里
    # M0 31（实际 33）/ G7 15（20）/ M5 16（18）/ render_path 22（24）+ 规模数字
    # 306/23/7（实际 344/24/9）**全部漂移**。⇒ 第三处也必须上机器对照。
    _decl = _declared_judge_counts(_ck)
    _decl_bad = _decl_drift(_decl, _counts, _GATE_DECL_TARGETS)
    check("W9 🔴 `run_ci_regression.py` 注释声明的判据数 == 门禁实跑数（缺声明/漂移即红）",
          not _decl_bad, "漂移=%s" % _decl_bad)

    _syn = '# x：7 判据\n"run_x_smoke.py",\n'
    _p9 = [_decl_drift(_decl, _counts, _GATE_DECL_TARGETS) == [],                 # 原样绿
           _decl_drift(_decl, dict(_counts, **{"run_pm_m2_smoke.py": 99}),
                       _GATE_DECL_TARGETS) != [],                              # 实跑数变必红
           _decl_drift({k: v for k, v in _decl.items() if k != "run_pm_m2_smoke.py"},
                       _counts, _GATE_DECL_TARGETS) != [],                     # 缺声明必红
           _declared_judge_counts(_syn) == {"run_x_smoke.py": 7},                # 解析器真读注释
           _decl_drift(_declared_judge_counts(_ck.replace("40 判据", "99 判据")),
                       _counts, _GATE_DECL_TARGETS) != []]                     # 注释数字改必红
    check("W9-P1 突变探针：原样绿 ∧ 实跑数变 / 缺声明 / 注释数字改 三改必红 ∧ 解析器真读注释",
          all(_p9), "p9=%s" % _p9)

    # ── W10 🔴 README「当前版本」行里的手写判据数 == 实跑数（第四处手写面）─────
    # 血案 v0.9.194：README 顶行（**对外第一屏**）写 ``run_pm_m5_smoke`` **16 判据`` /
    # ``前端门禁 22/0`` 全部落后（实为 18 / 26）。同一份数字至此已手写在**四处**
    # （门禁 docstring / pm_case.gate / CI 注释 / README）⇒ 每处都得机器对照。
    # 🔴 v0.9.197：对照面 `_counts10` = `_counts`（PM 门禁 + 契约门禁）**∪ 本版真改动的
    #   便宜门禁**（`_W10_EXTRA`）。W10b 曾把「v0.9.197 顶行（D-93 专项）未提任何门禁」
    #   判红 ⇒ 本版改的 `run_report_determinism_smoke` 不属 PM 门禁族，须补进对照面。
    _counts10 = dict(_counts, **{s: _pass_count(s) for s in _W10_EXTRA})
    _rd = os.path.join(_ROOT, "README.md")
    _rtext = open(_rd, encoding="utf-8").read() if os.path.exists(_rd) else ""
    _cur = next((ln for ln in _rtext.splitlines() if "✅ 当前版本" in ln), "")
    _rd_bad = _readme_decl_drift(_cur, _counts10)
    check("W10 🔴 README「当前版本」行里的 `run_pm_*_smoke` 判据数 == 实跑数",
          bool(_cur) and not _rd_bad, "漂移=%s" % (_rd_bad or "无"))

    # 🔴 W10b 反向完备：当前版本行**必须**至少含 1 条可对照条目 ——
    #   否则 `_readme_decl_drift` 恒返空 ⇒ W10 退化为恒绿（守卫空转）。
    _cur_names = re.findall(r"`(run_[A-Za-z0-9_]+)(?:\.py)?`\s*\*\*\d+\s*判据", _cur)
    check("W10b 🔴 反向完备：当前版本行至少含 1 条 `run_*` 判据数条目（防 W10 恒绿空转）",
          len(_cur_names) >= 1 and all(n + ".py" in _counts10 for n in _cur_names),
          "条目=%s" % _cur_names)

    # 🔴 W10-P1（v0.9.195 修）：原实现**硬编码** `run_pm_m5_smoke.py` —— 一旦当前版本行
    #   不再提及 m5（如本版改提 m6），探针第二项**恒 False**（改一个当前行里不存在的脚本
    #   当然不产生漂移）⇒ 探针自己失效。改为**动态取当前行第一个条目**做变异。
    _t10 = (_cur_names[0] + ".py") if _cur_names else "run_pm_m5_smoke.py"
    _p10 = [_readme_decl_drift(_cur, _counts10) == [],                  # 原样绿
            _readme_decl_drift(_cur, dict(_counts10,
                                          **{_t10: _counts10.get(_t10, 0) + 1}))
            != [],                                                      # 实跑数变必红
            _readme_decl_drift("`%s` **%d 判据" % (_t10.replace(".py", ""),
                                                 _counts10.get(_t10, 0) + 1),
                               _counts10) != []]                        # README 旧值必红
    check("W10-P1 突变探针：原样绿 ∧ 实跑数变 / README 旧值 两改必红（动态取当前行条目）",
          all(_p10), "p10=%s t=%s" % (_p10, _t10))

    # ── W7 自入 CI core ─────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("W7 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_pm_render_path_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
