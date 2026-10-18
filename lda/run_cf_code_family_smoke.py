# -*- coding: utf-8 -*-
"""CF 征程 · **CF-M0** 码族参数律 **常驻门禁**（闭环缺口 G-CF-1 · 🔴 **净增 0 锚**）。

本门禁守两件事，**后者比前者更重要**：

  ① **能力层正确**：闭式参数律与**独立图枚举**逐位相符（环面码族用 GF(2) 边界算子秩，
     这是真独立路径 —— 秩计算 vs 公式）；
  ② 🔴 **「本族不可锚」这个负结果不许被翻案**：任何人若把码族参数登记成锚（虚报），
     本门禁必红。负结果机器化 = 防未来虚报，比多一道锚更有价值。

判据分节：
  A 能力层正确性 6：三角色码 n(d) 命中**独立小表** · 编码率 · 环面码枚举 n/k ·
    GF(2) 秩 ≡ L²−1 · 旋转/平面表面码参数
  B **不可锚锁** 5：残差**恒 0.0**（判据 D 必红）· `ANCHORABLE is False` ∧ 理由 ≥3 ·
    本族**未**登记进 `benchmark_defs`（防偷登记）· 两点 Richardson 残差 **== 0.0** ·
    **C3 杀手**（n(d) 在非跳点处 ∂n/∂d ≡ 0）
  C 反向探针 4（**先证能变红**）：改闭式常数 · 删一条边 · 翻 `ANCHORABLE` · 模拟偷登记
  D 红线 2：零第三方 QEC SDK（AST import 白名单）· 本门禁 ∈ `CORE_SMOKES`

🔴 `main()` 返回真值而非恒 0。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3）。
🔴 本门禁**只读**产品代码；不改任何产品面、不写任何文件。
"""

from __future__ import annotations

import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_qeda import code_family as CF  # noqa: E402

_CF_SRC = os.path.join(_HERE, "lda_qeda", "code_family.py")
_DEFS_DIR = os.path.join(_HERE, "lda_harness", "benchmark_defs")
_REG = os.path.join(_HERE, "lda_harness", "benchmarks.py")
_CI = os.path.join(_HERE, "run_ci_regression.py")

# 独立硬编码小表（**不来自闭式**，防"公式抄成同一份"）
_REF_COLOR = {3: 7, 5: 19, 7: 37, 9: 61, 11: 91}
_ENUM_LS = (2, 3, 4, 5, 6)

# 防偷登记的哨兵名（若这些串出现在锚定义文件里 ⇒ 有人把能力层当锚）
_SENTINELS = ("code_family", "cf_color_code", "cf_toric_n", "cf_code_family")


def _eval_group_a():
    """重算 A 组（供 C 组反向探针复用）。返回 {判据名: bool}。"""
    r = {}
    r["A1 三角色码 n(d) ≡ 独立小表（d=3/5/7/9/11 → 7/19/37/61/91）"] = all(
        CF.color_code_n(d) == n for d, n in _REF_COLOR.items())
    r["A2 三角色码编码率 = 4/(3d²+1)（d=7）"] = abs(
        CF.color_code_rate(7) - 4.0 / 148.0) < 1e-18
    r["A3 环面码图枚举 n ≡ 2L²（L=2..6 逐位）"] = all(
        CF.toric_params_enumerated(L)["n"] == 2 * L * L for L in _ENUM_LS)
    r["A4 环面码图枚举 k ≡ 2（GF(2) 同调维数）"] = all(
        CF.toric_params_enumerated(L)["k"] == 2 for L in _ENUM_LS)
    r["A5 GF(2) 边界算子秩 ≡ L²−1（∂₁ 与 ∂₂ 同）"] = all(
        CF.toric_params_enumerated(L)["rank_d1"] == L * L - 1
        and CF.toric_params_enumerated(L)["rank_d2"] == L * L - 1 for L in _ENUM_LS)
    r["A6 旋转表面码 n=d²/k=1 ∧ 平面表面码 n=2d²−1/k=1"] = (
        CF.rotated_surface_params(5)["n"] == 25
        and CF.rotated_surface_params(5)["k"] == 1
        and CF.planar_surface_params(5)["n"] == 49
        and CF.planar_surface_params(5)["k"] == 1)
    return r


def _eval_group_b():
    """重算 B 组（不可锚锁）。"""
    r = {}

    # B1：残差恒 0.0 —— 这是判据 D 必红的**结构性**证据
    resid = {L: (abs(CF.toric_params_enumerated(L)["n"] - CF.toric_params(L)["n"]),
                 abs(CF.toric_params_enumerated(L)["k"] - CF.toric_params(L)["k"]))
             for L in _ENUM_LS}
    r["B1 枚举-闭式残差 **恒 0.0**（n 与 k 双零 ⇒ 代数恒等 ⇒ 判据 D 必红）"] = all(
        n == 0 and k == 0 for (n, k) in resid.values())

    # B2：声明本身
    r["B2 ANCHORABLE is False ∧ 不可锚理由 ≥3 条"] = (
        CF.ANCHORABLE is False and len(CF.NOT_ANCHORABLE_REASONS) >= 3)

    # B3：**未**被登记成锚（扫锚定义文件源码，避免 import 拉 scipy）
    hits = []
    files = [_REG] + [os.path.join(_DEFS_DIR, f) for f in sorted(os.listdir(_DEFS_DIR))
                      if f.endswith(".py")]
    for p in files:
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        for s in _SENTINELS:
            if s in txt:
                hits.append("%s:%s" % (os.path.basename(p), s))
    r["B3 本族**未**登记进 benchmark_defs/benchmarks（防把能力层当锚虚报）"] = not hits

    # B4：渐近律 Richardson 两点外推**代数精确**（第三条证据）
    # 🔴 两点须都能被色码契约接受（d 为奇 ≥3）；对 x=1/d² 线性的函数，任取两点外推都精确。
    d1, d2 = 5, 15
    r1, r2 = CF.resource_ratio_color_toric(d1), CF.resource_ratio_color_toric(d2)
    x1, x2 = 1.0 / d1 ** 2, 1.0 / d2 ** 2
    extrap = (r2 * x1 - r1 * x2) / (x1 - x2)
    r["B4 渐近律两点 Richardson 残差 **== 0.0**（比值对 1/d² 线性 ⇒ 外推代数精确）"] = (
        abs(extrap - CF.RATIO_ASYMPTOTIC) == 0.0)

    # B5：C3 杀手 —— 定义域离散 + 跳变恒为整数级（不存在"小响应"区）
    discrete = True
    for d in (3, 5, 7, 9):
        for eps in (1e-3, 1e-2, 0.1, 0.5):
            try:
                CF.color_code_n(d + eps)          # 非奇整数 ⇒ 契约必拒
            except ValueError:
                continue
            except Exception:                     # noqa: BLE001
                discrete = False
                break
            discrete = False                      # 没抛 = 接受了非奇整数
            break
    # 跳变幅度 Δn(d) = n(d+2) − n(d) = 3(d+1) ≥ 12 —— 整数级，无小响应区
    jumps = {d: CF.color_code_n(d + 2) - CF.color_code_n(d) for d in (3, 5, 7, 9, 11)}
    jump_ok = all(v == 3 * (d + 1) and v >= 12 for d, v in jumps.items())
    r["B5 **C3 杀手**：定义域仅奇整数（连续扰动必拒）∧ 跳变 Δn=3(d+1)≥12（无小响应区）"] = (
        discrete and jump_ok)
    return r


def main() -> int:
    print("=" * 78)
    print("CF-M0 码族参数律门禁（能力层 · 🔴 净增 0 锚 · 不可锚锁）")
    print("=" * 78)

    # ── A 能力层正确性 ────────────────────────────────────────────────
    for name, ok in _eval_group_a().items():
        check(name, ok, "")

    # ── B 不可锚锁（本门禁的核心） ────────────────────────────────────
    for name, ok in _eval_group_b().items():
        check(name, ok, "")

    # ── C 反向探针（**先证能变红**）────────────────────────────────────
    # C1：改闭式常数 3 → 4，A1 必红
    _orig_n = CF.color_code_n

    def _bad_n(d):
        if d < 3 or d % 2 == 0:
            raise ValueError("bad")
        return (4 * d * d + 1) // 4

    CF.color_code_n = _bad_n
    try:
        red1 = not _eval_group_a()["A1 三角色码 n(d) ≡ 独立小表（d=3/5/7/9/11 → 7/19/37/61/91）"]
    finally:
        CF.color_code_n = _orig_n
    check("C1 反向：改闭式常数 3→4 ⇒ A1 必红（证明 A1 有判别力）", red1,
          "red=%s" % red1)

    # C2：删一条边 ⇒ A3 必红
    _orig_build = CF._build_toric_complex

    def _bad_build(L):
        vid, edges, faces = _orig_build(L)
        return vid, edges[:-1], faces

    CF._build_toric_complex = _bad_build
    try:
        red2 = not _eval_group_a()["A3 环面码图枚举 n ≡ 2L²（L=2..6 逐位）"]
    finally:
        CF._build_toric_complex = _orig_build
    check("C2 反向：删一条边 ⇒ A3 必红（证明枚举是真数出来的）", red2,
          "red=%s" % red2)

    # C3：翻 ANCHORABLE=True ⇒ B2 必红
    _orig_anchorable = CF.ANCHORABLE
    CF.ANCHORABLE = True
    try:
        red3 = not _eval_group_b()["B2 ANCHORABLE is False ∧ 不可锚理由 ≥3 条"]
    finally:
        CF.ANCHORABLE = _orig_anchorable
    check("C3 反向：翻 ANCHORABLE=True ⇒ B2 必红（防悄悄翻案）", red3,
          "red=%s" % red3)

    # C4：模拟偷登记（把哨兵写进一份临时锚定义副本）⇒ B3 必红
    _orig_sentinels = _SENTINELS
    ok_before = _eval_group_b()["B3 本族**未**登记进 benchmark_defs/benchmarks（防把能力层当锚虚报）"]
    globals()["_SENTINELS"] = ("BENCHMARK_DEFS",)   # 该串**必然**存在于 benchmarks.py
    try:
        red4 = not _eval_group_b()["B3 本族**未**登记进 benchmark_defs/benchmarks（防把能力层当锚虚报）"]
    finally:
        globals()["_SENTINELS"] = _orig_sentinels
    check("C4 反向：注入必然存在的哨兵 ⇒ B3 必红（证明 B3 真在扫锚定义）",
          (ok_before is True) and red4, "before=%s red=%s" % (ok_before, red4))

    # ── D 红线 ────────────────────────────────────────────────────────
    # D1：零第三方 QEC SDK（AST 取顶层 import）
    with open(_CF_SRC, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mods.add(node.module.split(".")[0])
    _allow = {"__future__", "typing"}
    _forbidden = {"numpy", "scipy", "ldpc", "stim", "pymatching", "qecsim", "bposd"}
    check("D1 零第三方 QEC SDK（顶层 import ⊆ {__future__, typing} 且无 numpy/scipy）",
          (mods <= _allow) and not (mods & _forbidden),
          "mods=%s" % sorted(mods))

    # D2：本门禁 ∈ CORE_SMOKES
    with open(_CI, encoding="utf-8") as f:
        ci_txt = f.read()
    in_core = "run_cf_code_family_smoke.py" in ci_txt
    check("D2 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("CF-M0 门禁：%s（FAIL=%d）· 账本 **+0 锚**（精确量不可锚 · B1/B4 机器锁）"
          % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
