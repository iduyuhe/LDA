"""D-219 突变探针（scratch · 不入 CI）：证明 run_readout_mux_units_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 恢复旧写法 `*1e-6`（**本轮修的 bug 复发**）        ⇒ A1/A2/A3/G1 应红
  · M2 去掉 `/1e9`（返回 Hz 冒充 GHz）                    ⇒ A1/A2/A3 应红
  · M3 把 `4.0` 改成 `2.0`（λ/2 冒充 λ/4）               ⇒ A1/A2/A3/A4 应红
  · M4 反函数用错 ε（`eps_eff` 再开一次方）              ⇒ A1/A2/A3 应红
  · M5 `resonator_length_um` 里把长度乘 1e6（正向也错）  ⇒ A2/A3/A4 应红
  · M6 自检里删掉 `resonator_freq_ghz` 引用（回归死函数）⇒ H1 应红
  · M7 非法 ε 静默返回 inf（不再抛）                     ⇒ G2 应红
  · M8 模拟「偷偷加一个锚」                               ⇒ Z1 应红
🔴 教训：patch 必须打门禁同一模块对象（`lda_qeda.sc_readout_mux`）；
   且 patch `run_selfchecks` 时要**真的返回 False**，不能只换返回值骗过 H2。
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_readout_mux_units_smoke as S      # noqa: E402
from lda_qeda import sc_readout_mux as MUX   # noqa: E402


def run_smoke():
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                                   # noqa: BLE001
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    return rc, out.count("[FAIL]"), out


def main() -> int:
    rows = []

    rc, nf, _ = run_smoke()
    rows.append(("baseline 无突变（须全绿）", rc, nf))

    _len = MUX.resonator_length_um
    _freq = MUX.resonator_freq_ghz
    _self = MUX.run_selfchecks
    _c = MUX.C_UM_PER_S

    # M1 恢复旧写法 `*1e-6`（本轮修的 bug 复发）
    MUX.resonator_freq_ghz = lambda L, eps_eff=6.5: float(
        _c / math.sqrt(float(eps_eff)) / (4.0 * float(L) * 1e-6) / 1e9)
    rows.append(("M1 恢复 `*1e-6` 旧写法（bug 复发）", *run_smoke()[:2]))
    MUX.resonator_freq_ghz = _freq

    # M2 去掉 /1e9（返回 Hz 冒充 GHz）
    MUX.resonator_freq_ghz = lambda L, eps_eff=6.5: float(
        _c / math.sqrt(float(eps_eff)) / (4.0 * float(L)))
    rows.append(("M2 去掉 /1e9（Hz 冒充 GHz）", *run_smoke()[:2]))
    MUX.resonator_freq_ghz = _freq

    # M3 λ/2 冒充 λ/4
    MUX.resonator_length_um = lambda f, eps_eff=6.5: float(
        _c / math.sqrt(float(eps_eff)) / (2.0 * float(f) * 1e9))
    MUX.resonator_freq_ghz = lambda L, eps_eff=6.5: float(
        _c / math.sqrt(float(eps_eff)) / (2.0 * float(L)) / 1e9)
    rows.append(("M3 λ/2 冒充 λ/4（分母 4→2）", *run_smoke()[:2]))
    MUX.resonator_length_um, MUX.resonator_freq_ghz = _len, _freq

    # M4 反函数用错 ε（再开一次方 ⇒ ε^0.25）
    MUX.resonator_freq_ghz = lambda L, eps_eff=6.5: float(
        _c / (float(eps_eff) ** 0.25) / (4.0 * float(L)) / 1e9)
    rows.append(("M4 反函数 ε 开方两次（ε^0.25）", *run_smoke()[:2]))
    MUX.resonator_freq_ghz = _freq

    # M5 正向也错（长度乘 1e6）
    MUX.resonator_length_um = lambda f, eps_eff=6.5: float(
        _c / math.sqrt(float(eps_eff)) / (4.0 * float(f) * 1e9) * 1e6)
    rows.append(("M5 正向长度乘 1e6", *run_smoke()[:2]))
    MUX.resonator_length_um = _len

    # M6 自检里删掉 resonator_freq_ghz 引用（回归死函数）
    def _self_no_freq(verbose: bool = False) -> bool:
        return True
    _self_no_freq.__doc__ = "stub"
    MUX.run_selfchecks = _self_no_freq
    rows.append(("M6 自检不再引用反向函数（回归死函数）", *run_smoke()[:2]))
    MUX.run_selfchecks = _self

    # M7 非法 ε 静默返回 inf（不抛）
    def _freq_lenient(L, eps_eff=6.5):
        try:
            return float(_c / math.sqrt(float(eps_eff)) / (4.0 * float(L)) / 1e9)
        except (ValueError, ZeroDivisionError):
            return float("inf")

    def _len_lenient(f, eps_eff=6.5):
        try:
            return float(_c / math.sqrt(float(eps_eff)) / (4.0 * float(f) * 1e9))
        except (ValueError, ZeroDivisionError):
            return float("inf")

    MUX.resonator_freq_ghz = _freq_lenient
    MUX.resonator_length_um = _len_lenient
    rows.append(("M7 非法 ε 静默返回 inf（不再抛）", *run_smoke()[:2]))
    MUX.resonator_freq_ghz, MUX.resonator_length_um = _freq, _len

    # M8 模拟偷偷加一个锚
    try:
        from lda_harness import benchmarks as BM
        _orig = BM.BENCHMARK_DEFS
        fake = dict(_orig)
        fake["B999"] = dict(list(_orig.values())[0])
        BM.BENCHMARK_DEFS = fake
        rows.append(("M8 偷偷加一个锚（542）", *run_smoke()[:2]))
        BM.BENCHMARK_DEFS = _orig
    except Exception as e:                                   # noqa: BLE001
        rows.append(("M8 偷偷加一个锚（542）", 99, -1))
        print("M8 patch 失败：%s" % e)

    MUX.resonator_length_um, MUX.resonator_freq_ghz, MUX.run_selfchecks = _len, _freq, _self

    print("\n%-40s %4s %6s  %s" % ("突变", "rc", "FAIL", "结论"))
    ok = True
    for name, rc, nf in rows:
        if name.startswith("baseline"):
            good = (rc == 0 and nf == 0)
            verdict = "OK（全绿）" if good else "!! 基线应全绿"
        else:
            good = (rc != 0 and nf > 0)
            verdict = "咬住（%d 条红）" % nf if good else "!! 未咬住（假绿）"
        ok = ok and good
        print("%-40s %4s %6s  %s" % (name, rc, nf, verdict))
    print("\n探针结论：%s（%d/%d 突变被咬住）"
          % ("ALL_CAUGHT" if ok else "HAS_UNCAUGHT",
             sum(1 for n, r, f in rows if not n.startswith("baseline") and r != 0 and f > 0),
             len(rows) - 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
