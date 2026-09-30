"""The price gap, measured per game with the indexing finally right.

Chain of reasoning, each link measured:
  * our revenue over the steps that are SELL-only differs between wins and losses
    by about $7.4k per game ($129,456 vs $122,092 over 276 games);
  * our sold UNIT COUNT is identical across outcomes (t=0.24 on the day-10-14
    window, and the tape is fixed);
  * therefore the difference is price.
This script measures that price directly, per product, per game, and reports it
split by outcome -- the number earlier attempts failed to produce.

INDEXING, which has now cost this project three separate analyses: in a Kaggle
replay `steps[j][p]["action"]` is the action taken at observation step **j-1**.
The trade during step j is the action stored at `steps[j+1]`; it fills at the
prices shown in `steps[j]`; it moves the money between `steps[j]` and `steps[j+1]`.
Pair those correctly or the result is noise.

On a step whose market list is non-empty and contains only SELL orders, the money
change over that step is the realised revenue for exactly those units.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/realized_price_gap.py
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
KEY = "['BUY_PRODUCT', 'WHEAT', 5], ['BUY_SEED'"


def per_game(steps, p, lo=144, hi=719):
    """item -> (realised revenue, units, quote-weighted price) over SELL-only steps."""
    rev, qty, quo = {}, {}, {}
    for j in range(lo, min(hi, len(steps) - 1)):
        mk = (steps[j + 1][p].get("action") or {}).get("market") or []
        if not mk or any(len(o) < 1 or o[0] != "SELL" for o in mk):
            continue
        m0 = steps[j][p]["observation"]["farms"][p]["money"]
        m1 = steps[j + 1][p]["observation"]["farms"][p]["money"]
        r = m1 - m0
        tot = sum(int(o[2]) for o in mk if len(o) >= 3)
        if tot < 1 or r <= 0:
            continue
        prices = steps[j][p]["observation"]["market"]["prices"]
        for o in mk:
            if len(o) < 3:
                continue
            it, q = o[1], int(o[2])
            rev[it] = rev.get(it, 0.0) + r * q / tot
            qty[it] = qty.get(it, 0) + q
            quo[it] = quo.get(it, 0.0) + q * float(prices.get(it, 0))
    return {it: (rev[it], qty[it], quo[it]) for it in qty if qty[it] > 0}


def main():
    games = []
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
            games.append({"win": raw["rewards"][me] > raw["rewards"][1 - me],
                          "us": per_game(raw["steps"], me),
                          "them": per_game(raw["steps"], 1 - me),
                          "fam": bool(rc.get("sig")) and KEY in str(rc["sig"][0])})
    print("games %d (%dW-%dL)\n" % (len(games), sum(g["win"] for g in games),
                                    sum(not g["win"] for g in games)))

    items = ["MILK", "WOOL", "STRAWBERRY", "EGG", "MELON", "CARROT", "TOMATO", "WHEAT"]
    print("=== realised unit price (revenue/units) per game, averaged over games ===")
    print("%-12s %14s %14s %10s %8s | %14s %14s" %
          ("item", "wins us $/u", "losses us $/u", "diff", "t", "wins them", "losses them"))
    for it in items:
        def side(g, who):
            r = g[who].get(it)
            return (r[0] / r[1]) if r and r[1] else None
        w = [x for x in (side(g, "us") for g in games if g["win"]) if x]
        l = [x for x in (side(g, "us") for g in games if not g["win"]) if x]
        if len(w) < 20 or len(l) < 10:
            continue
        se = ((statistics.pvariance(w) / len(w)) + (statistics.pvariance(l) / len(l))) ** 0.5
        wt = [x for x in (side(g, "them") for g in games if g["win"]) if x]
        lt = [x for x in (side(g, "them") for g in games if not g["win"]) if x]
        print("%-12s %14.2f %14.2f %+10.2f %8.2f | %14.2f %14.2f"
              % (it, statistics.mean(w), statistics.mean(l),
                 statistics.mean(w) - statistics.mean(l),
                 abs(statistics.mean(w) - statistics.mean(l)) / se if se else 0,
                 statistics.mean(wt) if wt else 0, statistics.mean(lt) if lt else 0))

    print("\n=== the same, conditioned on the tetsutani family (n=%d) ==="
          % sum(g["fam"] for g in games))
    for it in ("MILK", "WOOL", "STRAWBERRY"):
        def side(g):
            r = g["us"].get(it)
            return (r[0] / r[1]) if r and r[1] else None
        w = [x for x in (side(g) for g in games if g["win"] and g["fam"]) if x]
        l = [x for x in (side(g) for g in games if not g["win"] and g["fam"]) if x]
        if len(w) < 10 or len(l) < 10:
            continue
        se = ((statistics.pvariance(w) / len(w)) + (statistics.pvariance(l) / len(l))) ** 0.5
        print("  %-12s wins %7.2f  losses %7.2f  diff %+7.2f  t=%.2f (n=%d/%d)"
              % (it, statistics.mean(w), statistics.mean(l),
                 statistics.mean(w) - statistics.mean(l),
                 abs(statistics.mean(w) - statistics.mean(l)) / se if se else 0,
                 len(w), len(l)))

    # total revenue per game, our side
    rw = [sum(v[0] for v in g["us"].values()) for g in games if g["win"]]
    rl = [sum(v[0] for v in g["us"].values()) for g in games if not g["win"]]
    uw = [sum(v[1] for v in g["us"].values()) for g in games if g["win"]]
    ul = [sum(v[1] for v in g["us"].values()) for g in games if not g["win"]]
    print("\n=== totals over SELL-only steps ===")
    print("  revenue: wins $%.0f  losses $%.0f  diff $%+.0f"
          % (statistics.mean(rw), statistics.mean(rl), statistics.mean(rw) - statistics.mean(rl)))
    print("  units  : wins %.0f  losses %.0f  diff %+.0f"
          % (statistics.mean(uw), statistics.mean(ul), statistics.mean(uw) - statistics.mean(ul)))
    print("  implied blended price: wins $%.2f  losses $%.2f"
          % (statistics.mean(rw) / statistics.mean(uw), statistics.mean(rl) / statistics.mean(ul)))


if __name__ == "__main__":
    main()
