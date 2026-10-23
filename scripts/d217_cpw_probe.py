"""D-217 突变探针（scratch · 不入 CI）：证明 run_cpw_quasi_static_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 `ellip_k` 恒回 π/2（椭圆积分退化）           ⇒ A1/A3/X2 应红
  · M2 填充因子第一因子写反（K/K' 而非 K'/K）        ⇒ X2 应红（h→∞ 不趋 (1+εr)/2）
  · M3 Z0 改回 30π 形式且不作定义式                  ⇒ A2 应红（恒等式不再精确成立）
  · M4 `cpw_from_layout` 把 gap_source 写成 measurement ⇒ G1/G2 应红（等效冒充实测）
  · M5 `cpw_from_layout` 无 gap 时默认 g=1.0        ⇒ G3 应红（开始猜）
  · M6 反提 w 放大 10%                              ⇒ G1 应红（w 真回提）
  · M7 `why_not_anchored` 把 anchorable 改 True     ⇒ Z1 应红（负结果被抹）
  · M8 `resonator_f0_ghz` 分母用 2L 而非 4L         ⇒ H1 应红（f0 口径错 ⇒ 与设计值漂移）
🔴 教训：patch 必须打门禁同一模块对象（`lda_qeda.cpw_quasi_static`）。
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_cpw_quasi_static_smoke as S       # noqa: E402
from lda_qeda import cpw_quasi_static as QS  # noqa: E402


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    return rc, buf.getvalue().count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _k = QS.ellip_k
    _closed = QS.cpw_closed_form
    _from_layout = QS.cpw_from_layout
    _why = QS.why_not_anchored
    _f0 = QS.resonator_f0_ghz

    # M1 椭圆积分退化
    QS.ellip_k = lambda k: math.pi / 2.0
    rows.append(("M1 ellip_k 恒回 π/2", *run_smoke()))
    QS.ellip_k = _k

    # M2 填充因子写反：把 q 乘一个倒数因子（用包装实现，不改源）
    def _closed_bad_q(w_um, g_um, **kw):
        out = dict(_closed(w_um, g_um, **kw))
        k = out["k"]
        kp = math.sqrt(max(0.0, 1.0 - k * k))
        ratio = (_k(k) / _k(kp)) ** 2          # 反向因子
        eps_new = 1.0 + (out["eps_eff"] - 1.0) * ratio
        out["eps_eff"] = eps_new
        out["n_eff"] = math.sqrt(eps_new)
        out["Z0_ohm"] = 1.0 / (QS.PHYSICAL_CONSTANTS["C0"]
                               * math.sqrt(out["C_air_F_per_m"] * out["C_air_F_per_m"] * eps_new))
        return out

    QS.cpw_closed_form = _closed_bad_q
    rows.append(("M2 填充因子写反（K/K' 代替 K'/K）", *run_smoke()))
    QS.cpw_closed_form = _closed

    # M3 Z0 用 30π 形式冒称定义式（恒等式不再精确）
    def _closed_30pi(w_um, g_um, **kw):
        out = dict(_closed(w_um, g_um, **kw))
        out["Z0_ohm"] = out["Z0_30pi_ohm"]
        out["zc_product"] = out["Z0_ohm"] * math.sqrt(out["C_air_F_per_m"] * out["C_d_F_per_m"]) \
            * QS.PHYSICAL_CONSTANTS["C0"]
        return out

    QS.cpw_closed_form = _closed_30pi
    rows.append(("M3 Z0 用 30π 形式冒称定义式", *run_smoke()))
    QS.cpw_closed_form = _closed

    # M4 等效冒充实测
    def _lay_measured(elements, **kw):
        out = _from_layout(elements, **kw)
        if out.get("ok"):
            out["gap_source"] = "measurement"
            out["caveat"] = "w/g 均由版图回提（无等效）"
        return out

    QS.cpw_from_layout = _lay_measured
    rows.append(("M4 gap_source 冒充 measurement", *run_smoke()))
    QS.cpw_from_layout = _from_layout

    # M5 无 gap 时默认 1.0（开始猜）
    def _lay_guess(elements, **kw):
        if kw.get("gap_um") is None and kw.get("ground_gap_um") is None:
            kw = dict(kw, ground_gap_um=1.0)
        return _from_layout(elements, **kw)

    QS.cpw_from_layout = _lay_guess
    rows.append(("M5 无 gap 时默认 1.0（猜）", *run_smoke()))
    QS.cpw_from_layout = _from_layout

    # M6 反提 w 放大 10%
    def _lay_w(elements, **kw):
        out = _from_layout(elements, **kw)
        if out.get("ok"):
            w = out["w_um"] * 1.1
            out.update(_closed(w, out["g_um"], h_um=kw.get("h_um", QS.DEFAULT_H_UM),
                               eps_r=kw.get("eps_r", QS.DEFAULT_EPS_R)))
            out["w_um"] = w
        return out

    QS.cpw_from_layout = _lay_w
    rows.append(("M6 反提 w 放大 10%", *run_smoke()))
    QS.cpw_from_layout = _from_layout

    # M7 负结果被抹
    def _why_true():
        w = dict(_why())
        w["anchorable"] = True
        return w

    QS.why_not_anchored = _why_true
    rows.append(("M7 anchorable 改 True（抹掉负结果）", *run_smoke()))
    QS.why_not_anchored = _why

    # M8 f0 分母用 2L
    QS.resonator_f0_ghz = lambda L_um, n_eff: (QS.PHYSICAL_CONSTANTS["C0"]
                                              / (2.0 * (L_um * 1e-6) * n_eff)) / 1e9
    rows.append(("M8 f0 分母用 2L（λ/2 冒称 λ/4）", *run_smoke()))
    QS.resonator_f0_ghz = _f0

    print("=" * 78)
    bad = 0
    for name, rc, nfail in rows:
        good = (rc == 0 and nfail == 0) if name.startswith("baseline") else (rc != 0 and nfail > 0)
        if not good:
            bad += 1
        print("%-6s %-46s rc=%-3d FAIL=%d" % ("[OK]" if good else "[BAD]", name, rc, nfail))
    print("=" * 78)
    print("突变探针：%d 条，%d 条未按预期变红" % (len(rows) - 1, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
