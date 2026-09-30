"""Diff our shop-pair -> tape assignment against our siblings' copies of it.

`claims.md` H10 (from `master-engine-v4`'s self-description) says the route table
is 13 classical tapes + 28 `EXP240` shop-specialised ones, chosen at step 144 by
the first two unlocked shops.  `scripts/route_audit.py` confirms the split is
exactly 13 + 28 on our side.

What static analysis *cannot* answer is "did a shop pair land in the wrong
group": every route in the table sells the same nine products, so the
specialisation is in timing, not in product mix, and there is no product-match
oracle to test against.  What we can do instead is cheaper and stronger --
several agents in our own lineage ship the same table, and `master-engine-v4`
is the source H10's claim comes from.  Where two independent copies disagree on
which tape a shop pair should get, at most one of them can be right.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/route_compare.py
"""
import base64
import json
import os
import re
import sys
import zlib

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SIBLINGS = ["main.py", "opponents/guruv4/main.py", "opponents/guru/main.py",
            "opponents/v56/main.py", "opponents/tetsutani_cha22/main.py",
            "opponents/v55/main.py", "opponents/prvsiyan/main.py",
            "opponents/pipe16/main.py", "opponents/hybrid2965/main.py"]


def shop_map(path):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"_R108_DATA\s*=\s*json\.loads\(zlib\.decompress\(base64\.b85decode\('([^']+)'\)\)\)", src)
    if not m:
        return None
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return {tuple(r["shops"]): r["route"] for r in data["shops"]}


def main():
    base_path = os.path.join(ROOT, "main.py")
    base = shop_map(base_path)
    if base is None:
        sys.exit("no _R108_DATA in main.py")
    print("main.py: %d shop pairs, %d distinct routes\n" % (len(base), len(set(base.values()))))

    print("%-34s %-8s %s" % ("sibling", "blobs", "disagreements with main.py"))
    print("-" * 100)
    for sib in SIBLINGS[1:]:
        p = os.path.join(ROOT, sib)
        if not os.path.exists(p):
            print("%-34s %-8s MISSING" % (sib, "-"))
            continue
        m = shop_map(p)
        if m is None:
            print("%-34s %-8s no _R108_DATA blob" % (sib, 0))
            continue
        diff = [(k, base[k], m[k]) for k in sorted(set(base) & set(m)) if base[k] != m[k]]
        only_us = sorted(set(base) - set(m))
        only_them = sorted(set(m) - set(base))
        tag = "%d/%d" % (len(diff), len(base))
        print("%-34s %-8d %s" % (sib, len(m), tag))
        for k, ours, theirs in diff[:40]:
            print("      %-40s ours r%-4s theirs r%-4s" % (str(k), ours, theirs))
        if len(diff) > 40:
            print("      ... and %d more" % (len(diff) - 40))
        if only_us:
            print("      pairs only we cover: %s" % (only_us[:8],))
        if only_them:
            print("      pairs only they cover: %s" % (only_them[:8],))

    out = os.path.join(ROOT, "tmp_analysis", "route_compare.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    dump = {}
    for s in SIBLINGS:
        p = os.path.join(ROOT, s)
        if os.path.exists(p):
            m = shop_map(p)
            if m:
                dump[s] = {"|".join(k): v for k, v in m.items()}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=1)
    print("\nwrote %s" % os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
