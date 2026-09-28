# -*- coding: utf-8 -*-
"""P6 · T6.4 突变探针：证明 `run_eic_behavioral_smoke.py` 的判据**会响**（非恒真）。

铁律 8：没被验证过的护栏不算护栏。对 `lda/lda_l2/eic_behavioral.py`（及**共享守卫所在**的
`lda/lda_l2/optical_pareto.py`）做**文件级**定向变异，每次只改一个行为，观察 smoke 是否变红，
随后**按原字节还原 + sha256 复核**。含**全局 no-op 守卫**。

🔴 T7 为**跨文件变异**（清空 `optical_pareto` 的令牌表）：它同时证明
「共享能效守卫是**单一真值来源**」—— T6.4 的 H1/H3 依赖同一张表 ⇒ 表一空，两套 smoke 都红。
（若当初在两处各写一份，此变异**只会红一处**，正是 U10 血案。）

用法：`python scripts/t64_probe.py`
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LDA = os.path.join(REPO, 'lda')
EIC = os.path.join(LDA, 'lda_l2', 'eic_behavioral.py')
PARETO = os.path.join(LDA, 'lda_l2', 'optical_pareto.py')
SMOKE = os.path.join(LDA, 'run_eic_behavioral_smoke.py')
PY = sys.executable

# (标签, 目标文件, old, new)
MUTATIONS = [
    ("T1 闭式改错（τ → 2τ）", EIC,
     b'    return float(v_dd * (1.0 - math.exp(-t_s / tau_s)))',
     b'    return float(v_dd * (1.0 - math.exp(-t_s / (2.0 * tau_s))))'),
    ("T2 RK4 降为一阶 Euler（阶数退化）", EIC,
     b'        k1 = f(v)\n        k2 = f(v + 0.5 * h * k1)\n        k3 = f(v + 0.5 * h * k2)\n        k4 = f(v + h * k3)\n        v += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)',
     b'        k1 = f(v)\n        v += h * k1'),
    ("T3 候选换成恒等（直接返回闭式）", EIC,
     b'    h = t_s / n_steps\n    v = 0.0',
     b'    return float(v_dd * (1.0 - math.exp(-t_s / tau_s)))\n    h = t_s / n_steps\n    v = 0.0'),
    ("T4 上升时延闭式改错（ln(1−f) → ln f）", EIC,
     b'    t_closed = -tau_s * math.log(1.0 - rise_frac)',
     b'    t_closed = -tau_s * math.log(rise_frac)'),
    ("T5 TIA 极点常数改错（2π → π）", EIC,
     b'    return complex(r_f_ohm) / complex(1.0, 2.0 * math.pi * f_hz * r_f_ohm * c_f_f)',
     b'    return complex(r_f_ohm) / complex(1.0, math.pi * f_hz * r_f_ohm * c_f_f)'),
    ("T6 相位公式去掉 π（φ = v/Vπ）", EIC,
     b'    return float(math.pi * float(v) / vpi_from_vpi_l(vpi_l_v_mm, arm_um))',
     b'    return float(float(v) / vpi_from_vpi_l(vpi_l_v_mm, arm_um))'),
    ("T7 量化步进取 2*bits（非 2^bits）", EIC,
     b'    v_step = float(v_dd) / float(2 ** dac_bits)',
     b'    v_step = float(v_dd) / float(2 * dac_bits)'),
    ("T8 🔴 跨文件：清空**共享**令牌表（证明单一来源）", PARETO,
     b'FORBIDDEN_ENERGY_TOKENS: Tuple[str, ...] = (\n    "pj_per_bit", "pJ/bit", "pJ_per_bit", "energy_per_bit", "energy_per_mac",\n    "power_w", "power_dissipation", "power_mw",\n    "tops_per_w", "TOPS/W", "tops", "fj_per_bit", "fJ/bit", "energy_efficiency",\n)',
     b'FORBIDDEN_ENERGY_TOKENS: Tuple[str, ...] = ()'),
]

ENV = dict(os.environ)
ENV['PYTHONPATH'] = LDA
ENV['PYTHONDONTWRITEBYTECODE'] = '1'


def run_smoke():
    p = subprocess.run([PY, SMOKE], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV, cwd=LDA, timeout=900)
    out = (p.stdout or '') + (p.stderr or '')
    fails = [ln.strip()[:96] for ln in out.splitlines() if '[FAIL]' in ln]
    return p.returncode, len(fails), fails


def main():
    originals = {}
    shas = {}
    for path in (EIC, PARETO):
        originals[path] = open(path, 'rb').read()
        shas[path] = hashlib.sha256(originals[path]).hexdigest()
    print('目标:')
    for path in (EIC, PARETO):
        print('  %s (%d B, sha %s)' % (path, len(originals[path]), shas[path][:12]))

    rc0, f0, _ = run_smoke()
    print('基线: rc=%s FAIL=%d  (须 rc=0 / FAIL=0)' % (rc0, f0))
    if rc0 != 0 or f0 != 0:
        print('!! 基线不绿，探针无意义 —— 中止')
        return 2

    results = []
    try:
        for label, path, old, new in MUTATIONS:
            hits = originals[path].count(old)
            if hits != 1:
                print('!! %s: 锚点命中 %d 次（须 1）' % (label, hits))
                results.append((label, 'ANCHOR_MISS', 0, []))
                continue
            mutated = originals[path].replace(old, new)
            if mutated == originals[path]:
                raise RuntimeError('%s: 变异为 no-op ⇒ 探针无效' % label)
            open(path, 'wb').write(mutated)
            rc, nf, fails = run_smoke()
            open(path, 'wb').write(originals[path])
            if hashlib.sha256(open(path, 'rb').read()).hexdigest() != shas[path]:
                raise RuntimeError('%s: 还原失败' % label)
            status = 'RED' if (rc != 0 and nf > 0) else 'GREEN(!!)'
            results.append((label, status, nf, fails))
            print('  %-44s rc=%-3s FAIL=%-3d %s' % (label, rc, nf, status))
            for f in fails[:3]:
                print('        ↳ %s' % f[:88])
    finally:
        for path in (EIC, PARETO):
            open(path, 'wb').write(originals[path])
            assert hashlib.sha256(open(path, 'rb').read()).hexdigest() == shas[path], \
                '还原复核失败: %s' % path

    rc0b, f0b, _ = run_smoke()
    print('还原后: rc=%s FAIL=%d  (须 rc=0 / FAIL=0)' % (rc0b, f0b))
    print('=' * 74)
    n_red = sum(1 for _, s, _, _ in results if s == 'RED')
    n_miss = sum(1 for _, s, _, _ in results if s == 'ANCHOR_MISS')
    print('突变探针：%d/%d 会响 · 锚点未命中 %d · 还原后基线 %s'
          % (n_red, len(MUTATIONS), n_miss, '绿 ✅' if (rc0b == 0 and f0b == 0) else '红 ❌'))
    ok = (n_red == len(MUTATIONS) and n_miss == 0 and rc0b == 0 and f0b == 0)
    print('RESULT: %s' % ('ALL_MUTATIONS_CAUGHT' if ok else 'NOT_ALL_CAUGHT'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
