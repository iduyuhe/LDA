# -*- coding: utf-8 -*-
"""E38g 全量 PathFinder 离线测量（精简版：只测 K=1 全量 × penalty∈{5,10}，关键对照贪心 38.7%）。
逐条写盘 /tmp/pf_k1.json，任何一步失败不丢已得数据。K=2/3 非关键，留作推理。
"""
import time, sys, json, os
sys.path.insert(0, 'lda')
from lda_l2.ecore import dctrl as C, dpathfinder as PF

OUT = "/tmp/pf_k1.json"
results = {}
if os.path.exists(OUT):
    try:
        results = json.load(open(OUT))
    except Exception:
        results = {}

def save():
    json.dump(results, open(OUT, "w"), indent=2)

b = C.build(); nl = b['netlist']
p = PF.real_place(nl)

def measure(K, penalty, pf_iters=8):
    t0 = time.time()
    r = PF.pathfinder_real(nl, p, K=K, layers=4, pf_iters=pf_iters,
                           sample=None, penalty=penalty)
    out = {
        "K": K, "penalty": penalty, "pf_iters_run": r["pf_iters_run"],
        "iter0_routability": round(r["iter0_routability"], 4),
        "routability_best": round(r["routability_best"], 4),
        "best_iter": r["best_iter"], "best_n_routed": r["best_n_routed"],
        "routability_final": round(r["routability_final"], 4),
        "final_overflow": r["final_overflow"],
        "seconds": round(time.time() - t0, 1),
        "overflow_log": [it["overflow"] for it in r["iters_log"]],
        "rout_log": [round(it["routability"], 4) for it in r["iters_log"]],
    }
    return out

for pen in (5.0, 10.0):
    key = "K1_p%.0f" % pen
    if key in results:
        print("skip %s (cached)" % key); continue
    results[key] = measure(1.0, pen)
    save()
    print("done %s -> best=%.1f%% final=%.1f%%" % (key, 100*results[key]["routability_best"], 100*results[key]["routability_final"]))

# 同配置贪心（对照）：route_rr 不自动兜底 max_expand，须显式整网格
try:
    if "greedy_K1" not in results:
        nx, ny = PF.RR._dims(p, 1.0)
        with PF.PA._pitch(PF.PITCH_REAL):
            g = PF.RR.route_rr(nl, p, spread=1.0, layers=4, rr_rounds=0, access_radius=4,
                               cell_block_up_to=2, max_expand=nx*ny*4 + 1)
        results["greedy_K1"] = {"routability": round(g["routability"], 4),
                                "n_routed": g["n_routed"], "n_nets": g["n_nets"]}
        save()
        print("done greedy_K1 -> %.1f%% (%d/%d)" % (100*g["routability"], g["n_routed"], g["n_nets"]))
except Exception as e:
    print("greedy failed:", repr(e))

print(json.dumps(results, indent=2))
