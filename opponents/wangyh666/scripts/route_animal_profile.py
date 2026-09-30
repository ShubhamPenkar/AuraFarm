"""What do our 41 routes actually differ IN?

The adaptive direction from `shiiin9` section 4 rests on one structural claim: the
routes the router can pick plant the same crops and differ only in the ANIMALS, and
cows and sheep share a pasture, so swapping one for the other at purchase time
changes nothing else in the route.  That is what makes a late, evidence-gated swap
safe.

Before building anything we need to know whether that holds for OUR table.  If our
41 tapes differ in crop plan or in timing, a mid-game swap is not a local edit and
the whole idea changes shape.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/route_animal_profile.py
"""
import base64
import collections
import json
import os
import re
import sys
import zlib

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_blob(src, varname):
    m = re.search(re.escape(varname) + r"\s*=\s*json\.loads\(zlib\.decompress\(base64\.b85decode\('([^']+)'\)\)\)", src)
    return json.loads(zlib.decompress(base64.b85decode(m.group(1)))) if m else None


def main():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    data = load_blob(src, "_R108_DATA")
    actions = data["actions"]
    routes = {int(k): [actions[i] for i in v] for k, v in data["routes"].items()}
    shops = {tuple(r["shops"]): r["route"] for r in data["shops"]}

    print("route  len  animals (type x count, first order step)          crops (count)")
    for rid in sorted(routes):
        tape = routes[rid]
        animals = collections.Counter()
        first = {}
        crops = collections.Counter()
        for t, step in enumerate(tape):
            if not isinstance(step, dict):
                continue
            for o in (step.get("market") or []):
                if len(o) >= 3 and o[0] == "BUY_ANIMAL":
                    animals[o[1]] += int(o[2])
                    first.setdefault(o[1], t)
        a = " ".join("%s x%d@%d" % (k, v, first[k]) for k, v in sorted(animals.items()))
        print("r%-4d  %-4d %-46s" % (rid, len(tape), a))

    # which animals, and do routes differ ONLY in animals?
    sig = {}
    for rid, tape in routes.items():
        key = []
        for step in tape:
            if not isinstance(step, dict):
                continue
            for o in (step.get("market") or []):
                if len(o) >= 3 and o[0] == "BUY_ANIMAL":
                    key.append((o[1], int(o[2])))
        sig[rid] = tuple(key)
    print("\ndistinct animal-order sequences across the 41 routes: %d"
          % len(set(sig.values())))
    groups = collections.defaultdict(list)
    for rid, k in sig.items():
        groups[k].append(rid)
    for k, ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print("  %-52s %s" % (str(k)[:52], sorted(ids)))

    print("\n=== which shop pairs map to which animal signature group ===")
    for sp in sorted(shops):
        rid = shops[sp]
        print("  %-40s -> r%-4d %s" % (str(sp), rid, str(sig.get(rid, ()))[:44]))


if __name__ == "__main__":
    main()
