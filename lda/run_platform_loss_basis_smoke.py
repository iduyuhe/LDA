"""平台级损耗口径 门禁 smoke（D-125 · 每模口径推到 lda_l2 + scale_bench 口径订正）。

═══ 为什么要有这个 smoke ═══
D-123/D-124 让「每模口径」在量子栈里落地；D-125 把它**推到平台层**：平台原语 +
经典 DRC 的损耗通道 + lvs_geom 的回提损耗 + scale_bench 的三口径一体登记。
这一层最容易被后人用「一个数字」糊过去，必须钉成常驻断言：

  ① **平台只有一份每模深度**：`mzi_mesh_matmul.mesh_per_mode_optical_depth`，
     量子 DRC（D-124）/ 规模对标（D-120 订正）/ 本门禁三处必须**同值**（防口径漂移）。
  ② **深度 ≠ 门总片数**：三角 2N−3 vs N(N−1)/2（N=8：13 vs 28）。
  ③ **三种口径不可互换**：每模（2N−3）/ 列（N−1）/ 总级联（全网格门合计），
     且 scale_bench 必须**同时**给出并标注，旧字段语义**不变**（兼容）。
  ④ **经典 DRC 有了损耗通道**：器件级几何规则管不到链路预算 ⇒ `drc_check_mesh_loss`
     判双口径（15/25 dB），与量子 DRC 的 `QDR-LOSS-BUDGET` **同限值、同迁移**。
  ⑤ **lvs_geom 的回提损耗**：只含传播+环形弯曲 ⇒ **下界**；登记的长度参数必须真可回提；
     读数由**回提几何**驱动（改声明长度 ⇒ 读数变）。

═══ 判什么（分六节 · 28 条）═══
A 平台原语 5 · B 经典 DRC 损耗通道 5 · C lvs_geom 损耗通道 5 ·
D scale_bench 口径订正 6 · E 诚实标注+红线 4 · F 跨模块一致 3。

运行：python run_platform_loss_basis_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from lda_qeda import scale_bench as SBM
    from lda_qeda import loss_budget as LB
    from lda_qeda import quantum_drc_lvs as QDR
    from lda_qeda import rect_mesh as RMB
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import scale_bench as SBM                             # noqa: E402
    import loss_budget as LB                              # noqa: E402
    import quantum_drc_lvs as QDR                         # noqa: E402
    import rect_mesh as RMB                               # noqa: E402

from lda_l2 import drc as DRC                            # noqa: E402
from lda_l2 import mzi_mesh_matmul as MMM                # noqa: E402
from lda_l2 import lvs_geom as G                         # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」劣化 · **名字在前**！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def _tri_ops(n):
    return MMM.reck_triangular_mesh(MMM.dft_matrix(n))[0]


def _rect_flat(n):
    layers, _D = RMB.rectangular_mesh_layers(MMM.dft_matrix(n))
    return [(int(j), float(t), float(p)) for L in layers for (j, t, p) in L]


def main() -> int:
    print("=" * 78)
    print("平台级损耗口径 门禁 smoke（D-125 · 每模口径推平台 + 三口径一体登记）")
    print("=" * 78)

    # ════════════════ A 节：平台原语 ════════════════
    print("── A 平台原语（mzi_mesh_matmul · 单一真源）──")
    ok_a1 = True
    detail_a1 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        d = MMM.mesh_per_mode_optical_depth(_tri_ops(n_))
        detail_a1.append(f"N={n_}:{d}")
        if d != 2 * n_ - 3:
            ok_a1 = False
    check("A1 平台每模深度（三角）= 2N−3（构造实测，N=4…64）", ok_a1, " · ".join(detail_a1))

    ok_a2 = True
    detail_a2 = []
    for n_ in (4, 5, 8, 16):
        d = MMM.mesh_per_mode_optical_depth(_rect_flat(n_))
        detail_a2.append(f"N={n_}:{d}")
        if d != n_:
            ok_a2 = False
    check("A2 平台每模深度（矩形 Clements）= N（构造实测）", ok_a2, " · ".join(detail_a2))

    ops8 = _tri_ops(8)
    check("A3 ★深度 ≠ 门总片数★ N=8：每模 13（=2N−3）≠ 门总片数 28（=N(N−1)/2）",
          MMM.mesh_per_mode_optical_depth(ops8) == 13 and len(ops8) == 28,
          "用 len(ops) 冒充会把三角深度高估约 (N−1)/2 倍")

    b = MMM.mesh_loss_basis(_tri_ops(16), n_crossings=3)
    pm = MMM.mesh_cascade_loss_db(1, n_crossings=0)
    check("A4 mesh_loss_basis 三口径自洽：per_mode = 深度×per_mzi · total = 门合计+交叉 · 交叉只进总口径",
          abs(b["per_mode_db"] - 29 * pm) < 1e-9
          and abs(b["total_db"] - (120 * pm + 3 * MMM.CROSSING_LOSS_DB)) < 1e-9
          and abs(b["crossing_loss_db"] - 3 * MMM.CROSSING_LOSS_DB) < 1e-9
          and b["crossing_loss_included_in_per_mode"] is False,
          f"per_mode={b['per_mode_db']:.1f} total={b['total_db']:.1f} 交叉={b['crossing_loss_db']:.2f}")

    guard = True
    for bad in ((lambda: MMM.mesh_per_mode_optical_depth([])),
                (lambda: MMM.mesh_per_mode_optical_depth([(0, 1)])),
                (lambda: MMM.mesh_per_mode_optical_depth([(-1, 0.3, 0.1)])),
                (lambda: MMM.mesh_per_mode_optical_depth(_tri_ops(4), n_modes=3))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    check("A5 平台原语护栏：空 ops / 非法元数 / 负模索引 / N 越界 ⇒ ValueError",
          guard, "四类非法输入全抛错")

    # ════════════════ B 节：经典 DRC 损耗通道 ════════════════
    print("── B 经典 DRC 的损耗通道（lda_l2.drc）──")
    check("B1 DEFAULT_RULES 含损耗通道两限值（每模 15 dB · 总级联 25 dB）",
          abs(DRC.DEFAULT_RULES["max_il_per_mode_db"] - 15.0) < 1e-12
          and abs(DRC.DEFAULT_RULES["max_il_total_db"] - 25.0) < 1e-12,
          "与量子 DRC `QDR-LOSS-BUDGET` 同限值")

    r5 = DRC.drc_check_mesh_loss(_tri_ops(5))
    bases5 = {c.basis: c for c in r5.checks}
    pm5, tot5 = bases5.get("每模口径"), bases5.get("总级联口径")
    check("B2 ★判定迁移（与 D-124 同）★ N=5：每模口径 16.8>15 拒绝 · 总级联 24≤25 通过",
          r5.passed is False and pm5 is not None and tot5 is not None
          and pm5.ok is False and tot5.ok is True,
          f"每模 {pm5.value_db:.1f} · 总 {tot5.value_db:.1f}" if (pm5 and tot5) else "缺口径 ⇒ 判红")

    r4 = DRC.drc_check_mesh_loss(_tri_ops(4))
    check("B3 N=4 两口径皆通过 ⇒ 网格损耗 PASS（无假阳）",
          r4.passed is True and len(r4.checks) == 2
          and {c.basis for c in r4.checks} == {"每模口径", "总级联口径"},
          f"{[(c.basis, round(c.value_db, 1)) for c in r4.checks]}")

    r4t = DRC.drc_check_mesh_loss(_tri_ops(4), rules={"max_il_per_mode_db": 10.0})
    check("B4 限值可覆盖：收紧每模到 10 dB ⇒ N=4 也拒绝（设计规则 · 可覆盖）",
          r4t.passed is False
          and any(c.basis == "每模口径" and not c.ok for c in r4t.checks),
          "12 dB > 10 dB")

    dev = DRC.drc_check_device("Waveguide", {"width": 0.5})
    check("B5 器件级 DRC 不受影响：DEFAULT_RULES 加键后 `drc_check_device` 仍 1 项几何检查且 PASS",
          dev.passed is True and len(dev.checks) == 1 and dev.checks[0].rule == "min_width",
          "损耗通道是**新增**函数，不碰既有器件级路径")

    # ════════════════ C 节：lvs_geom 损耗通道 ════════════════
    print("── C 几何回提 → 被动损耗（lda_l2.lvs_geom）──")
    from lda_chain.link_model import LinkModel
    from lda_agent.ring_adddrop import bending_loss_db_per_cm
    miss = [(k, p) for k, p in G.PROP_LENGTH_PARAM.items()
            if p not in G.PARAM_MEASURERS.get(k, {})]
    check("C1 登记的长度参数必须**真可回提**（机器复核，防漂移）",
          not miss and len(G.PROP_LENGTH_PARAM) >= 6,
          f"登记 {len(G.PROP_LENGTH_PARAM)} 类 · 未可回提={miss or '无'}")

    def _mk(wg_len):
        lm = LinkModel(name="t")
        lm.add_device("d0", "Waveguide", {"length": wg_len, "width": 0.5})
        lm.add_device("d1", "RingResonator", {"R": 10.0, "gap": 0.3, "wg_width": 0.5})
        return lm, {"d0": (0.0, 0.0, 0.0), "d1": (50.0, 0.0, 0.0)}

    lm_a, pl_a = _mk(12.0)
    lm_b, pl_b = _mk(24.0)
    ra = G.recovered_passive_loss(lm_a, pl_a)
    rb = G.recovered_passive_loss(lm_b, pl_b)
    check("C2 读数由**回提几何**驱动：波导长 12 → 24 µm ⇒ 传播项翻倍",
          ra["n_covered"] == 2 and abs(
              (rb["devices"]["d0"]["loss_db"] / ra["devices"]["d0"]["loss_db"]) - 2.0) < 1e-9,
          f"12µm={ra['devices']['d0']['loss_db']:.6f} → 24µm={rb['devices']['d0']['loss_db']:.6f}")

    check("C3 环形类走**弯曲项**（2πR），不走传播常数",
          "环形周长" in ra["devices"]["d1"]["note"]
          and ra["devices"]["d1"]["loss_db"] > 0.0
          and abs(ra["devices"]["d1"]["loss_db"]
                  - 2.0 * 3.141592653589793 * 10.0 / 1e4
                  * float(bending_loss_db_per_cm(10.0))) < 1e-9,
          ra["devices"]["d1"]["note"])

    disc = G.RECOVERED_LOSS_DISCLOSURE
    check("C4 披露齐备 + 明标**下界**：scope / from_recovered_geometry / parameterized",
          all(k in disc for k in ("scope", "from_recovered_geometry",
                                  "parameterized_not_measured"))
          and ra["is_lower_bound"] is True and ra["covers"] == "propagation+ring_bending"
          and "下界" in ra["honest_note"],
          f"键={sorted(disc)}")

    lm_u, pl_u = LinkModel(name="u"), {}
    lm_u.add_device("g0", "GratingCoupler", {"L": 10.0, "period": 0.63, "duty": 0.5})
    pl_u["g0"] = (0.0, 0.0, 0.0)
    ru = G.recovered_passive_loss(lm_u, pl_u)
    check("C5 未覆盖类如实登记：光栅/耦合/探测器**不在**通道内（不冒充已算）",
          ru["n_covered"] == 0 and "GratingCoupler" in ru["uncovered_by_kind"]
          and ru["devices"]["g0"]["loss_db"] is None,
          f"uncovered={ru['uncovered_by_kind']}")

    # ════════════════ D 节：scale_bench 口径订正 ════════════════
    print("── D scale_bench 三口径一体登记（订正 (N−1)·per 口径）──")
    L216 = SBM.mesh_scaling_laws(216)
    check("D1 mesh_scaling_laws 增每模口径：mzi_per_mode=2N−3=429 · loss_per_mode_db=1029.6",
          L216["mzi_per_mode"] == 429
          and abs(L216["loss_per_mode_db"] - 429 * SBM.PER_MZI_LOSS_DB) < 1e-9,
          f"每模 {L216['loss_per_mode_db']:.1f} dB")

    check("D2 每模口径 > 列口径（差 (N−2)·per = 513.6 dB）且 loss_basis_note 三口径齐",
          abs((L216["loss_per_mode_db"] - L216["loss_per_path_db"])
              - (216 - 2) * SBM.PER_MZI_LOSS_DB) < 1e-9
          and all(k in L216["loss_basis_note"] for k in ("列/阶段口径", "每模口径", "总级联口径")),
          f"每模 {L216['loss_per_mode_db']:.0f} vs 列 {L216['loss_per_path_db']:.0f}"
          f"（差 {(216-2)*SBM.PER_MZI_LOSS_DB:.1f}）")

    st = SBM.static_mesh_architecture(216)
    check("D3 static_mesh_architecture 并报两口径（loss_per_path_db 保留 · loss_per_mode_db 新增）",
          "loss_per_path_db" in st and "loss_per_mode_db" in st
          and abs(st["loss_per_path_db"] - L216["loss_per_path_db"]) < 1e-9
          and abs(st["loss_per_mode_db"] - L216["loss_per_mode_db"]) < 1e-9
          and st["mzi_per_mode"] == 429,
          f"列 {st['loss_per_path_db']:.0f} · 每模 {st['loss_per_mode_db']:.0f}")

    tr = SBM.architecture_tradeoff(216)
    check("D4 architecture_tradeoff 增每模省损（> 列口径省损）",
          tr["loss_saving_db_tmux_per_mode"] > tr["loss_saving_db_tmux"] > 400.0,
          f"每模省 {tr['loss_saving_db_tmux_per_mode']:.0f} dB vs 列省 {tr['loss_saving_db_tmux']:.0f} dB")

    br = SBM.scale_bottleneck_report((4, 8, 16, 32, 64, 216))
    row216 = [r for r in br["rows"] if r["n_modes"] == 216][0]
    check("D5 scale_bottleneck_report 行含每模口径 + 每模损耗墙（早于列口径关门）",
          "loss_per_mode_db" in row216 and "loss_mode_ok" in row216
          and br["loss_mode_wall_n"] > 0
          and br["loss_mode_wall_n"] <= br["loss_wall_n_at_useful"],
          f"每模墙 N*={br['loss_mode_wall_n']} ≤ 列墙 N*={br['loss_wall_n_at_useful']}")

    ok_d6 = True
    for n_ in (4, 16, 64, 216):
        Lx = SBM.mesh_scaling_laws(n_)
        if not (Lx["n_stages"] == n_ - 1 and Lx["mzi_per_path"] == n_ - 1
                and abs(Lx["loss_per_path_db"] - (n_ - 1) * SBM.PER_MZI_LOSS_DB) < 1e-9):
            ok_d6 = False
    check("D6 ★兼容性★ 旧键语义不变（n_stages / mzi_per_path = N−1 · loss_per_path_db = (N−1)·per）",
          ok_d6, "订正是**新增并标注**，不改旧字段 ⇒ 既有门禁零破坏")

    # ════════════════ E 节：诚实标注 + 红线 ════════════════
    print("── E 诚实标注 + 红线 ──")
    check("E1 三模块都有口径披露：scale_bench.loss_basis · lvs_geom.RECOVERED_LOSS_DISCLOSURE · drc 注释",
          "loss_basis" in SBM.RED_LINE_DISCLOSURE
          and "每模口径" in SBM.RED_LINE_DISCLOSURE["loss_basis"]
          and "RECOVERED_LOSS_DISCLOSURE" in open(os.path.join(_HERE, "lda_l2", "lvs_geom.py"),
                                                   encoding="utf-8").read(),
          "口径不是注释里的口头话，而是返回值里的键")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = []
    for f in ("lda_l2/mzi_mesh_matmul.py", "lda_l2/drc.py", "lda_l2/lvs_geom.py"):
        src = open(os.path.join(_HERE, f), encoding="utf-8").read()
        hits += [f"{f}:{b}" for b in banned
                 if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("E2 红线：三平台模块零量子 SDK 依赖（纯 numpy + 标准库，C 级自主）",
          not hits, f"命中={hits or '无'}")

    check("E3 无 LLM：口径值全为 float/int · 判决为 bool（死标量，零模型调用）",
          isinstance(b["per_mode_db"], float) and isinstance(b["per_mode_optical_depth"], int)
          and isinstance(r5.passed, bool) and isinstance(ra["total_loss_db"], float),
          "per_mode_db / passed / total_loss_db 均为死标量")

    check("E4 常数/限值明标设计预算（非实测 PDK）：per_mzi 2.4 · α_prop 2.0 · 限值 15/25",
          abs(pm - SBM.PER_MZI_LOSS_DB) < 1e-9
          and abs(ra["alpha_prop_db_cm"] - 2.0) < 1e-12,
          "三者同源，不另建常数")

    # ════════════════ F 节：跨模块一致 ════════════════
    print("── F 跨模块口径一致（平台 ≡ D-120 ≡ D-123 ≡ D-124）──")
    ok_f1 = True
    detail_f1 = []
    for n_ in (4, 8, 16, 64):
        o = _tri_ops(n_)
        a = MMM.mesh_per_mode_optical_depth(o)          # 平台原语
        c = QDR.per_mode_optical_depth(o)               # 量子 DRC（D-124）
        d = LB.triangular_optical_depth(n_)["per_mode_max"]   # 规模对标（D-123）
        e = SBM.mesh_scaling_laws(n_)["mzi_per_mode"]   # 平台规模律（D-120 订正）
        detail_f1.append(f"N={n_}:{a}/{c}/{d}/{e}")
        if not (a == c == d == e == 2 * n_ - 3):
            ok_f1 = False
    check("F1 ★单一真源★ 每模深度四处同值：平台原语 / 量子 DRC / D-123 / 规模律",
          ok_f1, " · ".join(detail_f1))

    check("F2 每模损耗常数同源：三处 per_mzi 均为 2.4 dB（同源常数，不另建）",
          abs(pm - LB.PER_MZI_LOSS_DB) < 1e-9
          and abs(pm - SBM.PER_MZI_LOSS_DB) < 1e-9,
          f"per_mzi={pm}")

    q5 = QDR.run_quantum_drc({"ops": _tri_ops(5), "N": 5, "n_crossings": 0})
    check("F3 判定一致：N=5 在**经典 DRC** 与**量子 DRC** 都因每模口径被拒（同迁移）",
          DRC.drc_check_mesh_loss(_tri_ops(5)).passed is False
          and q5["verdict"] == "REJECT"
          and any("每模口径" in v["detail"] for v in q5["violations"]),
          "两个签核通道口径一致")

    print()
    print(f"平台级损耗口径 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
