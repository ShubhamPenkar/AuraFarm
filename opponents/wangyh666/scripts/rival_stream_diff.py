"""What do near-mirror opponents do differently -- and does it track the outcome?

The user's observation, checked against the data: `quwon_000` opens like a different
lineage, yet their market list is identical to ours on 117/719 and 104/719 steps in
the two games we have against them, and we lost one of those by $53.  An opponent
running 84% of our own stream is the sharpest possible comparison -- every differing
step is a place where someone chose differently *on the same board*, which is exactly
the signal a replay can give that a counterfactual cannot.

This generalises that: find every game whose opponent's market stream largely agrees
with ours, and aggregate the differing (order) pairs by outcome.  A difference that
appears mostly in the games we LOSE is a candidate; one that appears in both is noise.

Reading a replay correctly: the action taken at observation step j is stored at
`steps[j+1]`.  Getting this wrong has cost this project three separate analyses.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/rival_stream_diff.py \
        --min-agree 0.55 [--episode replays_v56556192/episode-113471438-replay.json]
"""
import argparse
import collections
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def stream(raw, p):
    """The player's market list at every observation step, as a canonical string."""
    out = []
    for j in range(len(raw["steps"]) - 1):
        mk = (raw["steps"][j + 1][p].get("action") or {}).get("market") or []
        out.append(json.dumps([[o[0], o[1], o[2]] for o in mk if len(o) >= 3], sort_keys=True))
    return out


def load_all():
    """Streams only -- NEVER keep `raw`.

    A replay carries both players' full state for 720 steps and runs to megabytes;
    holding ~1000 of them exhausted memory and silently truncated this scan to one
    directory (47 of 993 episodes).  Convert each file to its two action streams
    while it is loaded, then let it go.
    """
    ratings = L.board()
    recs = []
    seen = 0
    for d in sorted(x for x in os.listdir(ROOT) if x.startswith("replays_v")):
        for f in sorted(glob.glob(os.path.join(ROOT, d, "episode-*-replay.json"))):
            seen += 1
            try:
                raw = json.load(open(f, encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            rc = L.dossier(raw, ratings)
            if not rc or rc.get("self_match"):
                del raw
                continue
            names = raw["info"]["TeamNames"]
            me = next(i for i, n in enumerate(names) if n in L.OURS)
            rec = {"dir": d, "file": os.path.relpath(f, ROOT), "me": me,
                   "opp_name": names[1 - me],
                   "margin": raw["rewards"][me] - raw["rewards"][1 - me],
                   "win": raw["rewards"][me] > raw["rewards"][1 - me],
                   "a": stream(raw, me), "b": stream(raw, 1 - me)}
            del raw
            recs.append(rec)
    print("  (load_all: %d files seen, %d usable)" % (seen, len(recs)))
    return recs


def orders_of(step_str):
    return {tuple(o) for o in json.loads(step_str)} if step_str else set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-agree", type=float, default=0.55)
    ap.add_argument("--episode", default="")
    args = ap.parse_args()

    if args.episode:
        raw = json.load(open(os.path.join(ROOT, args.episode), encoding="utf-8"))
        names = raw["info"]["TeamNames"]
        me = next(i for i, n in enumerate(names) if n in L.OURS)
        a, b = stream(raw, me), stream(raw, 1 - me)
        diff = [j for j in range(len(a)) if a[j] != b[j]]
        print("\n=== %s ===\n  %s vs %s   rewards %s"
              % (os.path.basename(args.episode), names[me], names[1 - me], raw["rewards"]))
        print("  market lists differ on %d/%d steps (agreement %.1f%%)"
              % (len(diff), len(a), 100 * (1 - len(diff) / len(a))))
        pat = collections.Counter()
        for j in diff:
            oa, ob = orders_of(a[j]), orders_of(b[j])
            pat[(tuple(sorted(oa - ob)), tuple(sorted(ob - oa)))] += 1
        for (only_a, only_b), c in pat.most_common(6):
            print("   x%-4d only ours   %s" % (c, str(only_a)[:76]))
            print("         only theirs %s" % str(only_b)[:76])
        print("  differing steps by day: %s"
              % sorted(collections.Counter(j // 24 for j in diff).items())[:12])
        return

    recs = load_all()
    print("scanned %d scored episodes" % len(recs))
    near = []
    for r in recs:
        a, b = r["a"], r["b"]
        n = min(len(a), len(b))
        agree = sum(1 for j in range(n) if a[j] == b[j]) / n
        if agree >= args.min_agree:
            near.append((agree, r, a, b))
    print("near-mirror games (market-stream agreement >= %.2f): %d  (%dW-%dL)"
          % (args.min_agree, len(near), sum(1 for _, r, _, _ in near if r["win"]),
             sum(1 for _, r, _, _ in near if not r["win"])))
    print("  agreement: min %.2f  median %.2f  max %.2f"
          % (min(x[0] for x in near), statistics.median(x[0] for x in near),
             max(x[0] for x in near)))

    print("\n=== what the opponent has that we do not, per step, by outcome ===")
    print("   (only counted on near-mirror games; 'ours-only' would mean the reverse)")
    cnt = {"win": collections.Counter(), "loss": collections.Counter()}
    ours_only = {"win": collections.Counter(), "loss": collections.Counter()}
    for agree, r, a, b in near:
        key = "win" if r["win"] else "loss"
        n = min(len(a), len(b))
        for j in range(n):
            if a[j] == b[j]:
                continue
            oa, ob = orders_of(a[j]), orders_of(b[j])
            for o in ob - oa:
                cnt[key][o] += 1
            for o in oa - ob:
                ours_only[key][o] += 1
    n_w = sum(1 for _, r, _, _ in near if r["win"]) or 1
    n_l = sum(1 for _, r, _, _ in near if not r["win"]) or 1
    print("  cohorts: %d wins, %d losses -- counts below are PER GAME" % (n_w, n_l))
    print("  (a ratio >1 means the difference is more common in the games we LOSE)")

    def table(counter, title, top=12):
        keys = set(counter["win"]) | set(counter["loss"])
        print("\n  %s" % title)
        print("  %-34s %10s %10s %s" % ("order", "per win", "per loss", "ratio"))
        for o in sorted(keys, key=lambda x: -(counter["loss"][x] / n_l + counter["win"][x] / n_w))[:top]:
            w, l = counter["win"][o] / n_w, counter["loss"][o] / n_l
            print("  %-34s %10.2f %10.2f %s" % (str(o), w, l, "%.2f" % (l / w) if w else "inf"))

    table(cnt, "THEY have it, we do not")
    table(ours_only, "WE have it, they do not")


if __name__ == "__main__":
    main()
