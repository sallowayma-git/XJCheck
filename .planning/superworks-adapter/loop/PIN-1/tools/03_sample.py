"""PIN-1 step 4: stratified random sample of production-admitted symb2 candidates for visual validation.

Excludes the cases already judged in PIN-ID (46 Pop-X samples: stratum A and A2). Strata:
  M  identities naming more than one physical pin in the project (quota first, multi-pin rule check)
  F  the rest, allocated to project families in proportion to the pool, at least one per family present,
     and round-robin over element types inside each family.

Usage: python 03_sample.py <pool_json> <pin_id_samples_json> <out_json> <n_total> <n_multi> <seed>
"""
import collections
import json
import random
import sys


def key(item):
    return (item["pid"], item["file"], item["insert"], str(item["pin"]))


def round_robin(items, n, rng):
    buckets = collections.defaultdict(list)
    for it in items:
        buckets[it["etype"]].append(it)
    for b in buckets.values():
        rng.shuffle(b)
    order = sorted(buckets, key=lambda t: -len(buckets[t]))
    picked = []
    while len(picked) < n and any(buckets.values()):
        for t in order:
            if buckets[t] and len(picked) < n:
                picked.append(buckets[t].pop())
    return picked


def allocate(sizes, n):
    total = sum(sizes.values())
    alloc = {f: max(1, round(n * s / total)) for f, s in sizes.items()}
    while sum(alloc.values()) > n:
        f = max(alloc, key=lambda k: alloc[k])
        alloc[f] -= 1
    while sum(alloc.values()) < n:
        f = max(sizes, key=lambda k: sizes[k] / (alloc[k] + 1))
        alloc[f] += 1
    return alloc


def main(pool_path, pin_id_path, out_path, n_total, n_multi, seed):
    rng = random.Random(seed)
    pool = json.load(open(pool_path, encoding="utf-8"))
    prior = {(r["pid"], r["file"], r["insert"], str(r.get("pin") if r.get("pin") is not None else r.get("port")))
             for r in json.load(open(pin_id_path, encoding="utf-8")) if r.get("stratum") in ("A", "A2")}
    pool = [p for p in pool if p["pair_present"] and p["wire_present"] and key(p) not in prior]
    # Almost every candidate identity also names a pin on another sheet (part-layout copies), so the
    # multi-pin split is only a covariate. n_multi=0 draws every stratum from the whole pool.
    multi = [p for p in pool if p["identity_pins"] > 1] if n_multi else []
    single = [p for p in pool if p["identity_pins"] <= 1] if n_multi else pool
    picked = []
    # M: multi-pin identities, spread over families
    fam_m = collections.defaultdict(list)
    for p in multi:
        fam_m[p["family"]].append(p)
    for f, n in allocate({f: len(v) for f, v in fam_m.items()}, n_multi).items():
        picked += [dict(it, stratum="M") for it in round_robin(fam_m[f], n, rng)]
    # F: the rest
    fam_f = collections.defaultdict(list)
    for p in single:
        fam_f[p["family"]].append(p)
    n_rest = n_total - len(picked)
    for f, n in allocate({f: len(v) for f, v in fam_f.items()}, n_rest).items():
        picked += [dict(it, stratum="F") for it in round_robin(fam_f[f], n, rng)]
    rng.shuffle(picked)
    out = []
    for i, it in enumerate(picked, 1):
        rec = {k: it[k] for k in ("pid", "family", "file", "sheet", "record", "wire", "pair_id", "insert", "pin",
                                  "identity", "label", "slot", "device", "seq", "etype", "term_insert", "term_port",
                                  "term_identity", "identity_pins", "stratum")}
        rec["sid"] = f"S{i:03d}"
        out.append(rec)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("pool_after_exclusion", len(pool), "multi", len(multi), "single", len(single))
    print("sample", len(out), dict(collections.Counter(o["stratum"] for o in out)),
          dict(collections.Counter(o["family"] for o in out)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
