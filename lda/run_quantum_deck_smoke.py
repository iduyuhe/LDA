#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""量子 foundry deck 契约层 + 导入链 门禁 smoke（D-215 建 · D-225 扩 · 净增 0 锚）。

═══ 判什么（分六节 · 24 条）═══
A 模块自检（契约层 12 条 + 导入链 8 条）2 · B 键集与真源一致 2 · C 判决零漂移 3 ·
D 改限值必翻判 / 改元信息必不翻 3 · E 防自封与防错配 3 · F 序列化与红线 3 ·
**G 导入链 8**。

🔴 **本门禁的核心价值 = 证明这层"真接进了判决，但没接进判决的噪声"**：
  · C 组：用自建 deck 跑出的判决与直接传 `limits` **逐字相同**（不允许"接了个壳"）；
  · D1：把每模损耗限值收紧 ⇒ 同一设计必从 ACCEPT 翻 REJECT（证明限值真进判决）；
  · D2/D3：只改厂名/工艺/可信等级 ⇒ 判决与 violations **逐字不变**，只改 signoff 档
    （证明元信息**不参与比较**，符合"元数据不进判决路径"红线）。
  · E 组：`provenance=foundry_nda` 无凭据必拒 ⇒ **任何人不能靠手写字段自封对外签核**。
  · **G 组（v0.9.277 · D-225）**：把「deck 从哪来」也纳入判据 ——
    文件加载与 dict 加载必须等价（G1）· **sha256 必须与文件现算一致**（G2，加载器不虚报来源）·
    缺文件/坏 JSON/缺键各走具名错误、不静默回落（G3–G5）· env 通道正反两向且**与光子
    `LDA_FOUNDRY_DECK` 是两个变量**（G6）· **`loader` 段不进判决**（G7）· 域错配拒（G8）。

🔴 本门禁**不产生任何锚**、不改任何既有判决（自建 deck 与默认限值等价）。
🔴 导入链单独成模块（`quantum_deck_io.py`）而不是塞进契约层：D-215 刻意保持
   `quantum_deck.py` **零文件 IO**（F3 断言源码无 `open(`），契约层不该认识"文件"。
"""

from __future__ import annotations

import io
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check          # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_N = 5  # 参考设计规模（DFT 酉 → 矩形网格，10 片门 / 5 层）


def _read(rel):
    fp = os.path.join(_HERE, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def _ref_design():
    """参考设计：N=5 的 DFT 酉 → 矩形 Clements 网格 → 展平 ops（4 元组）。"""
    import numpy as np
    from lda_qeda import rect_mesh as RM

    k = np.arange(_N)
    U = np.exp(-2j * np.pi * np.outer(k, k) / _N) / np.sqrt(_N)
    layers, _phase = RM.rectangular_mesh_layers(U)
    ops = [(c, j, th, ph) for c, layer in enumerate(layers) for (j, th, ph) in layer]
    return {"ops": ops, "N": _N, "n_crossings": 0}


def main():
    from lda_qeda import quantum_deck as QD
    from lda_qeda import quantum_drc_lvs as QDR

    # ═══════════════ A 模块自检 ═══════════════
    # 🔴 突变下必须「判红」不得「崩溃」：M4（键集缩水）会让 build_deck 在自检内部显式抛，
    #    旧写法直接把整门禁打成 rc=99，后续判据全丢。任何异常都算"自检未通过"。
    try:
        _a1_ok = QD.run_selfchecks(verbose=False)
    except Exception:                          # noqa: BLE001
        _a1_ok = False
    check("A1 契约层自检 12/12 PASS", _a1_ok,
          "键集守恒·缺/多键·负值NaN·NDA凭据·等级天花板·厂名不改级·拒覆盖·域错配·空目标·披露串")

    from lda_qeda import quantum_deck_io as QDI
    try:
        _a2_ok = QDI.run_selfchecks(verbose=False)
    except Exception:                          # noqa: BLE001
        _a2_ok = False
    check("A2 导入链自检 8/8 PASS（v0.9.277 · D-225）", _a2_ok,
          "dict加载·loader只回带·无loader必抛·坏schema·缺键·域不符·env正反·确定性无时间戳")

    # ═══════════════ B 键集与真源 ═══════════════
    ph_keys = tuple(sorted(QDR.DEFAULT_DRC_LIMITS))
    from lda_qeda import sc_layout as SCL
    sc_keys = tuple(sorted(SCL.DEFAULT_DRC_LIMITS))
    check("B1 光子 deck 键集 ≡ quantum_drc_lvs 真源（%d 键）" % len(ph_keys),
          QD.domain_limit_keys("photonic") == ph_keys and len(ph_keys) == 10,
          "keys=%s" % (list(ph_keys),))
    check("B2 超导 deck 键集 ≡ sc_layout 真源（%d 键）" % len(sc_keys),
          QD.domain_limit_keys("superconducting") == sc_keys and len(sc_keys) == 3,
          "keys=%s" % (list(sc_keys),))

    # ═══════════════ C 判决零漂移（接壳 vs 真接）═══════════════
    design = _ref_design()
    direct = QDR.run_quantum_drc(design)
    via_deck = QD.drc_with_deck(design, QD.self_built_deck("photonic"))
    check("C1 自建 deck 判决 ≡ 直传 limits（判决位相同）",
          direct["verdict"] == via_deck["verdict"]
          and direct["n_rules"] == via_deck["n_rules"],
          "direct=%s/%d deck=%s/%d" % (direct["verdict"], direct["n_rules"],
                                       via_deck["verdict"], via_deck["n_rules"]))
    check("C2 violations 逐字相同（json 排序后相等）",
          json.dumps(direct.get("violations"), sort_keys=True)
          == json.dumps(via_deck.get("violations"), sort_keys=True),
          "n_direct=%d n_deck=%d" % (len(direct.get("violations") or []),
                                     len(via_deck.get("violations") or [])))
    check("C3 limits_used ≡ 真源默认限值（逐键相等）",
          via_deck["limits_used"] == {k: float(v) for k, v in QDR.DEFAULT_DRC_LIMITS.items()},
          "n_keys=%d" % len(via_deck["limits_used"]))

    # ═══════════════ D 改限值必翻判 / 改元信息必不翻 ═══════════════
    tight = QD.deck_limits(QD.self_built_deck("photonic"))
    tight["max_loss_per_mode_db"] = 1.0
    r_tight = QD.drc_with_deck(design, QD.build_deck("photonic", tight))
    rules = [v.get("rule") for v in (r_tight.get("violations") or [])]
    check("D1 每模损耗限值 15→1 dB ⇒ ACCEPT 必翻 REJECT（限值真进判决）",
          via_deck["verdict"] == "ACCEPT" and r_tight["verdict"] == "REJECT"
          and "QDR-LOSS-BUDGET" in rules,
          "acc=%s tight=%s rules=%s" % (via_deck["verdict"], r_tight["verdict"], rules[:3]))

    renamed = QD.build_deck("photonic", None, foundry="ANY-FOUNDRY",
                            process="ANY-PROCESS", version="v99",
                            provenance="self_built", note="只改元信息")
    r_renamed = QD.drc_with_deck(design, renamed)
    check("D2 只改厂名/工艺/版本 ⇒ 判决与 violations 逐字不变（元信息不进判决）",
          r_renamed["verdict"] == via_deck["verdict"]
          and json.dumps(r_renamed.get("violations"), sort_keys=True)
          == json.dumps(via_deck.get("violations"), sort_keys=True),
          "verdict=%s" % r_renamed["verdict"])

    pub = QD.build_deck("photonic", None, provenance="foundry_public",
                        note="公开近似层")
    r_pub = QD.drc_with_deck(design, pub)
    check("D3 降级到 foundry_public ⇒ 判决不变但签核档降为 AUDIT_ONLY",
          r_pub["verdict"] == via_deck["verdict"]
          and r_pub["signoff"]["tag"] == "AUDIT_ONLY"
          and r_pub["signoff"]["allow_external"] is False,
          "tag=%s" % r_pub["signoff"]["tag"])

    # ═══════════════ E 防自封与防错配 ═══════════════
    guard = 0
    for bad_kw in ({"provenance": "foundry_nda"},                       # 无凭据
                   {"provenance": "foundry_nda", "attestation": "   "},  # 空白凭据
                   {"provenance": "foundry_nda", "attestation": ""}):    # 空凭据
        try:
            QD.build_deck("photonic", **bad_kw)
        except ValueError:
            guard += 1
    check("E1 provenance=foundry_nda 无/空/空白凭据 三例均拒（防自封对外签核）",
          guard == 3, "guard=%d/3" % guard)

    sb = QD.build_deck("photonic", foundry="BigNameFoundry", provenance="self_built")
    check("E2 自建 deck 写大厂名仍恒 DESIGN_SIGNOFF 且 allow_external=False",
          QD.signoff_ceiling(sb)["tag"] == "DESIGN_SIGNOFF"
          and QD.signoff_ceiling(sb)["allow_external"] is False,
          "tag=%s" % QD.signoff_ceiling(sb)["tag"])

    sc_deck = QD.build_deck("superconducting")
    try:
        QD.drc_with_deck(design, sc_deck, rule_check="photonic")
        ok_mix = False
    except ValueError:
        ok_mix = True
    except Exception:                          # noqa: BLE001 — 突变下不得崩，但也不算护栏生效
        ok_mix = False
    check("E3 域错配（超导 deck 跑光子 DRC）必拒", ok_mix,
          "deck_domain=%s rule_check=photonic" % sc_deck.get("domain"))

    # ═══════════════ F 序列化与红线 ═══════════════
    rt = json.loads(json.dumps(QD.self_built_deck("photonic")))
    check("F1 deck JSON round-trip 零损失（可落盘/跨进程传递）",
          QD.deck_limits(rt) == QD.deck_limits(QD.self_built_deck("photonic")),
          "n_keys=%d" % len(rt["limits"]))

    src = _read(os.path.join("lda_qeda", "quantum_deck.py")).lower()
    banned = ("qiskit", "cirq", "pennylane", "qutip", "braket", "requests",
              "urllib", "socket", "openai", "anthropic")
    hit = [b for b in banned if ("import %s" % b) in src or ("from %s" % b) in src]
    check("F2 零第三方 / 零网络 / 零 LLM import（静态扫描）", not hit, "hit=%s" % hit)

    check("F3 契约层零文件 IO（无 open 调用 / 无 outputs 目录依赖）",
          ("open(" not in src and "outputs" not in src),
          "静态扫描 source")

    # ═══════════════ G 导入链（v0.9.277 · D-225）═══════════════
    import hashlib
    import shutil
    import tempfile

    tmpd = tempfile.mkdtemp(prefix="lda_qdeck_")
    try:
        sb = QD.self_built_deck("photonic")
        fp = os.path.join(tmpd, "deck_ph.json")
        payload = json.dumps(sb, ensure_ascii=False, indent=1).encode("utf-8")
        with open(fp, "wb") as fh:
            fh.write(payload)
        sha_want = hashlib.sha256(payload).hexdigest()

        by_file = QDI.load_quantum_deck(fp)
        by_dict = QDI.load_quantum_deck(sb)
        lp = QDI.loader_provenance(by_file)
        meta_keys = ("schema", "domain", "foundry", "process", "version",
                     "provenance", "note")

        check("G1 文件加载 ≡ dict 加载：限值逐键相同 ∧ meta 逐字段相同",
              by_file["limits"] == by_dict["limits"]
              and all(by_file[k] == by_dict[k] for k in meta_keys),
              "n_keys=%d" % len(by_file["limits"]))

        check("G2 加载器 sha256 ≡ 文件现算 ∧ source=file ∧ 记 basename（不虚报来源）",
              lp["sha256"] == sha_want and lp["source"] == "file"
              and lp["basename"] == "deck_ph.json" and lp["env_var"] is None,
              "sha=%s… want=%s…" % (str(lp["sha256"])[:12], sha_want[:12]))

        try:
            QDI.load_quantum_deck(os.path.join(tmpd, "nope.json"))
            g3 = False
        except FileNotFoundError:
            g3 = True
        check("G3 文件不存在 ⇒ FileNotFoundError（不静默回落自建 deck）", g3)

        fbad = os.path.join(tmpd, "bad.json")
        with open(fbad, "wb") as fh:
            fh.write(b'{"schema": "lda_quantum_foundry_deck_v1",')
        try:
            QDI.load_quantum_deck(fbad)
            g4 = False
        except ValueError as exc:
            g4 = ("JSON" in str(exc) and "行" in str(exc))
        check("G4 非法 JSON ⇒ ValueError 且带行列（不吐裸 JSONDecodeError）", g4)

        fmiss = os.path.join(tmpd, "missing_key.json")
        broken = json.loads(json.dumps(sb))
        broken["limits"].pop(sorted(broken["limits"])[0])
        with open(fmiss, "w", encoding="utf-8") as fh:
            json.dump(broken, fh, ensure_ascii=False)
        try:
            QDI.load_quantum_deck(fmiss)
            g5 = False
        except ValueError as exc:
            g5 = "键集" in str(exc)
        check("G5 文件缺键 ⇒ ValueError（键集守恒不被文件路径绕开）", g5)

        _old_env = os.environ.pop(QDI.ENV_DECK_VAR, None)
        os.environ[QDI.ENV_DECK_VAR] = fp
        try:
            via_env = QDI.load_quantum_deck_from_env()
            env_ok = (via_env is not None
                      and QDI.loader_provenance(via_env)["env_var"] == QDI.ENV_DECK_VAR
                      and via_env["limits"] == sb["limits"])
            os.environ.pop(QDI.ENV_DECK_VAR, None)
            env_none = QDI.load_quantum_deck_from_env() is None
            try:
                QDI.load_quantum_deck_from_env(required=True)
                env_req = False
            except FileNotFoundError:
                env_req = True
        finally:
            os.environ.pop(QDI.ENV_DECK_VAR, None)
            if _old_env is not None:
                os.environ[QDI.ENV_DECK_VAR] = _old_env
        try:
            from lda_l2 import soc_tapeout_signoff as STS
            ph_env = STS.ENV_DECK_VAR
        except Exception:                      # noqa: BLE001 — 取不到真源就判红，不静默
            ph_env = None
        check("G6 env 通道：%s 生效 ∧ 未设返 None ∧ required 抛 ∧ 与光子 %s 是两个变量"
              % (QDI.ENV_DECK_VAR, ph_env),
              env_ok and env_none and env_req
              and ph_env is not None and QDI.ENV_DECK_VAR != ph_env,
              "env_ok=%s none=%s req=%s photo_var=%s"
              % (env_ok, env_none, env_req, ph_env))

        r_file = QD.drc_with_deck(design, by_file)
        r_dict = QD.drc_with_deck(design, by_dict)
        check("G7 文件加载的 deck 判决 ≡ 程序内构造同限值 deck（loader 段不进判决）",
              r_file["verdict"] == r_dict["verdict"]
              and json.dumps(r_file.get("violations"), sort_keys=True)
              == json.dumps(r_dict.get("violations"), sort_keys=True),
              "verdict=%s" % r_file["verdict"])

        try:
            QDI.load_quantum_deck(fp, expected_domain="superconducting")
            g8 = False
        except ValueError:
            g8 = True
        check("G8 expected_domain 不符 ⇒ 拒（防拿超导 deck 跑光子 DRC）", g8)
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("量子 foundry deck 契约层 门禁 smoke（D-215）：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
