"""Does the post-drain tick actually pay more, or only quote higher?

`step % 4 == 1` shows the highest mean market price (MILK 82.40 vs 79.68 at tick 0,
measured over 276 replays).  But the quoted price at a step is the price BEFORE that
step's trades: if sellers crowd tick 1, the realized price there need not be better.
That distinction decides whether a sale-timing layer can do anything at all, so
measure the realized side directly.

Method: on a step whose market list is non-empty and contains only SELL orders, the
player's money change over that step IS the realised revenue for exactly those units
(no purchase, no hire, no land to pay for).  Divide and group by `step % 4`.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/tick_realized.py
"""
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIRS = ["replays_v56566776", "replays_v56556192", "replays_v56552481", "replays_v56539741"]
WATCH = ["MILK", "WOOL", "STRAWBERRY"]
CONTROL = ["EGG", "MELON", "CARROT", "TOMATO", "WHEAT", "FERTILIZER"]


def buckets(steps, p, lo=144):
    """item -> [rev, units, quotes] per step%4, from SELL-only steps.

    INDEXING (this project's most-repeated trap): `steps[j][p]["action"]` is the
    action taken at observation step **j-1**.  So the trade that happened during
    step j is the action stored at `steps[j+1]`, it fills at the prices shown in
    `steps[j]`, and it moves the money between `steps[j]` and `steps[j+1]`.
    Pairing the action at `steps[j]` with that money delta divides one step's cash
    by the previous step's units and produces pure noise.
    """
    out = {}
    for j in range(lo, len(steps) - 1):
        mk = (steps[j + 1][p].get("action") or {}).get("market") or []
        if not mk or any(len(o) < 1 or o[0] != "SELL" for o in mk):
            continue
        m0 = steps[j][p]["observation"]["farms"][p]["money"]
        m1 = steps[j + 1][p]["observation"]["farms"][p]["money"]
        rev = m1 - m0
        tot = sum(int(o[2]) for o in mk if len(o) >= 3)
        if tot < 1 or rev <= 0:
            continue
        quotes = steps[j][p]["observation"]["market"]["prices"]
        for o in mk:
            if len(o) < 3:
                continue
            it, q = o[1], int(o[2])
            share = q / tot
            rec = out.setdefault(it, [[0.0, 0, 0.0] for _ in range(4)])
            rec[j % 4][0] += rev * share
            rec[j % 4][1] += q
            rec[j % 4][2] += q * float(quotes.get(it, 0))
    return out


def main():
    agg = {}
    n = 0
    for d in DIRS:
        for f in sorted(glob.glob(os.path.join(ROOT, d, "episode-*-replay.json"))):
            try:
                raw = json.load(open(f, encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            rc = L.dossier(raw, L.board())
            if not rc or rc.get("self_match"):
                continue
            names = raw["info"]["TeamNames"]
            me = next(i for i, x in enumerate(names) if x in L.OURS)
            n += 1
            b = buckets(raw["steps"], me)
            for it, rec in b.items():
                tgt = agg.setdefault(it, [[0.0, 0, 0.0] for _ in range(4)])
                for i in range(4):
                    tgt[i][0] += rec[i][0]
                    tgt[i][1] += rec[i][1]
                    tgt[i][2] += rec[i][2]
    print("episodes %d\n" % n)

    def show(items, title):
        print("=== %s ===" % title)
        print("%-12s %14s %14s %14s %14s   %s"
              % ("item", "tick0 $/u", "tick1 $/u", "tick2 $/u", "tick3 $/u", "tick1 - tick0"))
        for it in items:
            r = agg.get(it)
            if not r:
                continue
            got = [(r[i][0] / r[i][1] if r[i][1] else 0) for i in range(4)]
            units = [r[i][1] for i in range(4)]
            if sum(units) < 500:
                continue
            print("%-12s %14.2f %14.2f %14.2f %14.2f   %+.2f   (units %s)"
                  % (it, got[0], got[1], got[2], got[3], got[1] - got[0], units))
        print()

    show(WATCH, "REALISED price (money change / units) by tick -- the mechanism's target")
    show(CONTROL, "control items (no price sawtooth -- should show no tick effect)")

    print("=== quoted vs realised on the target items ===")
    print("%-12s %-18s %-18s" % ("item", "quoted 1 - quoted 0", "realised 1 - realised 0"))
    for it in WATCH:
        r = agg.get(it)
        if not r or not r[0][1] or not r[1][1]:
            continue
        q = [r[i][2] / r[i][1] if r[i][1] else 0 for i in range(4)]
        g = [r[i][0] / r[i][1] if r[i][1] else 0 for i in range(4)]
        print("%-12s %+18.2f %+18.2f" % (it, q[1] - q[0], g[1] - g[0]))


if __name__ == "__main__":
    main()
