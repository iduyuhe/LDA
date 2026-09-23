"""v0.9.128 P1-T1.2 · `lda build` 端到端单命令 smoke（指标 M1）。

验证 `lda_design.goal_build` + `lda_design.cli` 的 `build` 子命令 ——
「一句话目标 → 设计包 → 版图 → GDS + DRC/LVS 签核」一条命令走完：

  ① **1 条命令**：`cli.main(['build', <随包示例 goal>, '--out', tmp]) == 0`，
     且 4 类产物落盘（.gds / .signoff.json / .signoff.md / .design_packages.json）
  ② **无参数给指引而非 traceback**：`cli.main(['build']) == 2`，输出含用法
     指引且**不含 Traceback**（P1-T1.2 验收判据 ②）
  ③ **失败路径友好**：goal 不存在 / 非法 JSON / 空 goal ⇒ rc=2 且无 traceback
  ④ **装配正确（两档口径，不混为一谈）**：
     ④a **几何字段实证** —— 桥接后设计值确实进了版图几何（Waveguide width）；
     ④b **独立测量一致** —— 仅限「设计量 ∩ lvs_geom 可回提量」（RingResonator R）
  ⑤ **同口径（单一来源）**：`.signoff.md` 的判决 == `.signoff.json` 的判决；
     `.gds` 文件字节数 == `summary.gds_bytes`
  ⑥ **D4 口径**：签核走的 LVS **含几何回提**（`geom_check` 非空且已核对参数 > 0）
  ⑦ **反向 A**：不可桥接的器件出现在 goal 的 design ⇒ **整体失败并指名**，
     **不静默丢器件**（静默丢 = 交出一份与目标不符的 GDS）
  ⑧ **反向 B**：`design.engine` 与 `kind` 不一致 ⇒ 必报（拒绝按不一致声明装配）
  ⑨ **诚实边界**：honest_notes 含关键边界；bridgeable ∪ unbridgeable == ENGINE_KINDS
  ⑩ **红线**：`goal_build.py` 源码零 LLM 引用（判决全死标量）
  ⑪ **文档不再漂移**：README 引用的示例 JSON 路径真实存在；`examples/README.md`
     的 `lda design` 示例用的是**真实签名**（`--target`，不是 `--kind/--params`）

运行：python run_cli_build_smoke.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_chain.link_model import LinkModel            # noqa: E402
from lda_chain.route_sim import layout_only           # noqa: E402
from lda_design import cli as _cli                    # noqa: E402
from lda_design import goal_build as gb               # noqa: E402
from lda_harness.smoke_kit import make_check          # noqa: E402
from lda_l2.chip_layout_export import device_geom_of  # noqa: E402
from lda_l2.lvs_geom import measure_device_params     # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

_EXAMPLE_GOAL = os.path.join(_HERE, "examples", "cli_build_goal.json")
_REPO = os.path.dirname(_HERE)


def _run_cli(argv):
    """原地跑 CLI，返回 (rc, stdout, stderr)（不抛异常）。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = _cli.main(argv)
        except SystemExit as e:                     # argparse 自身退出（用法错）
            rc = int(e.code or 0)
    return rc, out.getvalue(), err.getvalue()


def main() -> int:                                  # noqa: C901
    tmp = tempfile.mkdtemp(prefix="lda_cli_build_")
    try:
        # ---------------- ① 1 条命令 + 4 类产物 ----------------
        rc, so, se = _run_cli(["build", _EXAMPLE_GOAL, "--out", tmp])
        check("① 单命令 rc==0（一条命令走完 目标→设计包→版图→GDS→签核）",
              rc == 0, f"rc={rc} stderr={se.strip()[:120]!r}")

        name = "goal_ring_fsr"
        paths = {k: os.path.join(tmp, f"{name}.{v}") for k, v in (
            ("gds", "gds"), ("json", "signoff.json"), ("md", "signoff.md"),
            ("pkg", "design_packages.json"))}
        missing = [os.path.basename(p) for p in paths.values()
                   if not (os.path.exists(p) and os.path.getsize(p) > 0)]
        check("① 四类产物落盘且非空（.gds / .signoff.json / .signoff.md / .design_packages.json）",
              not missing, f"缺失/空：{missing}")

        sign = json.load(open(paths["json"], encoding="utf-8")) \
            if os.path.exists(paths["json"]) else {}
        summ = sign.get("summary") or {}
        md = open(paths["md"], encoding="utf-8").read() \
            if os.path.exists(paths["md"]) else ""

        # ---------------- ② 无参数 ⇒ 指引而非 traceback ----------------
        rc2, so2, se2 = _run_cli(["build"])
        blob2 = so2 + se2
        check("② 无参数 rc==2（用法错，不当成功）", rc2 == 2, f"rc={rc2}")
        check("② 无参数给可用指引（含用法/示例 goal 路径）",
              ("用法" in blob2) and ("cli_build_goal.json" in blob2))
        check("② 无参数**不含 Traceback**",
              "Traceback" not in blob2 and "KeyError" not in blob2)

        # ---------------- ③ 失败路径友好 ----------------
        rc3, o3, e3 = _run_cli(["build", os.path.join(tmp, "_nope.json")])
        check("③ goal 不存在 ⇒ rc=2 且无 traceback",
              rc3 == 2 and "Traceback" not in (o3 + e3), f"rc={rc3}")
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        rc4, o4, e4 = _run_cli(["build", bad])
        check("③ 非法 JSON ⇒ rc=2 且无 traceback",
              rc4 == 2 and "Traceback" not in (o4 + e4), f"rc={rc4}")
        empty = os.path.join(tmp, "empty.json")
        with open(empty, "w", encoding="utf-8") as fh:
            fh.write("{}")
        rc5, o5, e5 = _run_cli(["build", empty])
        check("③ 空 goal（无 devices）⇒ rc=2 且给指引（不抛异常）",
              rc5 == 2 and "Traceback" not in (o5 + e5)
              and "用法" in (o5 + e5), f"rc={rc5}")

        # ---------------- ④ 装配正确（两档口径，不混为一谈） ----------------
        # 🔴 引擎结果**缓存**：BraggMirror 闭环含 2D FDTD，约 19s/验证候选 ⇒
        #    本 smoke 一律 top_k=1 且**每类只跑一次**（否则 60s+ 拖垮 CI core）。
        cache, cok, cdet = {}, True, []
        for ek, (lk, km) in sorted(gb.BRIDGEABLE.items()):
            r = gb.design_device(lk, top_k=1)
            cache[lk] = r
            if not r.get("ok"):
                cok, cdet = False, cdet + [f"{lk} 引擎闭环失败：{r.get('error')}"]
                continue
            got = set(r.get("engine_params") or {})
            if not set(km) <= got:                       # 方向一：映射键必须都在
                cok, cdet = False, cdet + [f"{lk} 引擎输出缺 {sorted(set(km) - got)}"]
            if r.get("dropped_keys"):                    # 方向二：不得有未登记键被丢
                cok, cdet = False, cdet + [f"{lk} 未登记键将被丢弃 {r['dropped_keys']}"]
        check("④ 桥接表与引擎实际输出**双向**一致（映射键都在 · 无未登记键被静默丢弃）",
              cok, str(cdet[:3]))

        def _chip_fp(kind, params):
            """芯片级几何指纹（device_geom_of 输出 → 哈希）。"""
            lm = LinkModel(domain="photon", name="p")
            lm.add_device("d0", kind, params=dict(params))
            pl = layout_only(lm, wg_width=0.5)["placement"]
            g = device_geom_of(lm.ir.components[0], pl, 0.5)
            return hashlib.sha256(repr(
                [(x[0], x[1], x[2], tuple(x[3])) for x in g]).encode()).hexdigest()

        aok, adet = True, []
        for lk, r in sorted(cache.items()):
            base = dict(r.get("layout_params") or {})
            if not base:
                aok, adet = False, adet + [f"{lk}:桥接结果为空（等于没设计）"]
                continue
            f0 = _chip_fp(lk, base)
            for lk_key, val in base.items():
                pert = dict(base)
                pert[lk_key] = float(val) * 1.2 + (0.1 if float(val) == 0 else 0.0)
                if _chip_fp(lk, pert) == f0:
                    # 设计值改了、几何却纹丝不动 ⇒ 该参数**没进版图**（不许登记）
                    aok, adet = False, adet + [f"{lk}.{lk_key} 对几何不敏感"]
        check("④a 桥接准入门槛：每个映射参数都对**芯片级几何**敏感"
              "（改设计值 ⇒ 几何必变；不敏感即『没进版图』，不得登记为可桥接）",
              aok, str(adet[:3]))

        ring = cache.get("RingResonator") or gb.design_device("RingResonator", top_k=1)
        rlp = ring.get("layout_params") or {}
        rlm = LinkModel(domain="photon", name="p")
        rlm.add_device("d0", "RingResonator", params=rlp)
        m = measure_device_params("RingResonator", device_geom_of(
            rlm.ir.components[0],
            layout_only(rlm, wg_width=0.5)["placement"], 0.5))
        check("④b 独立测量一致（RingResonator 设计 R == lvs_geom 独立测得的 R）",
              ("R" in rlp) and abs(float(m.get("R", -1)) - float(rlp["R"])) < 1e-9,
              f"设计 {rlp.get('R')} / 测量 {m.get('R')}")

        # ④c 已知分歧登记（engine_waveguide 被排除的根因 · 机器化）
        from lda_l2.gds_export import geometry_desc
        chip_a = _chip_fp("Waveguide", {"width": 0.5})
        chip_b = _chip_fp("Waveguide", {"width": 0.9})
        dev_a = repr(geometry_desc("Waveguide", {"width": 0.5}))
        dev_b = repr(geometry_desc("Waveguide", {"width": 0.9}))
        check("④c 已知口径分歧登记：**芯片级** device_geom_of 忽略 Waveguide "
              "params['width']（改宽度几何不变）",
              chip_a == chip_b, "芯片级已开始读 width ⇒ 分歧被修")
        check("④c 同一分歧的另一半：**器件级** geometry_desc 确实读 width"
              "（两半同时成立 ⇒ 分歧真实存在，非本判据误述）",
              dev_a != dev_b)


        # ---------------- ⑤ 同口径（单一来源） ----------------
        v_ok = summ.get("verdict") == "ACCEPT"
        check("⑤ 判决同口径：.md 与 .signoff.json 的判决一致（且为 ACCEPT）",
              v_ok and ("**ACCEPT**" in md) and (summ.get("verdict") in md),
              f"json={summ.get('verdict')}")
        gsz = os.path.getsize(paths["gds"]) if os.path.exists(paths["gds"]) else -1
        check("⑤ .gds 文件字节数 == summary.gds_bytes",
              gsz == summ.get("gds_bytes"), f"file={gsz} json={summ.get('gds_bytes')}")

        # ---------------- ⑥ D4 口径（几何回提参与判决） ----------------
        lvs = sign.get("lvs_report") or {}
        gc = lvs.get("geom_check") or {}
        check("⑥ 签核含几何回提（G4 参与 ⇒ 连接 + 尺寸双一致即 D4 口径）",
              bool(gc) and int(gc.get("n_params_checked") or 0) > 0
              and not (gc.get("violations") or []),
              f"checked={gc.get('n_params_checked')} viol={len(gc.get('violations') or [])}")

        # ---------------- ⑦ 反向 A：不可桥接 ⇒ 整体失败并指名 ----------------
        bad_goal = {"domain": "photon", "name": "t",
                    "devices": [{"id": "ps0", "kind": "PhaseShifter",
                                 "design": {"target": 250.0}}]}
        asm = gb.assemble_goal(bad_goal)
        check("⑦ 反向 A：不可桥接器件 ⇒ 整体失败且**指名**（不静默丢器件）",
              (not asm["ok"]) and any("ps0" in e for e in asm["errors"]),
              f"errors={asm['errors'][:1]}")
        bom = gb.build_goal(bad_goal, tmp)
        check("⑦ 反向 A：stage==assemble 且不产出 GDS（宁失败不交付错版图）",
              bom.get("stage") == "assemble" and not (bom.get("report_paths") or {}),
              f"stage={bom.get('stage')}")

        # ---------------- ⑧ 反向 B：engine 与 kind 不一致 ⇒ 必报 ----------------
        # 🔴 必须挑**两个都已登记**的引擎，才能命中「不一致」分支；
        #    若挑未登记的（如 engine_waveguide）会落到 ⑦ 的同一分支 ⇒ 覆盖不到本判据
        mismatch = {"devices": [{"id": "ring", "kind": "RingResonator",
                                "design": {"engine": "engine_braggmirror",
                                           "target": 0.999}}]}
        am = gb.assemble_goal(mismatch)
        check("⑧ 反向 B：design.engine 与 kind 不一致 ⇒ 必报（拒绝按不一致声明装配）",
              (not am["ok"]) and any("ring" in e for e in am["errors"])
              and any("不一致" in e for e in am["errors"]),
              f"errors={am['errors'][:1]}")
        try:
            gb.resolve_engine_kind("RingResonator", "engine_braggmirror")
            raised = False
        except ValueError:
            raised = True
        check("⑧ 反向 B：resolve_engine_kind 对不一致组合必 raise", raised)

        # ---------------- ⑨ 诚实边界 + 互斥完备 ----------------
        hn = " ".join(sign.get("honest_notes") or [])
        keys = ("单一来源", "主权几何子集", "D5", "代码路径级独立")
        check("⑨ honest_notes 披露关键边界（单一来源/主权子集/D5/代码路径级独立）",
              all(k in hn for k in keys), f"命中={[k for k in keys if k in hn]}")
        from lda_design.design_package import ENGINE_KINDS
        bset, uset = set(gb.bridgeable_engine_kinds()), set(gb.unbridgeable_engine_kinds())
        check("⑨ bridgeable ∪ unbridgeable == ENGINE_KINDS（互斥且完备，无漏登记）",
              (bset & uset) == set() and (bset | uset) == set(ENGINE_KINDS),
              f"bridge={len(bset)} un={len(uset)} all={len(ENGINE_KINDS)}")
        dup = {}
        for _ek, (_lk, _km) in gb.BRIDGEABLE.items():
            dup.setdefault(_lk, []).append(_ek)
        check("⑨ 反向表唯一（同一版图 kind 不得对应多引擎 ⇒ 不静默选错）",
              all(len(v) == 1 for v in dup.values()), str({k: v for k, v in dup.items() if len(v) > 1}))

        # ---------------- ⑩ 红线：源码零 LLM ----------------
        src = open(os.path.join(_HERE, "lda_design", "goal_build.py"),
                   encoding="utf-8").read().lower()
        hits = [t for t in ("openai", "anthropic", "llm", "qwen", "prompt")
                if t in src]
        check("⑩ 红线：goal_build.py 源码零 LLM 引用（判决全死标量）",
              not hits, f"hits={hits}")

        # ---------------- ⑪ 文档不再漂移 ----------------
        readme = open(os.path.join(_REPO, "README.md"), encoding="utf-8").read()
        want = ["lda/examples/cli_check_example.json", "lda/examples/cli_build_goal.json"]
        absent = [w for w in want if w not in readme]
        check("⑪ README 引用的示例 JSON 用**完整路径**且不再少一层目录",
              not absent, f"未按完整路径出现：{absent}")
        check("⑪ README 引用的示例路径在仓库中真实存在",
              all(os.path.exists(os.path.join(_REPO, w)) for w in want))
        exr = open(os.path.join(_REPO, "examples", "README.md"), encoding="utf-8").read()
        dlines = [l.strip() for l in exr.splitlines() if l.strip().startswith("lda design")]
        check("⑪ examples/README.md 的 `lda design` 示例用真实签名（--target，无 --kind/--params）",
              bool(dlines) and all(("--target" in l) and ("--kind" not in l)
                                   and ("--params" not in l) for l in dlines),
              f"示例行={dlines}")
        check("⑪ 随包示例 goal 可解析且含 devices/design（干净 clone 可直接跑）",
              os.path.exists(_EXAMPLE_GOAL)
              and bool(json.load(open(_EXAMPLE_GOAL, encoding="utf-8")).get("devices")))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nlda build smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
