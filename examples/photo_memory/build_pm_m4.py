# -*- coding: utf-8 -*-
"""PM-M4 货架脚本：光子存储**外设与系统**（读出链 / 写驱动 / 系统误码预算 / 2.5D 装配）·
自包含可复跑。

产出（落 `examples/photo_memory/`）：
  lda_pm_m4_report.json     案例卡数据源（只读消费 · 不含重算路径）
  lda_pm_m4_2p5d.gds        2.5D 装配真 GDSII（PIC 阵列 die + EIC 通道 die + interposer）

🔴 复跑纪律：本脚本是**唯一**的产物生成器；CI 不跑它（examples 不随包分发）⇒
   「入库快照 == 仓库当前状态」由 `lda/run_pm_m4_smoke.py` 的 G1 常驻判据守
   （比对快照各块键集与报告 JSON 的键集）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if os.path.join(_ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "lda"))

from lda_l2 import pm_m4 as M4   # noqa: E402

OUT = _HERE
GDS_NAME = "lda_pm_m4_2p5d.gds"
REPORT_NAME = "lda_pm_m4_report.json"
_TOP_KEYS = ("milestone", "material", "upstream", "readout", "rf_tradeoff",
             "write_driver", "system_budget", "assembly_2p5d", "disclosure")


def main() -> int:
    full = M4.m4_report("GST")
    asm = M4.system_2p5d("GST", n_cells=8, n_buses=1)
    gds = asm["gds_bytes"]
    p_gds = os.path.join(OUT, GDS_NAME)
    with open(p_gds, "wb") as fh:
        fh.write(gds)

    # 🔴 硬断言：报告里声明的字节数必须 == 落盘字节数（防「生成器落后写入器」静默失真）
    assert int(full["assembly_2p5d"]["gds_bytes_len"]) == len(gds), \
        "报告 bytes_len(%d) ≠ 落盘 GDS(%d)" % (int(full["assembly_2p5d"]["gds_bytes_len"]), len(gds))

    report = {
        "generated_by": "examples/photo_memory/build_pm_m4.py",
        "gds_artifact": {"path": GDS_NAME, "bytes": len(gds),
                         "sha256": hashlib.sha256(gds).hexdigest()},
    }
    report.update({k: full[k] for k in _TOP_KEYS})

    p_rep = os.path.join(OUT, REPORT_NAME)
    with open(p_rep, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    # 🔴 落盘前断言：产物不得含未替换的模板占位（血案：生成器给 README 顶行时漏 %. 格式化）
    with open(p_rep, encoding="utf-8") as fh:
        _txt = fh.read()
    assert "%s" not in _txt and "__" + "HEADER" not in _txt, "报告含未替换占位符"

    sb = full["system_budget"]
    print("[PM-M4] 读出: r_f=%.4g Ω f_read=%.4g Hz worst_SNR=%.4g ber=%.3g"
          % (full["readout"]["r_f_ohm"], full["readout"]["f_read_hz"],
             full["readout"]["worst_snr"], full["readout"]["worst_ber"]))
    print("[PM-M4] 系统: ε=%s bottleneck=%s BER=%.4g max_hold=%s"
          % ({k: round(v, 6) for k, v in sb["eps"].items()}, sb["bottleneck"],
             sb["ber_total"], sb["max_t_hold_human"]))
    print("[PM-M4] 2.5D: ch=%d pic_pitch=%.4f µm bottleneck=%s GDS=%d B DRC=%s LVS=%s"
          % (asm["n_channels"], asm["pic_pitch_um"], asm["density_bottleneck"],
             len(gds), asm["drc"]["all_pass"], asm["lvs"]["verdict"]))
    print("[PM-M4] artifacts -> %s" % OUT)
    ok = (asm["drc"]["all_pass"] and asm["lvs"]["verdict"] == "ACCEPT"
          and all(bool(v) for v in full["disclosure"].values() if isinstance(v, bool)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
