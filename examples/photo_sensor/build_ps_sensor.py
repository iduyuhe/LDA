"""PS-M7 结果源生成器 · 光子传感器征程 客户自助设计（吃狗粮 v7）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
把「光子传感器征程」此前各里程碑**已机器自检通过**的能力，固化成一份**可提交的
结果源**，供 WebUI 只读案例卡 `/api/sensor_demo`（`lda/lda_webui/sensor_case.py`）
读取 —— 镜像 `examples/photo_memory/`（PM 征程）与 `examples/lda_q*_report.json`
（量子征程）的既有范式。

本脚本**一次性**跑通三段**已在生产 CI 常驻**的链路，落盘：

  ① **主权流片链签核**（`ps_m0.design_sensor_v0`）：RingResonator → layout → routes
     → `export_chip_gds` ⇒ 真 GDSII 字节 + DRC 报告 + LVS 报告。产出
     `lda_ps_sensor_ring.gds`（真二进制 GDS）与 `lda_ps_sensor_report.json` 的
     `signoff` 段（gds_bytes / n_elements / drc_all_pass / n_drc_checked /
     lvs_present / blocked_nets）。
  ② **灵敏度物理链**（`ps_m3.real_waveguide_sensitivity`）：SOI 平板波导 HF 闭式
     `dneff/dn_clad = (n_clad/n_eff)·Γ_clad`（已 FD 验证，残差 ~1e-10）⇒ 各架构的
     `n_eff / Γ_clad / n_g / S_nm_per_riu`，写入 `architectures[]` 作为**参考快照**。
  ③ **规模与集成**（`ps_m6.selfcheck_ps_m6`）：阵列热串扰 / TIA 读出噪声底 / 封装
     对准耦合 / 集成预算，写入 `integration` 段。

🔴 **本报告是「参考快照」，不是判决**：`sensor_case.py` 顶部常量与 `architectures[]`
必须逐位一致，且由门禁 `run_sensor_panel_smoke` 的 B 节**对平台模块现算值**做跨源
一致性校验（漂移即红）。面板**不**在请求期跑本脚本（零重算纪律）。

═══ 用法 ═══
    PYTHONPATH=lda python examples/photo_sensor/build_ps_sensor.py
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_REPO, os.path.join(_REPO, "lda")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GDS_NAME = "lda_ps_sensor_ring.gds"
REPORT_NAME = "lda_ps_sensor_report.json"


def _architectures() -> list:
    """架构参考快照（n_eff / Γ_clad / n_g / S 取自 PS-M3 平板 HF 闭式）。

    `ring_ridge_v0` 的 S 取自 PS-M0 脊波导 2D-FD 灵敏度（同物理量、同量级，互为印证）。
    """
    from lda_l2 import ps_m3

    water = ps_m3.real_waveguide_sensitivity()
    oxide = ps_m3.real_waveguide_sensitivity(ps_m3.SCENARIOS["soi_slab_oxide"]["geo"])
    from lda_l2 import ps_m0  # noqa: F401

    return [
        {
            "id": "slab_hf_water",
            "label": "微环 · SOI 平板波导（水包层 · 真实传感窗）",
            "source": "PS-M3 · HF 闭式（FD 验证）",
            "n_eff": water["n_eff"],
            "gamma_clad": water["gamma_clad"],
            "n_g": water["n_g"],
            "S_bulk_nm_per_riu": water["S_nm_per_riu"],
        },
        {
            "id": "slab_hf_oxide",
            "label": "微环 · SOI 平板波导（氧化包层 · 上限对照）",
            "source": "PS-M3 · HF 闭式（FD 验证）",
            "n_eff": oxide["n_eff"],
            "gamma_clad": oxide["gamma_clad"],
            "n_g": oxide["n_g"],
            "S_bulk_nm_per_riu": oxide["S_nm_per_riu"],
        },
    ]


def build(out_dir: str = _HERE) -> dict:
    from lda_l2 import ps_m3, ps_m6

    os.makedirs(out_dir, exist_ok=True)

    # ① 主权流片链签核（真 GDS/DRC/LVS）
    from lda_l2 import ps_m0

    gds_path = os.path.join(out_dir, GDS_NAME)
    m0 = ps_m0.design_sensor_v0(out_dir=out_dir)
    chain = m0["layout_chain"]
    # design_sensor_v0 落盘的文件名固定为 ps_m0_ring_sensor.gds ⇒ 归一化为本征程命名
    produced = os.path.join(out_dir, "ps_m0_ring_sensor.gds")
    if os.path.isfile(produced):
        gds_bytes = open(produced, "rb").read()
        with open(gds_path, "wb") as f:
            f.write(gds_bytes)
        os.remove(produced)

    signoff = {
        "artifact": GDS_NAME,
        "gds_bytes": int(chain.get("gds_bytes") or 0),
        "n_elements": int(chain.get("n_elements") or 0),
        "drc_all_pass": bool(chain.get("drc_all_pass")),
        "n_drc_checked": int(chain.get("n_drc_checked") or 0),
        "lvs_present": bool(chain.get("lvs_present")),
        "blocked_nets": len(chain.get("blocked_nets") or []),
        "wg_width_um": float(m0["params"]["w_um"]),
        "ring_R_um": float(m0["params"]["R_um"]),
        "ring_Q": float(m0["params"]["Q"]),
    }

    # ② 灵敏度参考快照
    arches = _architectures()

    # ③ 集成（阵列 / 读出 / 对准 / 预算）
    r6 = ps_m6.selfcheck_ps_m6()
    integration = {
        "n_ch": int(r6["array"]["n_ch"]),
        "crosstalk_db": r6["array"]["crosstalk_db"],
        "pitch_min_um": r6["array"]["pitch_min_um"],
        "channel_density_per_mm": r6["array"]["channel_density_per_mm"],
        "v_n_uV": r6["readout"]["v_n_uV"],
        "f_3dB_Hz": r6["readout"]["f_3dB_Hz"],
        "align_eta": r6["alignment"]["eta"],
        "align_il_db": r6["alignment"]["insertion_loss_db"],
        "channel_split_loss_db": r6["integration"]["channel_split_loss_db"],
        "total_optical_loss_db": r6["integration"]["total_optical_loss_db"],
        "frame_rate_hz": float(r6["integration"]["frame_rate_hz"]),
        "area_mm2": float(r6["integration"]["area_mm2"]),
        "LOD_readout_riu": float(r6["integration"]["LOD_readout_riu"]),
    }

    report = {
        "schema": "lda.photo_sensor.case.v1",
        "generated_by": "examples/photo_sensor/build_ps_sensor.py",
        "source_modules": ["lda_l2.ps_m0", "lda_l2.ps_m3", "lda_l2.ps_m6"],
        "sense": "参考快照（非判决）· 面板请求期零重算 · 跨源一致性由 run_sensor_panel_smoke B 节守护",
        "architectures": arches,
        "integration": integration,
        "signoff": signoff,
    }
    # 🔴 newline="\n" 显式钉 LF（与 examples/photo_memory/*.json 同族惯例；Windows 文本模式
    #   默认 '\n'→'\r\n' 会产出 CRLF ⇒ 与同族不一致、且 Linux CI 检出后 git diff 噪声）
    with open(os.path.join(out_dir, REPORT_NAME), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


if __name__ == "__main__":
    rep = build()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    print(f"\n[OK] wrote {REPORT_NAME} + {GDS_NAME} -> {_HERE}")
