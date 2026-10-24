"""D-63 方向耦合器 × 量子读出 smoke：正例 + 负例。

═══ 判据（分两节 · 9 条）═══
P 判决正确性 5（原 5 条，语义不变）
C 缓存可观测性 5（v0.9.279 · D-227 · F-9）

🔴 **C 组为什么存在**：本门禁单道 **202 秒**，是 CI 时间分布里的异常点；而审计第二轮
   F-9 的定性是「慢得没有解释」——不是慢本身，是**没人知道 202 秒花在哪**。
   实测归因：5 例合计触发 **9 次单级 DC 真 FDTD 设计**，每次 ~20 s；
   而等功率二分的各层 `target_cross` 会**重复**（4 qubit 均匀的三级全是 0.5，
   3 qubit 的次层也是 0.5）⇒ **唯一设计只有 3 个**。
   ⇒ 对 `_design_dc` 做**同参缓存**（纯函数语义，实测同参两次 `cross_val_fdtd` 逐位相同）。

🔴 **三条纪律（C 组守的就是这三条）**：
  ① **缓存必须真命中**（C1：`u+h==c` ∧ `h>0` ∧ `u ≤ 0.5·c`）——
     否则"加了缓存"只是加了代码，没有加速；
  ② **命中不得改变输出**（C2：命中的 DC 与首算的 DC **除 id 外逐位相同、键序相同**）——
     `id` 属于调用点、`left_span/right_frac` 由上层写，共享对象会串味，故一律 deepcopy；
  ③ **统计可归零**（C4：`reset` 后 `hits==0`）——
     不归零的计数器会让 C1 在长进程里恒真，退化成假判据；
  ④ 🔴 **缓存必须有容量上限**（C3）—— 本模块**不只在门禁里跑**：WebUI `/api/splitter`
     也调它，`f01s`/`weights` 由用户任意输入 ⇒ `target_cross` 无界 ⇒
     无上限的模块级缓存 = **按请求泄漏内存**（这是本版自己差点引入的生产缺陷）。

🔴 **不把计数塞进产品返回值**：那会让「同参两次调用的输出字节」因缓存状态而异，
   直接违反 `run_report_determinism_smoke`（相同输入 ⇒ 字节一致）。故只经
   `dc_cache_stats()` 侧路暴露。

🔴 节标签用 P / C —— 避开 B/E/S（账本锚号前缀），防 K4 文本代理虚高覆盖。
"""

import sys

sys.path.insert(0, ".")
from lda_agent.splitter_readout import (  # noqa: E402
    dc_cache_stats, design_splitter_readout, reset_dc_cache)

PASS = FAIL = 0
_ROWS = []


def _p(ok, name, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f"  |  {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  |  {detail}" if detail else ""))
    _ROWS.append(ok)
    return ok


def run(name, expect_pass, **kw):
    try:
        r = design_splitter_readout(**kw)
        passed = bool(r.get("acceptance", {}).get("passed"))
    except Exception as e:  # noqa: BLE001
        passed, r = False, {"error": str(e)[:100]}
    ok = (passed == expect_pass)
    detail = (f"passed={passed} (期望 {expect_pass})" +
              (f" | {r.get('verdict', '')[:80]}" if passed else
               f" | {r.get('error', '')[:80]}"))
    _p(ok, f"{name}", detail)
    return ok, r


print("=== D-63 方向耦合器×量子读出 smoke ===")

# ── P 组：判决正确性（原 5 例，语义不变）────────────────────────────────
reset_dc_cache()          # 从干净状态起步，使 C1 的统计覆盖本门禁全部调用
_ok1, r1 = run("3 qubit 均匀分束", True, f01s=[4.8, 5.0, 5.2])
_ok2, r2 = run("4 qubit 均匀分束（3 级 DC）", True, f01s=[4.8, 5.0, 5.2, 5.4])
_ok3, r3 = run("极端权重（最弱路 SNR 不足应 FAIL）", False,
               f01s=[4.8, 5.0, 5.2], weights=[0.9, 0.05, 0.05], nbar0=3.0)
_ok4, r4 = run("nbar0 过低（均匀分配后 SNR 不足应 FAIL）", False,
               f01s=[4.8, 5.0, 5.2], nbar0=0.3)
_ok5, _r5 = run("weights 与 f01s 长度不匹配（应 FAIL）", False,
                f01s=[4.8, 5.0, 5.2], weights=[0.3, 0.7])

all_ok = all([_ok1, _ok2, _ok3, _ok4, _ok5])

# ── C 组：缓存可观测性（F-9）──────────────────────────────────────────
print("\n[C] 缓存可观测性（F-9：把「202 秒花在哪」变成数字）")
_st = dc_cache_stats()


def _cache_ratio_ok(st):
    """C1 的判据函数（提出来是为了让 C4 能反向喂假数据证伪它）。"""
    c, u, h = st.get("calls", 0), st.get("unique", 0), st.get("hits", 0)
    return bool(c > 0 and (u + h == c) and h > 0 and u <= 0.5 * c)


_p(_cache_ratio_ok(_st),
   "C1 同参 DC 设计真命中：calls ≡ unique + hits ∧ hits > 0 ∧ unique ≤ 50%·calls",
   "calls=%d unique=%d hits=%d ⇒ 命中率 %.1f%%（每次 DC ~20s ⇒ 省约 %d 次真 FDTD）"
   % (_st["calls"], _st["unique"], _st["hits"],
      100.0 * _st["hits"] / max(_st["calls"], 1), _st["hits"]))

# C2 命中返回体 ≡ 首算返回体（case1 与 case4 的 f01s/weights 完全相同 ⇒ 应逐位相同）
_s1 = r1.get("splitters") or []
_s4 = r4.get("splitters") or []


def _strip_id(items):
    return [{k: v for k, v in d.items() if k != "id"} for d in items]


_keys_same = all(list(a.keys()) == list(b.keys()) for a, b in zip(_s1, _s4))
_p(bool(_s1) and len(_s1) == len(_s4) and _strip_id(_s1) == _strip_id(_s4) and _keys_same,
   "C2 🔴 命中不改语义：同 f01s/weights 的两例，DC 参数除 id 外逐位相同 ∧ 键序相同",
   "n=%d/%d 键序同=%s" % (len(_s1), len(_s4), _keys_same))

# C3 🔴 容量上限（**必须在 reset 之前判**，否则占用恒 0 ⇒ 判据无判别力）：
#    本模块不只在本门禁里跑 —— WebUI `/api/splitter` 也调它，且 `f01s`/`weights`
#    由用户任意输入 ⇒ `target_cross` 无界 ⇒ 无上限缓存 = **按请求泄漏内存**。
from lda_agent import splitter_readout as _SR  # noqa: E402

_cap = getattr(_SR, "_DC_CACHE_MAX", None)
_p(isinstance(_cap, int) and 0 < _cap <= 4096
   and len(_SR._DC_CACHE) <= _cap,
   "C3 🔴 缓存容量有上限 ∧ 当前占用不越界（WebUI 端点也调用本模块，无界缓存=泄漏）",
   "上限=%r 当前占用=%d" % (_cap, len(_SR._DC_CACHE)))

# C4 统计可归零
reset_dc_cache()
_z = dc_cache_stats()
_p(_z == {"calls": 0, "unique": 0, "hits": 0, "hit_keys": 0, "cached_keys": 0},
   "C4 统计可归零（reset ⇒ 全零）—— 不归零的计数器会让 C1 在长进程里恒真",
   "reset后=%s" % (_z,))

_p(not _cache_ratio_ok({"calls": 9, "unique": 9, "hits": 0}),
   "C5 反向：喂 hits=0 的假统计 ⇒ C1 判据必为 False（证明 C1 有判别力，非恒真）",
   "假统计 calls=9/unique=9/hits=0 ⇒ 判据=%s" % _cache_ratio_ok(
       {"calls": 9, "unique": 9, "hits": 0}))

all_ok = all_ok and FAIL == 0
print(f"\n=== {'ALL PASS' if all_ok else 'HAS FAILURE'}（{PASS}/{PASS + FAIL}）===")
# v0.9.276（D-224 / F-9）：补标准计数末行 —— 此前用 `PASS |` 与中文括号「（5/5）」，
#   机械统计（认 `[PASS]` 或末行 `N/N PASS`）判成「0 判据」，实为 5 条。
# v0.9.279（D-227）：判据 5 → 10（新增 C 组 5 条缓存可观测性）。
print(f"D-63 方向耦合器×量子读出 smoke：{PASS}/{PASS + FAIL} PASS")
sys.exit(0 if all_ok else 1)
