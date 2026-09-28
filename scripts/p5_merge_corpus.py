"""P5 · T5.3 语料合并：三路核查产出 → `lda/lda_harness/seed_empirical.json`。

背景
----
T5.3（A 级实证锚扩容 30 → ≥60）此前由三个核查 agent 各自产出一批**公开文献实测**
语料（`tmp_p5_corpus_A/B/C.json`）。本脚本把三批**只收 A 级**的语料并入种子库。

纪律（每一条都机器判定，非人工目测）
------------------------------------
1. **A 级门禁**：`provenance.classify_citation` 必须判 `traceable=True`
   （citation / source_url 含 DOI / arXiv / 公开 URL 定位符）。B/X 级一律不收。
2. **字段完备**：`EmpiricalMeasurement(**it)` 必须构造成功 + `.validate()` 通过，
   且 `geometry` 非空、`uncertainty_abs` 为数值 ≥0 —— 与 M6-5/M6-6 同口径。
3. **id 唯一**：不得与库内既有 id 或本批其他新条重复。
4. **不改既有数值**：只**追加**新条 + 给 `E-Q-TTRANS-T1` 补 geometry（其原为 `{}`，
   导致 M6-5 红）。任何既有条目的 `measured_value` / `citation` 等一律不动。
5. **子代理自评 `confidence` 不进 schema**（`EmpiricalMeasurement` 无此字段，
   原样并入会 `TypeError`）⇒ 折成 tag `evidence_high` / `evidence_medium`；
   并在 note 中出现 `UPPER BOUND` / `inferred` 时显式打 `upper_bound` /
   `geometry_inferred` 标记 —— 诚实边界（上界值、推断几何）留在牌面上，
   而不是被静默抹平。

字节保真：`json.dumps(indent=2, ensure_ascii=False)` + **CRLF** 换行
（原文件为 CRLF；见 IRONLAWS §二 EOL 字节级判）。

用法：
    python scripts/p5_merge_corpus.py            # 实跑并落盘
    python scripts/p5_merge_corpus.py --dry-run  # 只体检不写盘
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
SEED = os.path.join(_REPO, "lda", "lda_harness", "seed_empirical.json")
NEW_FILES = ["tmp_p5_corpus_A.json", "tmp_p5_corpus_B.json", "tmp_p5_corpus_C.json"]

sys.path.insert(0, os.path.join(_REPO, "lda"))

# 新条目的规范键序（仅影响新增条目的可读性，不动既有条目）
_KEY_ORDER = ["id", "device", "metric", "measured_value", "uncertainty_abs",
              "fab_source", "citation", "source_url", "method", "geometry",
              "tags", "note"]

# 子代理自评 confidence → tag
_CONF_TAG = {"high": "evidence_high", "medium": "evidence_medium"}

# E-Q-TTRANS-T1 补 geometry（同源 DOI 10.1038/s41467-021-22030-5 · Place et al. 2021）
_TTRANS_GEOMETRY = {
    "material": "Ta (tantalum) 2D transmon on sapphire",
    "freq_range_ghz": "3.1-5.5",
    "freq_ghz": 4.3,
    "junction_area_um2": 0.03,
    "n_devices": 17,
}
_TTRANS_NOTE = (
    "P5（T5.3）补 geometry 以满足 M6-5「每条带 geometry」。同源 DOI "
    "10.1038/s41467-021-22030-5（Place et al., Nat. Commun. 12, 1779 (2021)）："
    "17 个钽替代铌的二维 transmon 器件，频率覆盖 3.1-5.5 GHz"
    "（freq_ghz=4.3 取区间中点作代表性单值，非单器件实测值）；结面积 ≈0.03 µm²。"
    "原文 T1 峰值 0.36±0.01 ms、均值 0.23 ms；本条 measured_value=300 µs 为"
    "「含动态解耦 >0.3 ms」口径，**未改动**任何既有数值，仅补几何。"
)


def _reorder(d: dict) -> dict:
    """按规范键序输出新条目（未知键追加在末尾，不丢字段）。"""
    out = {k: d[k] for k in _KEY_ORDER if k in d}
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


def _git_head_corpus():
    """读 `git show HEAD:<SEED>` 的语料（**已知良好基线**），失败返回 None。

    这是「既有条目只许白名单改动」对账的**唯一可信基准**：
    - 不能用「本次读入的旧值」——若文件读入时已被并发写坏，坏值对坏值零差异；
    - HEAD 版本是上次提交、已过全部门禁的干净态。
    """
    import subprocess

    rel = os.path.relpath(SEED, _REPO).replace("\\", "/")
    try:
        r = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True,
                           cwd=_REPO)
        if r.returncode != 0 or not r.stdout:
            return None
        items = json.loads(r.stdout.decode("utf-8")).get("corpus", [])
        return {x["id"]: x for x in items}
    except Exception:  # noqa: BLE001 无 git / 非仓库 ⇒ 由调用方降级并声明
        return None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv

    from lda_harness.empirical_bank import EmpiricalMeasurement
    from lda_harness.provenance import classify_citation

    raw_bytes = open(SEED, "rb").read()
    doc = json.loads(raw_bytes.decode("utf-8"))
    corpus = doc["corpus"]
    #: 写盘前对账用的**旧值快照**（深拷贝，避免被后续原地修改污染）
    pre_corpus = json.loads(json.dumps(corpus))
    existing = {x["id"] for x in corpus}

    print("=" * 74)
    print(f"合并前：{len(corpus)} 条")
    print("=" * 74)

    added, skipped, rejected = [], [], []
    for name in NEW_FILES:
        path = os.path.join(_REPO, name)
        if not os.path.exists(path):
            print(f"  [WARN] 缺文件 {name} → 跳过")
            continue
        items = json.load(open(path, "r", encoding="utf-8"))["corpus"]
        print(f"\n-- {name}：{len(items)} 条")
        for it in items:
            eid = it.get("id", "?")
            if eid in existing:
                skipped.append((eid, "id 已存在"))
                print(f"  [SKIP] {eid}（id 已存在）")
                continue
            # 1) A 级门禁
            tier = classify_citation(it.get("citation", ""), it.get("source_url", ""))
            if not tier["traceable"]:
                rejected.append((eid, f"非 A 级 tier={tier['tier']}"))
                print(f"  [REJECT] {eid} 非 A 级（{tier['tier']}）")
                continue
            # 2) 字段完备（构造 + validate 与 M6-5/M6-6 同口径）
            rec = _reorder({k: v for k, v in it.items() if k != "confidence"})
            conf = it.get("confidence")
            if conf:
                rec.setdefault("tags", [])
                tag = _CONF_TAG.get(conf, f"evidence_{conf}")
                if tag not in rec["tags"]:
                    rec["tags"].append(tag)
            note = rec.get("note", "") or ""
            rec.setdefault("tags", [])
            if "upper bound" in note.lower() and "upper_bound" not in rec["tags"]:
                rec["tags"].append("upper_bound")
            if "inferred" in note.lower() and "geometry_inferred" not in rec["tags"]:
                rec["tags"].append("geometry_inferred")
            try:
                m = EmpiricalMeasurement(**rec)
                m.validate()
            except Exception as e:  # noqa: BLE001 显式登记，不静默放过
                rejected.append((eid, f"{type(e).__name__}: {e}"))
                print(f"  [REJECT] {eid} 字段校验失败：{e}")
                continue
            if not (m.geometry or {}):
                rejected.append((eid, "geometry 空 → 违反 M6-5"))
                print(f"  [REJECT] {eid} geometry 空")
                continue
            # 3) 唯一性（同批内）
            if eid in {a["id"] for a in added}:
                rejected.append((eid, "本批内重复"))
                print(f"  [REJECT] {eid} 本批内重复")
                continue
            added.append(rec)
            print(f"  [ADD ] {eid:<20} tier={tier['tier']} "
                  f"kind={tier['locator_kind']} locator={str(tier['locator'])[:58]}")

    # 4) 补 E-Q-TTRANS-T1 geometry（只补几何，不动数值）
    patched = False
    for x in corpus:
        if x["id"] == "E-Q-TTRANS-T1":
            if x.get("geometry"):
                print("\n[INFO] E-Q-TTRANS-T1 已有 geometry，未改动")
            else:
                x["geometry"] = dict(_TTRANS_GEOMETRY)
                x["note"] = _TTRANS_NOTE
                patched = True
                print("\n[PATCH] E-Q-TTRANS-T1 补 geometry（M6-5）")

    corpus.extend(added)
    doc["corpus"] = corpus

    # 6) 🔴 既有条目**只允许**出现预期的补丁，任何其它字段变化都是事故。
    #    本轮血案：脚本与 `scripts/p5_probe.py` 并发跑，探针的
    #    `_seed_empty_geometry` 把 `E-TBOX-PL-TE` 的 geometry 清成 `{}`，
    #    而本脚本随后**原样写回** ⇒ 把一个健康条目**静默损毁**
    #    （表现为 M6-5 事后才红，且看起来像「数据本来就这样」）。
    #
    #    ⚠️ **对账基准必须是「已知良好」的参照**，不能用「本次读入的旧值」——
    #    若文件**读入时就已经坏了**，拿坏值对坏值 ⇒ 零差异 ⇒ 守卫照样沉默
    #    （本守卫第一版就栽在这：自验时 rc=0 且把坏文件写回）。
    #    正确基准 = **git HEAD 版本**（上次提交的、经过门禁的已知良好态）。
    _ALLOWED_PATCH = {"E-Q-TTRANS-T1": {"geometry", "note"}}
    base_by_id = _git_head_corpus()
    ref_name = "git HEAD"
    if base_by_id is None:
        # 无 git / 未跟踪 ⇒ 退回读入快照，并在输出里**显式声明降级**
        base_by_id = {x["id"]: x for x in pre_corpus}
        ref_name = "读入快照（非 git 基线 · 守卫降级）"
    violations = []
    for x in corpus:
        o = base_by_id.get(x["id"])
        if o is None:
            continue  # 新增条（HEAD 里没有），不算改动
        for k in set(o) | set(x):
            if o.get(k) == x.get(k):
                continue
            if k in _ALLOWED_PATCH.get(x["id"], set()):
                continue
            violations.append((x["id"], k, repr(o.get(k))[:70],
                               repr(x.get(k))[:70]))
    if violations:
        print("\n" + "!" * 74)
        print(f"检测到**既有条目的非预期改动**（基准={ref_name}）——已中止，未写盘：")
        for eid, k, ov, nv in violations:
            print(f"  [{eid}] {k}: {ov} -> {nv}")
        print("!" * 74)
        return 2
    print(f"[对账] 既有条目逐字段核对通过（基准={ref_name}，"
          f"{len(base_by_id)} 条）")

    print("\n" + "=" * 74)
    print(f"新增 {len(added)} 条 · 跳过 {len(skipped)} · 拒收 {len(rejected)}"
          f" · 补几何 {patched}")
    print(f"合并后：{len(corpus)} 条")
    print("=" * 74)

    # 5) 落盘（CRLF 字节保真）
    blob = (json.dumps(doc, indent=2, ensure_ascii=False).replace("\n", "\r\n")
            + "\r\n").encode("utf-8")
    if dry:
        print("[dry-run] 未写盘")
    else:
        with open(SEED, "wb") as f:
            f.write(blob)
        print(f"[write] {SEED} ({len(blob)} bytes)")

    return 0 if not rejected else 1


if __name__ == "__main__":
    sys.exit(main())
