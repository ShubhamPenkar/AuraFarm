"""What does each agent emit in its market list over the first few observation steps?

Drives the real engine by hand (the only way to stop before step 720) and applies
the engine's own shared-state projection, because agents never see a raw
`state[i].observation`: `core.act_agent` hands them `__get_shared_state(i)`, which
overwrites the schema's *shared* sub-fields (including `step`) from state[0].

NOTE: `env.steps[k].action` is the action taken at observation step **k-1**, not k.
Reading it directly (the first version of this script did) makes every opening look
as though it happened one step later than it does.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/step1_opp_market.py \
        --seeds 1 --steps 4 --out tmp_analysis/open_tapes.json
"""
import argparse
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DEFAULT = ["tetsutani_cha22", "v52", "v53", "v55", "v56", "fieldcraft",
           "hybrid2965", "pipe16", "reyhan", "beatv48"]


def load_agent(path, name):
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    callables = [(k, v) for k, v in vars(mod).items() if callable(v) and not k.startswith("__")]
    return callables[-1][1] if callables else mod.agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="main.py")
    ap.add_argument("--opponents", default=",".join(DEFAULT))
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--out", default="tmp_analysis/open_tapes.json")
    args = ap.parse_args()

    seed = int(args.seeds.split(",")[0])
    base = load_agent(os.path.join(ROOT, args.agent), "cand")
    rec = {}

    for name in ["self"] + args.opponents.split(","):
        path = (os.path.join(ROOT, args.agent) if name == "self"
                else os.path.join(ROOT, "opponents", name, "main.py"))
        if not os.path.exists(path):
            print("MISSING %s" % name)
            continue
        opp = base if name == "self" else load_agent(path, "opp_%s" % name)
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        env.reset(2)
        shared = env._Environment__get_shared_state
        obs = [shared(p) for p in range(2)]
        steps_out = []
        for _ in range(args.steps):
            a1 = opp(obs[1]["observation"], env.configuration) if obs[1]["status"] == "ACTIVE" else None
            env.step([base(obs[0]["observation"], env.configuration), a1])
            steps_out.append((obs[0]["observation"]["step"], (a1 or {}).get("market") or []))
            obs = [shared(p) for p in range(2)]
        rec[name] = steps_out
        print("### %s" % name)
        for st, mk in steps_out:
            print("  obs step %d: %s" % (st, mk))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
