# -*- coding: utf-8 -*-
"""K 征程 · K3 跨档复用常量表 **常驻门禁**（闭环缺口 G-K-5）。

判据分节（**判据数实跑现数**）：
  A 表存在与 schema：文件存在 · 顶层字段齐备 · schema 精确 · 计数自洽 · by_kind 求和自洽
  B 受跟踪生成物三件套：**子进程重跑生成器 ≡ 磁盘台账（逐字节）** · 生成器幂等 · LF only
  C 事实性（**独立重算，不复用表**）：站点三元组集 ≡ 现算独立扫描 · 跨档条数下限棘轮 ·
    stage 映射 ≡ 现算 · cross_stage 标志 ≡ 现算 · **const 值 ≡ 现算** · **签名 ≡ 现算**
  D 消费侧一致性（真漂移实证）：`qnet_transducer.cooperativity()` ≡ `qs_m3c.cooperativity_from_g`
    · `qs_m5` 复用常量 ≡ `qs_m0` 源常量
  E 反向探针（**先证能变红**）：篡改 const 值 / 删除站点 / 篡改签名 / 翻 cross_stage 标志
  F 红线：生成器零手写（走 `deterministic` 唯一口径 · 零时钟/随机）· 本门禁 ∈ `CORE_SMOKES`

🔴 `main()` 返回「真值」而非恒 0。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3）。
🔴 本门禁**只读**产品代码 + 读台账；不改任何产品面。
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # lda/
_ROOT = os.path.dirname(_HERE)                              # 仓库根
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3）

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_LEDGER = os.path.join(_HERE, "reports", "cross_stage_constants.json")
_GEN = os.path.join(_ROOT, "scripts", "k3_cross_stage.py")
_PY = sys.executable
_SCHEMA = "lda_cross_stage_constants_v1"
_CROSS_MIN = 20          # 🔵 下限棘轮：当前 20，只许升不许降

# 门禁侧**独立**档位映射（不复用生成器的 STAGE，避免同源自证）
_STAGE = {
    "qs_m0": "QS-M0", "qs_m1": "QS-M1", "qs_m2": "QS-M2", "qs_m3": "QS-M3",
    "qs_m3b": "QS-M3b", "qs_m3c": "QS-M3c", "qs_m4": "QS-M4",
    "qs_m5": "QS-M5", "qs_m6": "QS-M6", "qs_m7": "QS-M7", "qs_m9": "QS-M9",
    "qs_j4_integration": "J4", "qs_j4_microcell": "J4",
    "qs_j4_multiparam": "J4", "qs_j4_packaging": "J4", "qs_j4_system": "J4",
    "qnet_channel": "J5", "qnet_distribution": "J5", "qnet_source": "J5",
    "qnet_repeater": "J5", "qnet_transducer": "J5", "qnet_classical": "J5",
    "qnet_system": "J5",
    "qec_noise": "J1", "fault_tolerant_gates": "J1",
    "logical_error_rate": "J1", "decoder": "J1",
    "qubit_dynamics": "J2", "cross_resonance": "J2",
    "pulse_library": "J2", "gates": "J2",
    "cryo_electronics": "J3", "control_closed_loop": "J3",
    "rb_benchmark": "J3", "readout_demod": "J3", "j2_readout_mux": "J3",
    "j2_to_j1_calibration": "J2→J1",
    "sc_array": "SC", "sc_control": "SC", "sc_coupler": "SC",
    "loqc_states": "LOQC", "photon_sources": "LOQC", "detectors": "LOQC",
    "physical_error_model": "BUDGET", "qpu_error_budget": "BUDGET",
}
_PKG_REL = {"lda_l2": ("lda_l2", "lda/l2"), "lda_qeda": ("lda_qeda", "lda/qeda")}


def load():
    with open(_LEDGER, encoding="utf-8", newline="") as f:
        raw = f.read()
    return json.loads(raw), raw


def _subprocess_render():
    p = subprocess.run([_PY, _GEN], cwd=_ROOT, capture_output=True, text=True,
                       errors="replace")
    return p.returncode, p.stdout, p.stderr


# ── 独立重扫（只取三元组集合 + 类别，不复用生成器代码路径） ─────────────
def _independent_sites():
    out = set()
    for pkg in ("lda_l2", "lda_qeda"):
        d = os.path.join(_HERE, pkg)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py"):
                continue
            me = fn[:-3]
            if me not in _STAGE:
                continue
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                parts = node.module.split(".")
                if parts[0] not in ("lda_l2", "lda_qeda"):
                    continue
                sp = parts[0]
                if len(parts) == 1:
                    for a in node.names:
                        if a.name in _STAGE and not (sp == pkg and a.name == me):
                            out.add((me, a.name, "<module>"))
                    continue
                sm = parts[1]
                if sm not in _STAGE or (sp == pkg and sm == me):
                    continue
                for a in node.names:
                    out.add((me, sm, a.name))
    return out


def _validate(led):
    """把表结构与事实性校验收成一个可注入对象的纯函数（供反向探针复用）。"""
    r = {}
    sites = led.get("sites") or []
    sm = led.get("summary") or {}
    r["C1 站点三元组集 ≡ 独立扫描"] = (
        {(s["consumer_module"], s["source_module"], s["symbol"]) for s in sites}
        == _independent_sites())
    r["C2 跨档条数 ≥ 下限棘轮"] = (
        sum(1 for s in sites if s.get("cross_stage")) >= _CROSS_MIN
        and sm.get("sites_cross_stage") == sum(1 for s in sites if s.get("cross_stage")))
    r["C3 stage 映射 ≡ 现算"] = all(
        s.get("stage_from") == _STAGE.get(s["source_module"])
        and s.get("stage_to") == _STAGE.get(s["consumer_module"]) for s in sites)
    r["C4 cross_stage 标志 ≡ 现算"] = all(
        s.get("cross_stage") == (s.get("stage_from") != s.get("stage_to"))
        for s in sites)
    # C5 const 值现算
    ok5, d5 = True, []
    for s in sites:
        if s.get("kind") != "const":
            continue
        mod = __import__("%s.%s" % (s["source_pkg"], s["source_module"]),
                         fromlist=[s["symbol"]])
        obj = getattr(mod, s["symbol"])
        if isinstance(obj, (int, float, str)) and not isinstance(obj, bool):
            if led_val_of(s) != obj:
                ok5 = False
                d5.append("%s.%s" % (s["source_module"], s["symbol"]))
        else:
            if s.get("value_repr") != repr(obj)[:200]:
                ok5 = False
                d5.append("%s.%s(repr)" % (s["source_module"], s["symbol"]))
    r["C5 const 值 ≡ 现算（逐位）"] = ok5
    # C6 签名现算
    ok6, d6 = True, []
    for s in sites:
        if s.get("kind") not in ("function", "class"):
            continue
        mod = __import__("%s.%s" % (s["source_pkg"], s["source_module"]),
                         fromlist=[s["symbol"]])
        sig = str(inspect.signature(getattr(mod, s["symbol"])))
        if s.get("signature") != sig:
            ok6 = False
            d6.append("%s.%s" % (s["source_module"], s["symbol"]))
    r["C6 接口签名 ≡ 现算"] = ok6
    return r, d5, d6


def led_val_of(s):
    if "value" in s:
        return s["value"]
    return None


def main():
    print("=" * 78)
    print("K3 跨档复用常量表门禁（量子赛道 J1–J5 / QS-M* · 缺口 G-K-5）")
    print("=" * 78)

    # ── A 表存在与 schema ───────────────────────────────────────────
    exists = os.path.exists(_LEDGER)
    check("A1 台账文件存在", exists, "path=%s" % os.path.relpath(_LEDGER, _ROOT))
    led, raw = load()
    need = ("schema", "generated_by", "roadmap", "subject", "method",
            "stage_map", "summary", "sites")
    check("A2 顶层字段齐备", all(k in led for k in need),
          "缺=%s" % [k for k in need if k not in led])
    check("A3 schema 精确", led.get("schema") == _SCHEMA,
          "got=%r" % led.get("schema"))
    sm = led.get("summary") or {}
    sites = led.get("sites") or []
    check("A4 计数自洽（total ≡ len(sites) ≡ cross+same）",
          sm.get("sites_total") == len(sites)
          and sm.get("sites_cross_stage", 0) + sm.get("sites_same_stage", 0) == len(sites),
          "summary=%s len=%d" % (sm, len(sites)))
    bk = sm.get("by_kind") or {}
    check("A5 by_kind 求和 ≡ sites_total", sum(bk.values()) == len(sites),
          "by_kind=%s sum=%d" % (bk, sum(bk.values())))

    # ── B 受跟踪生成物三件套 ────────────────────────────────────────
    rc, out, err = _subprocess_render()
    disk = raw
    check("B1 子进程重跑生成器 ≡ 磁盘台账（逐字节）",
          rc == 0 and out == disk,
          "rc=%d · len(gen)=%d vs len(ledger)=%d %s"
          % (rc, len(out), len(disk), (err or "")[:80]))
    rc2, out2, _e2 = _subprocess_render()
    check("B2 生成器幂等（两次重跑逐字节相同）",
          rc2 == 0 and out2 == out, "rc=%d same=%s" % (rc2, out2 == out))
    check("B3 台账 LF only（无 CR）", b"\r" not in open(_LEDGER, "rb").read(),
          "CR count=%d" % open(_LEDGER, "rb").read().count(b"\r"))

    # ── C 事实性（独立重算） ───────────────────────────────────────
    r, d5, d6 = _validate(led)
    for k in sorted(r):
        det = ""
        if k.startswith("C5") and not r[k]:
            det = "不一致=%s" % d5[:8]
        elif k.startswith("C6") and not r[k]:
            det = "不一致=%s" % d6[:8]
        check(k, r[k], det)

    # ── D 消费侧一致性（真漂移实证） ────────────────────────────────
    from lda_l2 import qnet_transducer as TR  # noqa: E402
    from lda_l2 import qs_m3c as M3C  # noqa: E402
    from lda_l2 import qs_m0 as M0  # noqa: E402
    from lda_l2 import qs_m5 as M5  # noqa: E402

    d = M3C.design_defaults()
    del d  # 仅为确认源档默认档可用（消费侧走自己的默认参数）
    c_consumer = TR.cooperativity()
    c_source = M3C.cooperativity_from_g(TR.DEFAULT_G_RAD_S,
                                        TR.DEFAULT_KAPPA_MW_RAD_S,
                                        TR.DEFAULT_GAMMA_MECH_RAD_S)
    check("D1 qnet_transducer.cooperativity() ≡ qs_m3c.cooperativity_from_g（跨档实证）",
          abs(c_consumer - c_source) / abs(c_source) < 1e-15,
          "consumer=%.17g source=%.17g rel=%.2e"
          % (c_consumer, c_source,
             abs(c_consumer - c_source) / abs(c_source)))
    zfs_ok = (M5.zero_field_splitting_hz() == M0.D_ZFS_HZ)
    gyro_ok = (M5.nv_gyromagnetic_hz_per_t() == M0.GAMMA_E_HZ_T)
    check("D2 qs_m5 复用常量 ≡ qs_m0 源常量（零场劈裂 ∧ 旋磁比）",
          zfs_ok and gyro_ok,
          "zfs=%s gyro=%s" % (zfs_ok, gyro_ok))

    # ── E 反向探针（先证能变红） ───────────────────────────────────
    def mutated(mut):
        clone = json.loads(json.dumps(led))
        mut(clone)
        rr, _a, _b = _validate(clone)
        return [k for k, v in rr.items() if not v]

    def m_const(x):
        for s in x["sites"]:
            if s.get("kind") == "const" and "value" in s:
                s["value"] = float(s["value"]) * 1.0000001
                return

    def m_drop(x):
        x["sites"] = x["sites"][1:]

    def m_sig(x):
        for s in x["sites"]:
            if s.get("kind") == "function":
                s["signature"] = s["signature"].replace("float", "double", 1)
                return

    def m_flag(x):
        for s in x["sites"]:
            if s.get("cross_stage"):
                s["cross_stage"] = False
                return

    red1 = mutated(m_const)
    check("E1 反向探针：篡改 const 值 ⇒ C5 必红", "C5 const 值 ≡ 现算（逐位）" in red1,
          "红项=%s" % red1)
    red2 = mutated(m_drop)
    check("E2 反向探针：删除站点 ⇒ C1 站点集必红",
          "C1 站点三元组集 ≡ 独立扫描" in red2, "红项=%s" % red2)
    red3 = mutated(m_sig)
    check("E3 反向探针：篡改签名 ⇒ C6 必红",
          "C6 接口签名 ≡ 现算" in red3, "红项=%s" % red3)
    red4 = mutated(m_flag)
    check("E4 反向探针：翻 cross_stage 标志 ⇒ C4 必红",
          "C4 cross_stage 标志 ≡ 现算" in red4, "红项=%s" % red4)

    # ── F 红线 ────────────────────────────────────────────────────
    with open(_GEN, encoding="utf-8") as f:
        gsrc = f.read()
    wall = ("datetime.now", "time.strftime", "time.time", "random.",
            "uuid4", "json.dump(", "mkdtemp")
    hits = [t for t in wall if t in gsrc]
    check("F1 生成器零手写证据（走 deterministic · 零时钟/随机）",
          "deterministic" in gsrc and "det.write_text" in gsrc and not hits,
          "hits=%s det=%s" % (hits, "det.write_text" in gsrc))
    try:
        spec = importlib.util.spec_from_file_location(
            "_ci", os.path.join(_HERE, "run_ci_regression.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        in_core = "run_k3_cross_stage_smoke.py" in getattr(m, "CORE_SMOKES", []) or \
                  "run_k3_cross_stage_smoke.py" in list(getattr(m, "CORE_SMOKES", []))
    except Exception as ex:  # noqa: BLE001
        in_core = False
        print("    （无法读取 CORE_SMOKES：%s）" % ex)
    check("F2 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core,
          "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("K3 跨档复用常量表门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
