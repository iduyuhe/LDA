"""LDA · D-23 多波长耦合器件验收 smoke。

T-8 后（v0.9.38）：**无 GPU 亦可跑 live**。原写法把「无 CUDA」映射成 numpy
后端，而 CouplerAgent 的 numpy 路径未实现（直接 raise）⇒ 整条链路在无 GPU
机器上不可用——实测这是伪门禁：torch 后端内部本就有 cuda→cpu 回退，器件库侧
实测 DC 15.3s / YB 19.1s 已 PASS。现改为：**有 torch 就跑**（设备由 torch
自选 cuda/cpu），torch 缺失才诚实 SKIP。
分层：
  - contract：注册表 + 契约 + 波长扫描逻辑自检（快，CI 无 torch 也可跑）
  - live：真实 CouplerBandAgent 全波段 FDTD（DC/YB 各 7 波长；CPU 实测数分钟，
          配 timeout override；无 torch 诚实 SKIP 并打印说明，不 FAIL）
  - 附加验证：耦合强度波长依赖趋势（κ 随 λ 单调变化，证明不是走过场）
"""
import gc
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# 🔴 线程预算必须在任何数值内核（torch/numba/MKL）初始化之前落下去。
# 2026-09-05 血案：本 smoke 是本仓**最重的 CPU 任务**（torch CPU 全波段 3D FDTD，
# DC 7 波长 ~123s + YB ~164s），20 线程满载时两次触发整机硬掉电
# （Kernel-Power 41 / BugcheckCode=0 + Kernel-Processor-Power 37 固件限速），
# 内存 63GB 充足已排除 OOM ⇒ 满载功耗/散热峰值。压到一半核心（上限 10）。
from lda_solver.threads import apply_thread_budget  # noqa: E402
THREAD_INFO = apply_thread_budget(verbose=True)

from lda_agent.coupler_band_loop import CouplerBandAgent, CouplerBandTarget  # noqa: E402
from lda_l2.device_library import get_default_library  # noqa: E402


def check(cond: bool, msg: str, out: dict, key: str) -> bool:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {msg}")
    out["checks"].append({"key": key, "ok": bool(cond), "msg": msg})
    return bool(cond)


def main() -> int:
    report: dict = {"d05_d23": "coupler band acceptance", "checks": [],
                    "thread_budget": THREAD_INFO}
    ok = True

    # 0) 环境：torch 可用即可跑（GPU 仅加速，T-8 后不再是门禁）
    try:
        import torch
        cuda = torch.cuda.is_available()
        have_torch = True
    except Exception:
        cuda = False
        have_torch = False
    print(f"torch 可用={have_torch}  cuda.is_available()={cuda}"
          f"  ⇒ live 设备={'cuda' if cuda else 'cpu'}")

    # 1) contract 自检（始终）
    lib = get_default_library()
    c_dc = lib.verify_coupler_band(kind="dc", mode="contract", n_points=7)
    c_yb = lib.verify_coupler_band(kind="ybranch", mode="contract", n_points=7)
    ok &= check(c_dc["passed"] and c_dc["checks"]["wavelength_scan"]["n_points"] == 7
                and c_dc["checks"]["wavelength_scan"]["monotonic"],
                f"contract DC：{c_dc['verdict'][:60]}", report, "contract_dc")
    ok &= check(c_yb["passed"] and c_yb["checks"]["wavelength_scan"]["n_points"] == 7,
                f"contract YB：{c_yb['verdict'][:60]}", report, "contract_yb")

    # 2) live 全波段（有 torch 即跑；cuda 仅决定设备，不决定能否跑）
    if not have_torch:
        print("[SKIP] live 全波段 FDTD 需 torch（当前环境无 torch）→ 诚实 SKIP"
              "（注意：**不再要求 CUDA**，CPU 亦可跑，只是慢）")
        report["live"] = {"skipped": True, "reason": "no torch in this environment"}
    else:
        dc = CouplerBandAgent().run(
            CouplerBandTarget(kind="dc", gap_um=0.3, n_points=7,
                              label="DC gap=0.3µm 多波长"))
        report["live_dc"] = dc.to_dict()
        ok &= check(dc.passed, f"DC 全波段验收 PASS：{dc.verdict}", report, "live_dc")
        # ORACLE 真值谱形：κ(λ) 严格单调递增（物理趋势，Lc∝λ）
        ks = [e["kappa_oracle"] for e in dc.per_wl
              if e.get("kappa_oracle") is not None]
        ok &= check(dc.oracle_monotonic and ks[0] != ks[-1],
                    f"ORACLE κ(λ) 单调递增：κ({dc.wl_list[0]}µm)={ks[0]:.5f} → "
                    f"κ({dc.wl_list[-1]}µm)={ks[-1]:.5f}（真值谱形趋势）",
                    report, "oracle_kappa_trend")
        ok &= check(dc.band_mean_kappa_rel is not None
                    and dc.band_mean_kappa_rel <= 0.25,
                    f"FDTD↔ORACLE 平均相对偏差 mean={dc.band_mean_kappa_rel:.4f}"
                    f" ≤ 0.25（方法一致性，非走过场）",
                    report, "dc_mean_rel")

        # DC 完成后主动回收：DC 的 7 个波长点各持有一份 3D 场张量（torch CPU），
        # 若一直握到 YB 跑完，峰值提交内存会叠加。本机 RAM 63GB 但**页面文件仅
        # 4GB**，提交内存峰值是两次硬掉电的诱因之一 ⇒ 显式 gc 降峰（不是修 bug，
        # 是降资源峰值）。
        gc.collect()
        yb = CouplerBandAgent().run(
            CouplerBandTarget(kind="ybranch", sep_um=1.6, n_points=7,
                              label="YB 对称分束器多波长"))
        report["live_yb"] = yb.to_dict()
        ok &= check(yb.passed, f"YB 全波段验收 PASS：{yb.verdict}", report, "live_yb")

    # 3) 报告落盘
    out_path = os.path.join(_HERE, "reports", "coupler_band_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告：{out_path}")
    print("D-23 多波长耦合器件验收 smoke:", "ALL GREEN" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
