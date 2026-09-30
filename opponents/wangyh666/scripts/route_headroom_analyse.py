"""Read `route_headroom.py`'s output and ask the question that has power.

The runner forces each of the 41 tapes over ALL seeds, while the control switches
between ~20 tapes according to the first two shops.  So the control is a mixture, and
"no single fixed tape beats it" is expected and says nothing.  The informative
comparisons are inside a shop class:

    for the seeds where the router chose route R, does forcing R beat the control?
    and is any OTHER route better than R on exactly those seeds?

The second is the headroom of the router within a class; the first checks that the
router's own pick is not simply wrong.

Power is reported with every number, because these cells are small: the runner spends
its seeds across 64 shop pairs, so a class holding a third of the seeds still holds
only ~1/3 of the games.  A difference that the cell cannot resolve is not evidence of
absence, and this script says so rather than printing a bare ranking.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/route_headroom_analyse.py \
        --in tmp_analysis/route_headroom_full.json
"""
import argparse
import base64
import collections
import json
import os
import re
import statistics
import sys
import zlib

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def router_choice_map():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    blob = re.search(r"_R108_DATA\s*=\s*json\.loads\(zlib\.decompress\(base64\.b85decode\('([^']+)'\)\)\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(blob.group(1))))
    shop_map = {tuple(r["shops"]): r["route"] for r in data["shops"]}
    return lambda shops: (9 if "YARN_STORE" in shops else shop_map.get(tuple(shops), 100)) if shops else None


def mde(n, base=0.9):
    """Rough 95% resolution of a paired win-rate difference on n games per arm."""
    return 1.96 * (2 * base * (1 - base) / max(1, n // 2)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="tmp_analysis/route_headroom_full.json")
    args = ap.parse_args()
    recs = json.load(open(os.path.join(ROOT, args.inp), encoding="utf-8"))
    chosen_of = router_choice_map()
    for r in recs:
        r["chosen"] = chosen_of(r["shops"])

    opps = sorted({r["opponent"] for r in recs})
    for opp in opps:
        g = [r for r in recs if r["opponent"] == opp]
        by_arm = collections.defaultdict(list)
        for r in g:
            by_arm[r["arm"]].append(r)
        ctl = by_arm["ctl"]
        ctl_of = {r["seed"]: r for r in ctl}
        print("=" * 100)
        print("OPPONENT %s   %d games per arm (%d seeds x 2 seats)"
              % (opp, len(ctl), len(set(r["seed"] for r in ctl))))
        print("  control: %.1f%% win, mean margin $%+.0f"
              % (100 * statistics.mean(r["win"] for r in ctl),
                 statistics.mean(r["margin"] for r in ctl)))

        # ---- A. overall: best fixed tape vs the switching control -----------------
        rows = []
        for arm, rs in by_arm.items():
            if arm == "ctl":
                continue
            a_only = b_only = 0
            for s in set(x["seed"] for x in rs) & set(ctl_of):
                wa = sum(1 for x in rs if x["seed"] == s and x["win"])
                wc = 1 if ctl_of[s]["win"] else 0
                if wa > wc:
                    a_only += 1
                elif wa < wc:
                    b_only += 1
            rows.append((arm, statistics.mean(x["win"] for x in rs), a_only, b_only,
                         statistics.mean(x["margin"] for x in rs)))
        rows.sort(key=lambda t: -t[1])
        print("\n  A. every tape forced everywhere (control switches, so this mostly")
        print("     measures 'wrong tape for most seeds' -- shown only for reference)")
        print("     best three by win rate: %s"
              % ", ".join("r%s %.1f%% (%+d seeds)" % (t[0], 100 * t[1], t[2] - t[3]) for t in rows[:3]))

        # ---- B. inside each shop class -------------------------------------------
        classes = collections.Counter(r["chosen"] for r in ctl)
        print("\n  B. INSIDE A SHOP CLASS -- the comparison that has power")
        for cls, cnt in classes.most_common(4):
            seeds = {s for s, r in ctl_of.items() if r["chosen"] == cls}
            if len(seeds) < 6:
                continue
            n_games = 2 * len(seeds)
            print("\n   class r%s: %d seeds, %d games per arm, resolution ~%.1fpp"
                  % (cls, len(seeds), n_games, 100 * mde(n_games)))
            sub = []
            for arm, rs in by_arm.items():
                rr = [x for x in rs if x["seed"] in seeds]
                if not rr:
                    continue
                sub.append((arm, statistics.mean(x["win"] for x in rr),
                            statistics.mean(x["margin"] for x in rr), rr))
            sub.sort(key=lambda t: -t[1])
            csub = next((t for t in sub if t[0] == "ctl"), None)
            for arm, rate, mg, rr in sub:
                mark = ""
                if arm == cls:
                    # paired against the control on these very seeds
                    a_only = b_only = 0
                    for s in seeds:
                        wa = sum(1 for x in rr if x["seed"] == s and x["win"])
                        wc = 1 if ctl_of[s]["win"] else 0
                        if wa > wc:
                            a_only += 1
                        elif wa < wc:
                            b_only += 1
                    mark = "   <- router's own pick, paired vs ctl: +%d/-%d seeds" % (a_only, b_only)
                if arm == "ctl" or arm == cls or rate >= (sub[0][1] - 0.02):
                    print("     r%-6s %6.1f%%  $%+8.0f%s"
                          % (arm, 100 * rate, mg, mark))
            if csub:
                best = sub[0]
                print("     => best in class is r%s at %.1f%%, control %.1f%% (gap %+.1fpp)"
                      % (best[0], 100 * best[1], 100 * csub[1], 100 * (best[1] - csub[1])))

            # out-of-sample inside the class, by margin (continuous, less noisy)
            ss = sorted(seeds)
            A, B = set(ss[: len(ss) // 2]), set(ss[len(ss) // 2:])
            cand = []
            for arm, rs in by_arm.items():
                if arm == "ctl":
                    continue
                ra = [x["margin"] for x in rs if x["seed"] in A]
                if ra:
                    cand.append((arm, statistics.mean(ra)))
            if cand:
                best = max(cand, key=lambda t: t[1])
                rb = [x["margin"] for x in by_arm[best[0]] if x["seed"] in B]
                cb = [x["margin"] for x in ctl if x["seed"] in B]
                if rb and cb:
                    print("     OOS by margin: picked r%s on %d seeds, held out on %d -> "
                          "$%+.0f vs control $%+.0f (edge $%+.0f)"
                          % (best[0], len(A), len(B), statistics.mean(rb),
                             statistics.mean(cb), statistics.mean(rb) - statistics.mean(cb)))
        print()


if __name__ == "__main__":
    main()
