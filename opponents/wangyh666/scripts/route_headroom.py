"""Does the tape choice matter?  Measure the headroom before training anything on it.

`main.py:972` picks one of 41 recorded tapes from the first two unlocked shops and
never looks again, though the town keeps opening shops until day 24.  The tractable
form of "be adaptive" is a better-conditioned choice among those 41 tapes -- so the
first question is not how to learn it but whether the choice moves the result at all.
Everything the night shift measured on other ideas died on this question; this asks it
for the router.

Design, for objectivity:

  * PAIRED.  Every arm plays the SAME seeds and the SAME opponent.  Comparing win
    rates across arms that saw different boards would fold the draw into the answer.
  * BOTH SEATS, so a seat effect cannot masquerade as a tape effect.
  * A CONTROL arm (the unmodified host, its own router) on the same seeds, so an arm's
    number is read as a difference, not a level.
  * OUT-OF-SAMPLE.  Forty-one arms give forty-one noisy win rates; the maximum of them
    is biased upward by construction.  So the headline number splits the seeds in half,
    picks the best arm on one half and reports what it does on the other.
  * The first two shops are recorded for every game, so we can tell how often a forced
    arm even differs from what the router would have chosen.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/route_headroom.py \
        --opponents tetsutani_cha22,v55 --seeds 1000-1049 --workers 12
"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONTROL = "experiments/v45/v45_adv12.py"
ROUTES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
          100, 101, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114,
          115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128]


def load_agent(path, name):
    """Same rule as the ladder: the LAST callable in the namespace, and the agent's
    own directory on sys.path (a public release can ship a sibling module)."""
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    callables = [(k, v) for k, v in vars(mod).items() if callable(v) and not k.startswith("__")]
    return callables[-1][1] if callables else mod.agent


def arm_path(arm):
    """`arm` is "ctl" or a route id.  Command-line arms arrive as strings, the default
    list as ints, and the generated filenames are the same either way."""
    if arm == "ctl":
        return os.path.join(ROOT, CONTROL)
    return os.path.join(ROOT, "experiments", "v47", "forced_r%d.py" % int(arm))


def run_one(task):
    arm, opp_name, seed, seat = task
    cand = load_agent(arm_path(arm), "c_%s_%s_%d_%d" % (arm, opp_name, seed, seat))
    opp = load_agent(os.path.join(ROOT, "opponents", opp_name, "main.py"),
                     "o_%s_%d_%d" % (opp_name, seed, seat))
    agents = [cand, opp] if seat == 0 else [opp, cand]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.run(agents)
    fin = env.steps[-1]
    our, theirs = fin[seat].reward, fin[1 - seat].reward
    shops = []
    try:
        shops = list(env.steps[145][seat].observation["town"]["unlocked_shops"])[:2]
    except Exception:  # noqa: BLE001
        pass
    return {"arm": arm, "opponent": opp_name, "seed": seed, "seat": seat,
            "our": our, "theirs": theirs, "margin": our - theirs,
            "win": our > theirs, "shops": shops, "status": fin[seat].status}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opponents", default="tetsutani_cha22")
    ap.add_argument("--seeds", default="1000-1049")
    ap.add_argument("--arms", default="")           # default: control + all routes
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="tmp_analysis/route_headroom.json")
    args = ap.parse_args()

    a, b = args.seeds.split("-")
    seeds = list(range(int(a), int(b) + 1))
    arms = ([a if a == "ctl" else int(a) for a in args.arms.split(",")]
            if args.arms else (["ctl"] + ROUTES))
    opps = args.opponents.split(",")
    tasks = [(arm, o, s, seat) for arm in arms for o in opps for s in seeds for seat in (0, 1)]
    print("%d arms x %d opponents x %d seeds x 2 seats = %d games, %d workers"
          % (len(arms), len(opps), len(seeds), len(tasks), args.workers), flush=True)
    t0 = time.time()
    recs = []
    with mp.Pool(args.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, tasks), 1):
            recs.append(r)
            if i % 200 == 0:
                print("    %d/%d  %.0fs" % (i, len(tasks), time.time() - t0), flush=True)
    print("ran %d games in %.0fs\n" % (len(recs), time.time() - t0))

    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(recs, f)
    print("wrote %s" % os.path.relpath(out, ROOT))

    # ---- router's own choice, recomputed exactly (yarn pairs -> r9, else the EXP240 map)
    import base64
    import re
    import zlib
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    blob = re.search(r"_R108_DATA\s*=\s*json\.loads\(zlib\.decompress\(base64\.b85decode\('([^']+)'\)\)\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(blob.group(1))))
    shop_map = {tuple(r["shops"]): r["route"] for r in data["shops"]}

    def chosen(shops):
        shops = tuple(shops)
        if not shops:
            return None
        return 9 if "YARN_STORE" in shops else shop_map.get(shops, 100)

    for opp in opps:
        g = [r for r in recs if r["opponent"] == opp]
        if not g:
            continue
        print("=== %s (%d games per arm) ===" % (opp, len(seeds) * 2))
        by_arm = {}
        for r in g:
            by_arm.setdefault(r["arm"], []).append(r)
        ctl = by_arm.get("ctl", [])
        ctl_w = {r["seed"]: r["win"] for r in ctl}
        ctl_rate = statistics.mean(r["win"] for r in ctl) if ctl else float("nan")
        print("  control (router as-is): %.1f%% win over %d games"
              % (100 * ctl_rate, len(ctl)))
        same = {}
        for r in ctl:
            same[r["seed"]] = chosen(r["shops"])
        rows = []
        for arm, rs in by_arm.items():
            if arm == "ctl":
                continue
            rate = statistics.mean(x["win"] for x in rs)
            # paired: seeds where this arm and the control disagree over the 2 seats
            a_only = b_only = 0
            for s in set(x["seed"] for x in rs) & set(ctl_w):
                wa = sum(1 for x in rs if x["seed"] == s and x["win"])
                wc = ctl_w[s]
                if wa > wc:
                    a_only += 1
                elif wa < wc:
                    b_only += 1
            agree = sum(1 for x in rs if same.get(x["seed"]) == arm)
            # margin is continuous where win/loss is binary and each cell holds only
            # two games, so it ranks arms with far less noise.  Win rate still decides
            # the ladder (L1), so both are reported and the disagreement is the point.
            mg = statistics.mean(x["margin"] for x in rs)
            rows.append((arm, rate, a_only, b_only, agree, len(rs), mg))
        rows.sort(key=lambda t: -t[1])
        print("  %-6s %8s %12s %8s %8s %10s %s" % ("route", "win%", "mean margin",
                                                    "beat ctl", "lost ctl", "was chosen", "n"))
        for arm, rate, a_only, b_only, agree, n, mg in rows:
            print("  r%-5d %7.1f%% %+12.0f %8d %8d %9d/%d" % (arm, 100 * rate, mg,
                                                               a_only, b_only, agree, n))
        top = [r for r in rows if r[2] + r[3] >= 8]
        if top:
            print("  best by paired evidence: %s" % ", ".join("r%d %+.0f" % (t[0], t[2] - t[3])
                                                             for t in sorted(top, key=lambda t: -(t[2] - t[3]))[:5]))
        if rows:
            win_sorted = sorted(rows, key=lambda t: -t[1])
            mg_sorted = sorted(rows, key=lambda t: -t[6])
            print("  spread across 41 arms: win rate %.1f%% .. %.1f%%   mean margin $%+.0f .. $%+.0f"
                  % (100 * win_sorted[-1][1], 100 * win_sorted[0][1],
                     mg_sorted[-1][6], mg_sorted[0][6]))
            print("  (the max of 41 noisy arms is biased upward; the held-out number below is the honest one)")

        # ---- out-of-sample: pick on half the seeds, score on the other half
        half = len(seeds) // 2
        A = set(seeds[:half])
        B = set(seeds[half:])
        if ctl and len(seeds) >= 20:
            def stat_on(arm, S, key="win"):
                rs = [x for x in by_arm.get(arm, []) if x["seed"] in S]
                return statistics.mean(x[key] for x in rs) if rs else None
            for key, label in (("win", "win rate"), ("margin", "mean margin")):
                candA = [(arm, stat_on(arm, A, key)) for arm in arms if arm != "ctl"]
                candA = [(a, v) for a, v in candA if v is not None]
                best = max(candA, key=lambda t: t[1])
                vb, cb = stat_on(best[0], B, key), stat_on("ctl", B, key)
                va, ca = stat_on(best[0], A, key), stat_on("ctl", A, key)
                if key == "win":
                    print("\n  OUT-OF-SAMPLE by %s: best arm on seeds %d-%d is r%s (%.1f%%)"
                          % (label, min(A), max(A), best[0], 100 * best[1]))
                    print("    held-out seeds %d-%d: r%s %.1f%% vs control %.1f%%  -> edge %+.1fpp"
                          % (min(B), max(B), best[0], 100 * vb, 100 * cb, 100 * (vb - cb)))
                    print("    its in-sample edge on the picking half: %+.1fpp" % (100 * (va - ca)))
                else:
                    print("  OUT-OF-SAMPLE by %s: best arm r%s on the picking half ($%+.0f vs ctl $%+.0f);"
                          % (label, best[0], va, ca))
                    print("    held-out: r%s $%+.0f vs control $%+.0f  -> edge $%+.0f"
                          % (best[0], vb, cb, vb - cb))
        print()


if __name__ == "__main__":
    main()
