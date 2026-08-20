"""D-32 器件库真实 FDTD 验收 smoke。

验证 D-12 DeviceLibrary 的 RingResonator 已挂上 D-31 环形 FDTD 双验证
（解析契约 + 真实 FDTD drop 谱对拍）。

分层（与 D-12/D-23 同纪律）：
  contract —— 注册表 + RING-fsr 契约 + fdtd2d_ring 可导入 + 解析 FSR 量级（快，CI 用）
  live     —— 真实 FDTD（R=6 复用 D-27 已验证参数，21 点，GPU ~7min）；
              无 GPU 诚实 SKIP 不算失败。LDA_SKIP_LIVE=1 可本地强制跳过
              （本机 CUDA_VISIBLE_DEVICES="" 对 torch 无效）。
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

    # 4) live FDTD 双验证（GPU；无 GPU / LDA_SKIP_LIVE=1 诚实 SKIP）
    if os.environ.get("LDA_SKIP_LIVE") == "1":
        cuda = False
    else:
        try:
            import torch
            cuda = torch.cuda.is_available()
        except Exception:
            cuda = False
    if cuda:
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
        print("SKIP live FDTD 双验证（无 GPU / LDA_SKIP_LIVE=1）")
        report["live"] = {"skipped": True}

    report["all_green"] = ok
    os.makedirs(os.path.join(_HERE, "reports"), exist_ok=True)
    with open(os.path.join(_HERE, "reports", "device_fdtd_smoke.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("ALL GREEN" if ok else "HAS FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
