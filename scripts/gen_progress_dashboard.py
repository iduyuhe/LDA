# -*- coding: utf-8 -*-
"""对外进度仪表盘生成器（F-19 · B+C · v0.9.285）。

═══ 为什么要有它 ═══
四域**判决锚已 0 增长 14+ 版**（量子）/ 35+ 版（光子）/ 从未（电子）。
F-19 诊断结论（`docs/LDA_F19_锚产出机制诊断_2026-10-25.md`）：

  「闭式物理律 golden + 第二条独立数值路径」这套机制**只在两类条件下有效** ——
  物理量有解析解，且存在第二种成立的计算方法。**这类量已扫完**（86.1% 是闭式/解析）。

⇒ 问题不是"数字不够大"，是**用单一计数器衡量多维进展**。本模块把计量换成
**多维仪表盘**，并**显式声明锚已饱和**（C），而不是继续挤一个数字（A）。

═══ 三层计量（每项都可现算、可机核）═══
   ① 判决层 —— 锚（**已饱和**，但仍是对外最硬的东西：每锚 = 可独立复算的物理量）
   ② 证据层 —— 独立性证据分档（残差 / 扰动响应 / 桩）
   ③ 覆盖层 —— L2/L3 专属判据、盲区
   ④ 契约层 —— CI core 成员（防退化的机器）
   ⑤ 接口层 —— 端点 / 案例面板
   ⑥ 待改层 —— 缺口台账（含"未标状态"这一可核性缺口）

═══ 纪律 ═══
· 纯 stdlib、无时间戳、无随机 ⇒ 两次运行逐字节相同
· `--check` 只比对不写盘（供门禁守「文档与代码同源」）
· **饱和状态是声明式常量，不动态推断** —— 动态推断会引入版本/时间依赖，破坏确定性
· 不产生任何新物理量、不改账本
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "lda"))

# ═══════════════════════════════════════════════════════════════════════════
# C 的落地：**判决锚已饱和**（声明式，附可核理由）
# ═══════════════════════════════════════════════════════════════════════════
ANCHOR_SATURATED = True
ANCHOR_SATURATED_REASON = (
    "86.1% 的锚是闭式/解析类（analytical 249 + closed_form 217 = 466/541）；"
    "6 个被判死模块（R_s / cpw_quasi_static / ft_compiler / kinetic_inductance / "
    "noise_aware_schedule / conductor_surface）的 why_not_anchored 理由已逐条核实**全部成立**；"
    "唯一有实证的新机制（收敛阶锚）验实现不验物理，不能并入同一计数。"
    "详见 docs/LDA_F19_锚产出机制诊断_2026-10-25.md"
)


def _json(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def collect() -> dict:
    """现算全表（确定性）。缺某个数据源时该项标 None，**不猜**。"""
    from lda_harness.benchmarks import BENCHMARK_DEFS as D

    # ① 判决层：账本 + 成熟度 + oracle 类型
    tier = {}
    oracle = {}
    for v in D.values():
        tier[str(v.get("maturity_tier"))] = tier.get(str(v.get("maturity_tier")), 0) + 1
        pre = str(v.get("oracle")).split("(")[0]
        oracle[pre] = oracle.get(pre, 0) + 1
    closed_like = oracle.get("analytical", 0) + oracle.get("closed_form", 0)
    anchors = {
        "total": len(D),
        "by_tier": tier,
        "by_oracle": oracle,
        "closed_like": closed_like,
        "closed_like_pct": round(closed_like * 100.0 / len(D), 1) if D else None,
    }

    # ② 证据层：独立性证据分档
    rep = _json("lda/reports/verification_report.json") or {}
    ie = (rep.get("summary") or {}).get("independence_evidence") or {}
    evidence = {
        "strict_total": ie.get("strict_total"),
        "strict_dist": ie.get("strict_dist"),
        "dist": ie.get("dist"),
    }

    # ③ 覆盖层：锚-门禁覆盖
    cov = _json("lda/reports/anchor_gate_coverage.json") or {}
    cs = cov.get("summary") or {}
    coverage = {
        "anchors_total": cs.get("anchors_total"),
        "blind_without_any_coverage": cs.get("blind_without_any_coverage"),
        "blind_without_subset_coverage": cs.get("blind_without_subset_coverage"),
        "blind_by_band": cs.get("blind_by_band"),
    }

    # ④ 契约层：CI core 成员数（"防退化的机器"有多少道）
    try:
        from run_ci_regression import CORE_SMOKES as CORE
        core = len(CORE)
    except Exception:                      # noqa: BLE001 —— 取不到就如实说取不到
        core = None

    # ⑤ 接口层：端点 / 案例面板
    ap = _json("docs/api_reference.json") or {}
    ac = ap.get("counts") or {}
    try:
        from run_webui_entry_smoke import CASE_PANELS_MIN
        panels = int(CASE_PANELS_MIN)
    except Exception:                      # noqa: BLE001
        panels = None
    api = {"endpoints": ac.get("total"), "needs_login": ac.get("needs_login"),
           "described": ac.get("described"), "case_panels": panels}

    # ⑥ 待改层：缺口台账（**含未标状态**这一可核性缺口）
    gs = _json("docs/gap_settlement.json") or {}
    gaps = gs.get("total") or {}

    return {
        "schema": "lda_progress_dashboard_v1",
        "anchor_saturated": ANCHOR_SATURATED,
        "anchor_saturated_reason": ANCHOR_SATURATED_REASON,
        "anchors": anchors,
        "evidence": evidence,
        "coverage": coverage,
        "core_gates": core,
        "api": api,
        "gaps": gaps,
    }


def render_md(ref: dict) -> str:
    a, e, cv, api, gs = (ref["anchors"], ref["evidence"],
                         ref["coverage"], ref["api"], ref["gaps"])
    tier = a["by_tier"]
    sd = e.get("strict_dist") or {}
    out = [
        "# LDA 进度仪表盘（多维计量）",
        "",
        "> **本文件由 `scripts/gen_progress_dashboard.py` 生成，请勿手改** ——",
        "> 门禁 `run_p2_usability_smoke` 会重跑生成器比对，零漂移才通过。",
        "> 数据源全部**现算**（账本 / 报告 / 台账 / 路由表），无时间戳。",
        "",
        "## 为什么不用「锚数」当主轴",
        "",
        "> 🔴 **判决锚已饱和**：" + ref["anchor_saturated_reason"],
        "",
        "⇒ 锚数仍在表里（它是对外最硬的东西），但**不再单独代表进展**。",
        "",
        "## 一、判决层（**已饱和**）",
        "",
        "| 指标 | 值 | 状态 |",
        "|---|---|---|",
        "| 账本锚 | **%d** | 🔴 饱和 |" % a["total"],
        "| 其中 strict_independent | %d | — |" % tier.get("strict_independent", 0),
        "| 其中 self_certified | %d | 已知桩 |" % tier.get("self_certified", 0),
        "| 其中 degraded | %d | 已知降级 |" % tier.get("degraded", 0),
        "| 闭式/解析类占比 | **%d / %d = %.1f%%** | 🔴 饱和的**证据** |"
        % (a["closed_like"], a["total"], a["closed_like_pct"] or 0.0),
        "",
        "oracle 类型分布：",
        "",
        "| oracle | 数 |",
        "|---|---|",
    ]
    for k in sorted(a["by_oracle"], key=lambda x: -a["by_oracle"][x]):
        out.append("| `%s` | %d |" % (k, a["by_oracle"][k]))
    out += [
        "",
        "## 二、证据层（活跃）",
        "",
        "> 锚「通过」不等于「已验证」。本层回答：**每一条判决的证据到底是什么强度的**。",
        "",
        "| 证据档 | strict 内 | 全体 |",
        "|---|---|---|",
        "| `RESIDUAL_NONZERO`（有残差证据） | %s | %s |"
        % (sd.get("RESIDUAL_NONZERO", "—"), (e.get("dist") or {}).get("RESIDUAL_NONZERO", "—")),
        "| `PERTURBATION_RESPONSE`（靠扰动响应，**弱证据**） | %s | %s |"
        % (sd.get("PERTURBATION_RESPONSE", "—"), (e.get("dist") or {}).get("PERTURBATION_RESPONSE", "—")),
        "| `STUB`（桩） | %s | %s |"
        % (sd.get("STUB", "—"), (e.get("dist") or {}).get("STUB", "—")),
        "",
        "> `PERTURBATION_RESPONSE` **只证明「候选真在算」**，不证明方法学独立。",
        "",
        "## 三、覆盖层（活跃）",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        "| 锚总数（覆盖分母） | %s |" % cv.get("anchors_total"),
        "| 盲区（无任何门禁覆盖） | **%s** |" % cv.get("blind_without_any_coverage"),
        "| 盲区（无子集覆盖） | %s |" % cv.get("blind_without_subset_coverage"),
        "",
        "盲区按号段：`%s`" % json.dumps(cv.get("blind_by_band") or {}, ensure_ascii=False),
        "",
        "## 四、契约层（活跃）",
        "",
        "| 指标 | 值 | 意义 |",
        "|---|---|---|",
        "| CI core 门禁成员 | **%s** | 每道闸防一类退化；成员只增不减 |" % ref["core_gates"],
        "",
        "## 五、接口层（活跃）",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        "| REST 端点 | **%s**（需登录 %s） |" % (api.get("endpoints"), api.get("needs_login")),
        "| 端点有描述 | %s |" % api.get("described"),
        "| 案例面板族 | **%s** |" % api.get("case_panels"),
        "",
        "## 六、待改层（**本层最能说明「还差什么」**）",
        "",
        "| 指标 | 值 | 说明 |",
        "|---|---|---|",
        "| 案例卡缺口 | **%s** | 并账后总数（**四值口径**） |" % gs.get("gaps"),
        "| 已闭合 | %s | 证据链可查 |" % gs.get("closed"),
        "| 已结算 | %s | 已裁决**不再挂账**，但能力/证据未必具备 |" % gs.get("settled"),
        "| 🔴 **未闭合（真欠债）** | **%s** | 确认仍未做 —— **只有这一列是欠债** |" % gs.get("open"),
        "| 边界声明 | %s | 永久能力边界，**不是欠债** |" % gs.get("boundary"),
        "| 无状态标记 | %s | 应为 0（棘轮守，>0 即拒跑） |" % gs.get("unmarked"),
        "",
        "> 🔴 说「%s 条缺口」时**必须带分布**：把「边界声明」读成欠债、把「已结算」读成已完成，都是误读。"
        % gs.get("gaps"),
        "",
        "> 详见 `docs/GAP_SETTLEMENT.md`（同样由生成器产出，门禁 ⑬ 守）。",
        "",
        "## 七、签核维度（另有专表）",
        "",
        "18 张案例卡的 grade × evidence × deck 三维、以及**对外可宣称口径**，",
        "见 `GET /api/signing`（`lda_harness/signing_schema.py` 为真源）。",
        "",
        "> 🔴 **18 张卡无一可进对外材料**（`allow_external=[]`）—— 全项目零对外签核，",
        "> 因为没有一张卡的 deck 是 NDA。这是事实登记，不是缺陷遗漏。",
        "",
    ]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="对外进度仪表盘（F-19 B+C）")
    ap.add_argument("--check", action="store_true", help="只比对不写盘（供门禁）")
    a = ap.parse_args(argv)

    ref = collect()
    md = render_md(ref)
    js = json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    pm = os.path.join(ROOT, "docs", "PROGRESS.md")
    pj = os.path.join(ROOT, "docs", "progress_dashboard.json")

    if a.check:
        bad = []
        for path, want in ((pm, md), (pj, js)):
            if not os.path.isfile(path):
                bad.append("%s 缺" % os.path.basename(path))
                continue
            with open(path, "rb") as f:
                if f.read().decode("utf-8") != want:
                    bad.append("%s 漂移" % os.path.basename(path))
        if bad:
            print("FAIL: " + " / ".join(bad), file=sys.stderr)
            return 1
        print("OK: 仪表盘与代码一致（锚 %d · 闭式 %.1f%% · CI core %s · 端点 %s）"
              % (ref["anchors"]["total"], ref["anchors"]["closed_like_pct"] or 0.0,
                 ref["core_gates"], ref["api"].get("endpoints")))
        return 0

    for path, text in ((pm, md), (pj, js)):
        with open(path, "wb") as f:
            f.write(text.encode("utf-8"))
    print("已生成 docs/PROGRESS.md / docs/progress_dashboard.json")
    print("  锚 %d（闭式 %.1f%%）· 证据 strict %s · CI core %s · 端点 %s · 缺口 %s（未标 %s）"
          % (ref["anchors"]["total"], ref["anchors"]["closed_like_pct"] or 0.0,
             ref["evidence"].get("strict_total"), ref["core_gates"],
             ref["api"].get("endpoints"), ref["gaps"].get("gaps"),
             ref["gaps"].get("unmarked")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
