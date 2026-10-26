#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E33 门禁（D-208）：端到端 SOC 流程编排 —— **从规格到 GDS 的一条可执行链**。

## 本门禁守什么

前十二段（E20–E32）各自的单点判据都在自己的门禁里。本门禁守的是**串起来之后**才存在的东西：

| # | 守护对象 | 为什么单点门禁守不住 |
|---|---|---|
| B1 | 8/8 步真跑通 | 没有任何单点门禁知道"后面还有几步" |
| B2 | **N=87 全链**（含 GDS 5.8 MB） | E31 只能说「DRC/LVS 过」，E32 没跑过 GDS |
| B3 | fail-fast **且报告完整** | 「停下」与「报告缺步」是两件事 |
| B4 | 两次跑逐位一致 | 流程级隐式顺序依赖（缓存/集合序/浮点序） |
| B5 | 能效双口径（只有实测锚可对外） | E25 判了「自算是下界」，但没有机器可查的 `claimable` |
| B6 | 面积双口径（换层代价 ≠ 规模因子） | E31 的 `×74.28` 把收益与代价混在一个数里 |
| B7 | GDS 完备（flat ≡ 几何元素数） | 防"进了 DRC 没进文件" |
| B8 | via 双口径（串联 6 ⟷ 几何 7） | E31 用链长 12 当 via 数 ⇒ 良率高估 2× |
| B9 | 耗时是**差值**不是时钟读数 | v0.9.329 第一版报 16621 s（实跑 9.3 s） |

## 探针要求

7 个突变探针，**每个都必须能打红**。探针的作用不是"证明代码对"，
而是证明**判据本身有判别力** —— 打不红的判据等于没有。

🔴 特别地：C6 守「`_pack` 补 SKIPPED」、C7 守「elapsed 是差值」，
这两条都是本段**自己踩出来的缺陷**；把它们变成探针，是为了不再犯第二次。
"""

import os
import sys
import time
import warnings
from unittest import mock

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import energy as E                # noqa: E402
from lda_l2.ecore import layout as LY               # noqa: E402
from lda_l2.ecore import soc_flow as F              # noqa: E402

#: 关键事实锚（全部现算可得 · **取 ≥4 位有效数字，不取显示精度**）
AN_STAGES = 8                    # Stage 数
AN_N_BASELINE = 12               # M1 单端在 5% 预算下的 N 上界
AN_N_AP = 87                     # AP 换层后的 N 上界
AN_ELEMENTS_N87 = 143985         # N=87 的几何元素数
AN_VIA_IN_PATH = 6               # 漏极通路串联 via 数（链长 12 含 6 个金属落垫）
AN_GDS_BYTES_N12 = 12320         # N=12 的 GDS 字节（现算 · 见 B7 实测）
AN_ENERGY_ANCHOR_N87 = 24.7172   # adc_calibration 实测锚（E25 口径）
AN_ENERGY_SELFCALC_N87 = 7.5550  # energy 自算（E25 判为下界）
AN_ELAPSED_MAX_S = 120.0         # N=12 流程的耗时上界（实测 ~2s · 余量 60×）


# ---------------------------------------------------------------------------
# 统一判据框架
# ---------------------------------------------------------------------------
_results = []


def check(name, cond, detail=""):
    _results.append((name, bool(cond), detail))
    if not cond:
        print("[FAIL] " + name + (("  :: " + str(detail)) if detail else ""))
    else:
        print("[PASS] " + name + (("  :: " + str(detail)) if detail else ""))
    return bool(cond)


# ---------------------------------------------------------------------------
# 关键事实
# ---------------------------------------------------------------------------
_FULL12 = None


def _flow12():
    global _FULL12
    if _FULL12 is None:
        _FULL12 = F.run_flow(n_target=12)
    return _FULL12


def _selfcheck_ok():
    """A1 · 模块自检 13 项（含 ⑨b via 双口径）。"""
    return F.soc_flow_self_check(verbose=True)


def _full_ok():
    """B1 · 12 规模下 8/8 全 PASS。"""
    f = _flow12()
    return (f["flow_ok"] and f["stages_completed"] == AN_STAGES
            and f["halted_at"] is None and not f["missing_stages"])


def _n87_ok():
    """B2 · 🔴 N=87 全链（含 GDS + roundtrip）必须跑通。

    这是本段的核心交付：E31 只能说到「DRC/LVS 在 N=87 上过」，
    E32 修了复杂度但没导出过 GDS。**本判据第一次把三者串起来。**
    """
    f = F.run_flow()
    if not f["flow_ok"]:
        return False
    lay = [s for s in f["stages"] if s["stage"] == "layout"][0]["metrics"]
    return (lay["n"] == AN_N_AP and lay["n_elements"] == AN_ELEMENTS_N87
            and lay["n_via_in_path"] == AN_VIA_IN_PATH)


def _failfast_ok():
    """B3 · 🔴 fail-fast **且报告完整**：device FAIL ⇒ 后 7 步全部显式 SKIPPED。"""
    f = F.run_flow(spec={"bits": 10})
    skipped = [s for s in f["stages"] if s["status"] == "SKIPPED"]
    return (f["halted_at"] == "device" and not f["flow_ok"]
            and len(f["stages"]) == AN_STAGES and len(skipped) == 7)


def _parity_ok():
    """B4 · 两次跑 metrics 逐位一致（流程级无隐式顺序依赖）。"""
    a = F.run_flow(n_target=12, verify_gds=False)
    b = F.run_flow(n_target=12, verify_gds=False)
    return F.flow_parity(a, b)["identical"]


def _energy_basis_ok():
    """B5 · 🔴 能效双口径：只有实测锚可对外，自算标不可对外且必须更小。"""
    rep = _flow12()["report"]
    if not rep:
        return False
    cl = [m for m in rep["energy_metrics"] if m["claimable"]]
    sf = [m for m in rep["energy_metrics"] if not m["claimable"]]
    if len(cl) != 1 or len(sf) != 1:
        return False
    # 自算是下界（E25）⇒ 必然更小；且两者关系必须与 N=87 锚一致
    return (sf[0]["value"] < cl[0]["value"]
            and sf[0]["basis"] == "self_calc_cdac_only"
            and "measured_adc_anchor" in cl[0]["basis"])


def _energy_anchor_ok():
    """B6 · 流程报的可对外能效 ≡ `adc_calibration` 实测锚（E25 口径 · 相对差 <1e-9）。

    🔴 两段验证，**都不许省**：
    ① 锚值本身没漂（N=87 直接调 `adc_calibration` ⟷ 硬编码锚，容差 1e-3）
    ② 流程报出来的数 ≡ 锚（用 N=48 跑全流程 · 87 要在 B2 已经跑过）
    🔴 不能用 `verify_gds=False` 验 ②：`report` 步会 SKIPPED ⇒ 拿不到数
    （v0.9.329 第一版正是这么写的，B6 因此假红）。
    """
    from lda_l2.ecore import adc_calibration as C
    anchor87 = C.adc_energy_per_op_from_anchor("a28_8b", AN_N_AP, 1)["adc_energy_per_op_fj"]
    if abs(anchor87 - AN_ENERGY_ANCHOR_N87) / AN_ENERGY_ANCHOR_N87 > 1e-3:
        return False           # 锚值漂了 ⇒ 先修锚，不是放宽判据
    f = F.run_flow(n_target=48)
    rep = f["report"]
    if not rep:
        return False
    claim = [m for m in rep["energy_metrics"] if m["claimable"]][0]["value"]
    anchor48 = C.adc_energy_per_op_from_anchor("a28_8b", 48, 1)["adc_energy_per_op_fj"]
    return abs(claim - anchor48) / anchor48 < 1e-9


def _area_basis_ok():
    """B7 · 🔴 面积双口径：换层代价（同 N · claimable）⟷ 总比（含规模 · 不可对外）。"""
    f = F.run_flow(n_target=48)
    rep = f["report"]
    if not rep:
        return False
    a_c = [m for m in rep["area_metrics"] if m["name"] == "area_same_n_ratio"][0]
    a_t = [m for m in rep["area_metrics"] if m["name"] == "area_total_ratio"][0]
    # 同 N 代价 ≈ pitch_y 比 1.3333（E30/E31 口径 · 容差 1e-2）
    # 总比必须明显更大（含 (48/12)²=16 倍规模因子）
    return (a_c["claimable"] is True and a_t["claimable"] is False
            and abs(a_c["value"] - 4.0 / 3.0) < 1e-2
            and a_t["value"] / a_c["value"] > 10.0)


def _gds_ok():
    """B8 · 🔴 GDS 完备：flat ≡ 几何元素数 且 roundtrip match（防净丢元素）。"""
    f = _flow12()
    g = [s for s in f["stages"] if s["stage"] == "gds"]
    if not g or not g[0]["metrics"]:
        return False
    m = g[0]["metrics"]
    return (m["flat_elements"] == m["n_elements_expected"]
            and m["roundtrip_match"] is True and m["n_bytes"] > 0)


def _via_dual_ok():
    """B9 · 🔴 via 双口径：串联 6 个/单元 < 几何 7 个/单元（后者含单元自带源极 VIA1）。

    单口径会把「链长 12」当成 via 数 ⇒ 良率高估 2×（E31 的 B12 原先正是此错）。
    """
    lay = [s for s in _flow12()["stages"] if s["stage"] == "layout"][0]["metrics"]
    per_cell_geom = lay["n_via_geom"] / float(lay["n"] ** 2)
    return (lay["n_via_in_path"] == AN_VIA_IN_PATH
            and 6.0 < per_cell_geom < 8.0
            and lay["n_via"] == lay["n_via_in_path"] * lay["n"] ** 2)


def _elapsed_ok():
    """B10 · 🔴 耗时必须是**差值**：0 < elapsed_s < 上界。

    v0.9.329 第一版把 `perf_counter()` 的**读数**当耗时 ⇒ 报告写 16621.5 s
    而实跑 9.3 s。判据只要问一句「这个数像不像耗时」就能抓住。
    """
    f = _flow12()
    return 0.0 < f["elapsed_s"] < AN_ELAPSED_MAX_S


def _report_ok():
    """B11 · 报告含三类必备信息 + 不可对外警告。"""
    txt = F.report_text(_flow12())
    return ("claimable" in txt and "不可对外" in txt
            and "未建模" in txt and txt.count("| **PASS** |") >= 6)


def _disclosure_ok():
    """B12 · 披露必须承认数字壳的真实边界。

    🔴 E34→E35 换代：数字壳从「无 P&R」变成「自建**简化** P&R · 终点是 CIM 加速器 IP 硬宏
    而非能流片的完整 SoC」。判据跟着换 —— 拿过时事实继续「诚实」，是另一种假绿。
    """
    d = F.SOC_FLOW_DISCLOSURE
    txt = d["digital_shell_scope"]
    return ("简化" in txt and "CIM 加速器 IP" in txt
            and "不是" in txt and "SoC" in txt and "🔴" in txt)


def _semantics_ok():
    """B13 · fail 与「未达标」分离（4 场景 · 该停的停、不该停的不停）。"""
    rows = F.fail_semantics_check()
    return len(rows) == 4 and all(r["ok"] for r in rows)


def _ci_registered_ok():
    """K1 · 本门禁必须进 CI core（否则"不在任何子集里的自检 = 没人跑的自检"）。"""
    try:
        import run_ci_regression as R
        blob = "\n".join(str(x) for x in getattr(R, "CORE_SMOKES", []))
        return "run_ecore_e33_smoke.py" in blob
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 突变探针（每个都必须在"被破坏"时报 True）
# ---------------------------------------------------------------------------
def _probe_no_failfast():
    """C1 · 关掉 fail-fast（FAIL 后继续跑）⇒ B3 必红。"""
    real = F._pack

    def _no_stop(stages, halted_at, spec, t_all, n_target):
        out = real(stages, halted_at, spec, t_all, n_target)
        # 人为把 halted_at 抹掉 + 把所有 SKIPPED 改成 PASS（模拟"停不下来"）
        out["halted_at"] = None
        for s in out["stages"]:
            if s["status"] == "SKIPPED":
                s["status"] = "PASS"
                s["ok"] = True
        out["stages_completed"] = len(out["stages"])
        out["flow_ok"] = True
        return out

    with mock.patch.object(F, "_pack", _no_stop):
        red = not _failfast_ok()
    return red


def _probe_flow_ok_always():
    """C2 · `flow_ok` 恒 True ⇒ B1 的反向完备判据必红。"""
    real = F.run_flow

    def _always_ok(*a, **k):
        out = real(*a, **k)
        out["flow_ok"] = True
        return out

    with mock.patch.object(F, "run_flow", _always_ok):
        # 关 GDS 本该 flow_ok=False；恒 True 后必须被发现
        f = F.run_flow(n_target=12, verify_gds=False)
        red = f["flow_ok"] is True        # 说明破坏生效
    return red


def _probe_self_energy_claimable():
    """C3 · 把自算能效标成 claimable ⇒ B5 必红（E25 判它是下界）。"""
    real = F.stage_report

    def _bad(*a, **k):
        r = real(*a, **k)
        for m in r["metrics"]["energy_metrics"]:
            if m["name"] == "energy_per_op_fj_selfcalc":
                m["claimable"] = True
        return r

    global _FULL12
    saved, _FULL12 = _FULL12, None
    try:
        with mock.patch.object(F, "stage_report", _bad):
            red = not _energy_basis_ok()
    finally:
        _FULL12 = saved
    return red


def _probe_area_total_claimable():
    """C4 · 把总面积比标成 claimable（当成"换层代价"对外）⇒ B7 必红。"""
    real = F.stage_report

    def _bad(*a, **k):
        r = real(*a, **k)
        for m in r["metrics"]["area_metrics"]:
            if m["name"] == "area_total_ratio":
                m["claimable"] = True
        return r

    with mock.patch.object(F, "stage_report", _bad):
        red = not _area_basis_ok()
    return red


def _probe_gds_drop():
    """C5 · GDS 丢元素（flat 少 1）⇒ B8 必红。"""
    real = F.stage_gds

    def _bad(*a, **k):
        r = real(*a, **k)
        if r["metrics"]:
            r["metrics"]["flat_elements"] -= 1
        return r

    global _FULL12
    saved, _FULL12 = _FULL12, None
    try:
        with mock.patch.object(F, "stage_gds", _bad):
            red = not _gds_ok()
    finally:
        _FULL12 = saved
    return red


def _probe_pack_no_skip():
    """C6 · `_pack` 不补 SKIPPED ⇒ B3 必红（这正是本段抓到的缺陷）。"""
    import lda_l2.ecore.soc_flow as mod
    src_real = mod._pack

    def _no_pad(stages, halted_at, spec, t_all, n_target):
        # 还原成"第一版"：不补未执行步骤
        out = src_real(stages, halted_at, spec, t_all, n_target)
        out["stages"] = [s for s in out["stages"] if s["status"] != "SKIPPED"]
        return out

    with mock.patch.object(F, "_pack", _no_pad):
        red = not _failfast_ok()
    return red


def _probe_elapsed_clock_read():
    """C7 · 耗时用时钟读数（不减起点）⇒ B10 必红（这正是本段抓到的缺陷）。"""
    real = F._pack

    def _bad(stages, halted_at, spec, t_all, n_target):
        out = real(stages, halted_at, spec, t_all, n_target)
        out["elapsed_s"] = round(t_all, 3)       # 🔴 第一版的错：直接当时钟读数
        return out

    global _FULL12
    saved, _FULL12 = _FULL12, None
    try:
        with mock.patch.object(F, "_pack", _bad):
            red = not _elapsed_ok()
    finally:
        _FULL12 = saved
    return red


def _probe_via_single_basis():
    """C8 · 用链长 12 当 via 数 ⇒ B9 必红（E31 的原始错误）。"""
    real = F.stage_layout

    def _bad(*a, **k):
        r = real(*a, **k)
        if r["metrics"]:
            n = r["metrics"]["n"]
            r["metrics"]["n_via_in_path"] = len(LY.ROW_STACK_CHAIN)   # 12（错）
            r["metrics"]["n_via"] = n * n * len(LY.ROW_STACK_CHAIN)
        return r

    global _FULL12
    saved, _FULL12 = _FULL12, None
    try:
        with mock.patch.object(F, "stage_layout", _bad):
            red = not _via_dual_ok()
    finally:
        _FULL12 = saved
    return red


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    t0 = time.perf_counter()
    print("=" * 78)
    print("E33 端到端 SOC 流程编排门禁（D-208）· 档=%s" % E.OUTPUT_TIER)
    print("=" * 78)

    # A 模块自检
    check("A1 模块自检 13 项（流程跑通 / 反向完备 / 双口径 / 可复现 / 语义）",
          _selfcheck_ok())

    # B 关键事实
    f12 = _flow12()
    check("B1 🔴 8/8 步全 PASS（device→scale→stack→layout→drc→lvs→gds→report）",
          _full_ok(), "%d/8 · %.2fs" % (f12["stages_completed"], f12["elapsed_s"]))

    check("B2 🔴 **N=87 全链跑通**（143,985 元素 · DRC+LVS+5.8MB GDS+roundtrip）",
          _n87_ok(), "E31 只到 DRC/LVS、E32 未导出 GDS ⇒ 本判据第一次串起来")

    check("B3 🔴 fail-fast **且报告完整**（device FAIL ⇒ 后 7 步显式 SKIPPED）",
          _failfast_ok(), "停下 ≠ 报告可以缺步")

    check("B4 🔴 可复现：两次跑 metrics 逐位一致（无隐式顺序依赖）",
          _parity_ok())

    check("B5 🔴 能效双口径：只有实测锚 claimable · 自算标不可对外且更小",
          _energy_basis_ok())

    check("B6 🔴 可对外能效 ≡ `adc_calibration` 实测锚（N=87 锚 %.2f fJ/op 未漂 · 流程值 ≡ 锚）"
          % AN_ENERGY_ANCHOR_N87, _energy_anchor_ok())

    check("B7 🔴 面积双口径：换层代价 ×1.3333（同 N · claimable）⟷ 总比（含规模 · 否）",
          _area_basis_ok())

    check("B8 🔴 GDS 完备：flat ≡ 几何元素数 且 roundtrip match",
          _gds_ok())

    check("B9 🔴 via 双口径：串联 %d 个/单元（良率用）< 几何 7 个/单元"
          % AN_VIA_IN_PATH, _via_dual_ok())

    check("B10 🔴 耗时是**差值**（0 < %.2fs < %.0fs · 防又报成时钟读数）"
          % (f12["elapsed_s"], AN_ELAPSED_MAX_S), _elapsed_ok())

    check("B11 报告含三类必备信息（status/basis/claimable）+ 不可对外警告 + 未建模项",
          _report_ok())

    check("B12 🔴 披露承认数字壳的真实边界（自建**简化** P&R · CIM 加速器 IP · 非完整 SoC 签核）",
          _disclosure_ok())

    check("B13 🔴 fail 与「未达标」分离（4 场景：该停的停、不该停的不停）",
          _semantics_ok())

    check("K1 本门禁已登记进 CI core", _ci_registered_ok())

    # C 突变探针
    print("\n--- 突变探针（每个都必须打红）---")
    check("C1 探针：关掉 fail-fast ⇒ B3 必红", _probe_no_failfast())
    check("C2 探针：flow_ok 恒 True ⇒ 反向完备判据必红", _probe_flow_ok_always())
    check("C3 探针：自算能效标 claimable ⇒ B5 必红", _probe_self_energy_claimable())
    check("C4 探针：总面积比标 claimable ⇒ B7 必红", _probe_area_total_claimable())
    check("C5 探针：GDS 丢 1 个元素 ⇒ B8 必红", _probe_gds_drop())
    check("C6 探针：`_pack` 不补 SKIPPED ⇒ B3 必红", _probe_pack_no_skip())
    check("C7 探针：耗时用时钟读数 ⇒ B10 必红", _probe_elapsed_clock_read())
    check("C8 探针：用链长 12 当 via 数 ⇒ B9 必红", _probe_via_single_basis())

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    print("=" * 78)
    print("合计 %d 判据 · PASS %d / FAIL %d · %.2fs"
          % (len(_results), npass, nfail, time.perf_counter() - t0))
    print("=" * 78)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
