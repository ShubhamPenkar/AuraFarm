"""Can we steer which shop unlocks next?  (claims F8, and 52% of our income rides on it)

`godsmode_stores` reports that a single `DIG` placed just before an unlock changes
the next shop in 98 of 128 paired interventions (76.6%).  The mechanism is
compatible with our own E1: the town's shop draw and the weeds share one RNG seeded
by (seed * 1_000_003) ^ day, and weeds only consume a draw on an EMPTY tile -- so
changing what is empty changes the sequence.

Why it matters more after today: measuring the income channels in
`scripts/shop_channel.py` showed **52% of our revenue arrives automatically from the
town centre and the unlocked shops** (`townShopSellInterval = 4`), not from our own
SELL orders.  If the shop draw is steerable, that half of the economy becomes a
control variable.  F8's author never measured the score effect, which is exactly why
it was parked; this probe answers the cheaper question first -- does it reproduce
here at all, on our agent, in our engine?

Design: paired by seed.  Control = our agent against itself, run to just past an
unlock.  Treatment = identical, except player 0 emits one extra `DIG` on a chosen
tile shortly before the unlock.  Compare the unlocked-shop lists.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/shop_draw_probe.py \
        --seeds 100-149 --dig-step 68
"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UNLOCK_STEPS = [72, 144, 216, 288, 360, 432, 504, 576]


def load_agent(path, name):
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    callables = [(k, v) for k, v in vars(mod).items() if callable(v) and not k.startswith("__")]
    return callables[-1][1] if callables else mod.agent


def unit_on_weed(obs, p):
    """Index of a unit (0 = farmer, 1.. = hands) standing on a weed, else None.

    `DIG` takes no coordinate: the engine resolves every unit action at the cell
    that unit is standing on (`fx, fy = _farmer_position(farm, idx)`), and digging
    an already-empty cell is an explicit no-op (`if tile is None: return`).  So the
    cheapest intervention is to override one unit's action on a turn where it is
    already standing on a weed -- no movement needed.
    """
    f = obs["farms"][p]
    units = [f.get("farmer")] + list(f.get("hands") or [])
    for i, pos in enumerate(units):
        if not pos or len(pos) < 2:
            continue
        fx, fy = pos[0], pos[1]
        try:
            cell = f["tiles"][fy][fx]
        except Exception:  # noqa: BLE001
            continue
        if isinstance(cell, dict) and cell.get("kind") == "WEED":
            return i
    return None


def run_one(task):
    seed, dig_step, upto = task
    base = load_agent(os.path.join(ROOT, "main.py"), "cand")
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.reset(2)
    shared = env._Environment__get_shared_state
    obs = [shared(p) for p in range(2)]
    fired = False
    while obs[0]["observation"]["step"] < upto:
        acts = []
        for p in range(2):
            a = base(obs[p]["observation"], env.configuration)
            if p == 0 and dig_step is not None and obs[p]["observation"]["step"] == dig_step:
                idx = unit_on_weed(obs[p]["observation"], p)
                if idx is not None:
                    if idx == 0:
                        a = dict(a, farmer=["DIG"])
                    else:
                        hands = [list(h) for h in (a.get("hands") or [])]
                        while len(hands) < idx:
                            hands.append(["PASS"])
                        hands[idx - 1] = ["DIG"]
                        a = dict(a, hands=hands)
                    fired = True
            acts.append(a)
        env.step(acts)
        obs = [shared(p) for p in range(2)]
    shops = list(obs[0]["observation"].get("town", {}).get("unlocked_shops") or [])
    return {"seed": seed, "dig_step": dig_step, "shops": shops, "fired": fired,
            "status": obs[0]["status"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="100-149")
    ap.add_argument("--dig-steps", default="60,64,66,68,70")
    ap.add_argument("--upto", type=int, default=80)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    a, b = args.seeds.split("-")
    seeds = list(range(int(a), int(b) + 1))
    digs = [int(x) for x in args.dig_steps.split(",")]

    tasks = [(s, None, args.upto) for s in seeds]
    for ds in digs:
        tasks += [(s, ds, args.upto) for s in seeds]
    print("%d runs (%d seeds x (control + %d dig steps)), upto step %d, %d workers"
          % (len(tasks), len(seeds), len(digs), args.upto, args.workers))
    with mp.Pool(args.workers) as pool:
        recs = list(pool.imap_unordered(run_one, tasks))

    ctl = {r["seed"]: tuple(r["shops"]) for r in recs if r["dig_step"] is None}
    print("\ncontrol shop lists at step %d: %d distinct over %d seeds"
          % (args.upto, len(set(ctl.values())), len(ctl)))
    print("\n%-10s %-10s %-12s %s" % ("dig step", "changed", "rate", "fired ok"))
    tot_ch = tot_n = 0
    for ds in digs:
        g = [r for r in recs if r["dig_step"] == ds]
        ch = sum(1 for r in g if tuple(r["shops"]) != ctl[r["seed"]])
        fired = sum(1 for r in g if r["fired"])
        tot_ch += ch
        tot_n += len(g)
        print("%-10d %-10d %-12s %d/%d" % (ds, ch, "%.1f%%" % (100 * ch / len(g)), fired, len(g)))
    if tot_n:
        print("\nOVERALL: the DIG changed the unlocked-shop list in %d/%d = %.1f%% of paired runs"
              % (tot_ch, tot_n, 100 * tot_ch / tot_n))

    out = os.path.join(ROOT, "tmp_analysis", "shop_draw_probe.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(recs, f, indent=1)
    print("wrote %s" % os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
