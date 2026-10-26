"""E31 门禁（D-206）：换层签核 —— 漏极 via stack + DRC/LVS 两个静默漏检的修复。

## 这个门禁守什么

E30 说「AP 路径 DRC 全过」，但 LVS 挂、而且那个「DRC 全过」是**假绿**。本门禁守的是：

| 编号 | 守什么 | 打红条件 |
|---|---|---|
| B1 | 6 个新 via 全严格夹层 · **且数量 == 6** | z 错位 / via_map 少一项 |
| B2 | `pos_of(VIA_AP) < pos_of(AP)` | 回到 E30 的错位 |
| B3 | 落垫 `≥ via_size+2·enclosure`（VIA_AP 需 0.80） | 一律 0.40 |
| B4 | 签核 6 通过 / 仅 M2 失败 | 任一层意外变红或意外变绿 |
| B5 | M2 失败 = **同层短路**（不得说成工具问题） | 文案改成「工具缺陷」 |
| B6 | 关掉 via stack ⇒ M3/AP 的 LVS 全 REJECT | 栈不是必要件 |
| B7 | 默认路径与 v0.9.326 **逐位一致** | 改到 936/1272/1608 之外的任何值 |
| B8 | AP 最优（N=87 · vs Mythic 3.0×） | 数值漂移 |
| B9 | `r×40 ≡ t×10 × W×4`（精确恒等） | 分解对不上 |
| B10 | M3-M6 面积不变 · AP ×1.333 | pitch_y 被改 |
| B11 | 多层 GDS 端到端 roundtrip match | `to_gds` 不透传 stack |
| B12 | N=87 需 90,828 个 via（良率未建模） | 数量对不上 |

## 6 个突变探针（全部必须能打红）**

- C1 · 把 VIA_AP 的 z 改回 E30（在 AP 之上）⇒ B1/B2 必红
- C2 · 落垫一律 0.40 ⇒ AP 的 DRC 必红
- C3 · `via_map` 删掉 VIA_AP ⇒ B1 必红（**反向完备**：不能因为"剩下的都合格"就绿）
- C4 · 端帽归零 ⇒ AP 的 DRC 必红
- C5 · `to_gds` 不透传 `via_stack` ⇒ GDS 元素数对不上 ⇒ B11 必红
- C6 · 把 M2 的失败说成"工具问题" ⇒ B5 必红
"""

from __future__ import annotations

import copy
import os
import sys
import warnings
from unittest import mock

warnings.simplefilter("error", SyntaxWarning)

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import signed_off_stack as S      # noqa: E402
from lda_l2.ecore import layout as LY               # noqa: E402
from lda_l2.ecore import elayers as EL              # noqa: E402

_results = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, bool(ok), detail))
    return bool(ok)


# ---------------------------------------------------------------------------
# 关键事实
# ---------------------------------------------------------------------------
def _z_ok() -> bool:
    """B1 · 6 个新 via 全部严格夹层，**且数量必须是 6**（反向完备）。"""
    za = S.z_order_audit()
    return za["all_new_strict"] and za["n_new_vias"] == 6 and za["n_strict"] == 6


def _pos_ok() -> bool:
    """B2 · VIA_AP 必须排在 AP 之下（E30 是反的）。"""
    za = S.z_order_audit()
    o = za["order"]
    return o.index("VIA_AP") < o.index("AP") and o.index("M6") < o.index("VIA_AP")


def _pad_ok() -> bool:
    """B3 · 只有 VIA_AP 的落垫超过 0.40（需 0.80）。"""
    ps = S.pad_sizing_rule()
    over = ps["over_default"]
    return (len(over) == 1 and over[0]["via"] == "VIA_AP"
            and abs(over[0]["min_pad_um"] - 0.80) < 1e-12)


def _signoff_ok() -> bool:
    """B4 · 6 层通过，仅 M2 失败。"""
    sm = S.signoff_summary()
    return (sm["n_passed"] == 6 and sm["failed"] == ["M2"]
            and set(sm["passed"]) == {"M1", "M3", "M4", "M5", "M6", "AP"})


def _m2_reason_ok() -> bool:
    """B5 · M2 的失败根因必须是**同层短路**，不得说成工具问题。"""
    m2 = S.m2_infeasibility()
    txt = m2["reason"] + m2["verdict"]
    return (m2["n_short_issues"] > 0
            and ("同层" in txt or "拓扑" in txt)
            and "工具" not in m2["reason"])


def _stack_necessary_ok() -> bool:
    """B6 · 关掉 via stack ⇒ M3/AP 的 LVS 必须 REJECT（栈是充分必要件）。"""
    st = EL.get_estack("ecmos10")
    verdicts = []
    for rl in ("M3", "AP"):
        arr = LY.crossbar_array(S.MATRIX_N, S.MATRIX_N, S._params_for(rl),
                                row_layer=rl, via_stack=False)
        lv = LY.elvs_signoff(arr["descs"],
                             LY.expected_netlist(S.MATRIX_N, S.MATRIX_N, arr["params"]),
                             stack=st)
        verdicts.append(lv["verdict"])
    return all(v != "ACCEPT" for v in verdicts)


def _baseline_ok() -> bool:
    """B7 · 默认路径（M1 · 无栈）gds_bytes/flat 逐位一致 + roundtrip。"""
    bu = S.baseline_unchanged()
    return bu["all_ok"] and len(bu["rows"]) == 3


def _best_ok() -> bool:
    """B8 · AP 最优：N=87 · ADC 24.7 fJ/op · vs Mythic 3.0×（容差 2%）。"""
    bl = S.best_layer()
    r = bl["row"]
    return (bl["layer"] == "AP" and r["n_max"] == 87
            and abs(r["adc_fj"] - 24.7) / 24.7 < 0.02
            and abs(r["vs_mythic"] - 3.0) / 3.0 < 0.02)


def _decompose_ok() -> bool:
    """B9 · AP 的 r×40 ≡ t×10 × W×4（精确恒等，不是近似）。"""
    bl = S.best_layer()
    r = bl["row"]
    t_ratio = r["t_um"] / 0.20
    w_ratio = r["w_um"] / S.BASE_WIDTH_UM
    return (abs(r["r_ratio"] - 40.0) < 1e-9
            and abs(t_ratio * w_ratio - r["r_ratio"]) / r["r_ratio"] < 1e-12)


def _area_ok() -> bool:
    """B10 · M3-M6 的 pitch_y 保持 2.40（换层不加面积）· AP → 3.20（×1.333）。"""
    base_py = LY.DEFAULT_CELL_PARAMS["pitch_y_um"]
    for rl in ("M3", "M4", "M5", "M6"):
        if abs(S._params_for(rl).get("pitch_y_um", base_py) - base_py) > 1e-12:
            return False
    return abs(S._params_for("AP")["pitch_y_um"] / base_py - 4.0 / 3.0) < 1e-9


def _gds_ok() -> bool:
    """B11 · 多层几何 GDS 端到端：flat 元素数 ≡ 展开后元素数（roundtrip）。"""
    ok = True
    for n in (4, 8):
        pr = S._params_for("AP")
        arr = LY.crossbar_array(n, n, pr, row_layer="AP", via_stack=True)
        rt = LY.gds_roundtrip_check(n, n, pr, row_layer="AP", via_stack=True)
        ok &= (rt["match"] and rt["flat_elements"] == len(arr["descs"])
               and rt["expanded_top_elements"] == len(arr["descs"]))
    return ok


def _via_count_ok() -> bool:
    """B12 · N=87 ⇒ 87²×12 = 90,828 个 via（良率未建模必须显式报）。"""
    vc = S.via_count_cost()
    return (vc["rows"][-1]["n_vias"] == 90828 and vc["stack_len"] == 12
            and "良率" in vc["yield_note"] and "未建模" in vc["yield_note"])


# ---------------------------------------------------------------------------
# 突变探针（每个都必须在"被破坏"时报 True）
# ---------------------------------------------------------------------------
def _probe_broken_z() -> bool:
    """C1 · 把 VIA_AP 的 z 改回 E30（落在 AP 之上）⇒ B1/B2 必须变红。"""
    real_stack10 = S._stack10

    def bad_stack():
        # 🔴 **必须深拷贝**：`_stack10()` 返回的是 `ESTACK_REGISTRY` 里的**全局单例**，
        #   直接改它会把错位的 z **永久写进后面的所有判据**（C4 因此假绿 —— 本段实战踩到）。
        st = copy.deepcopy(real_stack10())
        st.layers["VIA_AP"] = EL.ELayer("VIA_AP", "via", EL.L_VIA_AP,
                                        z_bot_um=6.75, z_top_um=6.95)
        st.layers["AP"] = EL.ELayer("AP", "signal", EL.L_AP,
                                    z_bot_um=4.95, z_top_um=6.75)
        return st

    S._CACHE.clear()
    with mock.patch.object(S, "_stack10", bad_stack):
        red = (not _z_ok()) and (not _pos_ok())
    S._CACHE.clear()
    return red


def _probe_broken_pad() -> bool:
    """C2 · 落垫一律 0.40（E30 口径）⇒ AP 的 DRC 必须变红。"""
    real = LY.via_stack_descs

    def flat_pad(n, m, params=None, row_layer="M1", stack=None):
        descs = real(n, m, params, row_layer=row_layer, stack=stack)
        out = []
        for d in descs:
            if d["kind"] == "boundary" and d["layer"] == EL.L_M6:
                b = LY._bbox(d)
                cx, cy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
                out.append(LY._b_square(EL.L_M6, cx, cy, 0.40, d["net"]))
            else:
                out.append(d)
        return out

    st = EL.get_estack("ecmos10")
    pr = S._params_for("AP")
    S._CACHE.clear()
    with mock.patch.object(LY, "via_stack_descs", flat_pad):
        arr = LY.crossbar_array(S.MATRIX_N, S.MATRIX_N, pr,
                                row_layer="AP", via_stack=True)
        drc = LY.run_edrc(arr["descs"], stack=st)
    S._CACHE.clear()
    return (drc["verdict"] != "ACCEPT"
            and any("ENCLOSURE" in v["rule"] for v in drc["violations"]))


def _probe_drop_via_ap() -> bool:
    """C3 · `via_map` 删掉 VIA_AP ⇒ B1 必须变红（**不能因为剩下都合格就绿**）。"""
    real_stack10 = S._stack10

    def no_via_ap():
        st = copy.deepcopy(real_stack10())    # 🔴 同上：不得改全局单例
        st.via_map.pop("VIA_AP", None)
        return st

    S._CACHE.clear()
    with mock.patch.object(S, "_stack10", no_via_ap):
        red = not _z_ok()
    S._CACHE.clear()
    return red


def _probe_no_endcap() -> bool:
    """C4 · 端帽归零 ⇒ AP 的 DRC 必须变红（最外侧 VIA_AP 只被包围 0.025）。"""
    real_lines = LY.array_lines

    def no_cap(n, m, params=None, row_layer="M1", end_margin_um=0.0):
        return real_lines(n, m, params, row_layer=row_layer, end_margin_um=0.0)

    st = EL.get_estack("ecmos10")
    pr = S._params_for("AP")
    with mock.patch.object(LY, "array_lines", no_cap):
        arr = LY.crossbar_array(S.MATRIX_N, S.MATRIX_N, pr,
                                row_layer="AP", via_stack=True)
        drc = LY.run_edrc(arr["descs"], stack=st)
    return drc["verdict"] != "ACCEPT"


def _probe_gds_drop_stack() -> bool:
    """C5 · `to_gds` 不透传 via_stack ⇒ GDS 元素数少于 descs ⇒ B11 必红。"""
    real_gds = LY.to_gds

    def no_stack_gds(n, m, params=None, path=None, hierarchical=True,
                     row_layer="M1", via_stack=False):
        return real_gds(n, m, params, path, hierarchical,
                        row_layer=row_layer, via_stack=False)

    pr = S._params_for("AP")
    with mock.patch.object(LY, "to_gds", no_stack_gds):
        arr = LY.crossbar_array(4, 4, pr, row_layer="AP", via_stack=True)
        g = LY.to_gds(4, 4, pr, row_layer="AP", via_stack=True)
    return g["flat_elements"] != len(arr["descs"])


def _probe_m2_blame_tool() -> bool:
    """C6 · 把 M2 的失败说成"工具问题" ⇒ B5 必须变红。"""
    real = S.m2_infeasibility

    def blame_tool():
        r = dict(real())
        r["reason"] = "工具的层栈定义有缺陷，换个工具就能做"
        return r

    with mock.patch.object(S, "m2_infeasibility", blame_tool):
        red = not _m2_reason_ok()
    return red


# ---------------------------------------------------------------------------
# CI 登记
# ---------------------------------------------------------------------------
def _ci_registered() -> bool:
    p = os.path.join(_HERE, "run_ci_regression.py")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return "run_ecore_e31_smoke.py" in f.read()
    except OSError:
        return False


def main() -> int:
    print("=" * 78)
    print("E31 门禁 · 换层签核（漏极 via stack + DRC/LVS 静默漏检修复）· D-206")
    print("=" * 78)

    # A1 自检
    check("A1 `signed_off_stack` 自检 13 项全过",
          S.signed_off_stack_self_check(verbose=True))

    # B 关键事实
    za = S.z_order_audit()
    check("B1 🔴 6 个新 via 全严格夹层 · 数量 == 6（反向完备）", _z_ok(),
          "n_strict=%d/%d" % (za["n_strict"], za["n_new_vias"]))
    check("B2 🔴 `pos_of(M6) < pos_of(VIA_AP) < pos_of(AP)`（E30 是反的）", _pos_ok(),
          " → ".join([n for n in za["order"] if n in ("M6", "VIA_AP", "AP")]))
    ps = S.pad_sizing_rule()
    check("B3 🔴 落垫按上方 via 反算：仅 VIA_AP 超 0.40（需 %.2f）"
          % (ps["over_default"][0]["min_pad_um"] if ps["over_default"] else 0.0),
          _pad_ok())
    sm = S.signoff_summary()
    check("B4 🔴 签核 6 通过（%s）· 仅 M2 失败" % "、".join(sm["passed"]),
          _signoff_ok())
    m2 = S.m2_infeasibility()
    check("B5 🔴 M2 失败 = **同层短路**（%d 条），非工具缺陷" % m2["n_short_issues"],
          _m2_reason_ok())
    check("B6 🔴 关掉 via stack ⇒ M3/AP 的 LVS 全 REJECT（**栈是充分必要件**）",
          _stack_necessary_ok())
    bu = S.baseline_unchanged()
    check("B7 默认路径与 v0.9.326 逐位一致（%s）"
          % " · ".join("%dB" % r["gds_bytes"] for r in bu["rows"]), _baseline_ok())
    bl = S.best_layer()
    check("B8 🔴 AP 最优：N=%d · ADC %.1f fJ/op · vs Mythic %.1f×"
          % (bl["row"]["n_max"], bl["row"]["adc_fj"], bl["row"]["vs_mythic"]),
          _best_ok())
    check("B9 🔴 AP 的 r×%.0f ≡ t×%.0f × W×%.0f（**精确恒等**）"
          % (bl["row"]["r_ratio"], bl["row"]["t_um"] / 0.20,
             bl["row"]["w_um"] / S.BASE_WIDTH_UM),
          _decompose_ok())
    check("B10 🔴 面积：M3-M6 的 `pitch_y` 不变（换层不加面积）· AP ×1.333", _area_ok())
    check("B11 多层几何 GDS 端到端 roundtrip match（N=4/8）", _gds_ok())
    vc = S.via_count_cost()
    check("B12 🔴 N=87 需 %s 个 via · 良率未建模（显式报）"
          % format(vc["rows"][-1]["n_vias"], ","), _via_count_ok())

    # C 突变探针
    check("C1 探针：把 VIA_AP 的 z 改回 E30（在 AP 之上）⇒ B1/B2 必红",
          _probe_broken_z())
    check("C2 探针：落垫一律 0.40 ⇒ AP 的 DRC 必红（ENCLOSURE）", _probe_broken_pad())
    check("C3 探针：`via_map` 删掉 VIA_AP ⇒ B1 必红（**反向完备**）",
          _probe_drop_via_ap())
    check("C4 探针：端帽归零 ⇒ AP 的 DRC 必红（最外侧 via 只被包围 0.025）",
          _probe_no_endcap())
    check("C5 探针：`to_gds` 不透传 via_stack ⇒ B11 必红", _probe_gds_drop_stack())
    check("C6 探针：把 M2 说成「工具问题」⇒ B5 必红", _probe_m2_blame_tool())

    # K CI 登记
    check("K1 门禁已登记进 CI core（`run_ci_regression.py`）", _ci_registered())

    print()
    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    # 🔴 输出格式必须是**行首 `[PASS]`**：`run_webui_pm_render_path_smoke` 的 W10 用
    #   `_pass_count()` 按行首锚定数判据数（== 人工 `grep -c` 口径）。写成 `PASS | xxx`
    #   会被数成 0 ⇒ README 顶行声明的判据数与实跑数「漂移」⇒ W10 当场红。
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name
              + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 78)
    print("判据合计 %d · PASS %d · FAIL %d" % (len(_results), npass, nfail))
    print("结论：" + ("ALL GREEN ✅" if nfail == 0 else "存在 FAIL ❌"))
    print("=" * 78)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
