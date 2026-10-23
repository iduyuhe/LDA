"""D-218 突变探针（scratch · 不入 CI）：证明 run_ft_compiler_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 `bfs_path` 只回直连 [src,dst]（不做 BFS）        ⇒ X3(I2) 应红
  · M2 `do_swap` 只发 2 个 CX（SWAP 少展开一个）         ⇒ X2(I1) 应红
  · M3 restore 不交换 a/b（回到本轮修掉的那个 bug）       ⇒ H3/X4 应红
  · M4 `compile_circuit` 强制 restore=False              ⇒ X4(I3) 应红
  · M5 `schedule_asap` 全串行（一 op 一层）              ⇒ G3 应红
  · M6 `schedule_asap` 忽略同层冲突（全塞第一层）        ⇒ G1(I4) 应红
  · M7 `resource_report` 的 phys_per_patch 用 d² 而非 2d²−1 ⇒ H1 应红
  · M8 `why_not_anchored` 把 anchorable 改 True          ⇒ Z1 应红
🔴 教训：patch 必须打门禁同一模块对象（`lda_qeda.ft_compiler`）。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_ft_compiler_smoke as S          # noqa: E402
from lda_qeda import ft_compiler as FT     # noqa: E402


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

    _bfs = FT.bfs_path
    _compile = FT.compile_circuit
    _sched = FT.schedule_asap
    _res = FT.resource_report
    _why = FT.why_not_anchored

    # M1 BFS 退化成直连
    FT.bfs_path = lambda adj, a, b: [int(a), int(b)]
    rows.append(("M1 bfs_path 只回直连", *run_smoke()))
    FT.bfs_path = _bfs

    # M2 SWAP 只展开 2 个 CX（真删一个物理门 ⇒ 门计数不守恒）
    def _compile_short_swap(circuit, adjacency, *, restore=True):
        r = dict(_compile(circuit, adjacency, restore=restore))
        ops, out, i = r["ops"], [], 0
        while i < len(ops):
            o = ops[i]
            is_triple = (o["kind"] == "CX" and i + 2 < len(ops)
                         and ops[i + 1]["kind"] == "CX" and ops[i + 2]["kind"] == "CX"
                         and ops[i]["phys"] == ops[i + 2]["phys"]
                         and ops[i + 1]["phys"] == tuple(reversed(ops[i]["phys"])))
            if is_triple:
                out.extend(ops[i:i + 2])      # 少发第 3 个 CX
                i += 3
            else:
                out.append(o)
                i += 1
        r["ops"] = out
        r["n_ops_out"] = len(out)
        r["layers"] = _sched(out)
        r["depth"] = len(r["layers"])
        return r

    FT.compile_circuit = _compile_short_swap
    rows.append(("M2 SWAP 少展开一个 CX（I1 破）", *run_smoke()))
    FT.compile_circuit = _compile

    # M3 restore 方向错（不交换 a/b）
    def _compile_bad_restore(circuit, adjacency, *, restore=True):
        r = _compile(circuit, adjacency, restore=False)
        r = dict(r)
        r["restored"] = True          # 谎报已恢复，但 mapping_final 实际未复原
        return r

    FT.compile_circuit = _compile_bad_restore
    rows.append(("M3 restore 谎报（未真复原）", *run_smoke()))
    FT.compile_circuit = _compile

    # M4 强制不 restore
    def _compile_no_restore(circuit, adjacency, *, restore=True):
        return _compile(circuit, adjacency, restore=False)

    FT.compile_circuit = _compile_no_restore
    rows.append(("M4 强制 restore=False", *run_smoke()))
    FT.compile_circuit = _compile

    # M5 全串行调度
    FT.schedule_asap = lambda ops: [[o] for o in ops]
    rows.append(("M5 调度全串行（一 op 一层）", *run_smoke()))
    FT.schedule_asap = _sched

    # M6 忽略同层冲突
    FT.schedule_asap = lambda ops: [list(ops)]
    rows.append(("M6 调度忽略冲突（全塞一层）", *run_smoke()))
    FT.schedule_asap = _sched

    # M7 资源口径错（d² 而非 2d²−1）
    def _res_bad(result, *, d=3):
        r = _res(result, d=d)
        r = dict(r)
        r["phys_per_patch"] = d * d
        r["n_physical"] = r["n_logical"] * d * d
        return r

    FT.resource_report = _res_bad
    rows.append(("M7 资源 phys_per_patch 用 d²", *run_smoke()))
    FT.resource_report = _res

    # M8 抹掉负结果
    def _why_true():
        w = dict(_why())
        w["anchorable"] = True
        return w

    FT.why_not_anchored = _why_true
    rows.append(("M8 anchorable 改 True", *run_smoke()))
    FT.why_not_anchored = _why

    print("=" * 78)
    bad = 0
    for name, rc, nfail in rows:
        good = (rc == 0 and nfail == 0) if name.startswith("baseline") else (rc != 0 and nfail > 0)
        if not good:
            bad += 1
        print("%-6s %-44s rc=%-3d FAIL=%d" % ("[OK]" if good else "[BAD]", name, rc, nfail))
    print("=" * 78)
    print("突变探针：%d 条，%d 条未按预期变红" % (len(rows) - 1, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
