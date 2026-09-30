"""How much does `_ADV_LOOK` actually pull forward, and against whom?

The localization says larger `_ADV_LOOK` is much better against `tetsutani_cha22`
(+24pp for 6->8, +7pp for 8->12, two blocks each).  On the live ladder the two
versions at 6 and 8 sit ~200 points BELOW the two versions at 4, and the
ordering is monotone in the constant.

The `_ADV` layer is a *race* layer: it moves planned sales of cash products into
the current turn because a rival running the same tape would otherwise sell the
same goods first and take the better price.  `tetsutani_cha22` carries its own
`_ADV_LOOK = 3`, so the local A/B is a genuine contest.  The ladder is not one
opponent: our own family (`v55`/`v56`/`pipe16`/`hybrid2965`) has no `_ADV` at
all and was 34% of v44's ladder draw.

If the rival is not racing, pulling sales forward can only hurt: the same units
are sold earlier, into a book nobody else is depressing, and prices in this game
rise through the season rather than fall.

This script measures the layer's own telemetry (`adv_turns`, `adv_units`,
`front_turns`) per game alongside the result, against racing and non-racing
opponents, so the "how much did it move" number is on the table next to the
"what happened" number.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/adv_telemetry.py
"""
import argparse
import importlib.util
import multiprocessing as mp
import os
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (label, path, does it carry an _ADV layer of its own?)
OPPONENTS = [
    ("tetsutani_cha22", "opponents/tetsutani_cha22/main.py", True),
    ("v52", "opponents/v52/main.py", True),
    ("herdsafe", "opponents/herdsafe/main.py", False),
    ("v55", "opponents/v55/main.py", False),
]
ARMS = ["v45_adv4", "v45_adv8"]


def load_agent(path, name):
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    callables = [(k, v) for k, v in vars(mod).items() if callable(v) and not k.startswith("__")]
    return callables[-1][1] if callables else mod.agent


def one(task):
    arm, opp_name, opp_path, seed, our_seat = task
    cand = load_agent(os.path.join(ROOT, "experiments", "v45", arm + ".py"), "c")
    opp = load_agent(os.path.join(ROOT, opp_path), "o")
    agents = [cand, opp] if our_seat == 0 else [opp, cand]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.run(agents)
    fin = env.steps[-1]
    rep = dict(getattr(cand, "telemetry", {}) or {})
    return {"arm": arm, "opponent": opp_name, "seed": seed, "seat": our_seat,
            "margin": fin[our_seat].reward - fin[1 - our_seat].reward,
            "adv_turns": rep.get("adv_turns"), "adv_units": rep.get("adv_units"),
            "front_turns": rep.get("front_turns"), "errors": rep.get("adv_errors")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1000-1007")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    a, b = args.seeds.split("-")
    seeds = list(range(int(a), int(b) + 1))

    tasks = [(arm, name, p, s, seat) for arm in ARMS for name, p, _ in OPPONENTS
             for s in seeds for seat in (0, 1)]
    print("%d games (%d arms x %d opponents x %d seeds x 2 seats), %d workers"
          % (len(tasks), len(ARMS), len(OPPONENTS), len(seeds), args.workers))
    with mp.Pool(args.workers) as pool:
        recs = list(pool.imap_unordered(one, tasks))

    print("\n%-12s %-16s %-5s %-6s %-9s %-11s %-11s %s"
          % ("arm", "opponent", "n", "win%", "mean marg", "adv_turns", "adv_units", "front_turns"))
    for arm in ARMS:
        for name, _, _ in OPPONENTS:
            rs = [r for r in recs if r["arm"] == arm and r["opponent"] == name]
            if not rs:
                continue
            w = sum(1 for r in rs if r["margin"] > 0)
            au = [r["adv_units"] or 0 for r in rs]
            at = [r["adv_turns"] or 0 for r in rs]
            ft = [r["front_turns"] or 0 for r in rs]
            print("%-12s %-16s %-5d %-6.1f %+9.0f %-11.1f %-11.1f %.1f"
                  % (arm.replace("v45_", ""), name, len(rs), 100 * w / len(rs),
                     statistics.mean(r["margin"] for r in rs),
                     statistics.mean(at), statistics.mean(au), statistics.mean(ft)))
    err = sum((r["errors"] or 0) for r in recs)
    if err:
        print("\n!! adv_errors total = %d" % err)


if __name__ == "__main__":
    main()
