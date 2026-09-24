"""G12-B 突变探针（**人工运行，不入 CI**）——证明新判据能变红。

铁律⑧：没验证过的护栏不算护栏；铁律⑮：探针自身也会骗人。
本探针按「**零源码突变**」原则：把 `full_vector_mode_solver.py` 复制到临时
目录，在**副本**上做替换再 import，然后**只跑受影响的 G12-B 自校锚**，断言它
**由绿转红**。

🔴 首轮回炉教训（勿重犯，见 g12a_probe.py 注）：突变必须是「真缺陷」，不是
「无操作等价」；且必须确认**基线（未突变）全绿**，否则探针在自校锚已坏时
会给出虚假繁荣的 6/6。

═══ 每个突变 ⇄ 一类真实缺陷 ⇄ 目标判据 ═══
  M1 拉普拉斯次对角耦合错（−1/h²→−0.5/h²）⇒ 离散算子缩放错 ⇒ ⑱ 闭式金
  M2 质量矩阵退化为单位阵（忽略 ε）     ⇒ diel 与 air 同本征值 ⇒ ⑳ 物理判据
  M3 Kronecker 和丢 z 项                ⇒ k0²(2,1,1)/k0²(1,1,1)≠2 ⇒ ⑱ 闭式金
  M4 eigsh which="SM"→"LM"（取最大本征）⇒ 基模位置错 ⇒ ⑱ 闭式金
  M5 次对角量纲错（−1/h²→−1/h）         ⇒ 收敛阶退化越出 [1.8,2.2] ⇒ ⑲ 收敛阶
  M6 x 向拉普拉斯误用 Ny（忽略 Nx）      ⇒ 压扁 x 不改变本征值 ⇒ ㉑ 反向测试

运行（仓库根）：python scripts/g12b_probe.py
出口：全部命中 ⇒ 0；有「打不红」⇒ 1。
"""
from __future__ import annotations

import math
import os
import sys
import types

# 增量进度日志（绕过沙箱静默死：任何一步失败都能看到卡在哪）
_PROG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "g12b_probe_progress.txt")


def _progress(tag, msg=""):
    try:
        with open(_PROG, "a", encoding="utf-8") as _f:
            _f.write("%s %s\n" % (tag, msg))
    except BaseException:
        pass


# 顶层异常兜底：把任何未捕获异常的 traceback 强写到文件（绕过沙箱静默死）
def _exc_hook(et, ev, tb):
    try:
        import traceback as _tb_mod
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "g12b_probe_exc.txt"), "w", encoding="utf-8") as _f:
            _f.write("UNCAUGHT: " + "".join(_tb_mod.format_exception(et, ev, tb)))
    except BaseException:
        pass


sys.excepthook = _exc_hook
_progress("START", "probe process spawned")

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO, "lda", "lda_solver", "full_vector_mode_solver.py")
del _REPO

OK = []
BAD = []


def _make_module(tag, src_text):
    """把源文本 exec 进一个**全新命名空间**（不污染仓库、不重复 import scipy）。"""
    _progress("LOAD", tag)
    ns = {"__name__": "fv_mut_%s" % tag, "__file__": _SRC}
    try:
        exec(compile(src_text, _SRC, "exec"), ns)
    except BaseException as e:                       # noqa: BLE001
        _progress("LOAD_FAIL", "%s: %r" % (tag, e))
        raise
    return types.SimpleNamespace(**ns)


def _load_plain():
    return _make_module("plain", open(_SRC, encoding="utf-8").read())


def _load_patched(tag, patches):
    src = open(_SRC, encoding="utf-8").read()
    for o, _n in patches:
        if o not in src:
            raise AssertionError("锚点未命中，探针已失效：%r" % o[:70])
    blob = src
    for o, _n in patches:
        blob = blob.replace(o, _n, 1)
    return _make_module(tag, blob)


def _rows(seq):
    """selfcheck 返回 [(name,got,ex,d,tol,good)...] ⇒ 归一化。"""
    return [(r[0], r[3], r[4], r[5], False) for r in seq]


def _triple(t, name, tol, polarity):
    """selfcheck 返回 (a,b,d) ⇒ 归一化。polarity='gt' ⇒ 判据是 d > tol。"""
    _a, _b, d = t
    good = math.isfinite(d) and (d > tol if polarity == "gt" else abs(d) <= tol)
    return [(name, d, tol, good, polarity == "gt")]


def j_cubic(mod):
    return _rows(mod.selfcheck_cubic_cavity_golden())


def j_conv(mod):
    return _rows(mod.selfcheck_3d_convergence())


def j_diel(mod):
    return _triple(mod.selfcheck_3d_diel_lt_air(), "diel_lt_air", 0.0, "gt")


def j_shape(mod):
    return _triple(mod.selfcheck_3d_shape_sensitivity(), "shape", 1e-2, "gt")


def expect(tag, patches, judge, note=""):
    """要求：① 基线（未突变）该判据全绿；② 突变后**至少一行由绿转红**。"""
    _progress("EXPECT", tag)
    if isinstance(patches, tuple) and len(patches) == 2 \
            and all(isinstance(x, str) for x in patches):
        patches = [patches]
    try:
        base = judge(_load_plain())
        base_green = all(p[3] for p in base)
    except BaseException:                            # noqa: BLE001
        base_green = False
        base = [("BASELINE", float("nan"), 0.0, False, False)]
    if not base_green:
        BAD.append((tag, "基线非全绿 ⇒ 自校锚本身坏了，探针无意义（%s）"
                    % " ".join(p[0] for p in base)))
        _progress("BASELINE_BAD", tag)
        return
    try:
        mod = _load_patched(tag, patches)
        pairs = judge(mod)
    except BaseException as e:                       # noqa: BLE001
        OK.append((tag, "崩溃 ⇒ 判据必红（%s: %s）" % (type(e).__name__, e)))
        _progress("CRASH_OK", tag)
        return
    if not pairs:
        BAD.append((tag, "judge 没返回任何行"))
        _progress("NO_ROWS", tag)
        return
    red = not all(p[3] for p in pairs)
    detail = " ".join(
        "%s:d=%s(tol=%g%s)" % (p[0],
                               ("%.2e" % p[1]) if math.isfinite(p[1]) else str(p[1]),
                               p[2], ",须>" if p[4] else ",须<=")
        for p in pairs)
    msg = "红=%s  %s%s" % (red, detail, ("  ← " + note) if note else "")
    (OK if red else BAD).append((tag, msg))
    _progress("DONE", "%s red=%s" % (tag, red))


# M1：拉普拉斯次对角耦合系数错（−1/h² → −0.5/h²，离散算子缩放错 ⇒ 闭式金失配）
# 🔴 注意：绝不可改成「main 2/h²→1/h²」——那会让 1D 拉普拉斯**不对角占优/不定**，
#    eigsh(which="SM") 撞零交叉会**进程级崩溃（无 Python traceback）**。次对角 ×0.5 保持 SPD。
expect("M1_off_scale",
       ("    off = -1.0 / h ** 2 * np.ones(M - 1)",
        "    off = -0.5 / h ** 2 * np.ones(M - 1)"),
       j_cubic, note="⑱ 闭式金应红（k0² 缩放偏差）")

# M2：质量矩阵退化为单位阵（忽略 ε ⇒ diel 与 air 同本征值）
expect("M2_mass_identity",
       ("    Mvec = np.tile(node_eps.ravel(order=\"C\"), 3)",
        "    Mvec = np.ones(3 * nn)"),
       j_diel, note="⑳ 物理判据应红")

# M3：Kronecker 和丢 z 项（真实缺陷：z 方向未离散）
expect("M3_drop_z",
       ("    K1 = (kron(kron(Lx, Iy), Iz)\n"
        "          + kron(kron(Ix, Ly), Iz)\n"
        "          + kron(kron(Ix, Iy), Lz)).tocsr()",
        "    K1 = (kron(kron(Lx, Iy), Iz)\n"
        "          + kron(kron(Ix, Ly), Iz)).tocsr()"),
       j_cubic, note="⑱ 闭式金（211/111≠2）应红")

# M4：eigsh 取最大本征（真实缺陷：基模位置识别错）
expect("M4_which_LM",
       ("which=\"SM\", return_eigenvectors=False",
        "which=\"LM\", return_eigenvectors=False"),
       j_cubic, note="⑱ 闭式金应红（取到最大模）")

# M5：次对角量纲错（−1/h² → −1/h，引入 O(h) 误差 ⇒ 收敛阶退化到 ~1 或负值，越出 [1.8,2.2]）
# 🔴 注意：不可用「h→2h」（只平移 N 下标，收敛阶仍为 ~2，探针打不红）。
expect("M5_off_dim",
       ("    off = -1.0 / h ** 2 * np.ones(M - 1)",
        "    off = -1.0 / h * np.ones(M - 1)"),
       j_conv, note="⑲ 收敛阶应红（rate≈1 或负值，越出 [1.8,2.2]）")

# M6：x 向拉普拉斯误用 Ny（真实缺陷：x 几何被忽略）
expect("M6_Lx_uses_Ny",
       ("    Lx = _laplacian_1d_dirichlet(Nx, h)",
        "    Lx = _laplacian_1d_dirichlet(Ny, h)"),
       j_shape, note="㉑ 反向测试应红（压扁 x 无效）")


def main() -> int:
    print("=" * 76)
    print("G12-B 突变探针（副本突变 · 零源码改动 · 人工运行不入 CI）")
    print("=" * 76)
    for tag, msg in OK:
        print(f"  [OK]   {tag:<18} {msg}")
    for tag, msg in BAD:
        print(f"  [BAD]  {tag:<18} {msg}")
    print()
    print(f"G12-B 探针：{len(OK)}/{len(OK) + len(BAD)} 命中"
          f"（每条 OK = 该类真实缺陷下判据**确实会变红**）")
    # 自写 UTF-8 摘要（绕过 PowerShell UTF-16 重定向）
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "g12b_probe_result.txt"), "w", encoding="utf-8") as f:
            f.write(f"OK={len(OK)} BAD={len(BAD)}\n")
            for tag, msg in OK:
                f.write(f"[OK]   {tag}: {msg}\n")
            for tag, msg in BAD:
                f.write(f"[BAD]  {tag}: {msg}\n")
    except BaseException as e:                       # noqa: BLE001
        print("摘要文件写入失败：", e)
    return 0 if not BAD else 1


if __name__ == "__main__":
    sys.exit(main())
