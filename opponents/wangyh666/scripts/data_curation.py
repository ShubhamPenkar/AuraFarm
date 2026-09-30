"""Build the sampling frame for training: which of our 993 ladder replays may be used,
and for what.

The user's point is that the data volume is not the problem -- selection is.  The night
shift showed why that matters here: pooling across opponents produced two t>2 results
that reversed sign under conditioning, and one opponent in `replays_v56539741` emits
million-unit orders that poison any opponent-side statistic.

Three uses, and they do NOT take the same data:

  U1 labels   "from this day-6 state, which tape wins" -- NOT obtainable from replays.
              We only ever ran one tape per game; the other 40 outcomes are
              counterfactual.  Labels must come from simulation.
  U2 sampling which worlds, which opponents, which day-6 states to generate
              -- this is what the replays ARE good for, and it is irreplaceable.
  U3 opponent models  who goes into the simulator -- needs real, diverse, *working*
              opponents, so broken bots must be identified and dropped.

So this script does not try to make training data out of replays.  It produces the
sampling frame that U2 needs, an exclusion list with a reason per episode, and a
curated index another script can consume.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/data_curation.py
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
DIRS = sorted(d for d in os.listdir(ROOT)
              if d.startswith("replays_v") and os.path.isdir(os.path.join(ROOT, d)))
KEY = "['BUY_PRODUCT', 'WHEAT', 5], ['BUY_SEED'"
# a broken bot: one whose orders are absurd relative to a 100-unit shed
ABSURD_UNITS = 100000


def classify(raw, ratings):
    """-> (verdict, reason, meta)"""
    names = raw["info"].get("TeamNames") or []
    ours = [i for i, n in enumerate(names) if n in L.OURS]
    if not ours:
        return "drop", "no team name matched ours", None
    if len(ours) > 1:
        return "drop", "self-match: both sides are ours, the replay does not say which is which", None
    me = ours[0]
    opp = 1 - me
    steps = raw["steps"]
    rec = {"me": me, "eid": raw["info"].get("EpisodeId"),
           "opp_name": names[opp] if opp < len(names) else "?",
           "opp_rating": ratings.get(names[opp]) if opp < len(names) else None,
           "margin": raw["rewards"][me] - raw["rewards"][opp],
           "statuses": list(raw["statuses"])}

    # broken bot: absurd order sizes, or our side not ACTIVE at the end
    worst = 0
    for k in range(0, len(steps), 7):
        for o in ((steps[k][opp].get("action") or {}).get("market") or []):
            if len(o) >= 3:
                try:
                    worst = max(worst, int(o[2]))
                except Exception:  # noqa: BLE001
                    pass
    if worst > ABSURD_UNITS:
        return "drop", "opponent emits absurd orders (max %d units) -- pollutes any opponent-side statistic" % worst, rec
    if any(s != "DONE" for s in raw["statuses"]):
        return "drop", "a player did not finish: %s" % (raw["statuses"],), rec

    # opening fingerprint of the opponent (code fingerprint, claims section 16)
    sig = []
    for k in range(0, 4):
        mk = (steps[k + 1][opp].get("action") or {}).get("market") or [] if k + 1 < len(steps) else []
        if mk:
            sig.append(json.dumps([[o[0], o[1], o[2]] for o in mk if len(o) >= 3]))
    # normalise the quoting: the fingerprint below is built with json.dumps (double
    # quotes) while the reference string uses single quotes.  Matching one against the
    # other silently classified every opponent as "other".
    sig_norm = [s.replace('"', "'") for s in sig]
    rec["sig"] = sig
    rec["family"] = "tetsutani" if (sig_norm and KEY in sig_norm[0]) else "other"
    # the exact feature `_V93_ROUTE_BY_RIVAL` keys on: the opponent's (cash, wheat
    # inventory) in the observation at step 2.  Our local runs show it is perfectly
    # separated per opponent code, and the shipped table holds a single point that
    # never fires (measured 0/120 over three opponents).
    try:
        o2 = steps[2][opp]["observation"]
        rec["opp_key"] = [round(float(o2["farms"][opp]["money"]), 3),
                          int(o2["market"]["inventory"]["WHEAT"])]
    except Exception:  # noqa: BLE001
        rec["opp_key"] = None
    # first two shops, i.e. exactly what `_router` reads at step 144
    try:
        rec["shops"] = list(steps[145][me]["observation"]["town"]["unlocked_shops"])[:2]
    except Exception:  # noqa: BLE001
        rec["shops"] = []
    # our day-6 state, the conditioning candidate for a richer router
    try:
        f = steps[144][me]["observation"]["farms"][me]
        shed = steps[144][me]["observation"]["private"]["shed"] or {}
        rec["d6_money"] = f["money"]
        rec["d6_shed"] = sum(v for v in shed.values() if isinstance(v, (int, float)))
        rec["d6_quadrants"] = len(f.get("unlocked_quadrants") or [])
    except Exception:  # noqa: BLE001
        pass
    if not rec["shops"]:
        return "drop", "no shop list readable at step 145", rec
    return "keep", "", rec


def main():
    ratings = L.board()
    keep, drops = [], collections.Counter()
    total = 0
    for d in DIRS:
        for f in sorted(glob.glob(os.path.join(ROOT, d, "episode-*-replay.json"))):
            total += 1
            try:
                raw = json.load(open(f, encoding="utf-8"))
            except Exception:  # noqa: BLE001
                drops["unreadable json"] += 1
                continue
            verdict, reason, rec = classify(raw, ratings)
            if verdict == "drop":
                drops[reason.split(":")[0].split("(")[0].strip()] += 1
                continue
            rec["dir"], rec["file"] = d, os.path.relpath(f, ROOT)
            keep.append(rec)

    print("scanned %d replay files across %d submission dirs" % (total, len(DIRS)))
    print("kept %d   dropped %d" % (len(keep), total - len(keep)))
    for r, n in drops.most_common():
        print("   drop %-70s %d" % (r, n))

    print("\n=== U2 sampling frame: what the replays are actually good for ===")
    print("--- first two shops (exactly what `_router` reads at step 144) ---")
    c = collections.Counter(tuple(r["shops"]) for r in keep)
    print("   %d distinct pairs over %d games; top 10:" % (len(c), len(keep)))
    for k, v in c.most_common(10):
        print("     %-34s %4d  (%.1f%%)" % (str(k), v, 100 * v / len(keep)))
    yarn = sum(1 for r in keep if "YARN_STORE" in r["shops"])
    print("   pairs containing YARN_STORE: %d/%d = %.0f%%  (the router's binary branch)"
          % (yarn, len(keep), 100 * yarn / len(keep)))

    print("\n--- our day-6 state (the richer conditioning candidates) ---")
    for k, lab in (("d6_money", "cash at step 144"), ("d6_shed", "shed units"),
                   ("d6_quadrants", "unlocked quadrants")):
        v = [r[k] for r in keep if k in r]
        if v:
            print("   %-22s mean %8.1f  median %8.1f  p10 %8.1f  p90 %8.1f  range %s..%s"
                  % (lab, statistics.mean(v), statistics.median(v),
                     sorted(v)[len(v) // 10], sorted(v)[9 * len(v) // 10], min(v), max(v)))

    print("\n--- opponent families, overall and by rating band ---")
    print("   %-14s %-24s %s" % ("band", "n", "tetsutani share"))
    for lo, hi in ((0, 1500), (1500, 2000), (2000, 2300), (2300, 2600), (2600, 9999)):
        g = [r for r in keep if r.get("opp_rating") and lo <= r["opp_rating"] < hi]
        if not g:
            continue
        t = sum(1 for r in g if r["family"] == "tetsutani")
        print("   %-14s %-24d %.0f%%" % ("%d-%d" % (lo, hi), len(g), 100 * t / len(g)))

    out = os.path.join(ROOT, "tmp_analysis", "curated_index.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"n_kept": len(keep), "n_scanned": total, "index": keep}, f)
    print("\nwrote %s  (the sampling frame; labels still have to come from simulation)"
          % os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
