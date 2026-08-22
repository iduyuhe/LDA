# -*- coding: utf-8 -*-
"""D-67 分束网络×WDM smoke：WDM 解复用 × 每信道 DC 分束树联合设计。"""
import sys
sys.path.insert(0, ".")

from lda_agent.wdm_splitter import design_wdm_splitter  # noqa: E402

PASS = []


def run(name, expect, **kw):
    try:
        r = design_wdm_splitter(**kw)
        ok = bool(r.get("acceptance", {}).get("passed")) == expect
    except Exception as e:  # noqa: BLE001
        ok, r = False, {"error": str(e)}
    PASS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} | {name}"
          f"{' | ' + str(r.get('verdict', r.get('error')))[:80] if not ok else ''}")


# 正例 1：3 信道 WDM × 每信道 2-路分束
run("3 信道 WDM × DC 分束", True, channels_nm=[1550.0, 1553.0, 1556.0])

# 正例 2：4 信道 + 标定库驱动（DC gap 由 κ_c(gap,λ) 网格选择）
run("4 信道 + 标定库驱动", True, channels_nm=[1550.0, 1552.0, 1554.0, 1556.0],
    calibrated=True)

# 负例 1：单信道（WDM 至少 2 信道应 FAIL）
run("单信道（应 FAIL）", False, channels_nm=[1550.0])

# 负例 2：5 信道超 FSR 混叠（WDM 应 FAIL）
run("5 信道超 FSR（应 FAIL）", False, channels_nm=[1550.0, 1553.0, 1556.0,
                                                   1559.0, 1562.0])

# 负例 3：weights 长度不匹配（应 FAIL）
run("weights 长度不匹配（应 FAIL）", False,
    channels_nm=[1550.0, 1553.0, 1556.0], weights=[0.5, 0.5])

print(f"\n{'=' * 40}\nD-67 smoke: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
