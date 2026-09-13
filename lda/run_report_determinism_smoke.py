#!/usr/bin/env python
"""报告确定性护栏（v0.9.75 · 「根治提交噪声」的正向 + 反向测试）。

## 背景

`reports*/` 下的报告是**受版本控制的验证证据**。v0.9.74 及之前，每次跑 harness /
smoke 都会把它们重写成带 wall-clock 时间戳、耗时、浮点末位抖动的新内容 ⇒
`git status` 常红，提交时要么误带噪声、要么每次手动 checkout 掩盖。

v0.9.75 定为铁律：**受跟踪报告必须是输入的确定性函数** —— 相同输入 ⇒ 字节一致。

## 本 smoke 测什么（正反两面）

1. `deterministic.canon` 剔除 volatile 键（顶层 / 嵌套 dict / list 内）。
2. `canon` 浮点归一：末位抖动被吸收（1.0000000000000002 ≡ 1.0）。
3. `dumps` 幂等且稳定。
4. `report.format_json` 两次（其间 wall-clock 前进 + 浮点抖动）⇒ **字节一致**。
5. 输出**不含** volatile 键（generated_at / elapsed_s / …）。
6. `report.format_markdown` 两次 ⇒ 字节一致，且无「生成时间」/ ISO 时间戳。
7. **反向（可证伪）**：改一个真实 golden 值 ⇒ 输出字节**必须变化**
   —— 否则就是把真变化一起「归一化」掉了，比噪声更危险。
8. 源码 lint：**全部报告写入器**（core 中 21 个入口 + 报告格式化模块）不得再出现
   wall-clock 标记（生成时间 / 裁决时间 / 闭环耗时 / datetime.now / time.strftime），
   且必须走 `deterministic` 唯一口径。
9. `write_text` / `write_json` 落盘恒为 LF（跨平台不翻 CRLF）。
10. **线程环境确定性**：`threads.thread_env_overrides()` 必须显式关闭动态线程调整
   （`OMP_DYNAMIC`/`MKL_DYNAMIC`=FALSE）。否则 Intel OpenMP（torch 在 Windows 上
   随包的 libiomp5md.dll）会**按系统负载**伸缩线程数 ⇒ 归约顺序漂移 ⇒ float32
   结果抖动（D-23 实测被 κ=(βs−βa)/2 放大到 ~1e-5）。反向测试见注释。

纯标准库、秒级、零外部依赖 ⇒ 必进 core。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "lda_harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_harness import deterministic as det      # noqa: E402
from lda_harness import report as rep             # noqa: E402

_FAILS = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _FAILS.append(name)


class _R:
    """最小结果桩（模拟 harness 的 AnchorResult 属性面）。"""

    def __init__(self, bid, golden, candidate, passed=True, cls="strict_independent", ind=True):
        self.bid = bid
        self.metric = "metric_" + bid
        self.oracle = "analytical"
        self.source = "analytical"
        self.golden = golden
        self.candidate = candidate
        self.tol = 1e-3
        self.passed = passed
        self.note = None
        self.independent = ind
        self.candidate_class = cls


def _mk(jitter=0.0):
    """构造一组结果；jitter 只在浮点末位制造抖动。"""
    return [
        _R("B1", 0.9967000000000000 + jitter, 0.9967000000000000 + jitter * 0.5),
        _R("B2", 1.3571000000000000 + jitter, 1.3571000000000000 + jitter * 0.3),
        _R("B3", 2.8342000000000000 + jitter, 2.8342000000000000 + jitter * 0.7,
           passed=False, cls="self_consistent_stub", ind=False),
    ]


_META = {"candidate": "IndependentCandidateRouter(demo)", "self_consistent": True}


def main() -> int:
    print("=== 报告确定性护栏 ===")

    # 1) canon 剔除 volatile 键（顶层 / 嵌套 / list 内）
    src = {"a": 1, "generated_at": "2026-09-13T00:00:00", "elapsed_s": 3.14,
           "nested": {"timestamp": "x", "keep": 2},
           "rows": [{"bid": "B1", "elapsed_s": 9.9, "v": 1.0}]}
    c = det.canon(src)
    check("① canon 剔除顶层 volatile 键",
          "generated_at" not in c and "elapsed_s" not in c)
    check("① canon 剔除嵌套 dict 的 volatile 键",
          "timestamp" not in c["nested"] and c["nested"]["keep"] == 2)
    check("① canon 剔除 list 内 dict 的 volatile 键",
          "elapsed_s" not in c["rows"][0] and c["rows"][0]["bid"] == "B1")

    # 2) 浮点归一：末位抖动被吸收
    check("② canon 浮点归一吸收末位抖动",
          det.canon({"v": 1.0000000000000002}) == det.canon({"v": 1.0}),
          "1.0000000000000002 ≡ 1.0")
    check("② canon 不吞真实差异",
          det.canon({"v": 1.001}) != det.canon({"v": 1.0}))

    # 3) dumps 幂等
    check("③ dumps 幂等（同对象两次一致）",
          det.dumps(src) == det.dumps(src))

    # 4) format_json 双跑字节一致（wall-clock 前进 + 浮点抖动）
    js1 = rep.format_json(_mk(0.0), _META)
    js2 = rep.format_json(_mk(1e-15), _META)
    check("④ format_json 双跑字节一致（含浮点抖动）", js1 == js2,
          f"len={len(js1)}")

    # 5) 输出不含 volatile 键
    leaked = [k for k in det.VOLATILE_KEYS if f'"{k}"' in js1]
    check("⑤ format_json 输出无 volatile 键", not leaked, f"leaked={leaked}")

    # 6) format_markdown 双跑字节一致 + 无时间戳
    md1 = rep.format_markdown(_mk(0.0), _META)
    md2 = rep.format_markdown(_mk(1e-15), _META)
    check("⑥ format_markdown 双跑字节一致", md1 == md2, f"len={len(md1)}")
    iso = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", md1)
    check("⑥ format_markdown 无「生成时间」/ISO 时间戳",
          iso is None and "生成时间" not in md1, f"iso={iso.group(0) if iso else None}")

    # 7) 反向（可证伪）：改真值必须产生 diff，否则「归一化」成了「掩盖」
    js_changed = rep.format_json(_mk_golden_changed(), _META)
    check("⑦ 反向：改真实 golden ⇒ 输出必变（不可过度归一）",
          js_changed != js1)
    md_changed = rep.format_markdown(_mk_golden_changed(), _META)
    check("⑦ 反向：markdown 同样可证伪", md_changed != md1)

    # 8) 源码 lint：写入器不得再出现 wall-clock 标记。
    #    例外：`crosscheck_report.py` 的 `time.strftime` 只用于**被 .gitignore 的**
    #    历史归档**文件名**（`crosscheck_history/crosscheck_<ts>.json`），不进受跟踪
    #    报告内容，故不列入其禁用表（逐个文件显式声明，避免"一刀切"误伤）。
    _WALL = ("生成时间", "裁决时间", "闭环耗时", "datetime.now",
             "datetime.datetime.now", "time.strftime")
    _WALL_NO_STRFTIME = tuple(t for t in _WALL if t != "time.strftime")
    # v0.9.75 扩展：**core 中所有「写受跟踪报告」的入口**都必须走 deterministic
    # 唯一口径。前 10 项为报告格式化/聚合模块；其余为各 smoke / demo / bank 入口
    # ——它们原先自带 `json.dump(...)`（= 每次重写带 elapsed/浮点抖动 ⇒ 提交噪声）。
    # 🔴 在此显式登记 = 「没登记 = 门禁缺口」：新增报告写入者必须补进本表。
    lint_spec = {
        "lda_harness/report.py": _WALL,
        "lda_harness/benchmark_report.py": _WALL,
        "lda_harness/crosscheck_report.py": _WALL_NO_STRFTIME,
        "lda_agent/design_loop.py": _WALL,
        "lda_l1/protocol.py": _WALL,
        "run_harness.py": _WALL,
        "run_agent_loop.py": _WALL,
        "run_redteam_adjudication_smoke.py": _WALL,
        "run_redteam_anchor_fuzz_smoke.py": _WALL,
        "run_coupler_band_smoke.py": _WALL,
        # ——— v0.9.75 扩展：core 其余报告写入者 ———
        "run_agent_loop_smoke.py": _WALL,
        "run_benchmark_crosscheck_report.py": _WALL,
        "run_chip_scale_demo.py": _WALL,
        "run_dc_transmission_smoke.py": _WALL,
        "run_device_fdtd_smoke.py": _WALL,
        "run_drc_fix_smoke.py": _WALL,
        "run_drc_pdk_smoke.py": _WALL,
        "run_drc_smoke.py": _WALL,
        "run_ir_d05_smoke.py": _WALL,
        "run_layout_sim_smoke.py": _WALL,
        "run_pipeline_multidevice_smoke.py": _WALL,
        "run_quantum_design_smoke.py": _WALL,
        "run_quantum_devices_smoke.py": _WALL,
        "run_readout_chain_smoke.py": _WALL,
        "run_ring_double_verify_smoke.py": _WALL,
        "run_ring_fdtd_smoke.py": _WALL,
        "run_spectrum_loop_smoke.py": _WALL,
        "run_wdm_depth_smoke.py": _WALL,
        "run_wdm_system_smoke.py": _WALL,
        "run_golden_product_smoke.py": _WALL,
        "lda_harness/run_empirical_bank.py": _WALL,
    }
    lint_bad = []
    no_det = []
    for rel, forbidden in lint_spec.items():
        p = os.path.normpath(os.path.join(HERE, rel))
        try:
            s = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            lint_bad.append((rel, "MISSING"))
            continue
        for tok in forbidden:
            if tok in s:
                lint_bad.append((rel, tok))
        # 只有**实际落盘**的文件才必须走 deterministic（纯格式化器不必）。
        writes = bool(re.search(r"(json\.dump\(|open\([^)]*[\"']w[\"']|\.write\()", s))
        if writes and "deterministic" not in s:
            no_det.append(rel)
    check("⑧ 写入器源码无 wall-clock 标记", not lint_bad, f"violations={lint_bad}")
    check("⑧b 全部「落盘」报告写入者走 deterministic 唯一口径",
          not no_det, f"not-using-deterministic={no_det}")

    # 9) 落盘 EOL 恒为 LF
    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "sub", "x.json")
        tp = os.path.join(td, "x.md")
        det.write_json(jp, src)
        det.write_text(tp, "line1\nline2")
        bj = open(jp, "rb").read()
        bt = open(tp, "rb").read()
        check("⑨ write_json/write_text 落盘恒 LF（无 CR）",
              b"\r" not in bj and b"\r" not in bt,
              f"cr_in_json={b'\r' in bj} cr_in_md={b'\r' in bt}")
        check("⑨ 目录自动创建 + 末尾恰一换行",
              os.path.exists(jp) and bt.endswith(b"\n") and not bt.endswith(b"\n\n"))

    # 10) 线程环境确定性：动态线程调整必须显式关闭。
    #     🔴 反向可证伪：删掉 threads._ENV_FLAGS 里的 OMP_DYNAMIC ⇒ 本判据必 FAIL。
    try:
        from lda_solver.threads import thread_env_overrides, _ENV_KEYS
        ov = thread_env_overrides()
        ok_thr = (ov.get("OMP_DYNAMIC") == "FALSE"
                  and ov.get("MKL_DYNAMIC") == "FALSE"
                  and all(k in ov for k in _ENV_KEYS)
                  and "LDA_FDTD_THREADS" in ov)
        check("⑩ 线程环境关闭动态调整（OMP_DYNAMIC/MKL_DYNAMIC=FALSE）",
              ok_thr, f"OMP_DYNAMIC={ov.get('OMP_DYNAMIC')} "
                      f"MKL_DYNAMIC={ov.get('MKL_DYNAMIC')} n={ov.get('LDA_FDTD_THREADS')}")
    except Exception as e:                                    # noqa: BLE001
        check("⑩ 线程环境关闭动态调整（OMP_DYNAMIC/MKL_DYNAMIC=FALSE）",
              False, f"探测失败：{e}")

    print(f"\n=== 结果：{'全部通过' if not _FAILS else 'FAIL %d 项' % len(_FAILS)} ===")
    if _FAILS:
        for f in _FAILS:
            print("  FAIL:", f)
        return 1
    print("  ✅ 报告确定性 10 项判据全绿（相同输入 ⇒ 字节一致；真变更仍可证伪）")
    return 0


def _mk_golden_changed():
    """真值改变（非末位抖动）——用于反向可证伪测试。"""
    r = _mk(0.0)
    r[0].golden = 0.9000   # 从 0.9967 → 0.9000，显著变化
    r[0].candidate = 0.9000
    return r


if __name__ == "__main__":
    raise SystemExit(main())
