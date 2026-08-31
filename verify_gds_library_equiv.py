"""gds_library 旧(out+=循环) vs 新(list+join) 字节级等价铁证（v0.8.46）。

红线：任何提速必须证明输出逐字节一致。本脚本内联重建旧实现对照。
"""
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda"))
from lda_l2 import gds_export as G

# 旧实现（被替换前，精确还原）
def gds_library_old(name, structures):
    out = b""
    out += G._rec(0x00, 2, G._int2(600))
    out += G._rec(0x01, 0, b"")
    out += G._rec(0x02, 6, G._ascii(name))
    out += G._rec(0x03, 5, G._real8(G.DBU) + G._real8(1.0 / G.DBU))
    for sname, elements in structures.items():
        out += G._rec(0x05, 0, b"")
        out += G._rec(0x06, 6, G._ascii(sname))
        for el in elements:
            out += el
        out += G._rec(0x07, 0, b"")
    out += G._rec(0x04, 0, b"")
    return out

rng = random.Random(20260831)
fails = 0
total = 0
for trial in range(20):
    n_struct = rng.randint(1, 4)
    structures = {}
    for s in range(n_struct):
        n_el = rng.randint(0, 200)
        els = []
        for _ in range(n_el):
            k = rng.randint(0, 3)
            if k == 0:
                els.append(G.path(rng.randint(1, 9), 0.5,
                                   [(rng.uniform(0, 100), rng.uniform(0, 100))
                                    for _ in range(rng.randint(1, 8))]))
            elif k == 1:
                els.append(G._rec(0x08, 0, b""))
            elif k == 2:
                els.append(G.sref(f"CELL{rng.randint(0,50)}",
                                   (rng.uniform(0, 100), rng.uniform(0, 100))))
            else:
                els.append(G._rec(0x0D, 2, G._int2(rng.randint(1, 20))))
        structures[f"STR{rng.randint(0,99)}"] = els
    old = gds_library_old("LDA_CHIP", structures)
    new = G.gds_library("LDA_CHIP", structures)
    total += 1
    if old != new:
        fails += 1
        print(f"[FAIL] trial={trial} old_len={len(old)} new_len={len(new)}")
        # 找首个分叉
        for i in range(min(len(old), len(new))):
            if old[i] != new[i]:
                print(f"  first diff at byte {i}")
                break

print(f"\n===\n{total} 组断言, FAIL={fails}")
print("PASS · 新旧 gds_library 输出逐字节一致 ✓" if fails == 0 else "FAIL · 存在字节差异")
