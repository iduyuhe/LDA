"""LDA · D-39 量子域 Coupler / Resonator 双验证 smoke。

扩展 D-35 Transmon：给量子域另外两个器件挂上与光子栈同构的
「解析闭式契约 ↔ 严格数值物理自洽」双验证（纯 numpy，秒级，零 GPU）：
  ① Resonator（超导谐振器 λ/4）：闭式 f=1/(4l√(L′C′)) ↔ 离散 TL 严格本征值
  ② Coupler（双 transmon 电容耦合）：解析 J（n01 闭式）↔ 441 维电荷 basis 严格对角化
铁律：LLM 不进判决路径，PASS 由死标量比对决定。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_l2.device_library import DeviceLibrary  # noqa: E402


def main() -> int:
    lib = DeviceLibrary()
    report: dict = {"d39": "quantum resonator+coupler double-verify", "checks": []}
    ok = True

    print("=" * 70)
    print("D-39 量子域 Coupler / Resonator 双验证")
    print("=" * 70)

    # ① Resonator
    rc = lib.verify_resonator(mode="contract")
    rl = lib.verify_resonator(mode="live")
    ok &= bool(rc["passed"])
    ok &= bool(rl["passed"])
    num = rl["numerical"]
    print(f"[{'OK  ' if rl['passed'] else 'FAIL'}] Resonator: "
          f"f0_closed={rl['analytic_contract']['f0_closed_ghz']}GHz ↔ "
          f"f0_num={num['f0_num_ghz']}GHz rel={num['rel_err']:.2%} "
          f"(N={num['N_used']})")
    report["checks"].append({"key": "resonator", "ok": bool(rl["passed"]),
                             "detail": num})

    # ② Coupler
    cc = lib.verify_coupler(mode="contract")
    cl = lib.verify_coupler(mode="live")
    ok &= bool(cc["passed"])
    ok &= bool(cl["passed"])
    cn = cl["numerical"]
    print(f"[{'OK  ' if cl['passed'] else 'FAIL'}] Coupler: "
          f"J_analytic={cl['analytic_contract']['J_analytic_ghz']}GHz ↔ "
          f"J_num={cn['J_num_ghz']}GHz rel={cn['rel_err']:.2%} "
          f"(f01={cn['f01_1_ghz']}/{cn['f01_2_ghz']}GHz)")
    report["checks"].append({"key": "coupler", "ok": bool(cl["passed"]),
                             "detail": cn})

    # ③ 变体扫描（非共振 qubit / 不同 Cc —— 证明非单点 hack）
    vars_ok = True
    for (ej1, ec1, ej2, ec2, ccc) in [(25.0, 0.22, 18.0, 0.30, 0.01),
                                      (30.0, 0.18, 30.0, 0.18, 0.05)]:
        v = lib.verify_coupler(mode="live", E_J1=ej1, E_C1=ec1,
                               E_J2=ej2, E_C2=ec2, Cc=ccc)
        vars_ok &= bool(v["passed"])
        print(f"[{'OK  ' if v['passed'] else 'FAIL'}] Coupler 变体 "
              f"EJ1={ej1}/EC1={ec1} EJ2={ej2}/EC2={ec2} Cc={ccc}: "
              f"J={v['numerical']['J_num_ghz']}GHz")
    ok &= vars_ok
    report["checks"].append({"key": "coupler_variants", "ok": vars_ok})

    print("=" * 70)
    print("D-39 全绿:", ok)
    with open(os.path.join(_HERE, "reports", "quantum_devices_d39.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
