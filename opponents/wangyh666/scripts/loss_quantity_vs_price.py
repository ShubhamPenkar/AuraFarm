"""Quantity or price?  Split the day-10-to-14 revenue shortfall into its two factors.

`loss_mining.py` localised the divergence: our own income is ~$5.2k lower by day 26
in the games we lose, the opponent's income barely moves, and the cohorts separate
between day 10 and day 14.  Our plan is a fixed tape (planted/quadrants/animals are
identical to sd 0 across outcomes), and the final shed is empty in 169/170 wins and
77/78 losses.  So there are only two ways the income can differ:

  * we SELL a different number of units (production or timing), or
  * we sell the same units at different prices.

This measures the first one directly.  Requested units are read straight off the
SELL orders; since the shed ends empty, the tape's later SELLs are caps that are
filled by whatever arrived since, so the *requested* total is an upper bound on
what moved but a faithful signature of the plan.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/loss_quantity_vs_price.py
"""
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CASH = ["STRAWBERRY", "WOOL", "MILK", "EGG", "MELON", "CARROT", "TOMATO"]
DIRS = ["replays_v56566776", "replays_v56556192", "replays_v56552481", "replays_v56539741"]


def load(d):
    p = os.path.join(ROOT, d)
    ratings = L.board()
    out = []
    for f in sorted(glob.glob(os.path.join(p, "episode-*-replay.json"))):
        try:
            raw = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        rec = L.dossier(raw, ratings)
        if not rec or rec.get("self_match"):
            continue
        names = raw["info"].get("TeamNames") or []
        me = next(i for i, n in enumerate(names) if n in L.OURS)
        rec["_steps"], rec["_me"] = raw["steps"], me
        rec["margin"] = raw["rewards"][me] - raw["rewards"][1 - me]
        rec["win"] = rec["margin"] > 0
        out.append(rec)
    return out


def units(rec, prod):
    """(units sold days 0-9, days 10-14, days 15-29) from our own SELL orders."""
    buckets = [0, 0, 0]
    for k, st in enumerate(rec["_steps"]):
        for o in ((st[rec["_me"]].get("action") or {}).get("market") or []):
            if len(o) >= 3 and o[0] == "SELL" and o[1] == prod:
                b = 0 if k < 240 else (1 if k < 360 else 2)
                buckets[b] += int(o[2])
    return buckets


def main():
    recs = []
    for d in DIRS:
        recs += load(d)
    wins = [r for r in recs if r["win"]]
    loss = [r for r in recs if not r["win"]]
    print("episodes %d  (%dW-%dL)\n" % (len(recs), len(wins), len(loss)))

    print("=== requested SELL units, by product and phase (wins vs losses) ===")
    print("%-12s %-26s %-26s %s" % ("product", "wins  d0-9/d10-14/d15-29",
                                    "losses d0-9/d10-14/d15-29", "d(day10-14)"))
    for prod in CASH:
        wv = [units(r, prod) for r in wins]
        lv = [units(r, prod) for r in loss]
        if not any(sum(x) for x in wv + lv):
            continue
        mw = [statistics.mean(x[i] for x in wv) for i in range(3)]
        ml = [statistics.mean(x[i] for x in lv) for i in range(3)]
        print("%-12s %-26s %-26s %+.1f"
              % (prod, "/".join("%.0f" % v for v in mw), "/".join("%.0f" % v for v in ml),
                 mw[1] - ml[1]))

    print("\n=== the same, summed over the cash products ===")
    tw = twl = 0.0
    for i, lab in enumerate(("days 0-9", "days 10-14", "days 15-29")):
        wv = [sum(units(r, p)[i] for p in CASH) for r in wins]
        lv = [sum(units(r, p)[i] for p in CASH) for r in loss]
        se = ((statistics.pvariance(wv) / len(wv)) + (statistics.pvariance(lv) / len(lv))) ** 0.5
        print("  %-12s wins %7.1f   losses %7.1f   diff %+6.1f   t=%.2f"
              % (lab, statistics.mean(wv), statistics.mean(lv),
                 statistics.mean(wv) - statistics.mean(lv),
                 abs(statistics.mean(wv) - statistics.mean(lv)) / se if se else 0))
        if i == 1:
            tw, twl = statistics.mean(wv), statistics.mean(lv)

    print("\n=== these are the SAME tape, so if the totals match, the gap is price ===")
    print("  day-10-14 unit difference: %+.1f  (%.2f%% of the win-cohort volume)"
          % (tw - twl, 100 * (tw - twl) / tw if tw else 0))


if __name__ == "__main__":
    main()
