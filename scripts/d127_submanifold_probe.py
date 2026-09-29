"""D-127 突变探针（scratch · 不入 CI）：证明 run_submanifold_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**），逐条造假后重跑门禁，
确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 `reachable_dim` 恒返回 2N（实测秩抹成 O-only 饱和值）⇒ B2/C1/D1/D2/F5 应红
  · M2 `o_only_layers` 返回砖墙（**抹掉陷阱见证**）⇒ B3/B4/F5/G2 应红
  · M3 `brick_wall_layers` 返回 O-only（设计退化为块对角）⇒ B2/C1/D1/E3 应红
  · M4 `even_pairs` 返回 odd_pairs（E 抹成 O）⇒ B2/D1/E3 应红
  · M5 `saturation_bound` 恒返回 N²（上界抹成常数）⇒ B2 应红
  · M6 `layer_is_matching` 恒 True（匹配护栏空转）⇒ A2/E1/E4 应红
  · M7 `param_count` 漏掉相移屏 N ⇒ A4/B5 应红
  · M8 `path_matchings` 只回最大匹配（搜索空间缩小）⇒ A3/C1/C3 应红
  · M9 `design_shallow` 的 exhaustive 分支谎报最优 = 2N（最优性检验空转）⇒ C1 应红
  · M10 `universality_frontier` 谎报 d_star = N−1 ⇒ D1/D2/D4 应红
  · M11 披露删 `search_is_bounded`（诚实边界失守）⇒ A5/F2 应红
  · M12 `brick_wall_gate_count` 闭式写错 ⇒ A4 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.SM / S.TM / S.RM）；
   若门禁按名导入（`from x import f`），patch 模块属性会**打空 ⇒ 假绿**。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_submanifold_smoke as S      # noqa: E402

SM = S.SM
TM = S.TM
RM = S.RM


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                     # 突变致病态 ⇒ 崩溃也算红（exit≠0）
        rc = 99
        buf.write(f"[FAIL] 门禁异常：{type(e).__name__}: {e}")
    return rc, buf.getvalue().count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _rd = SM.reachable_dim
    _ool = SM.o_only_layers
    _bwl = SM.brick_wall_layers
    _ep = SM.even_pairs
    _sb = SM.saturation_bound
    _lim = SM.layer_is_matching
    _pc = SM.param_count
    _pm = SM.path_matchings
    _ds = SM.design_shallow
    _uf = SM.universality_frontier
    _disc = SM.SUBMANIFOLD_DISCLOSURE
    _bwg = SM.brick_wall_gate_count

    # M1 实测秩抹成 O-only 饱和值（2N 常数）
    SM.reachable_dim = lambda n_modes, layers, **kw: 2 * int(n_modes)
    rows.append(("M1 实测秩恒 2N（参数计数式谎报）", *run_smoke()))
    SM.reachable_dim = _rd

    # M2 抹掉陷阱见证
    SM.o_only_layers = lambda n_modes, depth: SM.brick_wall_layers(n_modes, depth)
    rows.append(("M2 O-only 抹成砖墙（陷阱消失）", *run_smoke()))
    SM.o_only_layers = _ool

    # M3 设计退化为块对角
    SM.brick_wall_layers = lambda n_modes, depth: tuple(
        [SM.odd_pairs(n_modes)] * int(depth))
    rows.append(("M3 砖墙退化为 O-only", *run_smoke()))
    SM.brick_wall_layers = _bwl

    # M4 E 抹成 O
    SM.even_pairs = lambda n_modes: SM.odd_pairs(n_modes)
    rows.append(("M4 交错匹配 E 抹成 O", *run_smoke()))
    SM.even_pairs = _ep

    # M5 上界抹成常数 N²
    SM.saturation_bound = lambda n_modes, layers: int(n_modes) ** 2
    rows.append(("M5 上界抹成常数 N²", *run_smoke()))
    SM.saturation_bound = _sb

    # M6 匹配护栏空转
    SM.layer_is_matching = lambda n_modes, layer: True
    rows.append(("M6 匹配护栏恒 True（空转）", *run_smoke()))
    SM.layer_is_matching = _lim

    # M7 参数口径漏掉相移屏
    SM.param_count = lambda n_modes, layers: 2 * SM.n_gates(layers)
    rows.append(("M7 参数漏掉相移屏 N", *run_smoke()))
    SM.param_count = _pc

    # M8 搜索空间缩小（只剩最大匹配）
    SM.path_matchings = lambda n_modes: (SM.odd_pairs(n_modes),)
    rows.append(("M8 搜索空间只剩最大匹配", *run_smoke()))
    SM.path_matchings = _pm

    # M9 exhaustive 分支谎报最优 = 2N
    def _ds_liar(n_modes, depth, *, method="brick_wall", **kw):
        r = _ds(n_modes, depth, method=method, **kw)
        if method == "exhaustive":
            r["best_dim"] = 2 * int(n_modes)
            r["beats_brick_wall"] = False
        return r

    SM.design_shallow = _ds_liar
    rows.append(("M9 穷举最优性谎报（空转）", *run_smoke()))
    SM.design_shallow = _ds

    # M10 前沿谎报 N−1
    def _uf_liar(n_modes, **kw):
        r = dict(_uf(n_modes, **kw))
        r["d_star"] = int(n_modes) - 1
        r["frontier_equals_N"] = False
        return r

    SM.universality_frontier = _uf_liar
    rows.append(("M10 通用前沿谎报 N−1", *run_smoke()))
    SM.universality_frontier = _uf

    # M11 披露失守
    SM.SUBMANIFOLD_DISCLOSURE = {k: v for k, v in _disc.items() if k != "search_is_bounded"}
    rows.append(("M11 披露删 search_is_bounded", *run_smoke()))
    SM.SUBMANIFOLD_DISCLOSURE = _disc

    # M12 门数闭式写错
    SM.brick_wall_gate_count = lambda n_modes, depth: int(depth)
    rows.append(("M12 门数闭式写错", *run_smoke()))
    SM.brick_wall_gate_count = _bwg

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：可编程子流形门禁（D-127）")
    print("=" * 74)
    for name, rc, nf in rows:
        print(f"  {name:34s} exit={rc}  [FAIL]×{nf}")

    n_probe = len(rows) - 2
    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 1 + n_probe))
          and rows[-1][1] == 0 and rows[-1][2] == 0)
    print()
    print(f"探针结论：{'PASS —— %d 条突变各必红，还原复绿' % n_probe if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
