"""Paired analysis of the v45 `_ADV_LOOK` localization (3 / 5 / 6 / 8, two blocks).

Why paired, and why it matters here.

Each arm is a separate tournament over the *same* seed list with both seats, so
arm A and arm B play literally the same 250 boards.  Treating the arms as
independent proportions throws that away: with n=500 per arm the standard error
of an unpaired difference between two ~60% win rates is ~3.1pp, so a 95% interval
is about +/-6pp -- i.e. 500 games per arm can only resolve differences of the
size of the effect v44 is built on.  Pairing by seed removes the board-to-board
variance and makes the test a McNemar one on the discordant pairs, which is far
sharper for the same compute.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/v45_analyse.py
"""
import glob
import json
import math
import os
import sys

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARMS = ["v45_adv3", "v45_adv5", "v45_adv6", "v45_adv8",
        "v45_adv10", "v45_adv12", "v45_adv16"]
BLOCKS = ["A", "B"]


def load():
    out = {}
    for arm in ARMS:
        for blk in BLOCKS:
            hits = sorted(glob.glob(os.path.join(
                ROOT, "tournament_results", "%s_blk%s-*.json" % (arm, blk))))
            if not hits:
                out[(arm, blk)] = None
                continue
            d = json.load(open(hits[-1], encoding="utf-8"))
            wins = {}          # seed -> wins out of 2 seats
            margins = {}
            for r in d["results"]:
                s = r["seed"]
                wins[s] = wins.get(s, 0) + (1 if r["margin"] > 0 else 0)
                margins.setdefault(s, []).append(r["margin"])
            out[(arm, blk)] = {"wins": wins, "margins": margins, "n": len(d["results"]),
                               "file": os.path.basename(hits[-1])}
    return out


def mcnemar(a, b, seeds):
    """Exact-ish paired test on seeds where the two arms differ."""
    a_only = b_only = 0
    for s in seeds:
        wa, wb = a["wins"].get(s), b["wins"].get(s)
        if wa is None or wb is None:
            continue
        if wa == wb:
            continue
        if wa > wb:
            a_only += 1
        else:
            b_only += 1
    n = a_only + b_only
    if n == 0:
        return a_only, b_only, 1.0
    # two-sided binomial with p=0.5
    k = min(a_only, b_only)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return a_only, b_only, min(1.0, p)


def main():
    data = load()
    missing = [k for k, v in data.items() if v is None]
    if missing:
        print("MISSING %s" % missing)
    print("=== raw win rates (each game = 1 seed x 1 seat) ===")
    print("%-10s %-6s %-8s %-10s %s" % ("arm", "block", "games", "win rate", "file"))
    for arm in ARMS:
        for blk in BLOCKS:
            d = data[(arm, blk)]
            if not d:
                continue
            w = sum(d["wins"].values())
            print("%-10s %-6s %-8d %-10s %s"
                  % (arm, blk, d["n"], "%.1f%%" % (100 * w / d["n"]), d["file"]))

    for blk in BLOCKS:
        print("\n=== block %s: paired-by-seed contrasts (2 seats/seed) ===" % blk)
        print("%-22s %-10s %-10s %-10s %s"
              % ("contrast", "A-only", "B-only", "diff(pp)", "p (two-sided binomial)"))
        for i, a in enumerate(ARMS):
            for b in ARMS[i + 1:]:
                da, db = data[(a, blk)], data[(b, blk)]
                if not da or not db:
                    continue
                seeds = sorted(set(da["wins"]) & set(db["wins"]))
                ao, bo, p = mcnemar(da, db, seeds)
                na = sum(da["wins"][s] for s in seeds)
                nb = sum(db["wins"][s] for s in seeds)
                diff = 100.0 * (nb - na) / (2 * len(seeds))
                print("%-22s %-10d %-10d %+10.2f %s"
                      % ("%s -> %s" % (a.replace("v45_", ""), b.replace("v45_", "")),
                         ao, bo, diff, "%.4f" % p if p >= 1e-4 else "<1e-4"))

    print("\n=== pooled across both blocks ===")
    print("%-10s %-8s %-10s" % ("arm", "games", "win rate"))
    for arm in ARMS:
        tot = win = 0
        for blk in BLOCKS:
            d = data[(arm, blk)]
            if d:
                tot += d["n"]
                win += sum(d["wins"].values())
        if tot:
            print("%-10s %-8d %-10s" % (arm, tot, "%.1f%%" % (100 * win / tot)))


if __name__ == "__main__":
    main()
