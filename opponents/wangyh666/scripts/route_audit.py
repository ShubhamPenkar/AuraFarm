"""Audit our 41-tape route table against the shop pairs it is indexed by.

Claim H10 (from `master-engine-v4`'s self-description): the 41 routes are
**13 classical V39 tapes + 28 `EXP240` shop-specialised tapes**, chosen at
step 144 by the first two unlocked shops.  `SESSION_STATE.md` §9.3.2 makes this
the cheap, verifiable open item: "do our 41 tapes group that way, and did any
shop pair land in the wrong group?"

The table lives in `main.py` as an embedded base85+zlib blob (`_R108_DATA`), so
this reads it out of the source rather than importing the agent (importing runs
the whole 1 MB build).

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/route_audit.py
"""
import base64
import json
import os
import re
import sys
import zlib

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_blob(src, varname, path):
    """Pull `<varname>=json.loads(zlib.decompress(base64.b85decode('...')))` out."""
    m = re.search(re.escape(varname) + r"\s*=\s*json\.loads\(zlib\.decompress\(base64\.b85decode\('([^']+)'\)\)\)", src)
    if not m:
        return None
    return json.loads(zlib.decompress(base64.b85decode(m.group(1))))


def action_kinds(tape):
    """Which products a tape ever touches, and how, over its whole length.

    `_ROUTES` stores index lists into the shared `actions` table, so the caller
    must resolve them first (`resolve`).
    """
    kinds = {}
    for step in tape:
        if not isinstance(step, dict):
            continue
        for order in (step.get("market") or []):
            if len(order) < 3:
                continue
            op, item = order[0], order[1]
            kinds.setdefault(item, set()).add(op)
    return kinds


def resolve(routes, actions):
    """route id -> concrete action list, via the shared `actions` blob table."""
    return {k: [actions[i] for i in v] for k, v in routes.items()}


def main():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    data = load_blob(src, "_R108_DATA", "main.py")
    if data is None:
        sys.exit("could not extract _R108_DATA from main.py")

    routes_raw = {int(k): v for k, v in data["routes"].items()}
    actions = data["actions"]
    routes = resolve(routes_raw, actions)
    shops = data["shops"]
    print("routes  : %d   ids: %s" % (len(routes), sorted(routes)))
    print("actions : %d (shared action blobs)" % len(actions))
    print("shop rows: %d" % len(shops))
    print("route lengths: %s" % sorted({len(r) for r in routes.values()}))

    # `_R108_SHOP_ROUTES={tuple(r['shops']):r['route'] for r in ...}`
    keyed = {tuple(r["shops"]): r["route"] for r in shops}
    used = sorted(set(keyed.values()))
    print("\nshop pairs: %d   distinct route ids referenced: %d" % (len(keyed), len(used)))
    missing = [k for k in routes if k not in used]
    print("route ids never referenced by any shop pair: %s" % (missing or "none"))
    dupes = {}
    for k, v in keyed.items():
        dupes.setdefault(v, []).append(k)
    print("\nroutes serving >1 shop pair:")
    for rid, ks in sorted(dupes.items()):
        if len(ks) > 1:
            print("  route %-4s  %d pairs  %s" % (rid, len(ks), ks[:6]))

    print("\n=== the shop table (route -> shop pair -> products the tape touches) ===")
    rows = []
    for r in shops:
        rid = r["route"]
        tape = routes.get(rid)
        k = action_kinds(tape) if tape else {}
        sell = sorted(p for p, ops in k.items() if "SELL" in ops)
        buy = sorted(p for p, ops in k.items() if p not in sell)
        rows.append((rid, tuple(r["shops"]), sell, buy, len(tape) if tape else 0))
    for rid, sp, sell, buy, n in sorted(rows, key=lambda x: (x[0], x[1])):
        print("  r%-4s len=%-4d shops=%-38s sells=%-42s buys=%s" % (rid, n, sp, sell, buy))

    # Does a route ever sell the product its shops actually buy?
    SHOP_PRODUCT = {"YARN_STORE": "WOOL", "MILK_STORE": "MILK", "EGG_STORE": "EGG",
                    "BAKERY": "WHEAT", "PET_CAFE": "EGG", "SMOOTHIE": "MILK",
                    "FLOWER_SHOP": "STRAWBERRY", "SUSHI": "FISH"}
    print("\n=== shops whose flagships product the tape never sells ===")
    bad = 0
    for rid, sp, sell, buy, n in sorted(rows, key=lambda x: (x[0], x[1])):
        want = {SHOP_PRODUCT[s] for s in sp if s in SHOP_PRODUCT}
        miss = sorted(want - set(sell))
        if miss:
            bad += 1
            print("  r%-4s shops=%-38s never sells %s (sells %s)" % (rid, sp, miss, sell))
    print("  %d/%d rows" % (bad, len(rows)))

    out = os.path.join(ROOT, "tmp_analysis", "route_audit.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"n_routes": len(routes), "n_shops": len(shops),
                   "used": used, "unused": missing,
                   "rows": [{"route": r, "shops": list(s), "sells": sl, "buys": b, "len": n}
                            for r, s, sl, b, n in rows]}, f, indent=1)
    print("\nwrote %s" % os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
