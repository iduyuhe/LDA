"""P3 门禁突变探针（v0.9.132）—— 证明 P3 两个新门禁的判据**会响**。

⚠️ **本脚本只作人工运行，不进 CI core**。理由同 `scripts/p2_usability_probe.py`：
它靠「改工作区文件 → 跑门禁 → 按原字节还原」取证，若中途异常退出可能留下被改坏的
门禁源码。CI 里跑这种自改脚本风险不对等（门禁本身每次都跑，探针只需在改门禁时人工跑）。

用法（仓库根）：python scripts/p3_matrix_probe.py   → 10/10 全响则 rc=0

铁律：「没被验证过的护栏不算护栏」。本脚本对每条高价值判据各造一个**真实反例**
（改的是**门禁自己的源码**），跑门禁断言「恰好该判据变红」，然后**按原字节还原**并用
sha256 复核（不留污染）。
"""
import hashlib
import os
import subprocess
import sys

ROOT = r"D:/agent_LDA"
LDA = os.path.join(ROOT, "lda")
PY = sys.executable
MATRIX = "run_cross_solver_matrix_smoke.py"
SCORING = "run_adversarial_scoring_smoke.py"


def _read_bytes(rel):
    return open(os.path.join(ROOT, rel), "rb").read()


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def run_smoke(name):
    r = subprocess.run([PY, os.path.join(LDA, name)], capture_output=True,
                       text=True, errors="replace", cwd=LDA,
                       env=dict(os.environ, PYTHONPATH=LDA))
    fails = [ln.strip() for ln in r.stdout.splitlines() if "[FAIL]" in ln]
    return r.returncode, fails


# --------------------------- 反例构造（矩阵门禁） ---------------------------
def _drop_three_cells(b):
    """删掉 3 个格 ⇒ 格数 9→6 边界，再删一个 ⋯ 直接删到 5 个。"""
    for cid in (b'"id": "X6-MZM-VPI"', b'"id": "X5-LINDBLAD"',
                b'"id": "X4-RESONATOR"', b'"id": "X7-MMI-EXCESS"'):
        i = b.find(cid)
        if i < 0:
            continue
        # 往前找到该 dict 的起始 "    {\n"
        j = b.rfind(b"    {", 0, i)
        # 往后找到配对的 "    },\n"（本文件的格都是这个缩进结尾）
        k = b.find(b"\n    },\n", i)
        if j >= 0 and k > 0:
            b = b[:j] + b[k + len(b"\n    },\n"):]
    return b


def _shuffle_bragg_values(b):
    """把 X1 的 N 序列改成乱序 ⇒ 残差不再严格单调降。"""
    return b.replace(b'"values": (120, 240, 480),', b'"values": (480, 120, 240),', 1)


def _fake_convergent(b):
    """把 M1（残差不随 N 变）的 kind 谎报成 convergent ⇒ 判据 D 必红。"""
    return b.replace('"kind": "model_limited", "param": "N(电荷基截断)"'.encode("utf-8"),
                     '"kind": "convergent", "param": "N(电荷基截断)"'.encode("utf-8"), 1)


def _insert_backend_swap(b):
    """把 X1 的 solver_b 改写成含 numba 的「换后端」表述 ⇒ 独立性格必红。"""
    return b.replace('"solver_b": "反周期 Bloch 广义本征值（全波谱，动力学）"'.encode("utf-8"),
                     '"solver_b": "反周期 Bloch 广义本征值（numba 加速后端）"'.encode("utf-8"), 1)


def _drop_excluded_field(b):
    """删掉 E1 的 repro 字段 ⇒ 否决项登记完备性必红。"""
    return b.replace('"repro": "见 ⑩：扫 (0.02, 0.01, 0.005)，断言**不**严格单调",'.encode("utf-8"),
                     b"", 1)


def _make_e1_monotone(b):
    """把 E1 的 dl 扫描改成**严格递减序** ⇒ 残差看起来在收敛 ⇒「否决理由可复现」必红。

    🔴 首版写成「简单倒序 (0.005, 0.01, 0.02)」—— 那只让序列变成
    5.913e-3 → 1.178e-2 → 1.016e-3，**仍不是**严格单调 ⇒ 判据照样绿、探针误报
    「恒真」（探针自己的假阴性）。要翻红必须让残差**严格递减**：实测三点
    rel = 1.016e-3(dl=.02) / 1.178e-2(dl=.01) / 5.913e-3(dl=.005) ⇒
    取 (0.01, 0.005, 0.02) 得 1.178e-2 → 5.913e-3 → 1.016e-3 **严格递减** ✓
    —— 而这正是该判据要拦的「把顺序排成看起来收敛」。
    """
    return b.replace(b"for dl in (0.02, 0.01, 0.005):",
                     b"for dl in (0.01, 0.005, 0.02):", 1)


def _drop_domain_row(b):
    """从域标签表删掉 X6 一行 ⇒ ⑦a「双向完备」必红（注册格漏标域）。

    「标签≠行为」同型：旧判据用 id 前缀硬编码筛域，X6（MZM · 光子器件）
    落在两组之外而判据照绿；新判据要求**每格都有标签**，漏一行即红。
    """
    return b.replace(b'    "X6-MZM-VPI": "photonic",\n', b"", 1)


# --------------------------- 反例构造（判分门禁） ---------------------------
def _unregister_unscorable(b):
    """把 A-BEND-R2 的理由键名改掉 ⇒ 该题落进 UNHANDLED ⇒ disposition 判据红。"""
    return b.replace(b'"A-BEND-R2": (', b'"A-BEND-R2_PROBE": (', 1)


def _trap_becomes_correct(b):
    """把 A-TAPER-FAST 的第一个陷阱答案换成**正确值** ⇒「错答必不通过」必红。"""
    return b.replace('("绝热极限高估：T=1.0（忽略非绝热损耗）", lambda g, t: 1.0),'.encode("utf-8"),
                     '("伪装成陷阱的正确答案", lambda g, t: 0.99862085),'.encode("utf-8"), 1)


def _reason_without_gap(b):
    """把 A-BEND-R2 理由里的「缺项：」抹掉 ⇒「含缺项指认」必红。"""
    return b.replace("缺项：**共形变换/辐射边界下的弯曲模损耗求解器**。".encode("utf-8"),
                     "本项暂不处理。".encode("utf-8"), 1)


PROBES = [
    # (标题, 目标文件, 反例构造, 期望变红的判据片段, 跑哪个门禁)
    ("矩阵只剩 5 格（跌破 M3 ≥6）", MATRIX, _drop_three_cells,
     "① 矩阵格数 ≥6", MATRIX),
    ("X1 的 N 序列倒序 ⇒ 判据 D 不再单调", MATRIX, _shuffle_bragg_values,
     "⑵ X1-BRAGG 有判据 D", MATRIX),
    ("把 model_limited 格谎报成 convergent", MATRIX, _fake_convergent,
     "⑵ M1-TRANSMON-KOCH 有判据 D", MATRIX),
    ("把 solver_b 换成 numba 后端口径", MATRIX, _insert_backend_swap,
     "③ X1-BRAGG 方法学独立声明非空且不含换后端字样", MATRIX),
    ("删掉实测否决项 E1 的 repro 字段", MATRIX, _drop_excluded_field,
     "⑨ 实测否决项登记完备", MATRIX),
    ("E1 的 dl 扫描改成正序 ⇒ 否决理由失效", MATRIX, _make_e1_monotone,
     "⑩ E1-SLAB-TE 否决理由可复现", MATRIX),
    ("域标签表删掉 X6 一行 ⇒ 格漏标域", MATRIX, _drop_domain_row,
     "⑦a 域标签表", MATRIX),
    ("不可判分题未登记 disposition", SCORING, _unregister_unscorable,
     "② 每题 disposition 都已判定", SCORING),
    ("把陷阱答案换成正确答案", SCORING, _trap_becomes_correct,
     "④ A-TAPER-FAST 反向", SCORING),
    ("不可判分理由里抹掉「缺项」指认", SCORING, _reason_without_gap,
     "⑤ A-BEND-R2 不可判分理由含", SCORING),
]


def main():
    print("=" * 76)
    print("P3 门禁突变探针 —— 每条判据造一个真实反例（改门禁源码），看它会不会响")
    print("=" * 76)

    # 基线：两个门禁都必须全绿
    for name in (MATRIX, SCORING):
        rc, fails = run_smoke(name)
        print("\n[基线] %s rc=%d · FAIL %d 条 %s" % (name, rc, len(fails), fails[:3]))
        assert rc == 0 and not fails, "基线必须全绿，否则先修门禁"

    ok_all = True
    for title, rel, mut, want, smoke in PROBES:
        path = os.path.join(LDA, rel)
        raw = _read_bytes(os.path.join("lda", rel))
        before = _sha(raw)
        try:
            new = mut(raw)
            assert new != raw, "反例构造未命中任何字节（探针自身缺陷）：%s" % title
            open(path, "wb").write(new)
            rc, fails = run_smoke(smoke)
            hit = any(want in f for f in fails)
            extra = [f for f in fails if want not in f]
            print("\n[%s] %s" % ("✅ 会响" if hit else "❌ 恒真（不响）", title))
            print("    目标判据: %s" % want)
            print("    连带变红 %d 条%s" % (len(extra),
                                        ("：" + " | ".join(x[:64] for x in extra[:3]))
                                        if extra else ""))
            ok_all = ok_all and hit
        finally:
            cur = _read_bytes(os.path.join("lda", rel))
            if _sha(cur) != before:
                open(path, "wb").write(raw)
            after = _sha(_read_bytes(os.path.join("lda", rel)))
            assert after == before, "还原失败！%s %s != %s" % (rel, after, before)
            print("    还原 ✓ sha256 %s" % after)

    # 收尾：全量复查
    for name in (MATRIX, SCORING):
        rc, fails = run_smoke(name)
        print("\n[收尾复查] %s rc=%d · FAIL %d 条" % (name, rc, len(fails)))
        ok_all = ok_all and rc == 0 and not fails
    print("\n探针结论：%s" % ("全部判据都会响 ✅" if ok_all else "存在恒真判据 ❌"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
