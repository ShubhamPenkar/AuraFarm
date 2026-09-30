"""Apples-to-apples comparison of two submissions' ladder episodes.

The displayed score cannot be compared directly between two submissions: it is
the mean rating of the field each was drawn into plus ~300 (R1/R2), so a version
that wins more can score lower simply by being matched against weaker opponents.
The only fair comparison is **within opponent-rating bands**.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/ladder_compare.py \
        --dirs replays_v56552481,replays_v56539741 --labels v44,v41 --scores 2091,2457
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
BANDS = [(0, 1500), (1500, 2000), (2000, 2300), (2300, 2600), (2600, 9999)]


def collect(d):
    p = d if os.path.isabs(d) else os.path.join(ROOT, d)
    ratings = L.board()
    recs = []
    for f in sorted(glob.glob(os.path.join(p, "episode-*-replay.json"))):
        try:
            r = L.dossier(json.load(open(f, encoding="utf-8")), ratings)
        except Exception:  # noqa: BLE001
            continue
        if r:
            recs.append(r)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--scores", default="")
    args = ap.parse_args()
    dirs = args.dirs.split(",")
    labels = args.labels.split(",")
    scores = args.scores.split(",") if args.scores else [""] * len(dirs)

    sets = {}
    for d, lab in zip(dirs, labels):
        recs = collect(d)
        sets[lab] = recs
        rated = [x for x in recs if x["opp_rating"] is not None]
        w = sum(1 for x in recs if x["win"])
        print("%-6s n=%-4d %dW-%dL  %5.1f%%   score=%-8s  opp rating mean %-7.0f median %-7.0f"
              % (lab, len(recs), w, len(recs) - w, 100 * w / max(1, len(recs)),
                 scores[labels.index(lab)],
                 statistics.mean(x["opp_rating"] for x in rated) if rated else float("nan"),
                 statistics.median(x["opp_rating"] for x in rated) if rated else float("nan")))

    print("\n=== win rate inside opponent-rating bands (the only fair comparison) ===")
    hdr = "%-14s" % "band"
    for lab in labels:
        hdr += " %-22s" % lab
    print(hdr)
    for lo, hi in BANDS:
        row = "%-14s" % ("%d-%d" % (lo, hi) if hi < 9999 else "%d+" % lo)
        for lab in labels:
            grp = [x for x in sets[lab] if x["opp_rating"] is not None and lo <= x["opp_rating"] < hi]
            if not grp:
                row += " %-22s" % "-"
                continue
            w = sum(1 for x in grp if x["win"])
            row += " %-22s" % ("n=%-3d %5.1f%%  m$%+.0f"
                               % (len(grp), 100 * w / len(grp),
                                  sum(x["margin"] for x in grp) / len(grp)))
        print(row)

    print("\n=== loss margins: are they close games? ===")
    for lab in labels:
        losses = sorted((x["margin"] for x in sets[lab] if not x["win"]), reverse=True)
        if not losses:
            continue
        print("  %-6s n=%-3d  best %+.0f  median %+.0f  worst %+.0f   |m|<1000: %d/%d"
              % (lab, len(losses), losses[0], statistics.median(losses), losses[-1],
                 sum(1 for m in losses if abs(m) < 1000), len(losses)))


if __name__ == "__main__":
    main()
