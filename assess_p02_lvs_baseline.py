"""P0-2 基线抓取：记录 LVS 在各规模 + 各反例下的**完整判决指纹**。

用途：优化后逐字节比对。任一反例的违规集合发生变化 = 假绿/假红，立即停手。
指纹 = verdict + 违规元组排序后的 sha256，不含任何耗时（耗时可变，判决不可变）。
"""
import hashlib
import json
import sys

sys.path.insert(0, r"D:\agent_LDA\lda")

from lda_l2.layers import get_stack           # noqa: E402
from lda_l2.lvs import (run_lvs, run_lvs_multilayer)  # noqa: E402
from lda_harness.lvs_anchor import (build_lvs_case, CASES,
                                    build_multilayer_case, MULTI_CASES)  # noqa: E402
from lda_harness.scale_anchor import build_chain_case  # noqa: E402


def fingerprint(rep):
    """判决指纹：只看判决内容，不看耗时。"""
    def norm(x):
        if isinstance(x, (list, tuple)):
            return [norm(i) for i in x]
        if isinstance(x, dict):
            return {k: norm(v) for k, v in sorted(x.items())}
        return x
    payload = {
        "verdict": rep.get("verdict"),
        "match": rep.get("match"),
        "violations": norm(rep.get("violations") or []),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False,
                   default=str).encode("utf-8")).hexdigest()[:16]


def main():
    out = {}
    stack = get_stack("soi")

    # 1) 单层全案例（含反例）
    for case in CASES:
        link, pl, rt = build_lvs_case(case)
        rep = run_lvs(link, pl, rt)
        out[f"single::{case}"] = (rep.get("verdict"), fingerprint(rep),
                                  len(rep.get("violations") or []))

    # 2) 多层全案例（含反例）
    for case in MULTI_CASES:
        link, pl, rt = build_multilayer_case(case)
        rep = run_lvs_multilayer(link, pl, rt, stack=stack)
        out[f"multi::{case}"] = (rep.get("verdict"), fingerprint(rep),
                                 len(rep.get("violations") or []))

    # 3) 规模正例（大规模短路候选对才是优化目标）
    for n in (32000, 128000):
        link, pl, rt = build_chain_case(n)
        rep = run_lvs_multilayer(link, pl, rt, stack=stack)
        out[f"scale::{n}"] = (rep.get("verdict"), fingerprint(rep),
                              len(rep.get("violations") or []))

    print(f"{'案例':<28} {'判决':<10} {'违规数':>6}  指纹")
    for k, (v, fp, nv) in out.items():
        print(f"{k:<28} {str(v):<10} {nv:>6}  {fp}")
    print(f"\n合计 {len(out)} 个案例")
    with open(r"D:\agent_LDA\_lvs_baseline.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("基线已写入 _lvs_baseline.json")


if __name__ == "__main__":
    main()
