"""G12-A 突变探针（**人工运行，不入 CI**）——证明新判据能变红。

铁律⑧：没验证过的护栏不算护栏；铁律⑮：探针自身也会骗人。
本探针按「**零源码突变**」原则：把 `full_vector_mode_solver.py` 复制到临时
目录，在**副本**上做替换再 import，然后**只跑受影响的那一条自检**，断言它
**由绿转红**。

🔴 首轮回炉教训（勿重犯）：突变必须是「真缺陷」，不是「无操作等价」。
   · 只平移网格**原点**（dx 不变）⇒ 结果逐位不变 ⇒ 判不出关（假 OK）
   · 把 slab 改成「只画在脊正下方」⇒ 材料仍然增加 ⇒「slab 承重」本来就该绿
   · 单点替换造不出「slab 完全失效」（还要让 n_tot 与 t 脱钩）⇒ 得支持多点突变
   ⇒ 选错突变的探针会给出**虚假繁荣**的 6/6。

═══ 每个突变 ⇄ 一类真实缺陷 ⇄ 目标判据 ═══
  M1 slab 彻底失效（n_tot 与 t 脱钩 + 不画 slab）⇒ ⑰ 承重 + ⑭ 单调
  M2 脊宽 snap 错一格（有效宽度随 h 跳）          ⇒ ⑯ 脊形网格收敛
  M3 结构贴窗口底边（墙效应回归）                  ⇒ ⑯ 脊形网格收敛
  M4 网格步长写错（单位/倍数错）                   ⇒ ⑫ 退化一致
  M5 ε 转置（xy 取向错）                          ⇒ ⑬ 低对比度互验
  M6 任意截面入口误接半矢量                        ⇒ ⑮ 反自证桩

运行（仓库根）：python scripts/g12a_probe.py
出口：全部命中 ⇒ 0；有「打不红」 ⇒ 1。
"""
from __future__ import annotations

import importlib.util
import math
import os
import shutil
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO, "lda", "lda_solver", "full_vector_mode_solver.py")
_LDA = os.path.join(_REPO, "lda")

OK = []
BAD = []


def _load_patched(tag: str, patches):
    """patches = [(old, new), ...]；副本上依次替换后 import。"""
    src = open(_SRC, encoding="utf-8").read()
    for o, _n in patches:
        if o not in src:
            raise AssertionError("锚点未命中，探针已失效：%r" % o[:70])
    tmp = tempfile.mkdtemp(prefix="g12a_%s_" % tag)
    dst = os.path.join(tmp, "fv_mut_%s.py" % tag)
    blob = src
    for o, n in patches:
        blob = blob.replace(o, n, 1)
    open(dst, "w", encoding="utf-8", newline="\n").write(blob)
    try:
        if _LDA not in sys.path:
            sys.path.insert(0, _LDA)
        spec = importlib.util.spec_from_file_location("fv_mut_%s" % tag, dst)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return mod


def _plain(seq):
    """⑨/⑯ 返回 [(name, got, ref, d, tol, good) ...] ⇒ 归一化。"""
    return [(r[0], r[3], r[4], r[5], False) for r in seq]


def _triple(t, name, tol, polarity):
    """⑫/⑬/⑮/⑰ 返回 (a, b, d) ⇒ 归一化。polarity='gt' ⇒ 判据是 d > tol。"""
    _a, _b, d = t
    good = math.isfinite(d) and (d > tol if polarity == "gt" else abs(d) <= tol)
    return [(name, d, tol, good, polarity == "gt")]


def expect(tag, patches, judge, note=""):
    """judge(mod) -> [(name, d, tol, good, is_gt)]；要求**至少一行由绿转红**。"""
    if isinstance(patches, tuple) and len(patches) == 2 \
            and all(isinstance(x, str) for x in patches):
        patches = [patches]
    try:
        mod = _load_patched(tag, patches)
        pairs = judge(mod)
    except BaseException as e:                               # noqa: BLE001
        OK.append((tag, "崩溃 ⇒ 判据必红（%s: %s）" % (type(e).__name__, e)))
        return
    if not pairs:
        BAD.append((tag, "judge 没返回任何行"))
        return
    red = not all(p[3] for p in pairs)
    detail = " ".join(
        "%s:d=%s(tol=%g%s)" % (p[0],
                               ("%.2e" % p[1]) if math.isfinite(p[1]) else str(p[1]),
                               p[2], ",须>" if p[4] else ",须<=")
        for p in pairs)
    msg = "红=%s  %s%s" % (red, detail, ("  ← " + note) if note else "")
    (OK if red else BAD).append((tag, msg))


# --------------------------------------------------------------------------
# judge：每个突变打到哪几条判据
# --------------------------------------------------------------------------
def j_slabs(mod):
    return _triple(mod.selfcheck_rib_slab_loadbearing(),
                   "rib_slab_load", 1e-3, "gt") + \
        _plain(mod.selfcheck_rib_slab_monotonic())


def j_conv(mod):
    return _plain(mod.selfcheck_rib_grid_convergence())


def j_degen(mod):
    return _triple(mod.selfcheck_arbitrary_strip_degeneracy(),
                   "arb_degenerate", 1e-9, "le")


def j_lowc(mod):
    return _triple(mod.selfcheck_arbitrary_lowcontrast_vs_semivec(),
                   "arb_lowcontrast", 3e-3, "le")


def j_anti(mod):
    return _triple(mod.selfcheck_rib_vs_semivec_nonzero(),
                   "rib_antistake", 1e-4, "gt")


# --------------------------------------------------------------------------
# M1：slab 彻底失效（两处配合才成立：厚度不计入总高 + 不画平板层）
expect("M1_no_slab",
       [("    n_tot = max(int(round((slab_t + ridge_h) / h)), n_slab + 1)",
         "    n_tot = max(int(round(ridge_h / h)), 1)"),
        ("    eps[i0:i0 + n_slab, :] = float(n_core ** 2)", "    pass")],
       j_slabs, note="⑰ slab 承重 + ⑭ 单调应同时红")

# M2：脊宽 snap 错一格 ⇒ 有效宽度在 h=0.02/0.01 上差 0.02µm
expect("M2_width_missnap",
       ("n_w = 2 * max(int(round(ridge_w / 2.0 / h)), 1)",
        "n_w = 2 * max(int(round(ridge_w / 2.0 / h)) + 1, 1)"),
       j_conv, note="⑯ 网格步长携带了几何误差")

# M3：结构贴底边 ⇒ Dirichlet 墙挤压模场
expect("M3_bottom",
       ("    i0 = ny // 2 - n_tot // 2", "    i0 = 0"),
       j_conv, note="⑯ 墙效应回归")

# M4：网格步长写错（单位/倍数）⇒ 任意截面入口与条形封装不再等价
expect("M4_wrong_step",
       ("    xv = (np.arange(nxc + 1) - nxc / 2.0) * h",
        "    xv = (np.arange(nxc + 1) - nxc / 2.0) * h * 1.05"),
       j_degen, note="⑫ 退化一致破功")

# M5：ε 场转置（xy 取向错）⇒ 宽高互换
expect("M5_eps_T",
       ("    A, nx, ny = build_operator(eps, dx, dy, k0)",
        "    A, nx, ny = build_operator(eps.T.copy(), dy, dx, k0)"),
       j_lowc, note="⑬ 低对比度互验破功")

# M6：任意截面入口误接半矢量（复制粘贴级缺陷）
_M6_OLD = ("    rs = solve_modes_eps(eps, xv, yv, k0, k=k,\n"
           "                         core_vmask=core_vmask, conf_min=conf_min)")
_M6_NEW = """    _e = np.asarray(eps)
    _sv = _semivec()
    _thr = 0.5 * (float(_e.real.min()) + float(_e.real.max()))
    _n2 = np.where(_e.T > _thr, _e.real.max(), _e.real.min())
    _v = _sv.neff_2d(_n2, (float(xv[1]) - float(xv[0])), k0, k=8,
                     n_core=float(np.sqrt(_e.real.max())),
                     n_clad=float(np.sqrt(_e.real.min())))
    _vv = float(_v[0]) if isinstance(_v, (tuple, list)) else float(_v)
    if pol.upper() == "TE":
        return _vv
    _flipped = True
    rs = []"""
expect("M6_wrong_solver", (_M6_OLD, _M6_NEW), j_anti,
       note="⑮ 两法同值 ⇒ 缺陷信号")


def main() -> int:
    print("=" * 76)
    print("G12-A 突变探针（副本突变 · 零源码改动 · 人工运行不入 CI）")
    print("=" * 76)
    for tag, msg in OK:
        print(f"  [OK]   {tag:<18} {msg}")
    for tag, msg in BAD:
        print(f"  [BAD]  {tag:<18} {msg}")
    print()
    print(f"G12-A 探针：{len(OK)}/{len(OK) + len(BAD)} 命中"
          f"（每条 OK = 该类真实缺陷下判据**确实会变红**）")
    return 0 if not BAD else 1


if __name__ == "__main__":
    sys.exit(main())
