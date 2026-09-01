"""产品级基准对照库 smoke（v0.8.32 · 实证锚产品级扩展 + B 生态播种）。

落点：A/B 阶段内可做的「产品级验证」，不碰 C 闸门。
动作：LDA 引擎规格驱动再设计 + 数值复现 → 对标已公开验证 golden 死标量。
出口：全部 PASS 才退出 0；任一 FAIL/SKIP 记失败（CI 计数守护）。

红线：LLM 不进判决；比对为死标量 rel。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.golden_product_benchmarks import (  # noqa: E402
    evaluate_all, to_markdown, save_library_json, HONEST_BANNER,
)


def main() -> int:
    # 1) 落盘库（可增量扩展：社区/文献贡献追加条目）
    lib = save_library_json()
    # 2) 全量评估
    results = evaluate_all()
    n_total = len(results)
    n_pass = sum(1 for r in results if r.get("passed_all"))

    print("=" * 68)
    print("LDA 产品级基准对照库（实证锚产品级扩展 + B 生态播种素材）")
    print(HONEST_BANNER)
    print("=" * 68)
    for r in results:
        if r.get("error"):
            print(f"\n[ERROR] {r['product_id']}: {r['error']}")
            continue
        status = "PASS" if r.get("passed_all") else "FAIL"
        print(f"\n[{status}] {r['product_id']} · {r['device_type']}")
        print(f"  来源: {r['source_kind']} | {r['source_ref']}")
        print(f"  引擎: {r['engine']} | 模型: {r['model']}")
        for row in r["rows"]:
            tag = "OK" if row["passed"] else "X"
            print(f"   - {row['name']}: replica={row['replica']}{row['unit']} "
                  f"vs golden={row['golden']}{row['unit']} (tol±{row['tol']}) -> {tag}")

    # ------------------------------------------------------------------
    # 2.5) 🔴 D-67 反向测试：**验证护栏本身会响**（没被验证过的护栏不算护栏）
    #   v0.9.10（D-66）把 engine_ybranch_split 的默认 `value` 从「含分光的
    #   分支插损」改成「过量损耗」，导致 5 条整芯片链路每个分束器少算
    #   3.0103 dB，却因插损 metric 方向为 `le`（越小越 PASS）**全部仍显示
    #   PASS → 假绿**；而本 smoke 只校验 PASS 条数，CI core 84/84 全绿也
    #   没抓到。这里注入那个回归，确认新加的两道护栏真的会拦下它。
    # ------------------------------------------------------------------
    from lda_design.loss_engines import ENGINE_FUNCS as _EF  # noqa: E402
    from lda_l2 import golden_product_benchmarks as _gpb  # noqa: E402
    _orig = _EF["engine_ybranch_split"]

    def _bad_ybranch(geom):
        """复现 D-66 回归：value 只给过量损耗，丢掉 3.0103 dB 分光。"""
        th = float(geom.get("theta_deg", 10.0))
        c1 = float(geom.get("excess_coef", 0.004))
        return {"metric": "excess_loss_dB", "value": round(c1 * th * th, 4),
                "model": "BAD-D66"}

    _EF["engine_ybranch_split"] = _bad_ybranch
    try:
        _hit_floor = 0
        _chips = [c for c in _gpb.DEFAULT_CHIP_BENCHMARKS
                  if getattr(c, "geom", {}).get("n_ybranch", 0) > 0]
        for _c in _chips:
            try:
                _c.evaluate()
            except AssertionError:
                _hit_floor += 1
        _yb = [b for b in _gpb.DEFAULT_BENCHMARKS
               if getattr(b, "product_id", None) == "GP-YBRANCH"][0]
        _sem = bool(_yb.evaluate().get("error"))
    finally:
        _EF["engine_ybranch_split"] = _orig

    if _hit_floor != len(_chips):
        print(f"FAIL: 能量守恒下界护栏失效 —— 注入漏算分光后仅拦下 "
              f"{_hit_floor}/{len(_chips)} 条含分束器链路")
        return 1
    if not _sem:
        print("FAIL: metric 语义错配护栏失效 —— 拿过量损耗比总插损 golden "
              "未被拦下（会静默 PASS = 假绿）")
        return 1
    print(f"\n[D-67 反向测试] 注入「漏算 3.0103dB 分光」回归 → 两道护栏均命中："
          f"能量守恒下界拦下 {_hit_floor}/{len(_chips)} 条链路 + "
          f"metric 语义错配拦下（护栏真实有效，非纸上谈兵）")

    # 3) 生成对照报告（B 生态播种硬核素材）
    report = to_markdown(results)
    out_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "docs", "golden_product_benchmarks_report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已写: {out_md}")
    print(f"库已落盘: {lib}")
    print(f"\n汇总: {n_pass}/{n_total} 产品级对标 PASS")

    if n_pass < n_total:
        print("FAIL: 存在未达标对标")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
