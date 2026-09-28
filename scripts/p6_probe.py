# -*- coding: utf-8 -*-
"""P6 · T6.1 突变探针：证明 `run_optical_pareto_smoke.py` 的判据**会响**（非恒真）。

铁律 8：**没被验证过的护栏不算护栏**。本探针对 `lda/lda_l2/optical_pareto.py` 做
**文件级**定向变异（字节替换），每次只改一个行为，观察 smoke 是否变红，随后
**按原字节还原并复核 sha256**。含**全局 no-op 守卫**（变异后字节必须真变，否则抛错
—— 防「锚点没命中 ⇒ 静默无操作 ⇒ 探针假绿」这一本项目高频陷阱）。

用法：`python scripts/p6_probe.py`
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LDA = os.path.join(REPO, 'lda')
TARGET = os.path.join(LDA, 'lda_l2', 'optical_pareto.py')
SMOKE = os.path.join(LDA, 'run_optical_pareto_smoke.py')
PY = sys.executable

# (标签, old, new) —— 字节级；old 必须**恰好命中 1 次**
MUTATIONS = [
    ("M1 面积口径回退（去掉 layout_mode=grid2d）",
     b'build_mesh_pnr(dft_matrix(N), rail_pitch=rail_pitch,\n                                             layout_mode="grid2d")',
     b'build_mesh_pnr(dft_matrix(N), rail_pitch=rail_pitch)'),
    ("M2 shared 面积误用 tiled（面积轴塌缩）",
     b'    area = shared_area if arch == ARCH_SHARED else naive_area',
     b'    area = naive_area'),
    ("M3 吞吐丢掉 K（K\u00b7N\u00b2 \u2192 N\u00b2）",
     b'"macs_per_pass": K * N * N,',
     b'"macs_per_pass": N * N,'),
    ("M4 能效守卫放行（禁用令牌表）",
     b'FORBIDDEN_ENERGY_TOKENS: Tuple[str, ...] = (\n    "pj_per_bit", "pJ/bit", "pJ_per_bit", "energy_per_bit", "energy_per_mac",\n    "power_w", "power_dissipation", "power_mw",\n    "tops_per_w", "TOPS/W", "tops", "fj_per_bit", "fJ/bit", "energy_efficiency",\n)',
     b'FORBIDDEN_ENERGY_TOKENS: Tuple[str, ...] = ()'),
    ("M5 front 退化为「返回全部」（支配失效）",
     b'    front = [r for r in pool if not any(_dominates(o, r) for o in pool if o is not r)]\n    return sorted(front, key=lambda r: (r["arch"], r["N"], r["K"]))',
     b'    front = list(pool)\n    return sorted(front, key=lambda r: (r["arch"], r["N"], r["K"]))'),
    ("M6 反向护栏空转（relaxed 上限 = tight）",
     b'    if relaxed_db is None:\n        relaxed_db = ils[-1] + 1e-9',
     b'    if relaxed_db is None:\n        relaxed_db = tight_db'),
    ("M7 K 参与网格内 IL（K \u2192 IL 假依赖）",
     b'    il = float(il_db(deg_max, float(geom["L_bus_um"]), alpha_prop, alpha_tap, rail_pitch, gap))',
     b'    il = K * float(il_db(deg_max, float(geom["L_bus_um"]), alpha_prop, alpha_tap, rail_pitch, gap))'),
]

ENV = dict(os.environ)
ENV['PYTHONPATH'] = LDA
ENV['PYTHONDONTWRITEBYTECODE'] = '1'


def run_smoke():
    p = subprocess.run([PY, SMOKE], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV, cwd=LDA, timeout=900)
    out = (p.stdout or '') + (p.stderr or '')
    n_fail = 0
    for ln in out.splitlines():
        if '[FAIL]' in ln:
            n_fail += 1
    fails = [ln.strip()[:96] for ln in out.splitlines() if '[FAIL]' in ln]
    return p.returncode, n_fail, fails


def main():
    original = open(TARGET, 'rb').read()
    sha0 = hashlib.sha256(original).hexdigest()
    print('目标: %s  (%d B, sha %s)' % (TARGET, len(original), sha0[:12]))

    rc0, f0, _ = run_smoke()
    print('基线: rc=%s FAIL=%d  (须 rc=0 / FAIL=0)' % (rc0, f0))
    if rc0 != 0 or f0 != 0:
        print('!! 基线不绿，探针无意义 —— 中止')
        return 2

    results = []
    try:
        for label, old, new in MUTATIONS:
            hits = original.count(old)
            if hits != 1:
                print('!! %s: 锚点命中 %d 次（须 1）' % (label, hits))
                results.append((label, 'ANCHOR_MISS', 0, []))
                continue
            mutated = original.replace(old, new)
            # 全局 no-op 守卫：字节必须真变
            if mutated == original:
                raise RuntimeError('%s: 变异为 no-op（字节未变）⇒ 探针无效' % label)
            open(TARGET, 'wb').write(mutated)
            rc, nf, fails = run_smoke()
            open(TARGET, 'wb').write(original)          # 立即还原
            now = hashlib.sha256(open(TARGET, 'rb').read()).hexdigest()
            if now != sha0:
                raise RuntimeError('%s: 还原失败（sha %s != %s）' % (label, now[:12], sha0[:12]))
            status = 'RED' if (rc != 0 and nf > 0) else 'GREEN(!!)'
            results.append((label, status, nf, fails))
            print('  %-44s rc=%-3s FAIL=%-3d %s' % (label, rc, nf, status))
            for f in fails[:3]:
                print('        ↳ %s' % f[:90])
    finally:
        open(TARGET, 'wb').write(original)
        assert hashlib.sha256(open(TARGET, 'rb').read()).hexdigest() == sha0, '还原复核失败'

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
