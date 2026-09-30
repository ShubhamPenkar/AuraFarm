"""What families make up each submission's ladder draw, and how do we do in each?

This is the input the `_ADV` question needs.  `_ADV` is a race layer: locally it
is worth +24pp against `tetsutani_cha22`, which carries its own `_ADV_LOOK = 3`,
and it is roughly neutral-to-negative against opponents that carry none
(`v52`, `herdsafe`, `v55`).  Whether that nets out positive on the ladder is a
question about the *mix*, not about any single opponent.

Buckets are by the opponent's opening market list, which `claims.md` section 16
established as a code fingerprint (the tape is fixed over its first steps, so the
opening orders identify the code).

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/ladder_mix.py
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (label, substring of the opening market list, carries an _ADV layer locally?)
RULES = [
    ("tetsutani_cha22  BUY 5+seed", "['BUY_PRODUCT', 'WHEAT', 5], ['BUY_SEED'", "RACE(adv3)"),
    ("v4x-family       BUY 20/15", "['BUY_PRODUCT', 'WHEAT', 20], ['SELL', 'WHEAT', 15]", "no-race"),
    ("herdsafe         BUY 8/3", "['BUY_PRODUCT', 'WHEAT', 8], ['SELL', 'WHEAT', 3]", "no-race"),
    ("v50-line         BUY 7/2", "['BUY_PRODUCT', 'WHEAT', 7], ['SELL', 'WHEAT', 2]", "RACE(adv3)"),
    ("ours             BUY 10/5", "['BUY_PRODUCT', 'WHEAT', 10], ['SELL', 'WHEAT', 5]", "RACE"),
    ("v52-line         BUY 7/2", "['BUY_PRODUCT', 'WHEAT', 7]", "RACE(adv3)"),
]

TARGETS = [("v45 adv8", "replays_v56556192"),
           ("v44 adv6", "replays_v56552481"),
           ("v41 adv4", "replays_v56539741")]


def main():
    ratings = L.board()
    print("%-46s %-11s %s" % ("family", "race?", "per submission: n / our win%"))
    totals = {}
    for lab, d in TARGETS:
        p = os.path.join(ROOT, d)
        cnt = collections.Counter()
        win = collections.Counter()
        for f in sorted(glob.glob(os.path.join(p, "episode-*-replay.json"))):
            try:
                r = L.dossier(json.load(open(f, encoding="utf-8")), ratings)
            except Exception:  # noqa: BLE001
                continue
            if not r:
                continue
            s = str(r["sig"][0]) if r["sig"] else ""
            hit = "other"
            for name, needle, _race in RULES:
                if needle in s:
                    hit = name
                    break
            cnt[hit] += 1
            win[hit] += 1 if r["win"] else 0
        totals[lab] = (cnt, win)
        n = sum(cnt.values())
        print("\n=== %s : %d games ===" % (lab, n))
        race_n = race_w = norace_n = race_w = 0
        race_n = race_w = norace_n = norace_w = 0
        for name, _needle, race in RULES:
            if not cnt[name]:
                continue
            print("   %-30s %-11s n=%-3d  %5.1f%%  our win %.0f%%"
                  % (name, race, cnt[name], 100 * cnt[name] / n, 100 * win[name] / cnt[name]))
            if race.startswith("RACE"):
                race_n += cnt[name]
                race_w += win[name]
            else:
                norace_n += cnt[name]
                norace_w += win[name]
        if cnt["other"]:
            print("   %-30s %-11s n=%-3d  %5.1f%%  our win %.0f%%"
                  % ("other", "?", cnt["other"], 100 * cnt["other"] / n,
                     100 * win["other"] / cnt["other"]))
        print("   --> RACE families %.0f%% of draw (our win %.0f%%)   no-race %.0f%% (our win %.0f%%)"
              % (100 * race_n / n, 100 * race_w / max(1, race_n),
                 100 * norace_n / n, 100 * norace_w / max(1, norace_n)))


if __name__ == "__main__":
    main()
