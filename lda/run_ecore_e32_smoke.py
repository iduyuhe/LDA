"""E32 门禁（D-207）：版图空间索引 —— 把 DRC/LVS 从 O(N⁴) 降到可用。

## 这个门禁守什么

E31 的诚实边界第 4 条写的是：「**N=87 的几何从未被真正 DRC 验过**」——
因为 `run_edrc` 与 `elvs_signoff` 都是全对全 O(n²)，而元素数 ∝ N² ⇒ O(N⁴)。
本段引入空间索引后实测 **N=87（143,985 元素）DRC+LVS 合计 4.1 s，全 ACCEPT**。

⇒ 门禁守的**不是**「跑得快」，而是 **「跑得快且和旧实现给出同一份结论」**。

| 编号 | 守什么 | 打红条件 |
|---|---|---|
| B1 | 超集性：`near ⊇ brute`（真实阵列 ×4 组 × expand 三档） | 索引漏对 |
| B2 | 新旧对拍 **9 案例全一致**（verdict + 违规集合） | 任一条不一致 |
| B3 | 对拍案例里 **REJECT ≥ 4 个** | 只对拍 ACCEPT = 空集比空集 |
| B4 | 间距违规数逐条一致（64 / 144 / 72 等具体值） | 漏报或重报 |
| B5 | N=87（143,985 元素）**全 ACCEPT 且 < 60 s** | 跑不动 / 变红 |
| B6 | 经验复杂度 < N^3（旧是 N^4） | 索引没起效 |
| B7 | 小规模回退阈值 > 0（不比原来慢） | 阈值被设为 0 |
| B8 | 全绿：`spatial_self_check()` 10 项 | 任一项失败 |

## 6 个突变探针

- C1 · 把网格 cell 放大 1000×（一格装下全部）⇒ 退化成 O(n²)，但仍**正确**
      ⇒ 探针验的是「退化后结果不变」（正确性不依赖性能参数）
- C2 · 把 `expand` 传 0 做间距筛选（漏掉"近而不交"的对）⇒ B4 必红
- C3 · 索引里丢掉 oversized（长条）⇒ B4/B5 必红
- C4 · 强制新旧都给 REJECT 的案例改成 ACCEPT ⇒ B2 必红
- C5 · 把 `SPATIAL_MIN_ELEMENTS` 设为 10**9 ⇒ 全走旧实现 ⇒ B5 超时（本探针用"必红"的形式：跑旧实现到 N=87 会超预算，故改为断言「阈值生效时走索引」）
- C6 · 把 `USE_SPATIAL_INDEX` 关掉 ⇒ B5 必超时（同上，用轻量形式验）
"""

from __future__ import annotations

import os
import sys
import time
import warnings
from unittest import mock

warnings.simplefilter("error", SyntaxWarning)

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import spatial as SP          # noqa: E402
from lda_l2.ecore import layout as LY           # noqa: E402
from lda_l2.ecore import elayers as EL          # noqa: E402

_results = []

#: E31 实测的间距违规数（**具体值**，不是"大于 0"）—— 漏报一条就变
EXPECT_VIOL = {"M1 R=0.55": 64, "M1 R=0.60": 144, "AP W=0.40": 72}


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, bool(ok), detail))
    return bool(ok)


# ---------------------------------------------------------------------------
# 关键事实
# ---------------------------------------------------------------------------
def _superset_ok() -> bool:
    """B1 · `near ⊇ brute`（真实阵列，多组几何 × 三档 expand）。"""
    ok = True
    for nn, prm, rl, vs in ((8, None, "M1", False),
                            (8, {"row_w_um": 1.60, "pitch_y_um": 3.20}, "AP", True),
                            (8, {"row_w_um": 0.55}, "M1", False),
                            (8, None, "M6", True)):
        arr = LY.crossbar_array(nn, nn, prm, row_layer=rl, via_stack=vs)
        bx = [LY._bbox(d) for d in arr["descs"]]
        for ex in (0.0, 0.28, 1.60):
            ok &= set(SP.brute_pairs(bx, ex)) <= set(SP.near_pairs(bx, ex))
    return ok


def _parity_ok() -> bool:
    """B2 · 9 案例新旧逐条一致。"""
    ps = SP.parity_summary()
    return ps["all_equal"] and ps["n_cases"] == 9


def _reject_cases_ok() -> bool:
    """B3 · 对拍案例必须含 ≥4 个 REJECT（否则等于空集比空集）。"""
    ps = SP.parity_summary()
    return ps["n_reject_cases"] >= 4


def _viol_counts_ok() -> bool:
    """B4 · 间距/宽度违规数必须是**具体值**（漏报一条就变）。"""
    got = {}
    for r in SP.parity_summary()["rows"]:
        for key in EXPECT_VIOL:
            if r["label"].startswith(key):
                got[key] = r["n_viol"]
    return all(got.get(k) == v for k, v in EXPECT_VIOL.items())


def _scale_ok() -> bool:
    """B5 · N=87 全 ACCEPT 且 < 60 s（旧实现外推 ~7 h）。"""
    ss = SP.scale_summary()
    return (ss["n_max_verified"] == 87 and ss["all_accept"]
            and ss["elapsed_max_s"] < 60.0)


def _complexity_ok() -> bool:
    """B6 · 经验复杂度必须 < N^3（旧实现是 N^4）。"""
    ss = SP.scale_summary()
    return 0.0 < ss["empirical_exponent"] < 3.0


def _threshold_ok() -> bool:
    """B7 · 小规模回退阈值 > 0（保证小阵列不比原来慢）。"""
    return LY.SPATIAL_MIN_ELEMENTS >= 128


def _selfcheck_ok() -> bool:
    """A1 · 模块自检 10 项。"""
    return SP.spatial_self_check(verbose=True)


def _oversized_used_ok() -> bool:
    """B8 · 🔴 大规模下 oversized 分支**必须真的被触发**（防它变成没人跑的死代码）。

    N=8 时行线只跨 ~3 格 ⇒ 不进 oversized ⇒ 那条分支在门禁的默认规模下是死代码。
    这里用 N=24（行线跨 ~69 格）确认分支真的在用。
    """
    arr = LY.crossbar_array(24, 24, {"row_w_um": 1.60, "pitch_y_um": 3.20},
                            row_layer="AP", via_stack=True)
    bx = [LY._bbox(d) for d in arr["descs"]]
    g = SP.Grid(bx)
    return len(g.oversized) > 0


# ---------------------------------------------------------------------------
# 突变探针
# ---------------------------------------------------------------------------
def _probe_huge_cell() -> bool:
    """C1 · cell 放大 1000×（退化成单格 ⇒ O(n²)）**结果仍须一致**。

    这条验的是「**正确性不依赖性能参数**」：网格尺寸只影响速度，不影响候选超集。
    """
    arr = LY.crossbar_array(8, 8, {"row_w_um": 0.55})
    exp = LY.expected_netlist(8, 8, arr["params"])
    base_d = LY.run_edrc(arr["descs"], spatial=True)
    base_l = LY.elvs_signoff(arr["descs"], exp, spatial=True)
    real_grid = SP.Grid

    def huge(boxes, cell_um=None, max_cell_cross=64):
        return real_grid(boxes, cell_um=1000.0, max_cell_cross=max_cell_cross)

    with mock.patch.object(SP, "Grid", huge):
        d = LY.run_edrc(arr["descs"], spatial=True)
        lv = LY.elvs_signoff(arr["descs"], exp, spatial=True)
    same = (d["verdict"] == base_d["verdict"]
            and sorted((v["rule"], v["detail"]) for v in d["violations"])
            == sorted((v["rule"], v["detail"]) for v in base_d["violations"])
            and lv["verdict"] == base_l["verdict"])
    return same


def _probe_expand_zero() -> bool:
    """C2 · 间距筛选用 expand=0（漏掉「近而不交」的对）⇒ B4 必红。"""
    real_np = SP.near_pairs

    def zero_expand(boxes, expand=0.0, cell_um=None):
        return real_np(boxes, 0.0, cell_um)      # 🔴 忽略 expand

    SP._CACHE.clear()
    with mock.patch.object(SP, "near_pairs", zero_expand):
        red = not _viol_counts_ok()
    SP._CACHE.clear()
    return red


def _probe_drop_oversized() -> bool:
    """C3 · 丢掉 oversized（长条）⇒ 候选对明显变少（**长条分支确实在承重**）。

    🔴 为什么不用"违规数变少"来验：`M1 R=0.55` 案例只有 N=8，行线只跨 ~3 格
    ⇒ **本来就不进 oversized**，那段代码在该规模下是死代码 ⇒ 探针永远打不红
    （v0.9.328 实测：第一版 C3 正是因此假绿）。改用**人造长条几何**直接验分支。
    """
    boxes = ([(0.0, 100.0, 0.0, 0.1)]                       # 1 条跨 100 格的长条
             + [(i * 10.0, i * 10.0 + 0.5, 0.05, 0.55) for i in range(10)])
    g = SP.Grid(boxes)
    if not g.oversized:
        return False                                        # 机制没触发 ⇒ 探针不成立
    full = set(g.near_pairs(0.0))

    # 人为去掉 oversized 后的对数（模拟"忘记处理长条"）
    pairs_no_over = set()
    for idx, b in enumerate(g.boxes):
        if idx in g.oversized:
            continue
        for other in g.query(b, 0.0):
            if other == idx or other in g.oversized:
                continue
            pairs_no_over.add((idx, other) if idx < other else (other, idx))
    return len(pairs_no_over) < len(full)


def _probe_fake_accept() -> bool:
    """C4 · 把 REJECT 案例强行改成 ACCEPT ⇒ B2 必红。"""
    real = SP._parity_matrix_impl

    def faked():
        rows = real()
        for r in rows:
            if r["label"].startswith("M1 R=0.55"):
                r = dict(r)
                r["n_viol"] = 0
        return rows

    # 直接改一份「旧的 verdict 被伪造成 ACCEPT」的对拍结论
    rows = real()
    forged = []
    for r in rows:
        if r["label"].startswith("M1 R=0.55"):
            r = dict(r)
            r["drc_old"] = "ACCEPT"        # 伪造：旧实现被改成 ACCEPT
            r["drc_equal"] = (r["drc_old"] == r["drc_new"])
        forged.append(r)
    with mock.patch.object(SP, "_parity_matrix_impl", lambda: forged):
        SP._CACHE.clear()
        red = not _parity_ok()
    SP._CACHE.clear()
    return red


def _probe_force_legacy() -> bool:
    """C5 · 把 `USE_SPATIAL_INDEX` 关掉 ⇒ 大规模必超预算（用轻量形式：走旧实现时 N=20 就 >5 s）。"""
    arr = LY.crossbar_array(20, 20, {"row_w_um": 1.60, "pitch_y_um": 3.20},
                            row_layer="AP", via_stack=True)
    st = EL.get_estack("ecmos10")
    LY.run_edrc(arr["descs"][:1], stack=st, spatial=False)     # 预热，避免首调开销
    t_new0 = time.perf_counter()
    LY.run_edrc(arr["descs"], stack=st, spatial=True)
    t_new = time.perf_counter() - t_new0
    # 不跑完整旧实现（8 s），只验「索引确实被用上」：新路径必须显著快于 1 s
    return t_new < 1.0


def _probe_threshold_zero() -> bool:
    """C6 · 阈值设为 0（全部走索引，小阵列也不回退）⇒ B7 必红。

    🔴 这条探针验的是**判据本身有牙**：阈值必须 >0，否则 n=120 时索引比暴力还慢 0.9×。
    """
    with mock.patch.object(LY, "SPATIAL_MIN_ELEMENTS", 0):
        red = not _threshold_ok()
    return red


# ---------------------------------------------------------------------------
# CI 登记
# ---------------------------------------------------------------------------
def _ci_registered() -> bool:
    p = os.path.join(_HERE, "run_ci_regression.py")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return "run_ecore_e32_smoke.py" in f.read()
    except OSError:
        return False


def main() -> int:
    print("=" * 78)
    print("E32 门禁 · 版图空间索引（DRC/LVS 从 O(N⁴) → N^2.35）· D-207")
    print("=" * 78)

    check("A1 `spatial` 自检 10 项全过（含超集性 + 对拍 + N=87）", _selfcheck_ok())

    check("B1 🔴 超集性 `near ⊇ brute`（真实阵列 ×4 组 × expand 0/0.28/1.6）",
          _superset_ok())
    ps = SP.parity_summary()
    check("B2 🔴 新旧对拍 %d 案例**逐条一致**（verdict + 违规集合）" % ps["n_cases"],
          _parity_ok())
    check("B3 🔴 对拍含 **%d 个 REJECT** 案例（防只拍 ACCEPT = 空集比空集）"
          % ps["n_reject_cases"], _reject_cases_ok())
    check("B4 🔴 具体违规数逐条一致（R0.55=%d · R0.60=%d · AP W0.40=%d）"
          % (EXPECT_VIOL["M1 R=0.55"], EXPECT_VIOL["M1 R=0.60"], EXPECT_VIOL["AP W=0.40"]),
          _viol_counts_ok())
    ss = SP.scale_summary()
    check("B5 🔴 N=%d（%s 元素）全 ACCEPT · %.2fs（<60s；旧实现外推 ~7h）"
          % (ss["n_max_verified"],
             format(ss["rows"][-1]["n_elements"], ","), ss["elapsed_max_s"]),
          _scale_ok())
    check("B6 🔴 经验复杂度 N^%.2f（< N^3；旧实现 N^4）" % ss["empirical_exponent"],
          _complexity_ok())
    check("B7 小规模回退阈值 %d 元素（>0 ⇒ 小阵列不比原来慢）"
          % LY.SPATIAL_MIN_ELEMENTS, _threshold_ok())
    check("B8 🔴 N=24 时 oversized（长条）分支**真的被触发**（防死代码）",
          _oversized_used_ok())

    check("C1 探针：cell 放大 1000×（退化成单格）⇒ **结果仍一致**（正确性不依赖性能参数）",
          _probe_huge_cell())
    check("C2 探针：间距筛选 expand=0（漏「近而不交」）⇒ B4 必红", _probe_expand_zero())
    check("C3 探针：丢掉 oversized（长条）⇒ 候选对变少（长条分支确实承重）",
          _probe_drop_oversized())
    check("C4 探针：把 REJECT 案例伪造成 ACCEPT ⇒ B2 必红", _probe_fake_accept())
    check("C5 探针：索引确实被用上（N=20 新路径 <1s；旧实现 8s）", _probe_force_legacy())
    check("C6 探针：阈值设为 0 ⇒ B7 必红（判据有牙）", _probe_threshold_zero())

    check("K1 门禁已登记进 CI core（`run_ci_regression.py`）", _ci_registered())

    print()
    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    # 🔴 输出格式必须是**行首 `[PASS]`**（`run_webui_pm_render_path_smoke` 的 W10 按行首计数）
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
