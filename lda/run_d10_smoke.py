#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-10 实测语料补登工具冒烟（纯静态，CI 友好）。

覆盖：submit --out issue 生成 markdown；submit --out bank 追加 + 去重；
validate 命令；缺 citation 校验失败。
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lda_harness.empirical_submit as es  # noqa: E402


def run_capture(argv):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = es.main(argv)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def main():
    # 1) issue 输出含关键字段
    rc, out = run_capture([
        "submit", "--id", "E-D10-TEST", "--device", "test wg",
        "--metric", "n_eff", "--measured_value", "2.50",
        "--uncertainty_abs", "0.02", "--fab_source", "test fab",
        "--citation", "test cite", "--out", "issue",
    ])
    assert rc == 0, rc
    assert "E-D10-TEST" in out and "test cite" in out, out
    print("[1] issue markdown OK")

    # 2) 缺 citation → 校验失败 rc=2
    rc, _ = run_capture([
        "submit", "--id", "E-NOCITE", "--device", "x", "--metric", "n_eff",
        "--measured_value", "1", "--uncertainty_abs", "0.1",
        "--fab_source", "x", "--citation", "", "--out", "issue",
    ])
    assert rc == 2, rc
    print("[2] missing-citation rejected OK")

    # 3) bank 追加 + 去重（重复 id 不覆盖）
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        f.write('{"corpus": []}')
        bank = f.name
    try:
        rc, out = run_capture([
            "submit", "--id", "E-BANK-1", "--device", "d1", "--metric", "fsr",
            "--measured_value", "10.0", "--uncertainty_abs", "0.1",
            "--fab_source", "f", "--citation", "c", "--out", "bank",
            "--bank", bank, "--contributor", "dr-su",
        ])
        assert rc == 0 and "added" in out, out
        # 重复 id（不同值）→ conflict，原值保留
        rc, out = run_capture([
            "submit", "--id", "E-BANK-1", "--device", "d1", "--metric", "fsr",
            "--measured_value", "99.9", "--uncertainty_abs", "0.1",
            "--fab_source", "f", "--citation", "c", "--out", "bank",
            "--bank", bank,
        ])
        assert rc == 0 and "conflict" in out, out
        # 验证文件内容：1 条，值=10.0（未被覆盖）
        import json
        data = json.load(open(bank, encoding="utf-8"))
        assert len(data["corpus"]) == 1, data
        assert data["corpus"][0]["measured_value"] == 10.0, data
        assert data["corpus"][0]["provenance"]["contributor"] == "dr-su", data
        print("[3] bank append + dedup OK")
    finally:
        os.unlink(bank)

    # 4) validate 命令
    rc, out = run_capture(["validate", "--bank",
                           os.path.join(HERE, "lda_harness", "seed_empirical.json")])
    assert rc == 0 and "5 条" in out, out
    print("[4] validate OK")

    print("D-10 smoke ALL GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
