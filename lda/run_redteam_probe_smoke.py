"""红队自动攻击端点护栏（T0 LLM 红队闭环 · 周期化 / 趋势落盘）。

死标量（红队自身可证伪，同构「生态/智能体出题，锚判卷」）：
  hit_rate     = 被锚确认缺陷 / 出题数   （目标 0：健康管线不应漏过）
  attack_ratio = 管线拒收 / 出题数       （红队是否真在对抗，目标 ≥0.3）
  coverage     = 意图攻击锚种类         （目标 ≥2：多角打法）

降级（核心零依赖优雅降级铁律）：无 LDA_REDTEAM_* → status=skipped，不联网，
趋势仍落盘可读（供 /api/redteam_trend 拉取）。有 key 时（手动跑）额外断言 ok 路径死标量。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_webui.redteam_probe import read_trend, run_redteam_probe

_PASS = 0
_FAIL = 0


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  [PASS] {name}  ({detail})")
    else:
        _FAIL += 1
        print(f"  [FAIL] {name}  ({detail})")


def main():
    print("红队自动攻击端点护栏（周期化 / 趋势落盘）")
    print("=" * 56)

    req = {"n_channels": 4, "p_tx_dbm": 0.0, "channel_spacing_ghz": 50.0,
           "filter_bw_ghz": 25.0, "wg_length_cm": 1.0}

    rt_enabled = bool(os.environ.get("LDA_REDTEAM_BASE", os.environ.get("LDA_LLM_BASE"))
                     and os.environ.get("LDA_REDTEAM_KEY"))

    # 无论有无 key：端点良构 + 趋势落盘 + 可读 都必须成立
    # 注意 read_trend(limit=N) 的 count 字段 = min(总条数, N)（返回条数），
    # 故取总数须传足够大的 limit。
    before = read_trend(limit=10 ** 9).get("count", 0)
    rec = run_redteam_probe(req, n=4)
    after = read_trend(limit=10 ** 9).get("count", 0)

    check("端点返回 status 字段（skipped/ok/error）",
          rec.get("status") in ("skipped", "ok", "error"),
          f"status={rec.get('status')}")
    ds = rec.get("dead_scalars", {})
    check("死标量良构：含 hit_rate/attack_ratio/coverage/confirmed_defects/n_proposed",
          all(k in ds for k in ("hit_rate", "attack_ratio", "coverage",
                                "confirmed_defects", "n_proposed")),
          f"ds={ds}")
    check("趋势落盘：调用后记录数增加", after >= before + 1,
          f"before={before} after={after}")
    trend = read_trend(limit=5).get("trend", [])
    check("趋势可读：返回升序趋势序列", isinstance(trend, list) and len(trend) >= 1,
          f"trend_len={len(trend)}")

    if not rt_enabled:
        check("无 key → status=skipped（优雅降级，不联网）",
              rec.get("status") == "skipped", f"status={rec.get('status')}")
        check("无 key → dead_scalars 全零（安全默认）",
              ds.get("hit_rate") == 0.0 and ds.get("attack_ratio") == 0.0
              and ds.get("n_proposed") == 0, f"ds={ds}")
        print("\n提示：配置 LDA_REDTEAM_BASE/KEY 后重跑，本护栏将断言 ok 路径死标量。")
    else:
        check("有 key → status=ok", rec.get("status") == "ok",
              f"status={rec.get('status')}")
        check("有 key → 出题数≥1（GLM 真出题）",
              ds.get("n_proposed", 0) >= 1, f"n_proposed={ds.get('n_proposed')}")
        check("有 key → 确认缺陷=0（健康管线无漏洞）",
              ds.get("confirmed_defects") == 0,
              f"confirmed={ds.get('confirmed_defects')}")
        check("有 key → 红队真在对抗（attack_ratio≥0.3）",
              ds.get("attack_ratio", 0) >= 0.3,
              f"attack_ratio={ds.get('attack_ratio')}")
        check("有 key → 覆盖≥2种锚（多角打法）",
              ds.get("coverage", 0) >= 2, f"coverage={ds.get('coverage')}")

    print("=" * 56)
    print(f"红队探针 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
