"""D-76 L0 IR 开放标准零漂移 smoke：3 例（正例全过 + 未知 kind FAIL + 缺意图 FAIL）。

注意：jsonschema 校验需 venv（`python envs/default`，含 numba/jsonschema），
运行：C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe run_ir_spec_smoke.py
"""
import sys
sys.path.insert(0, ".")

from lda_ir.spec_check import run_ir_spec_check, _load_schema
from lda_ir import IRModel, Waveguide, to_dict, validate

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok, r.get("verdict", r.get("error", ""))[:90]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：全 9 kind 零漂移 + conforms + 0.2 兼容 + physics round-trip + validate 负例检出
run("正例-零漂移全过", lambda: run_ir_spec_check(), True)


# 2) 负例：未知 kind 示例 → JSON Schema 必须拒绝（检测成功 = PASS）
def _unknown_kind():
    import jsonschema
    schema = _load_schema()
    v = jsonschema.Draft7Validator(schema)
    bad = {"schema_version": "0.3", "domain": "photon", "name": "bad-kind",
           "components": [{"id": "x", "kind": "FooBar", "params": {}}],
           "objectives": [{"bid": "B1", "target": 0.0}]}
    errs = [e.message for e in v.iter_errors(bad)]
    return {"ok": True, "acceptance": {"passed": bool(errs), "checks": []},
            "verdict": f"未知 kind 被 schema 拒绝（{len(errs)} 错误）" if errs
                       else "未知 kind 未被 schema 拒绝（FAIL）"}


run("负例-未知kind被schema拒绝", _unknown_kind, True)


# 3) 负例：IR 缺设计意图（无 spectrum 且无 objectives）→ validate 必须检出（检测成功 = PASS）
def _no_intent():
    m = IRModel(name="no-intent").add(Waveguide(id="w"))
    errs = validate(m)
    return {"ok": True, "acceptance": {"passed": bool(errs), "checks": []},
            "verdict": f"缺设计意图被 validate 检出（{len(errs)} 错误）" if errs
                       else "缺设计意图未被检出（FAIL）"}


run("负例-缺设计意图被validate检出", _no_intent, True)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
