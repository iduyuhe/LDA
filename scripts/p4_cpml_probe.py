# -*- coding: utf-8 -*-
"""P4 附属突变探针：证明 `run_cpml_absorber_smoke`（G11 真 PML）的判据**会响**。

人工运行 · **不进 CI**（遵「突变探针只人工跑」铁律）· 零源码突变（只 patch 运行时属性）。

为什么需要它（护栏自证纪律）
----------------------------
「没被验证过的护栏不算护栏」。本门禁有 14 条判据，其中多条如果**恒真**（例如把
④/⑦ 写成「CPML 的 Γ 是个小数」这种永真式），门禁就会长期假绿。本探针逐条造反例：
每次只注入**一个**缺陷，跑门禁，断言**该缺陷对应的判据必须变红**，且**其它判据不被
连带误伤**（隔离性 ⇒ 判据不是互相顶替的）。

实现方式（关键：**不碰源码**）
--------------------------------
`run_cpml_absorber_smoke.main()` 内部用 `from lda_solver import fdtd_cpml as fc`
取的是 `sys.modules` 里的**模块对象** ⇒ 只要 patch 模块对象的属性，`main()` 里的
`fc.measure_reflection(...)` 就会走注入版。门禁自身累积计数的 `_PASS/_FAIL` 是模块
全局，探针可 read/reset ⇒ 可直接取「这次跑红了几条、红了哪几条」。

另：`main()` 会把报告写到 `lda/reports/cpml_absorber_report.json` ⇒ 探针**先备份字节、
最后 finally 还原**（且校验 sha256），绝不让注入数据污染登记报告。

运行（仓库根）：python scripts/p4_cpml_probe.py  → 全过则 rc=0
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, os.path.join(_LDA, "lda_solver"), os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                             # noqa: E402
import run_cpml_absorber_smoke as S                             # noqa: E402
from lda_solver import cpml as cm                               # noqa: E402
from lda_solver import fdtd_cpml as fc                          # noqa: E402
from lda_solver import fdtd2d as f2                             # noqa: E402

REPORT = os.path.join(_LDA, "reports", "cpml_absorber_report.json")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_gate():
    """跑一次门禁，返回 (rc, stdout, 变红的判据标签列表)。"""
    S._PASS = 0
    S._FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = S.main()
    out = buf.getvalue()
    red = [ln.strip()[len("[FAIL]"):].strip()
           for ln in out.splitlines() if ln.strip().startswith("[FAIL]")]
    return rc, out, red


def _restorer(fn):
    """把 fn() 返回的『还原函数』包成上下文：异常也保证还原。"""
    class _Ctx:
        def __enter__(self):
            self.undo = fn()
            return self

        def __exit__(self, *exc):
            self.undo()
            return False
    return _Ctx()


# ---------------------------------------------------------------------------
# 注入器：每个返回 undo 函数
# ---------------------------------------------------------------------------
def inj_no_absorber():
    """M1 空集反例：CPML 侧强制 n_abs=0 ⇒ 退化成**无吸收器**（截断边界）。"""
    orig = fc.measure_reflection

    def fake(**kw):
        kw["n_abs"] = 0
        return orig(**kw)
    fc.measure_reflection = fake
    return lambda: setattr(fc, "measure_reflection", orig)


def inj_const_gamma():
    """M2 判据 D 假绿探测器：CPML 的 Γ 恒定（与层厚无关）⇒ 序列不单调。"""
    orig = fc.measure_reflection

    def fake(**kw):
        d = orig(**kw)
        if kw.get("absorber") == "cpml" and int(kw.get("n_abs", 0)) > 0:
            d = dict(d)
            d["gamma"] = 1e-5
            d["gamma_peak"] = 1e-5
        return d
    fc.measure_reflection = fake
    return lambda: setattr(fc, "measure_reflection", orig)


def inj_dead_instrument():
    """M3 仪器灵敏度反例：无吸收时也报小 Γ ⇒ 测量仪对「有没有吸收」不敏感。"""
    orig = fc.measure_reflection

    def fake(**kw):
        d = orig(**kw)
        if int(kw.get("n_abs", 0)) == 0:
            d = dict(d)
            d["gamma"] = 1e-6
        return d
    fc.measure_reflection = fake
    return lambda: setattr(fc, "measure_reflection", orig)


def inj_trace_pollution():
    """M4 传播子污染反例：回波到达**前**的波形被注入 1e-9 偏移。"""
    orig = fc.measure_reflection

    def fake(**kw):
        d = orig(**kw)
        if kw.get("return_trace") and kw.get("absorber") == "cpml" and d.get("trace") is not None:
            d = dict(d)
            t = np.array(d["trace"], dtype=float)
            t[:int(d["idx_pure"])] += 1e-9
            d["trace"] = t
        return d
    fc.measure_reflection = fake
    return lambda: setattr(fc, "measure_reflection", orig)


def inj_structure_wired():
    """M5 结构反例：伪造一份「含 cpml 字样」的 fdtd2d.py 指向它 ⇒ ⑩ 必须红。"""
    tmp = tempfile.mkdtemp(prefix="p4c_probe_")
    sd = os.path.join(tmp, "lda_solver")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "fdtd2d.py"), "w", encoding="utf-8") as fh:
        fh.write("# from lda_solver import cpml   # 伪造的接线\n")
    with open(os.path.join(sd, "fdtd3d.py"), "w", encoding="utf-8") as fh:
        fh.write("# 干净\n")
    orig = S._HERE
    S._HERE = tmp

    def undo():
        S._HERE = orig
        shutil.rmtree(tmp, ignore_errors=True)
    return undo


def inj_signature_drift():
    """M6 签名反例：把 2D 默认 sponge 从 200 改成 999 ⇒ ⑪ 必须红。"""
    orig = f2._run_planewave

    def fake(dl_factor=40.0, courant=0.95, ramp=400, sponge=999,
             target_exp=12.0, pbc_y=True):
        raise AssertionError("probe stub 不应被真正调用")
    f2._run_planewave = fake
    return lambda: setattr(f2, "_run_planewave", orig)


def inj_net_token():
    """M7 红线反例：把网络 token 注入**登记数据**（内核模块名）⇒ ⑫ 必须红。"""
    orig = cm.__name__
    cm.__name__ = "https://example.com/llm"
    return lambda: setattr(cm, "__name__", orig)


def inj_avg_coeffs():
    """M8 半格口径反例：把 b_h 直接退化成 0.5·(b_e[i]+b_e[i+1])。"""
    orig = cm.cpml_axis

    def fake(*a, **kw):
        d = dict(orig(*a, **kw))
        be = np.asarray(d["b_e"], dtype=float)
        bh = 0.5 * (be[:-1] + be[1:])
        bh = np.concatenate([bh, bh[-1:]])
        d["b_h"] = bh
        return d
    cm.cpml_axis = fake
    return lambda: setattr(cm, "cpml_axis", orig)


def inj_phys_region_dirty():
    """M9 物理区污染反例：把物理区 κ 从 1 改成 2（人为阻抗失配）。"""
    orig = cm.cpml_axis

    def fake(*a, **kw):
        d = dict(orig(*a, **kw))
        ke = np.array(d["kappa_e"], dtype=float)
        ke[400 // 4: 3 * 400 // 4] = 2.0
        d["kappa_e"] = ke
        return d
    cm.cpml_axis = fake
    return lambda: setattr(cm, "cpml_axis", orig)


def inj_impedance_jump():
    """M10 内边缘跳变反例：PML 内边缘 σ/κ 不为 (0, 1)（人为反射面）。"""
    orig = cm.cpml_axis

    def fake(*a, **kw):
        d = dict(orig(*a, **kw))
        n_abs = int(kw.get("n_abs", a[1] if len(a) > 1 else 40))
        sg = np.array(d["sigma"], dtype=float)
        kp = np.array(d["kappa"], dtype=float)
        sg[n_abs - 1] = 1.0     # 内边缘 σ ≠ 0
        kp[n_abs - 1] = 1.05    # 内边缘 κ ≠ 1
        d["sigma"], d["kappa"] = sg, kp
        return d
    cm.cpml_axis = fake
    return lambda: setattr(cm, "cpml_axis", orig)


# ---------------------------------------------------------------------------
# 探针清单：注入器 / 必须变红的判据前缀 / 说明
# ---------------------------------------------------------------------------
MUTATIONS = [
    ("M1  空集：CPML 无吸收（n_abs→0）", inj_no_absorber,
     ["④ CPML", "⑥ CPML", "⑦a", "⑦c"], "退化成截断边界 ⇒ 改善倍率与细端全掉"),
    ("M2  判据 D：Γ 恒定（与层厚无关）", inj_const_gamma,
     ["⑦a"], "隔离性：④/⑦c 仍过 ⇒ ⑦a 不是 ④ 的替身"),
    ("M3  仪器灵敏度：无吸收也报小 Γ", inj_dead_instrument,
     ["③"], "对「有无吸收」不敏感的假仪器"),
    ("M4  传播子污染：回波前注入 1e-9", inj_trace_pollution,
     ["⑨"], "污染物理区 ⇒ 表观 Γ 失真风险"),
    ("M5  结构接线：伪造含 cpml 的 fdtd2d.py", inj_structure_wired,
     ["⑩"], "故意的变更探测器（改默认吸收器须重跑锚）"),
    ("M6  默认签名漂移：2D sponge 200→999", inj_signature_drift,
     ["⑪"], "既有 FDTD 默认签名守卫"),
    ("M7  红线：登记数据注入网络 token", inj_net_token,
     ["⑫"], "证明「零 LLM/零网络」判据**可证伪**"),
    ("M8  半格口径退化成平均系数", inj_avg_coeffs,
     ["②"], "b 对 σ 非线性 ⇒ 不可平均系数"),
    ("M9  物理区污染：κ 内区 1→2", inj_phys_region_dirty,
     ["① CPML"], "物理区不是逐位恒等"),
    ("M10 内边缘阻抗跳变：σ/κ ≠ (0,1)", inj_impedance_jump,
     ["① PML"], "PML 内边缘人为反射面"),
]


def main() -> int:
    print("=" * 78)
    print("P4-G11 突变探针：证明 run_cpml_absorber_smoke 的判据会响（零源码突变）")
    print("=" * 78)

    bak = REPORT + ".probe_bak"
    existed = os.path.exists(REPORT)
    if existed:
        shutil.copyfile(REPORT, bak)
    sha0 = _sha(REPORT) if existed else None

    try:
        rc0, out0, red0 = run_gate()
        base_ok = (rc0 == 0 and not red0)
        print("  基线（无注入）：rc=%s · 变红 %d 条 ⇒ %s"
              % (rc0, len(red0), "合法必过 ✅" if base_ok else "基线本身红 ❌"))
        if red0:
            for l in red0[:6]:
                print("      " + l[:150])
        print("-" * 78)

        results = []
        for name, inj, want, why in MUTATIONS:
            with _restorer(inj):
                rc, out, red = run_gate()
            hit = {w: any(l.startswith(w) for l in red) for w in want}
            ok = rc != 0 and all(hit.values())
            results.append((name, ok, red, want, why))
            print("  %-40s rc=%-3s 变红 %2d 条  %s"
                  % (name, rc, len(red), "PASS" if ok else "FAIL"))
            print("      判据命中: %s"
                  % " · ".join("%s=%s" % (w, "红" if h else "**未红**")
                               for w, h in hit.items()))
            if not ok:
                print("      实际变红: %s" % ([x[:52] for x in red] or "（无）"))
            print("      用意: %s" % why)
        print("-" * 78)
    finally:
        if existed:
            shutil.copyfile(bak, REPORT)
            os.remove(bak)
        sha1 = _sha(REPORT) if os.path.exists(REPORT) else None
        print("  报告字节还原：%s（sha256 %s）"
              % ("✅ 一致" if sha0 == sha1 else "❌ 不一致（探针污染了登记报告！）",
                 "n/a" if sha1 is None else sha1[:16]))

    n_ok = sum(1 for r in results if r[1])
    print("=" * 78)
    print("汇总：%d/%d 突变全部被对应判据捕获 —— %s"
          % (n_ok, len(MUTATIONS),
             "判据会响 ✅" if n_ok == len(MUTATIONS) else "存在哑判据 ❌"))
    return 0 if (n_ok == len(MUTATIONS) and base_ok and sha0 == sha1) else 1


if __name__ == "__main__":
    sys.exit(main())
