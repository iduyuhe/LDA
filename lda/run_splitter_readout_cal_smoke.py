# -*- coding: utf-8 -*-
"""D-66 标定库×分束网络 smoke：gap 由 κ_c(gap,λ) 网格驱动 DC 设计。"""
import sys
sys.path.insert(0, ".")

from lda_agent.splitter_readout import design_splitter_readout  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_splitter_readout([4.8, 5.0, 5.2], **kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} | {name}"
          f"{' | ' + str(r.get('verdict', r.get('error')))[:80] if not ok else ''}")


# 正例 1：3 qubit 均匀 + 标定库驱动（gap 由 κ_c(gap,λ) 网格选择）
run("3 qubit 标定库驱动（gap 由标定库选择）", True, calibrated=True)

# 正例 2：非均匀权重 + 标定库驱动
run("非均匀权重 [0.5,0.25,0.25] + 标定库驱动", True,
    weights=[0.5, 0.25, 0.25], calibrated=True)

# 负例 1：标定文件缺失（grid={} → 每级 DC 设计失败）
run("标定库缺失（grid={} 应 FAIL）", False, calibrated=True, grid={})

# 负例 2：nbar0 过低（均匀分配后 SNR 不足应 FAIL，非标定快速路径）
run("nbar0=0.3（SNR 不足应 FAIL）", False, nbar0=0.3)

# 负例 3：极端权重（最弱路 SNR 不足应 FAIL）
run("极端权重 [0.9,0.05,0.05]+nbar0=3（应 FAIL）", False,
    weights=[0.9, 0.05, 0.05], nbar0=3.0)

print(f"\n{'=' * 40}\nD-66 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
