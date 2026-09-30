"""Split our income by channel, and test whether the outcome tracks the shop draw.

The money-flow residual in `fill_prices.py` showed the whole win/loss difference sits
outside our own SELL orders (+$6,630, t=2.28), while our SELL revenue is identical
across outcomes (t=0.34).  The config explains why:

    townCenterSellInterval : 24   the town centre buys from us once a day
    townShopSellInterval   :  4   every unlocked shop buys from us every 4 steps
    townShopUnlockInterval :  3   a new shop unlocks every 3 days

So most of our money arrives *automatically*, as a function of which shops the town
has unlocked -- a channel our market layer never touches.

Two questions:
  Q1  how big is the shop/town channel relative to our own SELL orders?
  Q2  is the outcome tracked by the shop *draw*?  If the games we win are the games
      where the town unlocked the more valuable shops, then a large part of our
      ladder result is world luck, and the lever is adapting to the world (which is
      exactly what our router fails to do: it fixes the herd at day 6 from the
      first two shops, and the town does not finish opening until day 24).

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/shop_channel.py
"""
import collections
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


def channels(steps, p):
    """(shop/town income, own-SELL income, own-SELL units) for one player."""
    shop = sell = 0.0
    units = 0
    for k in range(len(steps) - 1):
        mk = (steps[k][p].get("action") or {}).get("market") or []
        m0 = steps[k][p]["observation"]["farms"][p]["money"]
        m1 = steps[k + 1][p]["observation"]["farms"][p]["money"]
        if m1 <= m0:
            continue
        if any(len(o) >= 1 and o[0] == "SELL" for o in mk):
            sell += m1 - m0
            units += sum(int(o[2]) for o in mk if len(o) >= 3 and o[0] == "SELL")
        else:
            shop += m1 - m0
    return shop, sell, units


def main():
    recs = []
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
            me = next(i for i, n in enumerate(names) if n in L.OURS)
            steps = raw["steps"]
            shop, sell, units = channels(steps, me)
            opshop, opsell, _ = channels(steps, 1 - me)
            recs.append({"win": raw["rewards"][me] > raw["rewards"][1 - me],
                         "shop": shop, "sell": sell, "units": units,
                         "opshop": opshop, "opsell": opsell,
                         "shops": list(steps[719][0]["observation"].get("town", {}).get("unlocked_shops") or []),
                         "fam": bool(rc.get("sig")) and KEY in str(rc["sig"][0]),
                         "eid": rc["eid"]})
    w = [r for r in recs if r["win"]]
    l = [r for r in recs if not r["win"]]
    print("episodes %d (%dW-%dL)\n" % (len(recs), len(w), len(l)))

    print("=== Q1: income by channel ===")
    print("%-10s %5s %14s %14s %14s" % ("cohort", "n", "shop/town", "own SELL", "shop share"))
    for lab, g in (("wins", w), ("losses", l)):
        s = statistics.mean(x["shop"] for x in g)
        o = statistics.mean(x["sell"] for x in g)
        print("%-10s %5d %14.0f %14.0f %13.0f%%" % (lab, len(g), s, o, 100 * s / (s + o)))
    for key, name in (("shop", "shop/town"), ("sell", "own SELL")):
        a = [x[key] for x in w]
        b = [x[key] for x in l]
        se = ((statistics.pvariance(a) / len(a)) + (statistics.pvariance(b) / len(b))) ** 0.5
        print("  %-10s wins %+9.0f  losses %+9.0f  difference %+9.0f   t=%.2f"
              % (name, statistics.mean(a), statistics.mean(b),
                 statistics.mean(a) - statistics.mean(b),
                 abs(statistics.mean(a) - statistics.mean(b)) / se if se else 0))

    print("\n=== Q2: the shop draw, wins vs losses ===")
    for lab, g in (("wins", w), ("losses", l)):
        c = collections.Counter()
        for r in g:
            c.update(r["shops"])
        print("  %-7s n=%d  mean shops unlocked %.1f" % (lab, len(g),
                                                         statistics.mean(len(r["shops"]) for r in g)))
        for k, v in c.most_common():
            print("        %-16s %.2f/game" % (k, v / len(g)))

    print("\n=== Q2b: shops unlocked by day 6 (what our router sees) vs the final town ===")
    for lab, g in (("wins", w), ("losses", l)):
        first2 = collections.Counter(tuple(r["shops"][:2]) for r in g)
        print("  %-7s first two shops:" % lab)
        for k, v in first2.most_common(6):
            print("        %-40s %.2f/game" % (str(k), v / len(g)))


if __name__ == "__main__":
    main()
