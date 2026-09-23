# -*- coding: utf-8 -*-
"""U5 · 编译器 / AI 框架前端回归护栏（网络矩阵 → 酉分解 → 驱动清单）。

把 `lda_l2/compiler_frontend.py` 接入 CI 核心门禁。任何主权链改动
（mesh_pnr 分解 / 列分配 / 驱动清单 / numpy SVD 行为）一旦破坏下述任一条即 FAIL：

  - **酉路径**：酉输入 ⇒ 精确实现（残余 0、保真度机器精度）；
  - **非方阵路径**：最近**部分等距**（对原 m×n 求，不 pad）+ 正交补全为 N×N 酉，
    并断言硬性质 **U_full[:m,:n] == U_p（机器精度）** ⇒ 逼近结果物理可实现；
  - **非酉路径**：逼近残余**非零**且与**闭式解**（Procrustes：β*=Σσ/k、
    res²=Σσ²−(Σσ)²/k）逐位一致 ⇒ 诚实标注有解析依据；
  - **增益路径**：σ_max>1 ⇒ 夹持被检出、衰减 β=1/σ_max 被量化、损失被报出；
  - **边界守卫**（🔴 红线）：外部框架对象进判决路径 ⇒ 必 raise；numpy/内建
    容器 ⇒ 合法必过（双向都测，防「恒真护栏」）；
  - **反向护栏**：非酉直喂分解器 ⇒ 必 raise；非部分等距喂补全 ⇒ 必 raise；
    超 MAX_DIM ⇒ 必 raise；非二维 ⇒ 必 raise；
  - **交叉验证**：U5 产出的 (j,θ,φ,col) 与独立重算的分解结果**逐元素一致**。

数据流全程死标量：numpy SVD + Clements 分解，无外部框架、无 LLM。
不依赖 torch/onnx/meep/tidy3d；按准入准则（<5s 且无重依赖）无权豁免，
必须进 CORE_SMOKES。
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))   # lda/
ROOT = os.path.dirname(HERE)                         # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), return_ok=True, detail_on="fail")


def _rejects(fn, exc: type = Exception) -> bool:
    """执行 fn 若抛 exc（或子类）⇒ True（用于「必 raise」判据）。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main() -> int:
    import numpy as np

    from lda_l2.compiler_frontend import (COMPILER_DISCLOSURE, MAX_DIM,
                                          FrontendBoundaryError,
                                          clamp_singular_values, compile_layer,
                                          compile_network, complete_to_unitary,
                                          demo_network, demo_nonunitary_network,
                                          guard_no_framework_in_judgment,
                                          load_layers_from_json, matrix_spectrum,
                                          nearest_isometry, nearest_unitary,
                                          to_numpy_readonly,
                                          write_drive_manifest_csv,
                                          write_network_drive_manifest_csv)
    from lda_layout.mesh_pnr import (_rect_column_assignment,
                                     clements_rect_decompose)

    ok = True

    # ================= A. 酉路径：精确实现 =================
    nname, layers = demo_network()
    net = compile_network(layers, name=nname)
    L_u = net["layers"][0]                     # 'dft4'
    ok &= check("A1 酉层 exact_unitary == True", L_u["exact_unitary"] is True, detail="")
    ok &= check("A2 酉层 N=4 · n_mzi=6 (=N(N-1)/2)", L_u["N"] == 4 and L_u["n_mzi"] == 6,
                detail=f"N={L_u['N']} n_mzi={L_u['n_mzi']}")
    ok &= check("A3 酉层目标保真度 == 1.0（机器精度）",
                L_u["fidelity_vs_target"] >= 1.0 - 1e-12,
                detail=f"{L_u['fidelity_vs_target']:.15f}")
    ok &= check("A4 酉层版级保真度 == 1.0（机器精度）",
                L_u["layout_fidelity_vs_target"] >= 1.0 - 1e-12,
                detail=f"{L_u['layout_fidelity_vs_target']:.15f}")
    ok &= check("A5 酉层残余严格为 0", L_u["nearest_unitary_info"]["residual_fro"] == 0.0,
                detail=str(L_u["nearest_unitary_info"]["residual_fro"]))
    ok &= check("A6 酉层无补全（added=0）", L_u["embedding"]["added"] == 0,
                detail=str(L_u["embedding"]["added"]))
    ok &= check("A7 酉层 n_ps == N", L_u["n_ps"] == L_u["N"], detail=str(L_u["n_ps"]))
    ok &= check("A8 酉层 implemented_operator == 'input'",
                L_u["implemented_operator"] == "input", detail=L_u["implemented_operator"])

    # ================= B. 非方阵：部分等距 + 正交补全 =================
    L_r = net["layers"][1]                     # 'real4x16'
    emb = L_r["embedding"]
    ok &= check("B1 非方阵层 exact_unitary == False", L_r["exact_unitary"] is False, detail="")
    ok &= check("B2 补全方向 rows · 补 12 行",
                emb["mode"] == "orthogonal-completion" and emb["direction"] == "rows"
                and emb["added"] == 12,
                detail=f"{emb['mode']}/{emb['direction']}/{emb['added']}")
    ok &= check("B3 🔴 硬性质：端口块 U_full[:m,:n] == U_p（机器精度）",
                emb["embedding_residual_max"] <= 1e-12,
                detail=f"{emb['embedding_residual_max']:.3e}")
    ok &= check("B4 补全后矩阵为酉（单位性误差机器精度）",
                emb["unitarity_err_max"] <= 1e-12, detail=f"{emb['unitarity_err_max']:.3e}")
    ok &= check("B5 N=16 · 有效端口 16 in / 4 out",
                L_r["N"] == 16 and L_r["active_in_ports"] == 16
                and L_r["active_out_ports"] == 4,
                detail=f"N={L_r['N']} in={L_r['active_in_ports']} out={L_r['active_out_ports']}")
    ok &= check("B6 对酉目标保真度 == 1.0（尽管输入非酉）",
                L_r["fidelity_vs_target"] >= 1.0 - 1e-12,
                detail=f"{L_r['fidelity_vs_target']:.15f}")
    ok &= check("B7 非酉 ⇒ 逼近残余严格 > 0（不得虚报精确）",
                L_r["nearest_unitary_info"]["residual_fro"] > 0.0,
                detail=f"{L_r['nearest_unitary_info']['residual_fro']:.6e}")
    ok &= check("B8 实矩阵经复酉映射被标注",
                L_r["is_real_input"] is True and L_r["real_mapped_to_complex"] is True,
                detail=f"real={L_r['is_real_input']} mapped={L_r['real_mapped_to_complex']}")
    ok &= check("B9 implemented_operator 明示非 input（诚实标注）",
                L_r["implemented_operator"] != "input", detail=L_r["implemented_operator"])

    # ---- B10/B11 🔴 独立重算（不信模块自报值，防「自报即真」）----
    A_chk = np.array([[0.5 / (1.0 + i + j) for j in range(16)] for i in range(4)], dtype=complex)
    Up_chk, uinfo = nearest_isometry(A_chk)
    Uf_chk, _ = complete_to_unitary(Up_chk)
    ok &= check("B10 🔴 独立重算端口块误差（不读 embedding 自报值）",
                float(np.max(np.abs(Uf_chk[:4, :16] - Up_chk))) <= 1e-12,
                detail=f"{float(np.max(np.abs(Uf_chk[:4, :16] - Up_chk))):.3e}")
    ok &= check("B11 独立重算补全矩阵酉性（不读 embedding 自报值）",
                float(np.max(np.abs(Uf_chk @ Uf_chk.conj().T - np.eye(16)))) <= 1e-12,
                detail=f"{float(np.max(np.abs(Uf_chk @ Uf_chk.conj().T - np.eye(16)))):.3e}")

    # ================= C. 闭式解一致性（诚实标注有解析依据） =================
    k = min(A_chk.shape)
    s = np.linalg.svd(A_chk, compute_uv=False)
    beta_closed = float(np.sum(s) / k)
    res_closed = float(np.sqrt(max(0.0, float(np.sum(s ** 2)) - (float(np.sum(s)) ** 2) / k)))
    ok &= check("C1 β* 与闭式解 Σσ/k 一致（机器精度）",
                abs(uinfo["beta_opt"] - beta_closed) <= 1e-12,
                detail=f"{uinfo['beta_opt']:.15f} vs {beta_closed:.15f}")
    ok &= check("C2 最优缩放残余与闭式解一致（机器精度）",
                abs(uinfo["residual_at_opt_fro"] - res_closed) <= 1e-12,
                detail=f"{uinfo['residual_at_opt_fro']:.15e} vs {res_closed:.15e}")
    ok &= check("C3 最优残余 ≤ 未缩放残余（缩放确有收益）",
                uinfo["residual_at_opt_fro"] <= uinfo["residual_fro"] + 1e-15,
                detail=f"{uinfo['residual_at_opt_fro']:.6e} ≤ {uinfo['residual_fro']:.6e}")
    ok &= check("C4 最优相对残余 ≤ 1（尺度不变上界）",
                uinfo["residual_at_opt_relative"] <= 1.0 + 1e-12,
                detail=f"{uinfo['residual_at_opt_relative']:.6f}")

    # ================= D. 增益 / 夹持（有损，必须量化） =================
    nname2, layers2 = demo_nonunitary_network()
    net2 = compile_network(layers2, name=nname2)
    by_name = {lr["name"]: lr for lr in net2["layers"]}
    L_near, L_gain = by_name["near_unitary16"], by_name["gain16"]

    ok &= check("D1 近酉层残余小（< 2e-2，可预测）",
                0.0 < L_near["nearest_unitary_info"]["residual_relative"] < 2e-2,
                detail=f"{L_near['nearest_unitary_info']['residual_relative']:.6e}")
    ok &= check("D2 增益层 σ_max > 1（含增益被检出）",
                L_gain["unitarity"]["sigma_max"] > 1.0,
                detail=f"σ_max={L_gain['unitarity']['sigma_max']:.6f}")
    ok &= check("D3 增益层夹持计数 ≥ 1",
                L_gain["clamp"]["n_truncated"] >= 1,
                detail=str(L_gain["clamp"]["n_truncated"]))
    smax = L_gain["unitarity"]["sigma_max"]
    ok &= check("D4 衰减 β == 1/σ_max（机器精度）",
                abs(L_gain["clamp"]["attenuation_beta"] - 1.0 / smax) <= 1e-12,
                detail=f"{L_gain['clamp']['attenuation_beta']:.12f} vs {1.0 / smax:.12f}")
    ok &= check("D5 夹持残余 > 0（有损操作，必须报出）",
                L_gain["clamp"]["clamp_residual_fro"] > 0.0,
                detail=f"{L_gain['clamp']['clamp_residual_fro']:.6e}")
    ok &= check("D6 增益层 requires_attenuation == True",
                L_gain["clamp"]["requires_attenuation"] is True, detail="")
    ok &= check("D7 🔴 重增益算子最优残余仍 > 0.9（诚实暴露「无法被动实现」）",
                L_gain["nearest_unitary_info"]["residual_at_opt_relative"] > 0.9,
                detail=f"{L_gain['nearest_unitary_info']['residual_at_opt_relative']:.6f}")
    ok &= check("D8 酉层无夹持（σ_max == 1 ⇒ n_truncated == 0）",
                L_u["clamp"]["n_truncated"] == 0 and L_gain["unitarity"]["n_sigma_gt_1"] >= 1,
                detail="")

    # ================= E. 网络汇总 =================
    ok &= check("E1 网络层数 == 3", net["n_layers"] == 3, detail=str(net["n_layers"]))
    n_mzi_expected = 6 + 120 + 120
    ok &= check("E2 网络 MZI 总数 == ΣN(N-1)/2 == 246",
                net["n_mzi_total"] == n_mzi_expected, detail=str(net["n_mzi_total"]))
    n_drv_expected = (6 + 4) + (120 + 16) + (120 + 16)
    ok &= check("E3 网络驱动器总数（MZI + 输出相移器）== 282",
                net["n_driver_total"] == n_drv_expected, detail=str(net["n_driver_total"]))
    ok &= check("E4 网络最小目标保真度 == 1.0",
                net["min_fidelity_vs_target"] >= 1.0 - 1e-12,
                detail=f"{net['min_fidelity_vs_target']:.15f}")
    ok &= check("E5 网络非酉层计数 == 1 · all_exact_unitary == False",
                net["n_nonunitary_layers"] == 1 and net["all_exact_unitary"] is False,
                detail=f"nonuni={net['n_nonunitary_layers']}")
    ok &= check("E6 网络最大相对残余 > 0（诚实汇总）",
                net["max_relative_residual"] > 0.0,
                detail=f"{net['max_relative_residual']:.6e}")

    # ================= F. 驱动清单 CSV =================
    with tempfile.TemporaryDirectory() as td:
        p1 = write_drive_manifest_csv(L_u, os.path.join(td, "L0.csv"))
        p2 = write_network_drive_manifest_csv(net, os.path.join(td, "net.csv"))
        with open(p1, encoding="utf-8") as f:
            rows1 = [ln.rstrip("\n") for ln in f]
        with open(p2, encoding="utf-8") as f:
            rows2 = [ln.rstrip("\n") for ln in f]
        ok &= check("F1 单层 CSV 存在且非空",
                    os.path.exists(p1) and len(rows1) > 2, detail=str(len(rows1)))
        n_rows1 = 1 + 1 + L_u["n_mzi"] + L_u["n_ps"]
        ok &= check("F2 单层 CSV 行数 == 1(meta)+1(表头)+n_mzi+n_ps",
                    len(rows1) == n_rows1, detail=f"{len(rows1)} vs {n_rows1}")
        ok &= check("F3 单层 CSV 表头 == kind,idx,col_c_or_rail,phi_rad,V",
                    rows1[1] == "kind,idx,col_c_or_rail,phi_rad,V", detail=rows1[1][:60])
        ok &= check("F4 网络 CSV 表头首列 == layer",
                    rows2[1].startswith("layer,kind,idx,col_c_or_rail,phi_rad,V"),
                    detail=rows2[1][:60])
        n_rows2 = 1 + 1 + net["n_driver_total"]
        ok &= check("F5 网络 CSV 行数 == 1(meta)+1(表头)+Σ驱动器",
                    len(rows2) == n_rows2, detail=f"{len(rows2)} vs {n_rows2}")
        ok &= check("F6 meta 行含 n_mzi_total / n_driver_total",
                    "n_mzi_total" in rows2[0] and "n_driver_total" in rows2[0],
                    detail=rows2[0][:70])

    # ================= G. 边界外只读输入（JSON） =================
    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "net.json")
        with open(jp, "w", encoding="utf-8") as f:
            f.write('{"name":"json_net","layers":['
                    '{"name":"u2","matrix":[[0.0,1.0],[1.0,0.0]]},'
                    '{"name":"c2","matrix":[[[0.7071067811865476,0.0],[-0.7071067811865476,0.0]],'
                    '[[0.7071067811865476,0.0],[0.7071067811865476,0.0]]]}]}')
        jname, jlayers = load_layers_from_json(jp)
        jrep = compile_network(jlayers, name=jname)
        ok &= check("G1 JSON 读回层数 == 2 且网络名正确",
                    jrep["n_layers"] == 2 and jrep["name"] == "json_net",
                    detail=f"{jrep['n_layers']}/{jrep['name']}")
        ok &= check("G2 JSON 复数 [re,im] 解码 ⇒ 酉层保真度 1.0",
                    jrep["min_fidelity_vs_target"] >= 1.0 - 1e-12,
                    detail=f"{jrep['min_fidelity_vs_target']:.15f}")

    # ================= H. 🔴 红线边界守卫（双向） =================
    FakeTorchTensor = type("Tensor", (), {"__module__": "torch"})
    FakeOnnxModel = type("ModelProto", (), {"__module__": "onnx"})
    ok &= check("H1 反例：torch 对象进判决路径 ⇒ 必 raise",
                _rejects(lambda: guard_no_framework_in_judgment(FakeTorchTensor(),
                                                                "test"), FrontendBoundaryError),
                detail="")
    ok &= check("H2 反例：onnx 对象 ⇒ 必 raise",
                _rejects(lambda: guard_no_framework_in_judgment(FakeOnnxModel(), "test"),
                         FrontendBoundaryError), detail="")
    ok &= check("H3 反例：嵌套在 list 里的框架对象 ⇒ 必 raise",
                _rejects(lambda: guard_no_framework_in_judgment([1.0, FakeTorchTensor()],
                                                                "test"),
                         FrontendBoundaryError), detail="")
    ok &= check("H4 反例：compile_layer 收到框架对象 ⇒ 必 raise",
                _rejects(lambda: compile_layer(FakeTorchTensor(), name="bad"),
                         FrontendBoundaryError), detail="")
    ok &= check("H5 合法必过：numpy 数组不 raise",
                not _rejects(lambda: guard_no_framework_in_judgment(np.eye(3), "test"),
                             FrontendBoundaryError), detail="")
    ok &= check("H6 合法必过：嵌套 list / dict 不 raise",
                not _rejects(lambda: guard_no_framework_in_judgment(
                    {"a": [np.eye(2), [[1.0, 0.0]]]}, "test"), FrontendBoundaryError),
                detail="")
    ok &= check("H7 合法必过：to_numpy_readonly 对 numpy 直通且 dtype 复",
                to_numpy_readonly(np.eye(2)).dtype == complex, detail="")

    # ================= I. 反向护栏（缺陷态必亮红） =================
    A_nonuni = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=complex)
    ok &= check("I1 非酉直喂 clements_rect_decompose ⇒ 必 raise（酉化非多余步骤）",
                _rejects(lambda: clements_rect_decompose(A_nonuni), ValueError), detail="")
    ok &= check("I2 非部分等距喂 complete_to_unitary ⇒ 必 raise",
                _rejects(lambda: complete_to_unitary(A_nonuni), FrontendBoundaryError),
                detail="")
    ok &= check("I3 非方阵喂 nearest_unitary ⇒ 必 raise（须走 isometry 路径）",
                _rejects(lambda: nearest_unitary(np.zeros((2, 3), dtype=complex)),
                         FrontendBoundaryError), detail="")
    ok &= check("I4 一维输入 matrix_spectrum ⇒ 必 raise",
                _rejects(lambda: matrix_spectrum(np.array([1.0, 2.0])),
                         FrontendBoundaryError), detail="")
    ok &= check("I5 超 MAX_DIM ⇒ 必 raise",
                _rejects(lambda: compile_layer(np.eye(MAX_DIM + 1, dtype=complex)),
                         FrontendBoundaryError),
                detail=f"MAX_DIM={MAX_DIM}")
    ok &= check("I6 cap ≤ 0 喂 clamp ⇒ 必 raise",
                _rejects(lambda: clamp_singular_values(np.eye(2), cap=0.0),
                         FrontendBoundaryError), detail="")
    ok &= check("I7 缺 'matrix' 键的层定义 ⇒ 必 raise",
                _rejects(lambda: compile_network([{"name": "x"}]), FrontendBoundaryError),
                detail="")

    # ================= J. 交叉验证：与独立重算的分解逐元素一致 =================
    bs_ref, D_ref = clements_rect_decompose(np.array(
        [[np.exp(-2j * np.pi * (i * j) / 4) / 2.0 for j in range(4)] for i in range(4)]))
    cols_ref = _rect_column_assignment(bs_ref)
    ops_ref = [(int(j), float(th), float(ph), int(c))
               for (j, th, ph), c in zip(bs_ref, cols_ref)]
    L_x = compile_layer(np.array([[np.exp(-2j * np.pi * (i * j) / 4) / 2.0
                                  for j in range(4)] for i in range(4)]), name="dft4x")
    ops_same = (len(L_x["ops"]) == len(ops_ref)) and all(
        a[0] == b[0] and a[3] == b[3] and abs(a[1] - b[1]) <= 1e-15
        and abs(a[2] - b[2]) <= 1e-15 for a, b in zip(L_x["ops"], ops_ref))
    ok &= check("J1 U5 产出的 (j,θ,φ,col) 与独立重算逐元素一致",
                ops_same, detail=f"n={len(L_x['ops'])} vs {len(ops_ref)}")
    ok &= check("J2 U5 驱动清单 n_mzi 与分解 op 数一致（无丢项）",
                L_x["drive"]["n_mzi"] == len(ops_ref),
                detail=f"{L_x['drive']['n_mzi']} vs {len(ops_ref)}")

    # ================= K. 诚实披露存在性 =================
    for key in ("scope", "nonlinearity", "nonunitary", "clamping",
                "framework_boundary", "real_input", "drive_voltage", "sovereignty"):
        ok &= check(f"K 披露项存在且非空：{key}",
                    bool(COMPILER_DISCLOSURE.get(key)), detail="")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
