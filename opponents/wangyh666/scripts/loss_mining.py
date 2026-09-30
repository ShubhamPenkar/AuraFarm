"""Mine our ladder replays for what actually separates a loss from a win.

Why this shape.  `shiiin9`'s section 8 is the warning that governs this kind of
analysis: a set of losses has no wins in it to lose, so any change measured only
against losses looks free.  That is not a hypothetical -- he measured a variant
on 27 recorded losses (4 turned into wins, nothing got worse) and then on a
sample that held wins as well (5 losses turned into wins, **9 wins turned into
losses**).  So every question below is asked as "losses vs wins", never "look at
the losses".

What the replay gives us: both players' full state at every step, including the
fields the live agent never sees (`private.shed`, `private.seeds`,
`private.inventories`).  So the comparison can be paired and complete.

Two questions:
  Q1  At what step is a loss actually decided?  For each lost game, find the
      earliest step after which the money gap is never again non-negative, and
      look at the distribution.  Early decision => the lever is the early
      economy; late => it is the endgame.
  Q2  At a fixed grid of steps, which state variables separate wins from losses,
      and by how much, relative to how much they vary *within* the win cohort?
      A variable that moves more within wins than between wins and losses is
      noise dressed up as a finding.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/loss_mining.py \
        --dirs replays_v56566776,replays_v56556192,replays_v56552481,replays_v56539741
"""
import argparse
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OURS = L.OURS
GRID = [0, 24, 48, 96, 144, 240, 336, 432, 528, 624, 719]


def flat_tiles(x, out):
    """`tiles` nests (quadrant -> row -> cell) and a cell is a dict or 'LOCKED'."""
    if isinstance(x, dict):
        out.append(x)
    elif isinstance(x, (list, tuple)):
        for y in x:
            flat_tiles(y, out)
    return out


def state_at(step_obj, p):
    o = step_obj[p]["observation"]
    f = o["farms"][p]
    tiles = flat_tiles(f.get("tiles") or [], [])
    planted = sum(1 for t in tiles if t.get("kind") == "PLANT")
    animals = sum(1 for t in tiles if t.get("kind") in ("COOP", "PASTURE"))
    locked = 0
    shed = o.get("private", {}).get("shed", {}) or {}
    return {"money": f["money"],
            "crew": 1 + len(f.get("hands") or []),
            "planted": planted, "animals": animals, "locked": locked,
            "shed_units": sum(v for v in shed.values() if isinstance(v, (int, float))),
            "quadrants": len(f.get("unlocked_quadrants") or [])}


def series(rec):
    steps = rec["_steps"]
    me, opp = rec["_me"], rec["_opp"]
    out = {}
    for k in GRID:
        if k >= len(steps):
            continue
        a, b = state_at(steps[k], me), state_at(steps[k], opp)
        out[k] = {"gap": a["money"] - b["money"]}
        for key in ("money", "crew", "planted", "animals", "shed_units", "quadrants"):
            out[k]["our_" + key] = a[key]
            out[k]["their_" + key] = b[key]
    return out


def decision_step(gaps):
    """Earliest grid step after which the gap is never non-negative again."""
    ks = sorted(gaps)
    for i, k in enumerate(ks):
        if all(gaps[j] < 0 for j in ks[i:]):
            return k
    return None


def load(d):
    p = d if os.path.isabs(d) else os.path.join(ROOT, d)
    ratings = L.board()
    recs = []
    for f in sorted(glob.glob(os.path.join(p, "episode-*-replay.json"))):
        try:
            raw = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        rec = L.dossier(raw, ratings)
        if not rec or rec.get("self_match"):
            continue
        names = raw["info"].get("TeamNames") or []
        me = next(i for i, n in enumerate(names) if n in OURS)
        rec["_steps"] = raw["steps"]
        rec["_me"], rec["_opp"] = me, 1 - me
        # dossier() picks index 0 for "us"; re-point the result at the true side.
        rec["our"] = raw["rewards"][me]
        rec["theirs"] = raw["rewards"][1 - me]
        rec["margin"] = rec["our"] - rec["theirs"]
        rec["win"] = rec["margin"] > 0
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="replays_v56566776,replays_v56556192,"
                                    "replays_v56552481,replays_v56539741")
    args = ap.parse_args()

    recs = []
    for d in args.dirs.split(","):
        got = load(d)
        print("%-22s %d scored episodes" % (d, len(got)))
        recs += got
    wins = [r for r in recs if r["win"]]
    loss = [r for r in recs if not r["win"]]
    print("\ntotal %d episodes: %dW-%dL = %.1f%%"
          % (len(recs), len(wins), len(loss), 100 * len(wins) / len(recs)))

    # ---- Q1: when is a loss decided? ----
    print("\n=== Q1: earliest step after which the gap never recovers (losses only) ===")
    dec = []
    for r in loss:
        s = series(r)
        d = decision_step({k: v["gap"] for k, v in s.items()})
        if d is not None:
            dec.append((d, r["margin"], s[d]["gap"]))
    if dec:
        import collections
        by = collections.Counter(d // 24 for d, _, _ in dec)
        print("  n=%d   decision day histogram (day: count)" % len(dec))
        for day in sorted(by):
            print("    day %-3d %-4d %s" % (day, by[day], "#" * by[day]))
        print("  median decision day %.0f   median gap at that point $%+.0f   final median $%+.0f"
              % (statistics.median(d // 24 for d, _, _ in dec),
                 statistics.median(g for _, _, g in dec),
                 statistics.median(m for _, m, _ in dec)))
    no_dec = len(loss) - len(dec)
    print("  losses never fully behind on the money grid: %d/%d (they lost on the final step)"
          % (no_dec, len(loss)))

    # ---- Q1b: the gap day by day, wins vs losses ----
    print("\n=== Q1b: mean money gap by day (our money - theirs) ===")
    print("%-5s %-14s %-14s %-12s %s" % ("day", "wins", "losses", "all", "losses: % behind"))
    for day in range(30):
        k = day * 24
        wv, lv = [], []
        for r in wins + loss:
            s = series(r).get(k)
            if not s:
                continue
            (wv if r["win"] else lv).append(s["gap"])
        if not wv or not lv:
            continue
        behind = 100.0 * sum(1 for x in lv if x < 0) / len(lv)
        print("%-5d %-14.0f %-14.0f %-12.0f %.0f%%" % (
            day, statistics.mean(wv), statistics.mean(lv),
            statistics.mean(wv + lv), behind))

    # ---- Q3: the market, not the farm ----
    # Our agent is a fixed tape, so Q2 should show our own state identical across
    # outcomes.  If it does, the whole difference has to live in what the market
    # paid -- so measure the market directly.
    print("\n=== Q3: mean market price over days 12-29 (the selling window), wins vs losses ===")
    print("%-12s %12s %12s %10s %s" % ("product", "wins", "losses", "diff%", "t (rough)"))
    prods = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
    for prod in prods:
        wv, lv = [], []
        for r in recs:
            steps = r["_steps"]
            ps = []
            for k in range(288, 720):
                pr = steps[k][0]["observation"]["market"]["prices"].get(prod)
                if pr:
                    ps.append(pr)
            if not ps:
                continue
            (wv if r["win"] else lv).append(statistics.mean(ps))
        if not wv or not lv:
            continue
        mw, ml = statistics.mean(wv), statistics.mean(lv)
        se = ((statistics.pvariance(wv) / len(wv)) + (statistics.pvariance(lv) / len(lv))) ** 0.5
        t = abs(mw - ml) / se if se else 0
        print("%-12s %12.1f %12.1f %9.1f%% %8.2f  (n=%d/%d)"
              % (prod, mw, ml, 100 * (mw - ml) / ml, t, len(wv), len(lv)))

    # ---- Q3b: the same, but inside ONE opponent family (removes the confound) ----
    # Pooling every opponent makes the win/loss split a proxy for "which family did
    # we draw", and the families differ in how they trade.  Conditioning on the
    # largest family is the cheapest way to hold that fixed.
    print("\n=== Q3b: same, restricted to the tetsutani family (BUY 5 + seed opening) ===")
    KEY = "['BUY_PRODUCT', 'WHEAT', 5], ['BUY_SEED'"
    fam = [r for r in recs if r.get("sig") and KEY in str(r["sig"][0])]
    fw = [r for r in fam if r["win"]]
    fl = [r for r in fam if not r["win"]]
    print("  family size %d  (%dW-%dL)" % (len(fam), len(fw), len(fl)))
    for prod in ("STRAWBERRY", "WOOL", "MILK", "EGG"):
        wv, lv = [], []
        for r in fam:
            ps = [r["_steps"][k][0]["observation"]["market"]["prices"].get(prod)
                  for k in range(288, 720)]
            ps = [x for x in ps if x]
            if ps:
                (wv if r["win"] else lv).append(statistics.mean(ps))
        if not wv or not lv:
            continue
        mw, ml = statistics.mean(wv), statistics.mean(lv)
        se = ((statistics.pvariance(wv) / len(wv)) + (statistics.pvariance(lv) / len(lv))) ** 0.5
        print("  %-12s wins %7.1f  losses %7.1f  %+6.1f%%   t=%.2f  (n=%d/%d)"
              % (prod, mw, ml, 100 * (mw - ml) / ml, abs(mw - ml) / se if se else 0, len(wv), len(lv)))

    # ---- Q4: what is left in the shed at the final step ----
    print("\n=== Q4: our shed at step 719, wins vs losses (sum over products) ===")
    tot_w, tot_l = [], []
    for r in recs:
        sh = r["_steps"][719][r["_me"]]["observation"].get("private", {}).get("shed", {}) or {}
        s = sum(float(v or 0) for v in sh.values())
        (tot_w if r["win"] else tot_l).append(s)
    print("  total units left: wins %.1f   losses %.1f" % (statistics.mean(tot_w), statistics.mean(tot_l)))
    print("  games finishing with an empty shed: wins %d/%d   losses %d/%d"
          % (sum(1 for x in tot_w if x < 0.5), len(tot_w),
             sum(1 for x in tot_l if x < 0.5), len(tot_l)))

    # ---- Q5: is the price gap supply-driven?  (the race, seen from the book) ----
    print("\n=== Q5: mean market INVENTORY over days 12-29, wins vs losses ===")
    print("%-12s %12s %12s %10s   higher inventory = more supply = lower price" % ("product", "wins", "losses", "diff%"))
    for prod in ("STRAWBERRY", "WOOL", "MILK", "EGG"):
        wv, lv = [], []
        for r in recs:
            steps = r["_steps"]
            iv = [steps[k][0]["observation"]["market"]["inventory"].get(prod)
                  for k in range(288, 720)]
            iv = [x for x in iv if x is not None]
            if not iv:
                continue
            (wv if r["win"] else lv).append(statistics.mean(iv))
        if not wv or not lv:
            continue
        mw, ml = statistics.mean(wv), statistics.mean(lv)
        se = ((statistics.pvariance(wv) / len(wv)) + (statistics.pvariance(lv) / len(lv))) ** 0.5
        print("%-12s %12.1f %12.1f %9.2f%%   t=%.2f"
              % (prod, mw, ml, 100 * (mw - ml) / ml, abs(mw - ml) / se if se else 0))

    # ---- Q6: over days 8-18, does the winner earn more, or the loser earn less? ----
    print("\n=== Q6: our money and their money, days 8-18 (mean) ===")
    print("%-5s %-30s %-30s" % ("day", "wins: our / their / gap", "losses: our / their / gap"))
    for day in (8, 10, 12, 14, 16, 18, 20, 22, 26, 29):
        k = day * 24
        ow = [series(r)[k] for r in wins if k in series(r)]
        ol = [series(r)[k] for r in loss if k in series(r)]
        if not ow or not ol:
            continue
        f = lambda g, key: statistics.mean(x[key] for x in g)
        print("%-5d %-30s %-30s" % (
            day,
            "%.0f / %.0f / %+.0f" % (f(ow, "our_money"), f(ow, "their_money"), f(ow, "gap")),
            "%.0f / %.0f / %+.0f" % (f(ol, "our_money"), f(ol, "their_money"), f(ol, "gap"))))

    # ---- Q7: per-day income, so the shortfall is localised to a day ----
    print("\n=== Q7: income per day (delta of money), mean over games ===")
    print("%-12s %10s %10s %10s | %10s %10s %10s"
          % ("days", "our W", "our L", "d(our)", "their W", "their L", "d(their)"))
    def money(r, k):
        st = r["_steps"]
        me, op = r["_me"], r["_opp"]
        return (st[k][me]["observation"]["farms"][me]["money"],
                st[k][op]["observation"]["farms"][op]["money"])

    for d0 in range(0, 29):
        k0, k1 = d0 * 24, (d0 + 1) * 24
        acc = {("w", "o"): [], ("w", "t"): [], ("l", "o"): [], ("l", "t"): []}
        for r in recs:
            if k1 >= len(r["_steps"]):
                continue
            a0, b0 = money(r, k0)
            a1, b1 = money(r, k1)
            tag = "w" if r["win"] else "l"
            acc[(tag, "o")].append(a1 - a0)
            acc[(tag, "t")].append(b1 - b0)
        if not acc[("w", "o")]:
            continue
        m = lambda key: statistics.mean(acc[key])
        do = m(("w", "o")) - m(("l", "o"))
        dt = m(("w", "t")) - m(("l", "t"))
        if d0 >= 6:
            print("day %-3d-%-3d %10.0f %10.0f %+10.0f | %10.0f %10.0f %+10.0f"
                  % (d0, d0 + 1, m(("w", "o")), m(("l", "o")), do,
                     m(("w", "t")), m(("l", "t")), dt))

    # ---- Q2: which state variables separate wins from losses? ----
    print("\n=== Q2: state at grid steps, wins vs losses (sep/sd = |mean diff| / sd within wins) ===")
    print("%-6s %-18s %12s %12s %10s %8s" % ("step", "variable", "wins", "losses", "win sd", "sep/sd"))
    for k in GRID:
        for var in ("gap", "our_crew", "their_crew", "our_planted", "their_planted",
                    "our_animals", "their_animals", "our_shed_units", "our_quadrants",
                    "our_money", "their_money"):
            wv, lv = [], []
            for r in wins:
                s = series(r).get(k)
                if s:
                    wv.append(s[var])
            for r in loss:
                s = series(r).get(k)
                if s:
                    lv.append(s[var])
            if not wv or not lv:
                continue
            mw, ml = statistics.mean(wv), statistics.mean(lv)
            sd = statistics.pstdev(wv) or 1e-9
            print("%-6d %-18s %12.1f %12.1f %10.1f %8.2f" % (k, var, mw, ml, sd, abs(mw - ml) / sd))
        print()


if __name__ == "__main__":
    main()
