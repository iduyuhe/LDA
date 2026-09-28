"""P5 门禁突变探针（v0.9.138）—— 证明 P5 新门禁的判据**会响**。

⚠️ **本脚本只作人工运行，不进 CI core**。理由同 `scripts/p2_usability_probe.py` /
`scripts/p3_matrix_probe.py`：它靠「改工作区文件 → 跑门禁 → 按原字节还原」取证，
若中途异常退出可能留下被改坏的源码。CI 里跑这种自改脚本风险不对等。

用法（仓库根）：python scripts/p5_probe.py   → 全响则 rc=0

覆盖两组门禁：
  A. **M6 实证锚门禁**（`lda/run_empirical_anchor_smoke.py` 判据⑩）
  B. **pytest 双入口契约**（`tests/`，T5.1/T5.2）

每条探针各造一个**真实反例**（改的是被测产物本身，而不是判据的阈值），
断言「**恰好**该判据变红」，然后按原字节还原并 sha256 复核（不留污染）。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

ROOT = r"D:/agent_LDA"
LDA = os.path.join(ROOT, "lda")
PY = sys.executable
SEED = "lda/lda_harness/seed_empirical.json"
M6MOD = "lda/lda_harness/empirical_m6.py"
CIMOD = "lda/run_ci_regression.py"
PYPROJ = "pyproject.toml"

#: pytest 在当前共享 venv 里可能被无关三方插件（langsmith 等）拖崩，
#: 故禁用第三方插件自动加载。LDA 的 tests/ 不依赖任何三方插件。
_PYTEST_ENV = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONPATH=LDA)


# --------------------------------------------------------------------- 工具
def _read_b(rel: str) -> bytes:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return f.read()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def _write_b(rel: str, b: bytes) -> None:
    with open(os.path.join(ROOT, rel), "wb") as f:
        f.write(b)


def _run_smoke(name: str):
    r = subprocess.run([PY, os.path.join(LDA, name)], capture_output=True,
                       text=True, errors="replace", cwd=LDA,
                       env=dict(os.environ, PYTHONPATH=LDA))
    fails = [ln.strip() for ln in r.stdout.splitlines() if "[FAIL]" in ln]
    return r.returncode, fails


def _run_pytest(node: str):
    r = subprocess.run([PY, "-m", "pytest", "-q", node], capture_output=True,
                       text=True, errors="replace", cwd=ROOT, env=_PYTEST_ENV)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ------------------------------------------------------------- 反例构造器
def _seed(inner):
    """把「改 dict」的构造器包成「bytes → bytes」。"""
    def _f(b: bytes, arg=None) -> bytes:
        d = json.loads(b.decode("utf-8"))
        d = inner(d, arg) if arg is not None else inner(d)
        return json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8")
    return _f


def _seed_drop_to(d: dict, keep: int) -> dict:
    d["corpus"] = d["corpus"][:keep]
    return d


def _seed_strip_locator(d: dict, _=None) -> dict:
    """把一条语料改成 B 级（无 DOI/arXiv/公开 URL）⇒ M6-3/M6-4 必红。"""
    for x in d["corpus"]:
        if x["id"] == "E-SOI-PL-36":
            x["citation"] = "某公开文献典型量级（无定位符）"
            x["source_url"] = ""
            break
    return d


def _seed_empty_geometry(d: dict, _=None) -> dict:
    """清空一条**当前确实有 geometry** 的语料 ⇒ M6-5 必红。

    🔴 **锚点选择纪律**：必须挑一条 geometry **非空**的条目。本轮踩坑——
    原锚点 `E-TBOX-PL-TE` 的 geometry 彼时**已经是 `{}`**，`{} → {}` 是 no-op
    ⇒ 被新加的全局 no-op 守卫当场抓住（附原写死 `\\n`/CRLF 坑，两次都属静默失败）。
    这里改为**先找一条真正非空的**，找不到就显式抛错。
    """
    for x in d["corpus"]:
        if x["id"] == "E-TBOX-PL-TE" and (x.get("geometry") or {}):
            x["geometry"] = {}
            return d
    # 兜底：任选一条非空几何的语料（防未来 seed 变动使锚点失效）
    for x in d["corpus"]:
        if (x.get("geometry") or {}):
            x["geometry"] = {}
            return d
    raise RuntimeError("探针锚点未命中：语料库中找不到任何带 geometry 的条目")


def _seed_break_engine_input(d: dict, _=None) -> dict:
    """抽掉独立对照 E-RING-FSR 的 w_core_um ⇒ 引擎抛 KeyError ⇒ 出现 error 行。"""
    for x in d["corpus"]:
        if x["id"] == "E-RING-FSR":
            x["geometry"].pop("w_core_um", None)
            break
    return d


def _seed_blow_up_rels(d: dict, _=None) -> dict:
    """把 rel 最小的 5 条对照的实测值改到离谱 ⇒ 「rel ≤25% 条数」跌破地板。"""
    bad = {"E-GRATING-EFF", "E-SIN-NG-300", "E-SOI-CROSS-XT",
           "E-SOI-NG-220", "E-GE-PD-RESP"}
    for x in d["corpus"]:
        if x["id"] in bad:
            x["measured_value"] = float(x["measured_value"]) * 9.0 + 7.0
    return d


def _text_recategorize_to_anchor(b: bytes, _=None) -> bytes:
    """把 4 条 independent 改标 calibration_anchor ⇒ 计入数跌破 12。"""
    out = b
    for eid in (b'"E-SIN-NG-300"', b'"E-SOI-NG-220"',
                b'"E-RING-FSR"', b'"E-TBOX-FSR-TE"'):
        i = out.find(eid)
        if i < 0:
            raise RuntimeError(f"探针锚点未命中：语料/登记表缺 {eid!r}")
        j = out.find(b'"kind": "independent"', i)
        if j < 0:
            raise RuntimeError(f"探针锚点未命中：{eid!r} 后无 \"kind\": \"independent\"")
        out = (out[:j] + b'"kind": "calibration_anchor"'
               + out[j + len(b'"kind": "independent"'):])
    return out


def _text_inject_ghost_member(b: bytes, _=None) -> bytes:
    """往 CORE_SMOKES 注入一个**不存在**的成员 ⇒ 幽灵假绿通道。"""
    anchor = b'CORE_SMOKES: List[str] = [\n'
    if anchor not in b:
        raise RuntimeError("探针锚点未命中：run_ci_regression.py 无 "
                           "CORE_SMOKES 列表头（EOL 变了？）")
    return b.replace(
        anchor,
        anchor + b'    "run_p5_probe_ghost_smoke.py",  # PROBE\n', 1)


def _text_drop_default_deselect(b: bytes, _=None) -> bytes:
    old = b'addopts = "-m \'not smoke\' --strict-markers"'
    if old not in b:
        raise RuntimeError("探针锚点未命中：pyproject 无默认档 addopts")
    return b.replace(old, b'addopts = "--strict-markers"', 1)


def _text_drop_package(b: bytes, _=None) -> bytes:
    """删一个包登记 ⇒ 装出来会缺模块 ⇒ 打包契约必红。

    🔴 **EOL 陷阱（本探针首次实跑即踩中）**：`pyproject.toml` 是 **CRLF** 文件，
    而 `lda/*.py` 是 LF。早先锚点硬编码 `\\n` ⇒ `replace` **静默不命中**、
    字节未变 ⇒ 探针跑完「没红」而被记为**假绿**（假绿方向恰好是「误判门禁无效」）。
    现改为**两种 EOL 都试**，且命中数为 0 时显式抛错（不再静默通过）。
    """
    for eol in (b"\r\n", b"\n"):
        anchor = b'    "lda_qeda",' + eol
        if anchor in b:
            return b.replace(anchor, b'', 1)
    raise RuntimeError("探针锚点未命中：pyproject 无 '    \"lda_qeda\",'（EOL 变了？）")


def _text_make_selfcert_stub(b: bytes, _=None) -> bytes:
    """把一条 independent 对照改成「输出＝实测值」的自证桩（模拟引擎里藏答案）。"""
    old = (b'    return [_evaluate(eid, spec, corpus, raw_by_id)\n'
           b'            for eid, spec in sorted(targets.items())]')
    new = (b'    _rows = [_evaluate(eid, spec, corpus, raw_by_id)\n'
           b'             for eid, spec in sorted(targets.items())]\n'
           b'    for _r in _rows:  # PROBE: self-cert stub (computed := measured)\n'
           b'        if _r.get("ok") and _r["id"] == "E-RING-FSR":\n'
           b'            _r["computed"] = _r["measured"]\n'
           b'    return _rows')
    if old not in b:
        raise RuntimeError("探针锚点未命中（empirical_m6.py 已改动？）")
    return b.replace(old, new, 1)


# ------------------------------------------------------------------- 探针表
# (名称, [(文件, 变更函数, 参数)], runner, 期望变红的判据子串, 说明)
PROBES = [
    ("M6-1 语料条数跌破 60", [(SEED, _seed(_seed_drop_to), 59)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-1",
     "截到 59 条 ⇒ 条数下限必红"),
    ("M6-3 混入 B 级（无定位符）语料", [(SEED, _seed(_seed_strip_locator), None)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-3",
     "抽掉 DOI/URL ⇒ A 级 100% 门禁必红"),
    ("M6-5 语料缺 geometry", [(SEED, _seed(_seed_empty_geometry), None)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-5",
     "清空 geometry ⇒ 「对照可复算前提」必红"),
    ("M6-9 对照无法执行（缺输入几何）", [(SEED, _seed(_seed_break_engine_input), None)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-9",
     "抽掉 w_core_um ⇒ 引擎抛错 ⇒ error 行必红"),
    ("M6-7 计入对照数跌破 12", [(M6MOD, _text_recategorize_to_anchor, None)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-7",
     "4 条 independent 改标标定锚 ⇒ 计入数必红"),
    ("M6-10 对照质量地板（rel 分布恶化）", [(SEED, _seed(_seed_blow_up_rels), None)],
     ("smoke", "run_empirical_anchor_smoke.py"), "M6-10",
     "5 条 rel 打到离谱 ⇒ 地板必红"),
    ("T5.1 幽灵成员（不存在的 CORE_SMOKES 项）",
     [(CIMOD, _text_inject_ghost_member, None)],
     ("pytest", "tests/test_ci_entry_contract.py"), "test_core_smokes_members_exist",
     "登记一条不存在的 smoke ⇒ 契约必红（防账本 +1、从未执行）"),
    ("T5.1 默认档未排除 smoke", [(PYPROJ, _text_drop_default_deselect, None)],
     ("pytest", "tests/test_ci_entry_contract.py"),
     "test_smoke_marker_registered_and_deselected_by_default",
     "删掉 -m 'not smoke' ⇒ 默认档会裸跑 200+ 子进程 ⇒ 必红"),
    ("T5.2 声明包集与真实包集失配", [(PYPROJ, _text_drop_package, None)],
     ("pytest", "tests/test_packaging_contract.py"),
     "test_declared_packages_match_real_packages",
     "删一个包登记 ⇒ 装出来会缺模块 ⇒ 必红"),
    ("M6 独立性（引擎里藏答案＝自证桩）", [(M6MOD, _text_make_selfcert_stub, None)],
     ("pytest", "tests/test_m6_empirical.py"),
     "test_independent_comparisons_do_not_read_measured_value",
     "让 computed:=measured ⇒ 扰动实测值后输出会动 ⇒ 必红"),
]


# --------------------------------------------------------------------- 主流程
def main() -> int:
    n_ok = 0
    print("=" * 78)
    print("P5 门禁突变探针 —— 每条判据都要证明「会响」")
    print("=" * 78)

    for name, edits, runner, expect, why in PROBES:
        originals = {}
        ok = False
        detail = ""
        try:
            for rel, fn, arg in edits:
                originals[rel] = _read_b(rel)
                mutated = fn(originals[rel], arg)
                # 🔴 静默 no-op 守卫（本探针首次实跑即踩中过：CRLF 文件 + 硬编码 \n
                # 的锚点 ⇒ replace 不命中 ⇒ 字节未变 ⇒ 门禁自然「不红」⇒
                # 探针把它误记为「判据假绿」。方向极坏：会让人误以为门禁没用。）
                if mutated == originals[rel]:
                    raise RuntimeError(
                        f"[{rel}] 突变是 no-op（字节未变）——锚点未命中或 EOL 不符")
                _write_b(rel, mutated)
            if runner[0] == "smoke":
                rc, fails = _run_smoke(runner[1])
                hit = [f for f in fails if expect in f]
                rc_bad = rc != 0
            else:
                rc, out = _run_pytest(runner[1])
                hit = [ln for ln in out.splitlines() if expect in ln]
                rc_bad = rc != 0
            ok = bool(hit) and rc_bad
            detail = (f"命中：{hit[0][:96]}" if hit else "**判据未响应（假绿）**")
        except Exception as e:  # noqa: BLE001
            detail = f"探针自身异常：{type(e).__name__}: {e}"
        finally:
            # 按原字节还原 + sha256 复核（不留污染）
            bad = [rel for rel, blob in originals.items()
                   if (_write_b(rel, blob) or _sha(_read_b(rel)) != _sha(blob))]
            if bad:
                print(f"  [FAIL] {name} —— 还原失败！工作区可能已被污染：{bad}")
                return 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print(f"          期望判据：{expect} · {why}")
        print(f"          {detail}")
        n_ok += 1 if ok else 0

    print("-" * 78)
    print(f"P5 突变探针：{n_ok}/{len(PROBES)} 判据被证明会响")
    return 0 if n_ok == len(PROBES) else 1


if __name__ == "__main__":
    sys.exit(main())
