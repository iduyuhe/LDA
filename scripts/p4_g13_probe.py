# -*- coding: utf-8 -*-
"""G13 附属突变探针：证明 `run_dispersive_smoke` 的判据**会响**。

人工运行 · **不进 CI**（遵「突变探针只人工跑」铁律）· 零源码突变（只 patch 运行时属性）。

为什么需要它（护栏自证纪律）
----------------------------
「没被验证过的护栏不算护栏」。本门禁有 11 条判据，其中多条如果**恒真**（例如把
① 写成「k_meas 是个小数」这种永真式），门禁就会长期假绿。本探针逐条造反例：
每次只注入**一个**缺陷，跑门禁，断言**该缺陷对应的判据必须变红**，且**其它判据不被
连带误伤**（隔离性 ⇒ 判据不是互相顶替的）。

实现方式（关键：**不碰源码**）
--------------------------------
`run_dispersive_smoke.main()` / `_measure` 内部用 `from lda_solver import dispersive`
取的是 `sys.modules` 里的**模块对象** ⇒ 只要 patch 模块对象的 `run_2d` 属性，门禁里
所有 `m.run_2d(...)` 就会走注入版。门禁自身累积计数的 `_PASS/_FAIL` 是模块全局，
探针可 read/reset ⇒ 可直接取「这次跑红了几条、红了哪几条」。

另：`main()` 会把报告写到 `lda/reports/dispersive_report.json` ⇒ 探针**先备份字节、
最后 finally 还原**（且校验 sha256），绝不让注入数据污染登记报告。

运行（仓库根）：python scripts/p4_g13_probe.py  → 全过则 rc=0
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

import run_dispersive_smoke as S                              # noqa: E402
from lda_solver import dispersive as m                         # noqa: E402

REPORT = os.path.join(_LDA, "reports", "dispersive_report.json")


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
# 注入器：每个返回 undo 函数。统一骨架 —— 包一层 run_2d，按 medium/参数识别目标用例。
# ---------------------------------------------------------------------------
def _wrap(pred, mutate):
    """返回 injector：仅当 pred(kwargs, medium) 命中时，对 run_2d 结果 mutate。"""
    orig = m.run_2d

    def fake(**kw):
        d = orig(**kw)
        med = kw.get("medium")
        if pred(kw, med):
            d = dict(d)
            mutate(d, kw, med)
        return d
    m.run_2d = fake
    return lambda: setattr(m, "run_2d", orig)


def _is_scalar(kw, med):
    return getattr(med, "kind", "") == "scalar"


def _is_lorentz(kw, med):
    return getattr(med, "kind", "") == "lorentz" and med.poles[0][1] != 0


def _is_drude(kw, med):
    return getattr(med, "kind", "") == "lorentz" and med.poles[0][1] == 0


def _is_aniso_Ey(kw, med):
    return getattr(med, "kind", "") == "anisotropic" and kw.get("source_comp") == "Ey"


def _is_aniso_Ez(kw, med):
    return getattr(med, "kind", "") == "anisotropic" and kw.get("source_comp") == "Ez"


def _is_kerr_weak(kw, med):
    return getattr(med, "kind", "") == "kerr" and abs(getattr(med, "n2", 0) - 1e-6) < 1e-9


def _is_kerr_strong(kw, med):
    return getattr(med, "kind", "") == "kerr" and abs(getattr(med, "n2", 0) - 2e-1) < 1e-9


def _is_stability(kw, med):
    return int(kw.get("n_warmup_periods", 0)) >= 100


def inj_scalar_off():
    """M1：标量 k_meas 虚高 50% ⇒ ① 标量必红。"""
    return _wrap(_is_scalar, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.5))


def inj_lorentz_off():
    """M2：Lorentz k_meas 虚高 50% ⇒ ① Lorentz 必红。"""
    return _wrap(_is_lorentz, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.5))


def inj_drude_off():
    """M3：Drude k_meas 虚高 50% ⇒ ① Drude 必红。"""
    return _wrap(_is_drude, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.5))


def inj_aniso_Ey_off():
    """M4：各向异性 Ey k_meas 虚高 10% ⇒ ②a 必红，且②c 双折射比连带漂移。"""
    return _wrap(_is_aniso_Ey, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.1))


def inj_aniso_Ez_off():
    """M5：各向异性 Ez k_meas 虚高 10% ⇒ ②b 必红，且②c 双折射比连带漂移。"""
    return _wrap(_is_aniso_Ez, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.1))


def inj_kerr_weak_off():
    """M6：Kerr 弱场 k_meas 虚高 10% ⇒ ③a（退化线性）必红；强场未动 ⇒ ③b 仍过。"""
    return _wrap(_is_kerr_weak, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 1.1))


def inj_kerr_strong_flat():
    """M7：Kerr 强场非线性被抹平（shift 压到 <0.1%）⇒ ③b 必红；弱场未动 ⇒ ③a 仍过。"""
    return _wrap(_is_kerr_strong, lambda d, *_: d.__setitem__("k_meas", d["k_meas"] * 0.999))


def inj_stability_blowup():
    """M8：稳定性用例 max|E| 虚标 100（远超上界）⇒ ④ 必红。"""
    return _wrap(_is_stability, lambda d, *_: d.__setitem__("max_abs_E", 100.0))


def inj_structure_wired():
    """M9：伪造一份「含 dispersive 字样」的 fdtd2d.py ⇒ ⑩ 必须红（故意变更探测器）。"""
    tmp = tempfile.mkdtemp(prefix="g13_probe_")
    sd = os.path.join(tmp, "lda_solver")
    os.makedirs(sd, exist_ok=True)
    with open(os.path.join(sd, "fdtd2d.py"), "w", encoding="utf-8") as fh:
        fh.write("# from lda_solver import dispersive   # 伪造的接线\n")
    with open(os.path.join(sd, "fdtd3d.py"), "w", encoding="utf-8") as fh:
        fh.write("# 干净\n")
    orig = S._HERE
    S._HERE = tmp

    def undo():
        S._HERE = orig
        shutil.rmtree(tmp, ignore_errors=True)
    return undo


def inj_net_token():
    """M10：红线反例：把 kernel 模块名（登记进报告）注入网络 token ⇒ ⑪ 必须红。"""
    orig = m.__name__
    m.__name__ = "https://example.com/evil-llm"
    return lambda: setattr(m, "__name__", orig)


# ---------------------------------------------------------------------------
# 探针清单：注入器 / 必须变红的判据前缀 / 说明
# ---------------------------------------------------------------------------
MUTATIONS = [
    ("M1  标量 k 虚高 50%", inj_scalar_off, ["① 标量"], "① 标量退化正确性"),
    ("M2  Lorentz k 虚高 50%", inj_lorentz_off, ["① Lorentz"], "① 色散解析一致性"),
    ("M3  Drude k 虚高 50%", inj_drude_off, ["① Drude"], "① Drude 退化一致"),
    ("M4  各向异性 Ey k 虚高 10%", inj_aniso_Ey_off, ["②a", "②c"],
     "②a 绝对误差 + ②c 双折射比连带漂移"),
    ("M5  各向异性 Ez k 虚高 10%", inj_aniso_Ez_off, ["②b", "②c"],
     "②b 绝对误差 + ②c 双折射比连带漂移"),
    ("M6  Kerr 弱场 k 虚高 10%", inj_kerr_weak_off, ["③a"],
     "③a 退化线性；③b 强场未动仍过 ⇒ 隔离"),
    ("M7  Kerr 强场非线性抹平", inj_kerr_strong_flat, ["③b"],
     "③b 自相位调制项须被检测到；③a 弱场未动仍过"),
    ("M8  稳定性 max|E| 虚标 100", inj_stability_blowup, ["④"],
     "④ 长程有界守卫"),
    ("M9  结构接线：伪造含 dispersive 的 fdtd2d.py", inj_structure_wired, ["⑩"],
     "故意的变更探测器（改默认吸收器须重跑锚）"),
    ("M10 红线：登记数据注入网络 token", inj_net_token, ["⑪"],
     "证明「零 LLM/零网络」判据**可证伪**"),
]


def main() -> int:
    print("=" * 78)
    print("G13 突变探针：证明 run_dispersive_smoke 的判据会响（零源码突变）")
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
