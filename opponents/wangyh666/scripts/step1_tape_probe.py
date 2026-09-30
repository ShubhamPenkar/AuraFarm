"""Dump the first few market lists our own agent emits, straight from the engine.

Purpose: the step-1 squeeze port (goodpjw2008, `SESSION_STATE.md` §四.2) ships a
hard-coded guard written against V45's tape.  Before rewriting it we need the
tape *our* agent actually emits, read from a real episode rather than from the
source (the route table is an embedded base85 blob and the router can pick any
of 41 tapes).

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/step1_tape_probe.py [--agent main.py] [--steps 4] [--seeds 1,2,3]
"""
import argparse
import importlib.util
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from kaggle_environments import make  # noqa: E402

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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
    ap.add_argument("--opponent", default="main.py")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seeds", default="1,2,3")
    args = ap.parse_args()

    cand = load_agent(os.path.join(ROOT, args.agent), "cand")
    opp = load_agent(os.path.join(ROOT, args.opponent), "opp")
    for seed in [int(s) for s in args.seeds.split(",")]:
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        env.run([cand, opp])
        print("=== seed %d  agent=%s ===" % (seed, args.agent))
        for k in range(args.steps):
            acts = []
            for pid in (0, 1):
                a = env.steps[k][pid].get("action") or {}
                acts.append(a.get("market") or [])
            print("  step %d  p0=%s" % (k, acts[0]))
            if args.opponent != args.agent:
                print("           p1=%s" % (acts[1],))
            if k == 0:
                print("           p0 shed=%s money=%s" % (
                    env.steps[0][0].observation.get("private", {}).get("shed"),
                    env.steps[0][0].observation["farms"][0]["money"]))


if __name__ == "__main__":
    main()
