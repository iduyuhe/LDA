"""LDA · D-44 统一设计包规范 smoke。

验证 4 类设计结果（add_drop/quantum/wdm/readout_chain）统一为同一
DesignPackage schema：必填字段齐、schema 版本一致、domain 合法、
verification.passed 验收门存在、honest_notes 必填——机器可校验的统一交付格式。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_design.design_package import (build_all, build_package,  # noqa: E402
                                       summarize, validate_package)

KINDS = ("add_drop", "quantum", "wdm", "readout_chain")


def main() -> int:
    ok = True
    print("=" * 70)
    print("D-44 统一设计包规范（design outcome 统一交付格式）")
    print("=" * 70)
    for kind in KINDS:
        pkg = build_package(kind)
        errs = validate_package(pkg)
        passed = bool(pkg.get("verification", {}).get("passed"))
        good = (not errs) and passed
        ok &= good
        print(f"[{'OK  ' if good else 'FAIL'}] {kind}: id={pkg.get('package_id')} "
              f"domain={pkg.get('domain')} passed={passed} schema={errs or 'OK'}")
        print("     ", summarize(pkg)[:110])
    # 汇总 + 落盘
    out = build_all(os.path.join(_HERE, "reports", "packages"))
    ok &= bool(out["all_schema_ok"])
    print("=" * 70)
    print("D-44 smoke 全绿:", ok, "（schema v%s，4 类包）" % out["schema_version"])
    with open(os.path.join(_HERE, "reports", "design_packages_d44.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
