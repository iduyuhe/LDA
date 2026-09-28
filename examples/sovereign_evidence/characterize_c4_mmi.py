"""C4 MMI（主权证据版图）真实光学表征 · 走法一合规。

目标：对主权证据集 C4 的 MMI 1×2（真实几何 W_mmi=6.0 / L_mmi=20.0 / w=0.5 /
out_gap=0.5 µm，2D slab SOI n_core=2.80 / n_clad=1.44 @ λ=1.55µm）做**真实数值
表征**，产出：

  - FDTD（2D-TEz 全场时域，lda_solver/fdtd2d_mmi）插入损耗 IL 与两臂不平衡；
  - EME（2D-EIM，lda_solver/mmi_eme）独立路线对账 → 两法一致性 = 2D 模型稳健度；
  - 收敛轨迹（t_end 多截断点）证明结果不随 t_max 漂移。

诚实边界（项目红线）：本表征是 **2D-TEz 模型数值结果**，不是物理定律锚
（golden）。依 E5 报告（lda_e5_mmi_candidate_probe），MMI 1×2 过量损耗在 2D 层级
对 220nm 高对比 SOI 失真过大、对 L_π 病态敏感，原理上不可判到 0.1dB tol。真锚需
3D 矢量求解器或流片（E5 §六.2）。本脚本只交付"模型级真实数值 + 诚实标注"，
不冒充已锚定 GP-*。

运行：python examples/sovereign_evidence/characterize_c4_mmi.py
产物：同目录 c4_mmi_characterization.json
"""
from __future__ import annotations
import json
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_solver.fdtd2d_mmi import mmi_excess_loss_fdtd
from lda_solver.mmi_eme import mmi_excess_loss

# —— C4 真实几何（与 build_sovereign_evidence.py 中 mmi1 完全一致）——
GEOM = dict(w_um=0.5, W_mmi=6.0, L_mmi=20.0, out_gap=0.5,
            n_core=2.80, n_clad=1.44, wl_um=1.55)


def run(dl: float) -> dict:
    fd = mmi_excess_loss_fdtd(dl=dl, **GEOM)
    em = mmi_excess_loss(dl=dl, **{k: v for k, v in GEOM.items()
                                    if k in ("w_um", "W_mmi", "L_mmi",
                                             "out_gap", "n_core",
                                             "n_clad", "wl_um")})
    # 各臂 IL 与不平衡（来自 FDTD 双输出端口）
    ports = fd["ports"]
    ks = sorted(ports.keys())
    t_a = ports[ks[0]]["T"]
    t_b = ports[ks[1]]["T"]
    total_T = t_a + t_b
    total_il = -10.0 * math.log10(max(total_T, 1e-300))
    excess = total_il - 3.0103        # 过量损耗（扣除理想 3dB 分束）
    return {
        "dl_um": dl,
        "fdtd": {
            "per_arm_IL_db": {f"{k:.1f}um": ports[k]["value"] for k in ks},
            "per_arm_T": {f"{k:.1f}um": ports[k]["T"] for k in ks},
            "total_transmission": total_T,
            "total_IL_db": total_il,
            "excess_loss_db": excess,
            "imbalance_db": fd["spread_db"],
            "t_end_drift_db": fd["t_end_drift_db"],
            "convergence_t_ends": fd["t_ends"],
            "convergence_values_db": [fd["convergence"][str(t)]["value"]
                                      for t in fd["t_ends"]],
            "n_eff_in": fd["n_eff_in"], "nx": fd["nx"], "ny": fd["ny"],
            "nsteps": fd["nsteps"],
        },
        "eme": {
            "value_db": em["value"], "T": em["T"],
            "excess_loss_db": em["value"] - 3.0103,
        },
        "two_method_delta_db": abs(fd["value"] - em["value"]),
    }


def _b16_self_image_length(W_e_um: float, n_eff: float = 2.80,
                            wl_um: float = 1.55) -> float:
    """B16 解析锚：1×2 自映像长度 L = (9/4)·n_eff·W²/λ0（device_library._mmi_multimode_core）。"""
    return 2.25 * n_eff * (W_e_um ** 2) / wl_um


def main() -> None:
    out = {}
    # 主网格 dl=0.05（t_end 漂移已实测 0.000 dB，时间维收敛；2D 数值色散误差
    # 依 fdtd2d_mmi.beat_dispersion_error ~ 17.21·dl² ≈ 0.043 dB，量级可控）
    out["dl_005"] = run(0.05)

    b16 = _b16_self_image_length(GEOM["W_mmi"], GEOM["n_core"], GEOM["wl_um"])
    out["b16_root_cause"] = {
        "W_mmi_um": GEOM["W_mmi"], "n_eff": GEOM["n_core"], "wl_um": GEOM["wl_um"],
        "L_pi_um": GEOM["n_core"] * GEOM["W_mmi"] ** 2 / GEOM["wl_um"],
        "b16_self_image_length_um": b16,
        "c4_as_laid_L_mmi_um": GEOM["L_mmi"],
        "ratio_laid_to_image": GEOM["L_mmi"] / b16,
        "interpretation": (f"C4 版图 L={GEOM['L_mmi']}µm 仅达 B16 理想成像长度 "
                           f"{b16:.1f}µm 的 {GEOM['L_mmi']/b16*100:.0f}%，"
                           f"自映像未形成 → 大部分功率未耦合进两输出臂，"
                           f"过剩损耗 {out['dl_005']['fdtd']['excess_loss_db']:.2f} dB。"
                           f"两臂 50/50 仍极准（不平衡 "
                           f"{out['dl_005']['fdtd']['imbalance_db']:.3f} dB）"
                           f"仅因几何对称，非成像成功。"),
    }
    out["geometry"] = GEOM
    out["model"] = ("2D-TEz slab (n_core=2.80 effective index, n_clad=1.44) "
                    "@ λ=1.55µm — NOT a 3D-vector or taped-out physical anchor")
    out["honest_note"] = (
        "本表征为 2D 模型数值结果，非物理定律锚（golden）。依 E5 报告，MMI 1×2 "
        "过量损耗在 2D 层级对 220nm SOI 失真过大、对 L_π 病态敏感，原理上不可判到 "
        "0.1dB tol。真锚需 3D 矢量求解器或流片（E5 §六.2）。此处仅交付模型级真实 "
        "数值 + 两法（FDTD/EME）一致性 + B16 根因，作为 C4 版图光学行为的可复算证据，"
        "不冒充已锚定可售 GP-MMI-1X2。")
    out["upgrade_path_to_gp"] = {
        "step1": "按 B16 将 L_mmi 设到理想成像长度（W=6 时 ≈146µm），或改用窄 MMI "
                 "（W≈2.8 → L≈32µm，贴近真实 SOI PDK）。",
        "step2": "FDTD/EME 复核过剩损耗与不平衡（2D 模型级，仍可复算）。",
        "step3_HARD_CEILING": "即便长度正确，2D 模型对 220nm SOI 的过量损耗仍不可判到 "
                              "0.1dB tol（E5 实测 EME/FDTD 给出 4.3dB 量级）。真·GP-MMI-1X2 "
                              "锚定需 3D 矢量求解器或流片验证（E5 §六.2），且 device_library "
                              "当前缺 MMI DeviceSpec 注册（仅 DirectionalCoupler/Ring/Bragg）。",
        "do_not": "不得在 2D 数值上挂 'sellable GP-*' 标签——违反项目物理锚红线。",
    }
    path = os.path.join(HERE, "c4_mmi_characterization.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    # 终端摘要
    print("=== C4 MMI 真实几何表征（W=6/L=20/w=0.5/out_gap=0.5 µm）===")
    for tag, r in out.items():
        if not isinstance(r, dict) or "fdtd" not in r:
            continue
        fdd = r["fdtd"]
        print(f"\n[{tag}] dl={r['dl_um']}")
        print(f"  FDTD 总透射 T={fdd['total_transmission']:.4f} "
              f"总IL={fdd['total_IL_db']:.3f} dB  过量损耗={fdd['excess_loss_db']:.3f} dB")
        print(f"  FDTD 两臂不平衡={fdd['imbalance_db']:.3f} dB  "
              f"t_end漂移={fdd['t_end_drift_db']:.3f} dB")
        print(f"  EME  过量损耗={r['eme']['excess_loss_db']:.3f} dB  "
              f"FDTD-EME 差={r['two_method_delta_db']:.3f} dB")
        print(f"  FDTD 网格={fdd['nx']}x{fdd['ny']} 步数={fdd['nsteps']}")
    print(f"\n诚实边界：{out['honest_note']}")
    print(f"产物: {path}")


if __name__ == "__main__":
    main()
