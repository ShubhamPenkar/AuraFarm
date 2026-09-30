"""Upper bound on what a SALE-TIMING change is worth, measured on real ladder replays.

WHAT THIS IS
-----------
The market has a 4-step sawtooth: `_town_consume` removes shop demand from
`market["inventory"]` only when `step % 4 == 0` and immediately re-prices, so the
step that trades right after the refresh (`step % 4 == 1`) sees the highest prices
for MILK / WOOL / STRAWBERRY.  So: if our sale units could be moved off the bad
ticks onto tick 1, how many dollars are on the table?  This script answers that
with an ORACLE on top of the recorded price tape.

FOR EACH EPISODE, FOR OUR SIDE AND SEPARATELY FOR THE OPPONENT:
  (a) ACTUAL  revenue proxy = sum over steps k in [144,720) of
      (units of X we SELL at k) * (market price of X in the observation at k),
      summed over X in {MILK, WOOL, STRAWBERRY}.
  (b) ORACLE  revenue proxy = the same, except every sale is priced at the FIRST
      step k' >= k with k' % 4 == 1, using that step's observed price.  If no such
      k' exists before step 720, the sale is priced at step k (nothing to gain at
      the end of the game).

(b) IS AN UPPER BOUND, NOT AN ACHIEVABLE ESTIMATE.  Two reasons, both fatal to any
claim that the gap is collectable:
  (i)  The shifted sales are priced on the OBSERVED price path, a path that already
       contains the effect of our own sales landing where they did.  Moving supply
       from tick 2 to tick 1 lowers the tick-1 price and raises the tick-2 price, so
       the real gain is strictly smaller than this oracle - and against an opponent
       who is also moving its supply, it can be smaller still.
  (ii) It assumes the goods are still in the shed when the delayed sale happens.
       Shed capacity is 100 and stock that cannot be stored is simply not sellable
       later; the oracle never models that.
Use this number to decide whether the idea is worth BUILDING (is the ceiling worth
the trouble?), never as a prediction of the gain.

TWO PRICE-BASIS CONVENTIONS, AND WHY BOTH ARE PRINTED
----------------------------------------------------
`steps[k][p]["action"]` is the action taken at observation step k-1 and it is
executed in the step whose end-state is recorded at index k, so the price it
actually trades against is the one in the observation at index k-1.  This script
verifies that against the replay's own cash deltas (the CALIBRATION line): for
steps whose only orders are SELLs, `money[k] - money[k-1]` is the cash from
`action[k]`, and predicting it with obs[k-1] prices is much closer than with
obs[k] prices.
  * PRIMARY   -- the requested convention: action recorded at index k priced at
                 obs[k]; shift = first k' >= k with k' % 4 == 1.
  * ENGINE-TRUTH -- the physically correct one: the sale actually got the obs[k-1]
                 price, so BOTH its columns are priced from obs[k-1]; shift = first
                 j >= k-1 with j % 4 == 1.
Each block is internally matched (one basis for actual, one for the shifted sale);
only PRIMARY answers the question as literally asked.  The two differ because the
recorded price at index k is the post-trade price of the action recorded at index
k, so PRIMARY reads a price the sale never got.  Watch the ENGINE-TRUTH block: its
ACTUAL is the better revenue proxy (it is what the shed actually banked), and its
gain can be NEGATIVE, because the tape's next tick-1 price is often below the price
our own dump got -- see the per-tick WHY line.

Neither is "our sale revenue" exactly: the recorded market price is the price of
the FIRST unit of that order (the engine walks a per-unit lockstep loop, so the
2nd..nth unit of a big order fill slightly worse), orders are capped at
maxMarketOrdersPerTurn and can fail on shed capacity.  (a) and (b) share that bias,
so the difference between them is still meaningful.

SELF-MATCHES ARE EXCLUDED: when both team names are ours the replay does not say
which index is which version (`ladder_dossier.dossier` flags `self_match`).

Usage:  .venv/Scripts/python -u scripts/tick_oracle.py [dirs...]
"""
import argparse
import collections
import glob
import json
import os
import statistics
import sys

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ITEMS = ("MILK", "WOOL", "STRAWBERRY")
T0, T1 = 144, 720
DEFAULT_DIRS = ["replays_v56566776", "replays_v56556192",
                "replays_v56552481", "replays_v56539741"]


def sells_by_item(action):
    """SELL orders in one action, by product, summed."""
    out = collections.Counter()
    mk = (action or {}).get("market") or [] if isinstance(action, dict) else []
    if not isinstance(mk, list):
        return out
    for o in mk:
        if (isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                and isinstance(o[1], str)):
            try:
                q = int(o[2])
            except (TypeError, ValueError):
                continue
            if q > 0:
                out[o[1]] += q
    return out


def other_ops(action):
    """True if the action carries any non-SELL market order."""
    mk = (action or {}).get("market") or [] if isinstance(action, dict) else []
    if not isinstance(mk, list):
        return False
    return any(isinstance(o, list) and o and o[0] != "SELL" for o in mk)


def first_tick1(b, hi=T1):
    """Smallest j >= b with j % 4 == 1; None if there is none below hi."""
    j = b + ((1 - b) % 4)
    return j if j < hi else None


def run_episode(raw):
    steps = raw.get("steps") or []
    n = min(len(steps), T1)
    names = raw["info"].get("TeamNames") or []
    rec = L.dossier(raw, {})
    if rec is None or rec.get("self_match"):
        return None
    ours = [i for i, nm in enumerate(names) if nm in L.OURS]
    if not ours:
        return None
    me = ours[0]
    opp = 1 - me

    # prices[k] = market prices as recorded at index k (shared by both players)
    prices = []
    for k in range(n):
        try:
            prices.append(steps[k][me]["observation"]["market"]["prices"])
        except Exception:  # noqa: BLE001
            prices.append(None)

    out = {"eid": raw["info"].get("EpisodeId"), "opp": names[opp] if opp < len(names) else "?",
           "win": rec["win"], "margin": rec["margin"],
           "our": rec["our"], "theirs": rec["theirs"], "calib": [], "sides": {}}

    for tag, pid in (("our", me), ("opp", opp)):
        acc = {c: {"act": 0.0, "act_true": 0.0, "oracle": 0.0, "units": 0} for c in ITEMS}
        acc["_tru"] = {c: 0.0 for c in ITEMS}
        acc["_shift"] = collections.Counter()
        acc["_tshift"] = collections.Counter()
        acc["_byidx"] = collections.Counter()
        acc["_tick"] = {}      # (item, execution tick) -> [units, $ actual, $ at shift target]
        acc["_qb"] = {}        # (execution tick, qty bucket) -> [units, $ actual, $ at target]
        acc["_tape"] = {}      # (item, price-index tick) -> [sum of tape prices, steps]
        acc["_endcap"] = 0
        acc["_tendcap"] = 0
        act_all = 0.0
        act_all_true = 0.0
        for k in range(T0, n):
            s = sells_by_item(steps[k][pid].get("action"))
            if not s:
                continue
            act_all_items = s
            pk = prices[k]
            if pk is None:
                continue
            act_all += sum(q * float(pk.get(it, 0)) for it, q in act_all_items.items())
            pkm1 = prices[k - 1] if k >= 1 else None
            if pkm1 is None:
                pkm1 = pk
            act_all_true += sum(q * float(pkm1.get(it, 0)) for it, q in act_all_items.items())
            for it in ITEMS:
                tc = acc["_tape"].setdefault((it, k % 4), [0.0, 0])
                tc[0] += float(pk.get(it, 0))
                tc[1] += 1
            for it, q in act_all_items.items():
                if it not in ITEMS:
                    continue
                p = pk.get(it)
                if not p:
                    continue
                acc[it]["act"] += q * p
                acc[it]["units"] += q
                acc["_byidx"][k % 4] += q
            # PRIMARY shift (action index k -> obs[k])
            k2 = first_tick1(k)
            if k2 is None:
                acc_end = True
                pk2 = pk
            else:
                acc_end = False
                pk2 = prices[k2] or pk
            for it, q in act_all_items.items():
                if it in ITEMS and pk.get(it):
                    acc[it]["oracle"] += q * (pk2.get(it, pk[it]))
            acc["_shift"][(k2 - k) if k2 is not None else 0] += sum(
                q for it, q in act_all_items.items() if it in ITEMS and pk.get(it))
            if acc_end:
                acc["_endcap"] += sum(q for it, q in act_all_items.items()
                                      if it in ITEMS and pk.get(it))
            # ENGINE-TRUTH shift (b = k-1 is the price basis, target index j)
            b = k - 1
            j = first_tick1(b)
            pj = (prices[j] if j is not None else None) or pkm1
            for it, q in act_all_items.items():
                if it not in ITEMS or not pkm1.get(it):
                    continue
                acc[it]["act_true"] += q * pkm1[it]
                acc["_tru"][it] += q * pj.get(it, pkm1[it])
                acc["_tshift"][(j - b) if j is not None else 0] += q
                if j is None:
                    acc["_tendcap"] += q
                fill = q * pkm1[it]
                tgt = q * pj.get(it, pkm1[it])
                tc = acc["_tick"].setdefault((it, b % 4), [0.0, 0.0, 0.0])
                tc[0] += q
                tc[1] += fill
                tc[2] += tgt
                qb = "1" if q == 1 else ("2-4" if q <= 4 else "5+")
                tq = acc["_qb"].setdefault((b % 4, qb), [0.0, 0.0, 0.0])
                tq[0] += q
                tq[1] += fill
                tq[2] += tgt
        # calibration on our side: does obs[k-1] predict the cash delta better than obs[k]?
        if tag == "our":
            ea = eb = sa = sb = 0.0
            cnt = zero = 0
            gross = 0.0
            for k in range(1, n):
                try:
                    d = (steps[k][pid]["observation"]["farms"][pid]["money"]
                         - steps[k - 1][pid]["observation"]["farms"][pid]["money"])
                except Exception:  # noqa: BLE001
                    continue
                gross += d if d > 0 else 0.0
                act = steps[k][pid].get("action")
                s = sells_by_item(act)
                if not s or other_ops(act) or prices[k] is None or prices[k - 1] is None:
                    continue
                pa = sum(q * float(prices[k].get(it, 0)) for it, q in s.items())
                pb = sum(q * float(prices[k - 1].get(it, 0)) for it, q in s.items())
                ea += abs(pa - d)
                eb += abs(pb - d)
                sa += abs(pa)
                sb += abs(pb)
                cnt += 1
                zero += 1 if abs(d) < 1 else 0
            out["calib"] = (cnt, ea, sa, eb, sb, zero)
            out["gross"] = gross
        out["sides"][tag] = {"acc": acc, "act_all": act_all, "act_all_true": act_all_true}
    # cash check: our all-item proxy vs the replay's own gross sell receipts
    ou = out["sides"]["our"]
    out["scale"] = (out["gross"] / ou["act_all"]) if (ou["act_all"] and out.get("gross")) else 1.0
    out["scale_true"] = (out["gross"] / ou["act_all_true"]) if (ou["act_all_true"]
                                                                and out.get("gross")) else 1.0
    return out


def fmt_money(x):
    return "$%s" % format(int(round(x)), ",")


def pad(s, w):
    return str(s).ljust(w)


def side_totals(recs, tag, conv):
    """Per-item and total (units, actual, oracle) for one side under one convention."""
    per = {it: [0.0, 0.0, 0.0] for it in ITEMS}   # units, actual, oracle
    shifts = collections.Counter()
    byidx = collections.Counter()
    ticks = {}
    tape = {}
    qbuck = {}
    cap = 0
    act_all = 0.0
    for r in recs:
        acc = r["sides"][tag]["acc"]
        act_all += r["sides"][tag]["act_all" if conv == "PRIMARY" else "act_all_true"]
        for it in ITEMS:
            d = acc[it]
            per[it][0] += d["units"]
            per[it][1] += d["act"] if conv == "PRIMARY" else d["act_true"]
            per[it][2] += d["oracle"] if conv == "PRIMARY" else acc["_tru"][it]
        shifts.update(acc["_shift"] if conv == "PRIMARY" else acc["_tshift"])
        byidx.update(acc["_byidx"])
        for k2, v in acc["_tick"].items():
            t = ticks.setdefault(k2, [0.0, 0.0, 0.0])
            for i in range(3):
                t[i] += v[i]
        for k2, v in acc["_tape"].items():
            t = tape.setdefault(k2, [0.0, 0])
            t[0] += v[0]
            t[1] += v[1]
        for k2, v in acc["_qb"].items():
            t = qbuck.setdefault(k2, [0.0, 0.0, 0.0])
            for i in range(3):
                t[i] += v[i]
        cap += acc.get("_endcap" if conv == "PRIMARY" else "_tendcap", 0)
    total = [sum(per[it][i] for it in ITEMS) for i in range(3)]
    return per, total, shifts, cap, act_all, byidx, ticks, tape, qbuck


HDR = "     %-11s %10s %15s %15s %14s %8s"


def report(label, recs, pooled):
    lines = []
    n = len(recs)
    wins = sum(1 for r in recs if r["win"])
    margins = [r["margin"] for r in recs]
    lines.append("")
    lines.append("=" * 92)
    lines.append("%s   episodes %d   %dW-%dL   mean margin %s"
                 % (label, n, wins, n - wins, fmt_money(sum(margins) / n)))
    lines.append("=" * 92)
    pooled.extend(recs)

    for conv in ("PRIMARY", "TRUTH"):
        if conv == "PRIMARY":
            lines.append("")
            lines.append("-- PRIMARY (as specified): action recorded at index k priced at obs[k]; "
                         "shift to first k'>=k with k'%4==1")
        else:
            lines.append("")
            lines.append("-- ENGINE-TRUTH (matched basis: BOTH columns priced from obs[k-1]): "
                         "the price the sale actually got was obs[k-1], target = first j>=k-1 "
                         "with j%4==1")
        for tag in ("our", "opp"):
            lines.append("   %s side:" % tag.upper())
            lines.append(HDR % ("item", "units", "actual", "oracle", "gain", "gain%"))
            per, total, shifts, cap, act_all, byidx, ticks, tape, qbuck = side_totals(recs, tag, conv)
            for it in ITEMS:
                u, a, o = per[it]
                lines.append(HDR % (it, "%d" % u, fmt_money(a), fmt_money(o),
                                    fmt_money(o - a), "%.2f%%" % (100 * (o - a) / a if a else 0)))
            u, a, o = total
            lines.append(HDR % ("TOTAL 3", "%d" % u, fmt_money(a), fmt_money(o),
                                fmt_money(o - a), "%.2f%%" % (100 * (o - a) / a if a else 0)))
            lines.append("     all-item sell revenue proxy (all 9 products), same basis: %s"
                         % fmt_money(act_all))
            us = sum(shifts.values()) or 1
            lines.append("     units by steps moved:  "
                         + "   ".join("%d step%s: %d (%.1f%%)"
                                      % (s, "" if s == 1 else "s", shifts.get(s, 0),
                                         100 * shifts.get(s, 0) / us) for s in (0, 1, 2, 3))
                         + "    no room before step 720: %d units" % cap)
            lines.append("     units by action index k%4 (= execution tick k-1): "
                         + "  ".join("%d:%d (%.1f%%)" % (i, byidx.get(i, 0),
                                                         100 * byidx.get(i, 0) / us)
                                     for i in (0, 1, 2, 3)))
            if conv == "TRUTH" and tag == "our":
                lines.append("     WHY: units and $/unit by execution tick (b = k-1), "
                             "before vs after the shift to the next price index %4==1:")
                for it in ITEMS:
                    cells = []
                    for t in (0, 1, 2, 3):
                        v = ticks.get((it, t))
                        if not v or not v[0]:
                            continue
                        a, b2 = v[1] / v[0], v[2] / v[0]
                        cells.append("tick%d n=%-6d $%.1f -> $%.1f (%+.1f%%)"
                                     % (t, v[0], a, b2, 100 * (b2 / a - 1) if a else 0))
                    lines.append("       %-11s %s" % (it, "   ".join(cells)))
                cells = []
                for it in ITEMS:
                    cells.append("%s %s" % (it[:3], " ".join(
                        "t%d $%.1f" % (t, tape[(it, t)][0] / tape[(it, t)][1])
                        for t in (0, 1, 2, 3) if tape.get((it, t)) and tape[(it, t)][1])))
                lines.append("       tape mean price over the same games/steps: " + "   ".join(cells))
                cells = []
                for b2 in ("1", "2-4", "5+"):
                    row = []
                    for t in (0, 1, 2, 3):
                        v = qbuck.get((t, b2))
                        if v and v[0]:
                            row.append("t%d n=%-5d $%.1f->$%.1f (%+.1f%%)"
                                       % (t, v[0], v[1] / v[0], v[2] / v[0],
                                          100 * (v[2] / v[1] - 1) if v[1] else 0))
                    cells.append("     sale size %-3s %s" % (b2, "  ".join(row)))
                lines.append("       same, split by how many units the order carried"
                             " (small orders cannot move the tape):")
                lines.extend(cells)

        gaps = []
        for r in recs:
            acc = r["sides"]["our"]["acc"]
            sc = r["scale"] if conv == "PRIMARY" else r["scale_true"]
            a = sum((acc[it]["act"] if conv == "PRIMARY" else acc[it]["act_true"])
                    for it in ITEMS)
            o = sum(acc[it]["oracle"] if conv == "PRIMARY" else acc["_tru"][it] for it in ITEMS)
            gaps.append({"g": o - a, "gsc": (o - a) * sc, "scale": sc,
                         "win": r["win"], "eid": r["eid"]})
        g = [x["g"] for x in gaps]
        gs = [x["gsc"] for x in gaps]
        w = [x["g"] for x in gaps if x["win"]]
        l = [x["g"] for x in gaps if not x["win"]]
        mm = statistics.mean(margins)
        lines.append("   ORACLE - ACTUAL per game (our side): mean %s  median %s  min %s  max %s"
                     % (fmt_money(statistics.mean(g)), fmt_money(statistics.median(g)),
                        fmt_money(min(g)), fmt_money(max(g))))
        lines.append("     games with a positive gap: %d/%d   |   cash-scaled mean %s "
                     "(scale = replay gross sell receipts / all-item proxy = %.3f)"
                     % (sum(1 for x in g if x > 0), len(g), fmt_money(statistics.mean(gs)),
                        statistics.mean(x["scale"] for x in gaps)))
        lines.append("     our 3-item proxy revenue/game %s, mean margin %s  ->  gap = %.1f%% of |margin|"
                     % (fmt_money(sum(sum((r["sides"]["our"]["acc"][it]["act"] if conv == "PRIMARY"
                                           else r["sides"]["our"]["acc"][it]["act_true"])
                                          for it in ITEMS) for r in recs) / n), fmt_money(mm),
                        100 * statistics.mean(g) / abs(mm) if mm else 0))
        lines.append("     won  games (n=%-3d): mean %s     lost games (n=%-3d): mean %s"
                     % (len(w), fmt_money(statistics.mean(w)) if w else "-",
                        len(l), fmt_money(statistics.mean(l)) if l else "-"))
        top = sorted(gaps, key=lambda x: -x["g"])[:5]
        lines.append("     biggest gaps: " + " | ".join(
            "%s %s %s" % (x["eid"], fmt_money(x["g"]), "W" if x["win"] else "L") for x in top))

    cnt = sum(r["calib"][0] for r in recs if r["calib"])
    if cnt:
        ea = sum(r["calib"][1] for r in recs if r["calib"])
        sa = sum(r["calib"][2] for r in recs if r["calib"])
        eb = sum(r["calib"][3] for r in recs if r["calib"])
        sb = sum(r["calib"][4] for r in recs if r["calib"])
        zero = sum(r["calib"][5] for r in recs if r["calib"])
        lines.append("   CALIBRATION (our side, %d steps whose only orders are SELLs; %d of them "
                     "moved no cash at all):" % (cnt, zero))
        lines.append("     sum|predicted - replay cash delta| / sum|predicted|: "
                     "obs[k] (PRIMARY) %.2f%%   obs[k-1] (ENGINE-TRUTH) %.2f%%"
                     % (100 * ea / sa if sa else 0, 100 * eb / sb if sb else 0))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*", default=None)
    args = ap.parse_args()
    dirs = args.dirs or DEFAULT_DIRS
    print(__doc__.split("\n")[0])
    out = []
    pooled = []
    for d in dirs:
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        files = sorted(glob.glob(os.path.join(p, "episode-*-replay.json")))
        recs = []
        skipped = 0
        for f in files:
            try:
                raw = json.load(open(f, encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print("  skip %s (%s)" % (os.path.basename(f), e))
                continue
            r = None
            try:
                r = run_episode(raw)
            except Exception as e:  # noqa: BLE001
                print("  skip %s (%s)" % (os.path.basename(f), e))
                continue
            if r is None:
                skipped += 1
            else:
                recs.append(r)
            del raw
        label = "%s  (%d files, %d self-match/unusable excluded)" % (
            os.path.basename(p), len(files), skipped)
        out += report(label, recs, pooled)
    out += report("POOLED  (all four dirs)", pooled, [])
    print("\n".join(out))


if __name__ == "__main__":
    main()
