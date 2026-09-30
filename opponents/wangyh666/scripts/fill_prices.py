"""Per-player realised sale prices, straight out of the replay.

The loss mining established by elimination that the ladder win/loss is decided by
price, not quantity: our plan is a fixed tape, our SELL unit count is identical
across outcomes (140.5 vs 140.7 in the day-10-14 window, t=0.24), and the shed is
empty at step 719 in 169/170 wins and 77/78 losses.  Revenue = sum(q * p) with q
fixed, so the difference has to be in p.

But every attempt to measure p by comparing the *market price path* between win
and loss cohorts failed, because that comparison is confounded by which opponent
family we drew (the wool differential flips sign under conditioning).  What is
needed is a per-player number.

This gets one, without simulating the engine: on any step where a player's market
list is non-empty and contains only SELL orders, that player's money change over
that step IS their realised revenue for those units -- there is no purchase, no
hire and no land to pay for.  Summing those steps gives a realised revenue, and
dividing by the units sold in them gives a realised average price.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/fill_prices.py
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


def pure_buy_spend(steps, p):
    """(spend, units) over steps whose market list is BUY_PRODUCT-only.

    Costs are NOT all tape-determined: animals, seeds, land and hire fibs are
    fixed prices, but WHEAT and FERTILIZER are bought at the market price, so our
    cost side moves with the book exactly as the revenue side does.
    """
    spend = 0.0
    units = 0
    for k in range(len(steps) - 1):
        mk = (steps[k][p].get("action") or {}).get("market") or []
        if not mk or any(len(o) < 3 or o[0] != "BUY_PRODUCT" for o in mk):
            continue
        q = sum(int(o[2]) for o in mk)
        if q < 1:
            continue
        m0 = steps[k][p]["observation"]["farms"][p]["money"]
        m1 = steps[k + 1][p]["observation"]["farms"][p]["money"]
        spend += m0 - m1
        units += q
    return spend, units


def pure_sell_revenue(steps, p, lo=0, hi=720):
    """(revenue, units) summed over steps whose market list is SELL-only."""
    rev = 0.0
    units = 0
    used = 0
    for k in range(lo, min(hi, len(steps) - 1)):
        mk = (steps[k][p].get("action") or {}).get("market") or []
        if not mk:
            continue
        if any(len(o) >= 1 and o[0] != "SELL" for o in mk):
            continue
        q = sum(int(o[2]) for o in mk if len(o) >= 3)
        if q < 1:
            continue
        m0 = steps[k][p]["observation"]["farms"][p]["money"]
        m1 = steps[k + 1][p]["observation"]["farms"][p]["money"]
        rev += m1 - m0
        units += q
        used += 1
    return rev, units, used


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
            our_r, our_q, our_n = pure_sell_revenue(steps, me)
            th_r, th_q, th_n = pure_sell_revenue(steps, 1 - me)
            our_sp, our_sq = pure_buy_spend(steps, me)
            th_sp, th_sq = pure_buy_spend(steps, 1 - me)
            recs.append({"win": raw["rewards"][me] > raw["rewards"][1 - me],
                         "our_price": our_r / our_q if our_q else None,
                         "their_price": th_r / th_q if th_q else None,
                         "our_q": our_q, "their_q": th_q, "steps": our_n,
                         "rev": our_r, "spend": our_sp,
                         "their_rev": th_r, "their_spend": th_sp,
                         "fam": bool(rc.get("sig")) and KEY in str(rc["sig"][0]),
                         "eid": rc["eid"]})
    ok = [r for r in recs if r["our_price"] and r["their_price"]]
    print("episodes with usable SELL-only steps: %d/%d" % (len(ok), len(recs)))
    print("median SELL-only steps per game: %.0f ; median units priced: %.0f"
          % (statistics.median(r["steps"] for r in ok),
             statistics.median(r["our_q"] for r in ok)))
    print("\nNOTE: this prices only the steps that happened to be SELL-only.  It is a")
    print("      subsample of each player's sales, not the whole book.\n")
    print("%-22s %5s %9s %9s %9s %8s" % ("cohort", "n", "ours", "theirs", "ours-theirs", "t"))
    for lab, sel in (("all", lambda r: True),
                     ("wins", lambda r: r["win"]),
                     ("losses", lambda r: not r["win"]),
                     ("wins | tetsutani", lambda r: r["win"] and r["fam"]),
                     ("losses | tetsutani", lambda r: not r["win"] and r["fam"])):
        g = [r for r in ok if sel(r)]
        if len(g) < 8:
            continue
        d = [r["our_price"] - r["their_price"] for r in g]
        se = statistics.pstdev(d) / len(d) ** 0.5
        print("%-22s %5d %9.1f %9.1f %+9.1f %8.2f"
              % (lab, len(g), statistics.mean(r["our_price"] for r in g),
                 statistics.mean(r["their_price"] for r in g), statistics.mean(d),
                 abs(statistics.mean(d)) / se if se else 0))

    wa = [r["our_price"] - r["their_price"] for r in ok if r["win"]]
    la = [r["our_price"] - r["their_price"] for r in ok if not r["win"]]
    se = ((statistics.pvariance(wa) / len(wa)) + (statistics.pvariance(la) / len(la))) ** 0.5
    print("\nKEY CONTRAST  wins %+.1f  losses %+.1f  difference %+.1f  t=%.2f"
          % (statistics.mean(wa), statistics.mean(la),
             statistics.mean(wa) - statistics.mean(la),
             abs(statistics.mean(wa) - statistics.mean(la)) / se if se else 0))

    # ---- absolute revenue and spend, per game, wins vs losses ----
    print("\n=== ABSOLUTE money flows over the SELL-only / BUY-only steps ===")
    print("%-10s %5s %14s %14s %14s" % ("cohort", "n", "revenue", "spend", "net"))
    stat = {}
    for lab, sel in (("wins", lambda r: r["win"]), ("losses", lambda r: not r["win"])):
        g = [r for r in recs if sel(r)]
        rv = [r["rev"] for r in g if r["rev"] is not None]
        sp = [r["spend"] for r in g if r["spend"] is not None]
        stat[lab] = (rv, sp)
        print("%-10s %5d %14.0f %14.0f %14.0f"
              % (lab, len(g), statistics.mean(rv), statistics.mean(sp),
                 statistics.mean(rv) - statistics.mean(sp)))
    for name, i in (("revenue", 0), ("spend", 1)):
        a, b = stat["wins"][i], stat["losses"][i]
        se = ((statistics.pvariance(a) / len(a)) + (statistics.pvariance(b) / len(b))) ** 0.5
        print("  %-8s wins %+9.0f  losses %+9.0f  difference %+9.0f   t=%.2f"
              % (name, statistics.mean(a), statistics.mean(b),
                 statistics.mean(a) - statistics.mean(b),
                 abs(statistics.mean(a) - statistics.mean(b)) / se if se else 0))


if __name__ == "__main__":
    main()
