# -*- coding: utf-8 -*-
"""P6 · T6.3 突变探针：证明 `run_mesh_tiling_smoke.py` 的判据**会响**（非恒真）。

铁律 8：没被验证过的护栏不算护栏。对 `lda/lda_l2/mesh_tiling.py` 做**文件级**定向变异，
每次只改一个行为，观察 smoke 是否变红，随后**按原字节还原 + sha256 复核**。含全局 no-op 守卫。

🔴 M8/M9 是本批关键：它们证明「**旧档数字不得复用**」这条守护**真的会拦**——
   M8 把天花板写成常数（不复算）、M9 把档间指纹退化成空 ⇒ 均必须变红。

用法：`python scripts/t63_probe.py`
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LDA = os.path.join(REPO, 'lda')
MOD = os.path.join(LDA, 'lda_l2', 'mesh_tiling.py')
SMOKE = os.path.join(LDA, 'run_mesh_tiling_smoke.py')
PY = sys.executable

# (标签, old, new) —— 锚点一律 ASCII
MUTATIONS = [
    ("M1 默认布局模式改为 serpentine", b'LAYOUT_MODE_DEFAULT: str = "grid2d"',
     b'LAYOUT_MODE_DEFAULT: str = "serpentine"'),
    ("M2 D1 丢掉轨切换余量", b'    il_full = a_prop * L_cm + (avg_deg * rail_switch_margin) * a_tap',
     b'    il_full = a_prop * L_cm + avg_deg * a_tap'),
    ("M3 D1 用线性律替代真实几何（旧档数字复用）",
     b'    L_cm = geo["L_bus_um"] / 1e4',
     b'    L_cm = (35.6 * N) / 1e4'),
    ("M4 D2 预算不随 N 收缩", b'    budget = D2_FIDELITY_COEF / float(N_tile)',
     b'    budget = D2_FIDELITY_COEF'),
    ("M5 D2 丢掉保守倍数", b'    dphi_worst = D2_WORST_MULT * dphi_single',
     b'    dphi_worst = dphi_single'),
    ("M6 P3 互连长度写成常数（不复用该档 x 跨度）",
     b'    il_link = a_prop * (geo["L_bus_um"] / 1e4)',
     b'    il_link = 0.1                                            '),
    ("M7 P3 寄生项写成常数",
     b'    il_par_tile = c_sub_loss_db_per_ff * geo["C_total_ff"]',
     b'    il_par_tile = 0.05                                       '),
    ("M8 🔴 天花板写成常数（不复算 ⇒ 旧档数字复用）",
     b'        if fr:\n            last_rx = N',
     b'        if fr:\n            last_rx = 128'),
    ("M9 🔴 档间指纹退化为空（守护失效）", b'    for s in scenarios:\n        fp += [',
     b'    for s in []:\n        fp += ['),
    ("M10 取消指纹重复检查", b'        if fp in seen:', b'        if False:'),
    ("M11 清空 disclosure_keys（防删披露失效）",
     b'        "disclosure_keys": sorted(TILING_DISCLOSURE.keys()),',
     b'        "disclosure_keys": [],'),
    ("M12 il_per_n_at 加插值（不可整除也返回）",
     b'    if N_target <= 0 or int(N_target) % int(N_tile) != 0:',
     b'    if N_target <= 0:'),
]

ENV = dict(os.environ)
ENV['PYTHONPATH'] = LDA
ENV['PYTHONDONTWRITEBYTECODE'] = '1'


def run_smoke():
    p = subprocess.run([PY, SMOKE], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=ENV, cwd=LDA,
                       timeout=900)
    out = (p.stdout or '') + (p.stderr or '')
    fails = [ln.strip()[:96] for ln in out.splitlines() if '[FAIL]' in ln]
    return p.returncode, len(fails), fails


def main():
    original = open(MOD, 'rb').read()
    sha = hashlib.sha256(original).hexdigest()
    print('目标: %s (%d B, sha %s)' % (MOD, len(original), sha[:12]))

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
            if mutated == original:
                raise RuntimeError('%s: 变异为 no-op ⇒ 探针无效' % label)
            open(MOD, 'wb').write(mutated)
            rc, nf, fails = run_smoke()
            open(MOD, 'wb').write(original)
            if hashlib.sha256(open(MOD, 'rb').read()).hexdigest() != sha:
                raise RuntimeError('%s: 还原失败' % label)
            # 崩溃（rc!=0 但无 [FAIL] 行）也算「护栏亮了」——例如 plan_tiling 直接 raise
            status = 'RED' if (rc != 0) else 'GREEN(!!)'
            results.append((label, status, nf, fails))
            print('  %-46s rc=%-3s FAIL=%-3d %s' % (label, rc, nf, status))
            for f in fails[:2]:
                print('        ↳ %s' % f[:86])
    finally:
        open(MOD, 'wb').write(original)
        assert hashlib.sha256(open(MOD, 'rb').read()).hexdigest() == sha, \
            '还原复核失败: %s' % MOD

    rc0b, f0b, _ = run_smoke()
    print('还原后: rc=%s FAIL=%d  (须 rc=0 / FAIL=0)' % (rc0b, f0b))
    print('=' * 76)
    n_red = sum(1 for _, s, _, _ in results if s == 'RED')
    n_miss = sum(1 for _, s, _, _ in results if s == 'ANCHOR_MISS')
    print('突变探针：%d/%d 会响 · 锚点未命中 %d · 还原后基线 %s'
          % (n_red, len(MUTATIONS), n_miss,
             '绿 ✅' if (rc0b == 0 and f0b == 0) else '红 ❌'))
    ok = (n_red == len(MUTATIONS) and n_miss == 0 and rc0b == 0 and f0b == 0)
    print('RESULT: %s' % ('ALL_MUTATIONS_CAUGHT' if ok else 'NOT_ALL_CAUGHT'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
