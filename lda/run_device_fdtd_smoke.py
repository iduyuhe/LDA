"""D-32 器件库真实 FDTD 验收 smoke。

验证 D-12 DeviceLibrary 的 RingResonator 已挂上 D-31 环形 FDTD 双验证
（解析契约 + 真实 FDTD drop 谱对拍）。

分层（与 D-12/D-23 同纪律）：
  contract —— 注册表 + RING-fsr 契约 + fdtd2d_ring 可导入 + 解析 FSR 量级（快，CI 用）
  live     —— 真实 FDTD（R=6 复用 D-27 已验证参数，21 点，GPU ~7min）；
              **CPU 亦可跑但慢**：实测 ~74.6s/波长 ⇒ 21 点 ≈ 26min，故无 CUDA
              时默认跳过（`LDA_FORCE_RING_FDTD=1` 可强制启用），SKIP 诚实标注、
              不算失败。LDA_SKIP_LIVE=1 可本地强制跳过
              （本机 CUDA_VISIBLE_DEVICES="" 对 torch 无效）。
              ⚠️ 与 device_library 的 5/5 live 快验收区分：后者走 RING-fsr
              解析契约层，T-8 后 DC/YB/WG/Bragg/Ring **全部零 GPU 现场可跑**。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def check(cond, msg, report, key):
    ok = bool(cond)
    report["checks"][key] = {"ok": ok, "msg": msg}
    print(("OK  " if ok else "FAIL") + " " + msg)
    return ok


def main() -> int:
    report = {"checks": {}, "live": None}
    ok = True

    from lda_l2.device_library import get_default_library

    lib = get_default_library()

    # 1) Ring 已注册 + RING-fsr 契约
    dev = lib.get("RingResonator")
    ok &= check(dev.name == "RingResonator" and dev.verify_spec is not None
                and dev.verify_spec.spec_id == "RING-fsr",
                "RingResonator 已注册且带 RING-fsr 解析契约（D-12）",
                report, "registered")

    # 2) verify_ring_fdtd contract 自检（快）
    c = lib.verify_ring_fdtd(mode="contract", R_um=6.0)
    ok &= check(c["passed"] and c["checks"]["registered"]
                and c["checks"]["ring_fdtd_import"]
                and c["checks"]["analytic_fsr"]["physical"],
                f"verify_ring_fdtd contract 自检：R=6 解析 FSR="
                f"{c['checks']['analytic_fsr']['fsr_analytic_nm']}nm"
                f"（物理量级）+ fdtd2d_ring 可导入",
                report, "contract")

    # 3) 解析契约独立可跑（RING-fsr live，快）
    a = lib.verify_one("RingResonator", mode="live")
    ok &= check(bool(a.passed) and a.err is not None,
                f"RING-fsr 解析契约 live：candidate FSR="
                f"{a.candidate if a.candidate is not None else '?'} vs oracle "
                f"{a.oracle_value if a.oracle_value is not None else '?'} "
                f"(err={a.err:.2e} ≤ tol {a.tol})", report, "analytic_live")

    # 4) live FDTD 双验证（21 点深度谱：CPU 能跑但 ≈26min ⇒ 默认跳过；
    #    LDA_FORCE_RING_FDTD=1 强制启用；LDA_SKIP_LIVE=1 优先强制跳过）
    if os.environ.get("LDA_SKIP_LIVE") == "1":
        run_live, reason = False, "LDA_SKIP_LIVE=1 强制跳过"
    elif os.environ.get("LDA_FORCE_RING_FDTD", "") not in ("", "0", "false"):
        run_live, reason = True, "LDA_FORCE_RING_FDTD=1 强制启用"
    else:
        try:
            import torch
            run_live = torch.cuda.is_available()
        except Exception:
            run_live = False
        reason = ("默认跳过（CPU 可跑但 21 点 ≈26min，属耗时取舍非能力限制；"
                  "LDA_FORCE_RING_FDTD=1 可强制启用）")
    if run_live:
        r = lib.verify_ring_fdtd(mode="live", R_um=6.0, n_points=21,
                                 tol_rel=0.30)
        report["live"] = r
        ok &= check(r["passed"],
                    f"Ring 器件库 live FDTD 双验证 PASS：解析契约 "
                    f"{r['analytic_contract']['passed']} + FDTD "
                    f"{r['fdtd']['accepted']}（FSR(FDTD)="
                    f"{r['fdtd']['fsr_fdtd_nm']}nm vs 解析 "
                    f"{r['fdtd']['fsr_analytic_nm']}nm，"
                    f"rel={r['fdtd']['fsr_rel_dev']:.2%} ≤ "
                    f"{r['fdtd']['tol_rel']:.0%}）",
                    report, "live_fdtd")
        ok &= check(len(r["fdtd"]["peaks_um"]) >= 3,
                    f"FDTD drop 谱 {len(r['fdtd']['peaks_um'])} 个谐振峰",
                    report, "live_peaks")
    else:
        print(f"SKIP live FDTD 双验证（{reason}）")
        report["live"] = {"skipped": True, "reason": reason}

    # 5) Waveguide 真实 FDTD 双验证（D-32 延伸，纯 numpy CPU 可跑）
    wg = lib.verify_waveguide_fdtd(mode="contract", width_um=0.5)
    ok &= check(wg["passed"] and wg["checks"]["fdtd2d_waveguide_import"]
                and wg["checks"]["analytic_slab_neff"]["physical"],
                f"verify_waveguide_fdtd contract 自检：width=0.5µm slab neff="
                f"{wg['checks']['analytic_slab_neff']['slab_neff']}nm（物理区间）"
                f" + fdtd2d_waveguide 可导入", report, "wg_contract")
    wa = lib.verify_waveguide_fdtd(mode="live", width_um=0.5)
    ok &= check(wa["passed"],
                f"Waveguide 真实 FDTD 双验证 PASS：slab契约物理="
                f"{wa['analytic_contract']['physical']} + FDTD neff="
                f"{wa['fdtd']['neff_fdtd']} ↔ slab "
                f"{wa['fdtd']['neff_oracle']}（rel="
                f"{wa['fdtd']['rel_err']:.2%} ≤ {wa['fdtd']['tol_rel']:.0%}）",
                report, "wg_live")

    # 6) Bragg 真实 FDTD 双验证（D-32 延伸，纯 numpy CPU 可跑）
    bg = lib.verify_bragg_fdtd(mode="contract")
    ok &= check(bg["passed"] and bg["checks"]["fdtd3d_import"]
                and bg["checks"]["tmm_import"],
                "verify_bragg_fdtd contract 自检：fdtd3d + tmm 可导入",
                report, "bg_contract")
    bgl = lib.verify_bragg_fdtd(mode="live")
    ok &= check(bgl["passed"],
                f"Bragg 真实 FDTD 双验证 PASS：TMM契约物理="
                f"{bgl['analytic_contract']['physical']} + FDTD R_min="
                f"{bgl['fdtd']['R_min_fdtd']} ↔ TMM "
                f"{bgl['fdtd']['R_min_tmm']}（abs="
                f"{bgl['fdtd']['abs_err']:.2e} ≤ {bgl['fdtd']['tol_abs']:.0%}）",
                report, "bg_live")

    # 7) 预计算 WG/Bragg 真实 FDTD 双验证产物（供 WebUI ⑬ 面板秒回加载，仿 D-28）
    precomp = {
        "waveguide": wa,
        "bragg": bgl,
        "generated_by": "run_device_fdtd_smoke.py",
        "note": "Waveguide/Bragg 真实 FDTD 双验证预计算（纯 numpy ~30s）；WebUI "
                "⑬ 面板加载此 JSON 秒回展示，避免 HTTP 阻塞。解析契约层由 "
                "WebUI 现场跑 contract 模式（秒级）。",
    }
    with open(os.path.join(_HERE, "reports", "device_fdtd_wg_bragg.json"),
              "w", encoding="utf-8") as f:
        json.dump(precomp, f, ensure_ascii=False, indent=2)
    print("OK  预计算 reports/device_fdtd_wg_bragg.json 已写入（WG/Bragg 真实 FDTD）")

    report["all_green"] = ok
    os.makedirs(os.path.join(_HERE, "reports"), exist_ok=True)
    with open(os.path.join(_HERE, "reports", "device_fdtd_smoke.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("ALL GREEN" if ok else "HAS FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
