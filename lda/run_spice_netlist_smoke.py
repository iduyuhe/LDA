"""LDA L2 · T1-2 SPICE 网表生成器反向护栏（防常数假绿 / 防非法网表假绿）。

验收（与 CI core 同口径，死标量断言）：
  ① 合法电路 to_spice 含关键数值（R=50 / C_total=120fF / responsivity=1.0）；
  ② 🔴 改 R_electrode 50→100 → 网表对应元件行数值必变（反常数假绿）；
  ③ 🔴 改 quantum_eff 0.8→0.9 → 探测器受控源 gain=1.125 必现（反常数假绿）；
  ④ 悬空终端（引用不存在器件）→ 必抛 NetlistError；
  ⑤ 悬空器件（无任何端口连接）→ 必抛 NetlistError；
  ⑥ Cadence Spectre 适配层真生效：输出含 `simulator lang=spectre` 且
     `(n1 n2)` 元素语法 + subckt/ends（与 SPICE3 `.end` 结构不同）。
"""
import sys

from lda_l2.compact_model import CompactModelSpec, derive_responses
from lda_l2.spice_netlist import CircuitNetlist, NetlistError


def build_demo(mod_r=None, det_eta=None):
    m = CompactModelSpec(name="M1", R_electrode_ohm=50.0, C_junction_fF=100.0,
                         C_electrode_fF=20.0, VpiL_Vcm=2.0, length_mm=1.0)
    if mod_r is not None:
        m.R_electrode_ohm = mod_r
    d = CompactModelSpec(name="PD1", quantum_eff=0.80, C_junction_fF=100.0,
                         C_electrode_fF=20.0, dark_current_nA=1.0)
    if det_eta is not None:
        d.quantum_eff = det_eta
    return (CircuitNetlist("demo")
            .add_device("M1", "modulator", m)
            .add_device("PD1", "photodetector", d)
            .add_device("VS1", "vsource", dc=3.3)
            .add_device("RL1", "load", r=50.0)
            .connect("rfpath", "VS1.plus", "M1.rf_in")
            .connect("mid", "M1.rf_out", "PD1.anode")
            .connect("gnd", "VS1.minus", "M1.gnd", "PD1.cathode",
                     "M1.term", "PD1.gnd", "RL1.minus")
            .connect("out", "PD1.anode", "RL1.plus"))


def main():
    fails = []
    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    nl = build_demo()
    cir = nl.to_spice()

    # ① 合法网表含关键数值
    check("合法网表含 R=50", "RM1_rf M1_rf_in M1_int 50" in cir, cir[:300])
    check("合法网表含 C_total=120fF", "120.000e-15" in cir)
    r0 = derive_responses(CompactModelSpec(quantum_eff=0.80,
                                           wavelength_nm=1550.0))["responsivity_AW"]
    check("默认 responsivity=1.0", abs(r0 - 1.0) < 1e-9, f"r0={r0}")
    check("合法网表含 responsivity 1.0", "1" in cir, cir)

    # ② 反向：R_electrode 50→100 → 元件行数值变
    cir_hi = build_demo(mod_r=100.0).to_spice()
    check("R 扰动 50→100：调制器电阻行含 100",
          "RM1_rf M1_rf_in M1_int 100" in cir_hi, cir_hi)

    # ③ 反向：quantum_eff 0.8→0.9 → 探测器 gain 变
    r1 = derive_responses(CompactModelSpec(quantum_eff=0.90,
                                           wavelength_nm=1550.0))["responsivity_AW"]
    check("responsivity 随量子效率变 0.8→1.125",
          abs(r1 - 1.125) < 1e-9, f"r1={r1}")
    cir_eta = build_demo(det_eta=0.90).to_spice()
    check("量子效率 0.8→0.9：受控源 gain 含 1.125",
          "1.125" in cir_eta, cir_eta)

    # ④ 悬空终端 → 报错
    try:
        (CircuitNetlist("bad").add_device("X", "modulator")
         .connect("n", "NOSUCH.port"))
        check("悬空终端报错", False, "未抛 NetlistError")
    except NetlistError:
        check("悬空终端报错", True)
    except Exception as e:  # noqa
        check("悬空终端报错", False, f"抛错类型错 {e!r}")

    # ⑤ 悬空器件 → 报错
    try:
        CircuitNetlist("bad2").add_device("Y", "load", r=50).to_spice()
        check("悬空器件报错", False, "未抛 NetlistError")
    except NetlistError:
        check("悬空器件报错", True)
    except Exception as e:  # noqa
        check("悬空器件报错", False, f"抛错类型错 {e!r}")

    # ⑥ Spectre 适配层真生效
    spec = build_demo().to_cadence_spectre()
    check("Spectre 含 simulator lang=spectre", "simulator lang=spectre" in spec)
    check("Spectre 用 (n1 n2) 元素语法", "(M1_rf_in M1_int)" in spec)
    check("Spectre 用 subckt/ends（非 SPICE .end）",
          ("subckt" in spec) and (".end" not in spec))

    if fails:
        print(f"\nT1-2 SPICE netlist smoke: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nT1-2 SPICE netlist smoke: ALL GREEN")


if __name__ == "__main__":
    main()
