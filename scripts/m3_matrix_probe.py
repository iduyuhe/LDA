#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3 横向交叉验证矩阵 smoke 的**突变探针**（人工运行，刻意不进 CI core）。

目的（呼应项目血案 25 / 32：护栏必须真能变红，且还原须字节级一致）：
  ① 证明矩阵 smoke 的判据不是恒真自证（mutate -> 必红）；
  ② 证明还原源码后 sha256 与原始逐字节一致（release 即绿）。

两类突变：
  A. 把一个 convergent 格的 tol_rel 改到不可能小（1e-20）=> 判据 D 必失败 => smoke 退出码 != 0
  B. 从 CELL_DOMAIN 删掉 X11 的域标签 => 判据 ⑦a 双向完备必失败 => 退出码 != 0

用**二进制**读写源码：不做换行翻译，保证还原 sha256 逐字节一致。
"""
import hashlib
import subprocess
import sys

SRC = "D:/agent_LDA/lda/run_cross_solver_matrix_smoke.py"
PY = "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
ENV = {"PYTHONPATH": "D:/agent_LDA/lda", "PYTHONIOENCODING": "utf-8"}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text():
    with open(SRC, "rb") as f:
        return f.read().decode("utf-8")


def write_text(text):
    with open(SRC, "wb") as f:
        f.write(text.encode("utf-8"))


def run_smoke():
    # 用字节模式捕获，避免中文输出触发 locale 解码错误
    p = subprocess.run([PY, SRC], env=ENV, capture_output=True)
    return p.returncode


def mutate(text, old, new):
    assert old in text, "mutation anchor not found: %r" % old
    return text.replace(old, new, 1)


def main():
    orig_sha = sha256_of(SRC)
    print("[probe] original sha256 = %s" % orig_sha)

    results = []

    # ---- Mutation A: tol_rel -> impossible (判据 D 必失败) ----
    text = read_text()
    text_a = mutate(text, '1e-1, "probe": _p_pn_e,', '1e-20, "probe": _p_pn_e,')
    write_text(text_a)
    rc = run_smoke()
    red_a = rc != 0
    print("[probe-A] tol_rel X11 -> 1e-20 : rc=%d  RED=%s" % (rc, red_a))
    results.append(("A: tol_rel impossible", red_a))
    write_text(text)  # restore
    assert sha256_of(SRC) == orig_sha, "restore A failed (sha mismatch)"

    # ---- Mutation B: drop X11 domain label (判据 ⑦a 必失败) ----
    text = read_text()
    text_b = mutate(text, '    "X11-PN-DD": "quantum",\n', "")
    write_text(text_b)
    rc = run_smoke()
    red_b = rc != 0
    print("[probe-B] drop X11 domain label : rc=%d  RED=%s" % (rc, red_b))
    results.append(("B: drop domain label", red_b))
    write_text(text)  # restore
    assert sha256_of(SRC) == orig_sha, "restore B failed (sha mismatch)"

    final_sha = sha256_of(SRC)
    print("[probe] final   sha256 = %s" % final_sha)
    ok = all(red for _, red in results) and final_sha == orig_sha
    for name, red in results:
        print("  %-28s %s" % (name, "RED OK" if red else "GREEN (dead guard!)"))
    print("[probe] byte-identical restore: %s" % ("OK" if final_sha == orig_sha else "FAIL"))
    if not ok:
        print("[probe] FAIL: a guard did not turn red or restore mismatch")
        sys.exit(1)
    print("[probe] PASS: both guards turn red + source restored byte-identical")
    sys.exit(0)


if __name__ == "__main__":
    main()
