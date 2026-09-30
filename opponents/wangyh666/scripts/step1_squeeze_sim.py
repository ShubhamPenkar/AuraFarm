"""Does the step-1 squeeze (goodpjw2008) transfer to OUR tape?

The donor's guard is hard-coded to V45's tape
(`market[0]==['SELL','WHEAT',13] and market[1]==['BUY_PRODUCT','WHEAT',5]`) and the
donor's *rival model* is `slot0 = no-op, slot1 = BUY WHEAT 5`.  Neither holds for us:

  * our step-1 tape is `[BUY WHEAT 10, SELL WHEAT 5, BUY_SEED WHEAT 1]` (measured,
    `scripts/step1_tape_probe.py`) -- we are already the round-tripper;
  * the 71%-of-ladder family (`tetsutani_cha22`) buys WHEAT 5 in **slot 0**, not slot 1.

Slot 0 is processed for both players before slot 1, so the donor's "deplete the book
while the rival's buy is quoted" geometry does not obviously survive the move.

This script measures it on the real engine instead of arguing about it: three steps
are enough to read both players' cash immediately after the step-1 market resolves,
and step 0 has an empty market for every agent we have measured, so the step-1
observation -- and therefore the opponent's step-1 action -- is *identical* across
arms.  The difference at step 2 is a deterministic market effect, not draw noise.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/step1_squeeze_sim.py \
        --opponents tetsutani_cha22,v52,fieldcraft --seeds 1,2,3
"""
import argparse
import copy
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# The three market orders our agent emits at step **0** (measured on the real
# engine, `scripts/step1_tape_probe.py` -- an earlier probe read `env.steps[k].action`,
# which lags the observation step by one, so the opening looked like it was at step 1).
OUR_TAPE = [["BUY_PRODUCT", "WHEAT", 10], ["SELL", "WHEAT", 5], ["BUY_SEED", "WHEAT", 1]]
SEED_TAIL = ["BUY_SEED", "WHEAT", 1]


def mk(units_buy, units_sell):
    """Opening variant: our buy leg resized, sell leg optional, seed tail preserved."""
    out = [["BUY_PRODUCT", "WHEAT", units_buy]]
    if units_sell:
        out.append(["SELL", "WHEAT", units_sell])
    out.append(list(SEED_TAIL))
    return out


ARMS0 = {
    "ctl": OUR_TAPE,                                    # BUY 10 / SELL 5   net +5
    "nosell5": mk(5, 0),                                # BUY 5  / no sell  net +5
    "nosell10": mk(10, 0),                              # BUY 10 / no sell  net +10
    "v4x": mk(20, 15),                                  # the family standard
    "roundtrip5": mk(5, 5),                             # pure round trip, net 0
    "big": mk(90, 85),                                  # upsized, net +5
    "donor0": [["BUY_PRODUCT", "WHEAT", 90], ["SELL", "WHEAT", 90]] + OUR_TAPE,
}

# Step 1: our tape sends no market orders at all (HIRE x5, COW 2, SHEEP 2), so the
# donor's move is an *insertion* in front of the hire block, not a substitution.
ARMS1 = {
    "ctl": [],
    "sq30": [["BUY_PRODUCT", "WHEAT", 30], ["SELL", "WHEAT", 30]],
    "sq90": [["BUY_PRODUCT", "WHEAT", 90], ["SELL", "WHEAT", 90]],
    "sq150": [["BUY_PRODUCT", "WHEAT", 150], ["SELL", "WHEAT", 150]],
    "buyonly90": [["BUY_PRODUCT", "WHEAT", 90]],
    "donor_exact": [["BUY_PRODUCT", "WHEAT", 90], ["SELL", "WHEAT", 90],
                    ["BUY_PRODUCT", "WHEAT", 5]],
}
ARMS = ARMS0


def load_agent(path, name):
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    callables = [(k, v) for k, v in vars(mod).items() if callable(v) and not k.startswith("__")]
    return callables[-1][1] if callables else mod.agent


def play(base, opp, seed, arm, steps, our_seat=0, at_step=0):
    """Drive the real engine by hand for `steps` steps and return the ledger.

    led[k] is the state *after* the action taken at observation step k, so
    led[0] is the cash right after the opening market resolves.
    """

    def cand(obs, config=None):
        a = base(obs, config)
        if arm != "ctl" and int(obs.get("step", -1)) == at_step and isinstance(a, dict):
            cur = [list(o) for o in (a.get("market") or [])]
            # step 0: substitute the opening round trip.  step 1: our tape sends no
            # market orders at all (HIRE x5, COW 2, SHEEP 2), so the donation's move
            # is an insertion in front of the hire block.
            if at_step == 0:
                if cur[:2] == OUR_TAPE[:2]:
                    a = dict(a, market=copy.deepcopy(ARMS0[arm]) + cur[2:])
            elif cur[:1] == [["HIRE"]]:
                a = dict(a, market=copy.deepcopy(ARMS1[arm]) + cur)
        return a

    agents = [cand, opp] if our_seat == 0 else [opp, cand]
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.reset(2)
    led = []
    # Agents never see a raw state[i].observation: the engine merges the *shared*
    # sub-fields from state[0] before handing it over (core.act_agent ->
    # __get_shared_state).  `step` is one of those, so driving the loop by hand
    # with the raw observation would KeyError inside every agent.
    shared = env._Environment__get_shared_state
    obs = [shared(p) for p in range(2)]
    for _ in range(steps):
        actions = [agents[p](obs[p]["observation"], env.configuration)
                   if obs[p]["status"] == "ACTIVE" else None for p in range(2)]
        env.step(actions)
        obs = [shared(p) for p in range(2)]
        led.append({"money": [obs[p]["observation"]["farms"][p]["money"] for p in (0, 1)],
                    "shed": [obs[p]["observation"]["private"]["shed"] for p in (0, 1)]})
    return ledger_view(led, our_seat)


def ledger_view(led, our_seat):
    """Reorder so index 0 = us, 1 = them, regardless of seat."""
    flip = our_seat == 1

    def rev(pair):
        return [pair[1], pair[0]] if flip else pair

    return [{"money": rev(s["money"]), "shed": rev(s["shed"])} for s in led]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--opponents", default="tetsutani_cha22,v52,v53,fieldcraft,hybrid2965,v55,v56,reyhan")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--arms", default="")
    ap.add_argument("--steps", type=int, default=1)
    ap.add_argument("--at-step", type=int, default=0)
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--out", default="tmp_analysis/step1_squeeze_sim.json")
    args = ap.parse_args()

    base = load_agent(os.path.join(ROOT, args.agent), "cand")
    arm_table = ARMS1 if args.at_step == 1 else ARMS0
    arms = (args.arms or ",".join(arm_table)).split(",")
    seeds = [int(s) for s in args.seeds.split(",")]
    out = {}

    for name in args.opponents.split(","):
        path = os.path.join(ROOT, "opponents", name, "main.py")
        if not os.path.exists(path):
            print("MISSING %s" % name)
            continue
        opp = load_agent(path, "opp_%s" % name)
        rec = {}
        print("\n### %s   (override at obs step %d, read after obs step %d)"
              % (name, args.at_step, args.steps - 1))
        print("| arm | our $ | their $ | our-them $ | after-open our/their | d(our) | d(their) | d(gap) |")
        print("|---|---|---|---|---|---|---|---|")
        for seed in seeds:
            row = {}
            for arm in arms:
                r = play(base, opp, seed, arm, args.steps, args.seat, args.at_step)
                s = r[-1]
                row[arm] = {"our": s["money"][0], "their": s["money"][1],
                            "our_after_open": r[0]["money"][0],
                            "their_after_open": r[0]["money"][1],
                            "their_shed": s["shed"][1]}
            c = row["ctl"]
            rec[seed] = row
            for arm in arms:
                d_o = row[arm]["our"] - c["our"]
                d_t = row[arm]["their"] - c["their"]
                print("| s%d %s | %s | %s | %s | %s/%s | %+d | %+d | %+d |" % (
                    seed, arm, fmt(row[arm]["our"]), fmt(row[arm]["their"]),
                    fmt(row[arm]["our"] - row[arm]["their"]),
                    fmt(row[arm]["our_after_open"]), fmt(row[arm]["their_after_open"]),
                    d_o, d_t, d_o - d_t))
        out[name] = rec

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("\nwrote %s" % args.out)


def fmt(v):
    return "$%.0f" % v


if __name__ == "__main__":
    main()
