# -*- coding: utf-8 -*-
"""P6 · T6.2 突变探针：证明 `run_wdm_channel_plan_smoke.py` 的判据**会响**（非恒真）。

铁律 8：没被验证过的护栏不算护栏。对 `lda/lda_layout/wdm_channel_plan.py` 做**文件级**
定向变异，每次只改一个行为，观察 smoke 是否变红，随后**按原字节还原 + sha256 复核**。
含**全局 no-op 守卫**（变异后字节与原文相同 ⇒ 直接抛错，防「锚点命中但空变异」假绿）。

🔴 变异 M7（取消 FSR 折返）**只在越域档可见** ⇒ 它同时证明判据 G4 是必需的：
   达标档（span < FSR）永远不会走到 `m_lo ≥ 1` 分支 ⇒ 若无 G4，折返逻辑可被
   「直接返回 delta」的恒等实现替换而**全绿**（判据覆盖缺口）。

用法：`python scripts/t62_probe.py`
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LDA = os.path.join(REPO, 'lda')
MOD = os.path.join(LDA, 'lda_layout', 'wdm_channel_plan.py')
SMOKE = os.path.join(LDA, 'run_wdm_channel_plan_smoke.py')
PY = sys.executable

# (标签, old, new) —— 锚点一律 ASCII（bytes 字面量不得含非 ASCII）
MUTATIONS = [
    ("M1 FSR 判据放宽（1.5 → 0.5）", b'FSR_OVER_SPAN_MIN: float = 1.5',
     b'FSR_OVER_SPAN_MIN: float = 0.5'),
    ("M2 FWHM 预算比例改错（与 U4 脱钩）", b'FWHM_BUDGET_RATIO: float = 0.2',
     b'FWHM_BUDGET_RATIO: float = 0.5'),
    ("M3 串扰目标放松（-20 → -25 dB）", b'XTALK_TARGET_DB: float = -20.0',
     b'XTALK_TARGET_DB: float = -25.0'),
    ("M4 洛伦兹串扰公式改错",
     b'    return float(10.0 * math.log10(1.0 / (1.0 + (2.0 * detune_nm / fwhm_nm) ** 2)))',
     b'    return float(-3.0 * detune_nm / fwhm_nm)'),
    ("M5 串扰反解忽略目标（恒 0.2·Δλ）",
     b'    return float(2.0 * spacing_nm / math.sqrt(r))',
     b'    return float(0.2 * spacing_nm)'),
    ("M6 m 选取忽略约束（恒用默认 30）",
     b'    m_design = int(min(int(M_RING_DEFAULT), m_margin))',
     b'    m_design = int(M_RING_DEFAULT)'),
    ("M7 🔴 取消 FSR 折返（只取 m=0 阶）",
     b'    cands = [abs(delta_nm - mm * fsr_nm) for mm in (m_lo, m_lo + 1)]',
     b'    cands = [abs(delta_nm - 0 * fsr_nm)]'),
    ("M8 FSR 公式改错（λ/m → λ/2m）",
     b'    return float(wl_nm) / float(m)',
     b'    return float(wl_nm) / (2.0 * float(m))'),
    ("M9 丢保守 max（只用闭式）",
     b'            x_cons = x_lor if x_ex is None else max(x_lor, x_ex)',
     b'            x_cons = x_lor'),
    ("M10 🔴 严格路用 λ0 统一建环（复刻已修血案）",
     b'    R_v = ring_radius_um(wl_v, n_g, m_ring)',
     b'    R_v = ring_radius_um(1550.0, n_g, m_ring)'),
    ("M11 清空 disclosure_keys（防删披露失效）",
     b'        "disclosure_keys": sorted(WDM_CHANNEL_DISCLOSURE.keys()),',
     b'        "disclosure_keys": [],'),
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
            status = 'RED' if (rc != 0 and nf > 0) else 'GREEN(!!)'
            results.append((label, status, nf, fails))
            print('  %-44s rc=%-3s FAIL=%-3d %s' % (label, rc, nf, status))
            for f in fails[:3]:
                print('        ↳ %s' % f[:88])
    finally:
        open(MOD, 'wb').write(original)
        assert hashlib.sha256(open(MOD, 'rb').read()).hexdigest() == sha, \
            '还原复核失败: %s' % MOD

    rc0b, f0b, _ = run_smoke()
    print('还原后: rc=%s FAIL=%d  (须 rc=0 / FAIL=0)' % (rc0b, f0b))
    print('=' * 74)
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
