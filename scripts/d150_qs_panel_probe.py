#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M8 量子传感器案例卡门禁 · 突变探针（13 条突变各必红 + 还原复绿）。

每条突变只破坏**一个**语义，验证门禁 `run_qs_panel_smoke` 的对应判据确实能变红
（"先证能变红" —— 全绿的门禁若探针打不红，就是死测试）：

  M1  腿 A 基线 η 漂移 +1 pT/√Hz        ⇒ B7/B9 应红
  M2  闭式镜像篡改（散粒极限 ×2）        ⇒ A1(⑤)/B8 应红
  M3  verdict 冒充 PASS                  ⇒ A1(②)/B2 应红
  M4  诚实边界删条（honest_note 只剩一句）⇒ A1(③)/B5 应红
  M5  缺口粉饰（G11 谎报「已闭合」）      ⇒ A1(⑨)/B4 应红
  M6  跨源漂移（腿 B 优化后 B_N ×2）      ⇒ B14 应红
  M7  手写自检项数谎报（QS-M0: 8→99）     ⇒ B15 应红
  M8  路由未注册（删 GET_ROUTES 行）      ⇒ F1 应红
  M9  面板删「不宣称「已达国际水平」」     ⇒ F9 应红
  M10 端点误入登录闸门（HEAVY_POST_PATHS）⇒ E1 应红
  M11 首屏案例条删 #sec-qsensor 直达       ⇒ F8 应红
  M12 hash 深链映射删除（CASE_MAP）        ⇒ F7/F7b 应红
  M13 前端抹掉一处取值路径引用             ⇒ D3 应红

运行：python scripts/d150_qs_panel_probe.py
（本机 Bash shim 坏 ⇒ 建议 `python scripts/d150_qs_panel_probe.py > out.txt 2>&1` 再读）
"""
from __future__ import annotations

import copy
import io
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_qs_panel_smoke as SMOKE          # noqa: E402
from lda_webui import qs_case as QS         # noqa: E402

_IDX = os.path.join(_LDA, "lda_webui", "static", "index.html")
_RT = os.path.join(_LDA, "lda_webui", "routes.py")


# ── 加速：把门禁要现算的 `qs_m*` 设计入口**记忆化**（语义不变 —— 这些是纯函数，
#    且本探针的 13 条突变**只打 QS（面板模块）与 routes/index.html**，从不改 qs_m*）。
#    不加速的话 15 次 in-process 门禁跑 ≈ 300 s（单次 ~21 s，重头是九档 selfcheck）。
_MEMO = {}


def _install_memo():
    from lda_l2 import (qs_m0, qs_m1, qs_m2, qs_m3, qs_m3b,  # noqa: E402
                        qs_m4, qs_m5, qs_m6, qs_m7)
    targets = [
        (qs_m0, "design_magnetometer_v0"), (qs_m0, "selfcheck_qs_m0"),
        (qs_m1, "design_fom_system"), (qs_m2, "design_coherence_noise"),
        (qs_m3, "design_geometry"), (qs_m3b, "design_qs_devices"),
        (qs_m4, "design_qs_array"), (qs_m5, "design_qs_locked"),
        (qs_m6, "design_qs_squid"), (qs_m7, "design_qs_noise_opt"),
    ]
    for mod, name in targets:
        orig = getattr(mod, name)

        def make(orig=orig, key=(id(mod), name)):
            def wrapper(*a, **k):
                kk = (key, a, tuple(sorted(k.items())))
                if kk not in _MEMO:
                    _MEMO[kk] = orig(*a, **k)
                return _MEMO[kk]
            wrapper.__name__ = getattr(orig, "__name__", name)
            return wrapper

        setattr(mod, name, make())

# 🔴 可变容器必须**深拷贝**备份：本探针的多条突变是**原地改**容器元素
#    （`NV_LEG[k]=…` / `GAPS[10]["status"]=…` / `MILESTONES[0][…]=…`），
#    只存引用的话 `_restore()` 把同一个（已被改的）对象塞回去 ⇒ 还原不复绿。
_ORIG = {
    "case_card": QS.case_card,
    "shot_limit_eta_pT": QS.shot_limit_eta_pT,
    "NV_LEG": copy.deepcopy(QS.NV_LEG),
    "SQUID_LEG": copy.deepcopy(QS.SQUID_LEG),
    "GAPS": copy.deepcopy(QS.GAPS),
    "MILESTONES": copy.deepcopy(QS.MILESTONES),
    "QS_HONEST_NOTE": QS.QS_HONEST_NOTE,
}


def run_smoke():
    """in-process 跑门禁 main()，返回 (退出码, FAIL 行列表)。"""
    SMOKE.PASS = 0
    SMOKE.FAIL = 0
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = SMOKE.main()
    except SystemExit as e:                       # pragma: no cover
        rc = e.code
    except Exception as e:                        # noqa: BLE001
        rc = 99
        buf.write("[CRASH] %r\n" % (e,))
    finally:
        sys.stdout = old
    lines = buf.getvalue().splitlines()
    fails = [l.strip() for l in lines if "[FAIL]" in l]
    crashes = [l for l in lines if "[CRASH]" in l]
    return (rc, fails, crashes)


def _restore():
    for k, v in _ORIG.items():
        setattr(QS, k, copy.deepcopy(v) if isinstance(v, (dict, list)) else v)


class _TextMut:
    """临时替换文件文本（try/finally 保证还原）。

    🔴 全替换（`t.replace(old, new)` 不带 count）：同一字样出现两次时若只换一处，
    「存在性」断言仍成立 ⇒ 探针**假绿**（血案 ④）。
    """

    def __init__(self, path, pairs):
        self.path, self.pairs = path, pairs

    def __enter__(self):
        self.orig = io.open(self.path, encoding="utf-8").read()
        t = self.orig
        for old, new in self.pairs:
            assert old in t, "锚点缺失：%r" % (old[:60],)
            t = t.replace(old, new)          # 全替换：须让该字样在文件中**彻底消失**
        io.open(self.path, "w", encoding="utf-8", newline="").write(t)
        return self

    def __exit__(self, *exc):
        io.open(self.path, "w", encoding="utf-8", newline="").write(self.orig)
        return False


def _hit(fails, keys):
    """FAIL 行里是否出现全部期望关键词中的任意一个。"""
    return any(any(k in ln for k in keys) for ln in fails)


def main():
    _install_memo()
    rows = []

    # 基线（须全绿）
    rc0, f0, c0 = run_smoke()
    rows.append(("基线（须全绿 exit=0）", rc0, f0, c0, []))
    if rc0 != 0:
        print("！！基线未全绿 —— 后续突变结论不可信")
        for ln in f0:
            print("   ", ln)

    # ---- M1 腿 A 基线 η 漂移 ----
    QS.NV_LEG["eta_baseline_pT_per_sqrtHz"] = (
        _ORIG["NV_LEG"]["eta_baseline_pT_per_sqrtHz"] + 1.0)
    rows.append(("M1 腿 A 基线 η 漂移 +1", *run_smoke(), ["B7", "B9"]))
    _restore()

    # ---- M2 闭式镜像篡改（散粒极限 ×2）----
    QS.shot_limit_eta_pT = lambda *a, **k: _ORIG["shot_limit_eta_pT"](*a, **k) * 2.0
    rows.append(("M2 闭式镜像篡改（η ×2）", *run_smoke(), ["A1", "B8"]))
    _restore()

    # ---- M3 verdict 冒充 PASS ----
    def _m3(*a, **k):
        c = dict(_ORIG["case_card"](*a, **k))
        c["verdict"] = "PASS"
        return c
    QS.case_card = _m3
    rows.append(("M3 verdict 冒充 PASS", *run_smoke(), ["A1", "B2"]))
    _restore()

    # ---- M4 诚实边界删条 ----
    QS.QS_HONEST_NOTE = "本案例已完成。"
    rows.append(("M4 诚实边界删条", *run_smoke(), ["A1", "B5"]))
    _restore()

    # ---- M5 缺口粉饰（G11 谎报已闭合）----
    QS.GAPS[10]["status"] = "已闭合"
    rows.append(("M5 G11 谎报「已闭合」", *run_smoke(), ["A1", "B4"]))
    _restore()

    # ---- M6 跨源漂移（腿 B 优化后 B_N ×2）----
    QS.SQUID_LEG["b_n_opt_fT_per_sqrtHz"] = (
        _ORIG["SQUID_LEG"]["b_n_opt_fT_per_sqrtHz"] * 2.0)
    rows.append(("M6 腿 B 优化后 B_N ×2", *run_smoke(), ["B14"]))
    _restore()

    # ---- M7 手写自检项数谎报 ----
    QS.MILESTONES[0]["selfchecks"] = 99
    rows.append(("M7 自检项数谎报（8→99）", *run_smoke(), ["B15"]))
    _restore()

    # ---- M8 路由未注册 ----
    with _TextMut(_RT, [('    "/api/qsensor_demo": h_qsensor_demo,\n', "")]):
        rows.append(("M8 路由未注册（删 GET_ROUTES 行）", *run_smoke(), ["F1"]))

    # ---- M9 面板删诚实标注 ----
    with _TextMut(_IDX, [("不宣称「已达国际水平」", "已达国际水平")]):
        rows.append(("M9 面板删「不宣称已达国际水平」", *run_smoke(), ["F9"]))

    # ---- M10 端点误入登录闸门 ----
    with _TextMut(_RT, [("HEAVY_POST_PATHS = {\n",
                         'HEAVY_POST_PATHS = {\n    "/api/qsensor_demo",\n')]):
        rows.append(("M10 端点误入登录闸门", *run_smoke(), ["E1"]))

    # ---- M11 首屏案例条删 sec-qsensor 直达 ----
    with _TextMut(_IDX, [(
        '    <a href="#sec-qsensor" style="color:#0b1220;background:#f0abfc;'
        'border-radius:8px;padding:5px 12px;text-decoration:none;font-weight:700">'
        '★ 量子传感器 QS-M0–M7（NV 色心 + 超导 SQUID 双腿 · 建模设计预算 · 只读案例）</a>\n',
        "")]):
        rows.append(("M11 首屏条删 #sec-qsensor", *run_smoke(), ["F8"]))

    # ---- M12 hash 深链映射删除 ----
    with _TextMut(_IDX, [(', "#sec-qsensor": "runQsensor"', "")]):
        rows.append(("M12 CASE_MAP 删 sec-qsensor", *run_smoke(), ["F7"]))

    # ---- M13 前端抹掉一处取值路径引用 ----
    with _TextMut(_IDX, [("nv.optimal_depth_nm", "nv.__cut__")]):
        rows.append(("M13 前端抹掉取值路径引用", *run_smoke(), ["D3"]))

    # ---- 还原复绿 ----
    rc_z, fz, cz = run_smoke()
    rows.append(("还原（须复绿 exit=0）", rc_z, fz, cz, []))

    print("=" * 78)
    print("QS-M8 量子传感器案例卡门禁 · 突变探针（13 条）")
    print("=" * 78)
    bad = 0
    for name, rc, fails, crashes, keys in rows:
        if name.startswith("基线") or name.startswith("还原"):
            ok = (rc == 0)
            print("  [%s] %s   exit=%s fails=%d" % ("PASS" if ok else "FAIL", name, rc, len(fails)))
            if not ok:
                bad += 1
                for ln in fails:
                    print("        ", ln)
            continue
        expect_ok = (rc != 0) and bool(fails) and (not keys or _hit(fails, keys)) and not crashes
        print("  [%s] %-34s exit=%-3s fails=%-2d %s"
              % ("PASS" if expect_ok else "FAIL", name, rc, len(fails),
                 ("命中 " + ",".join(keys)) if expect_ok else "期望=%s" % keys))
        if not expect_ok:
            bad += 1
            for ln in (fails or crashes)[:4]:
                print("        ", ln)
    print("-" * 78)
    print("探针结论：%s（%d 项不符）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(2)
