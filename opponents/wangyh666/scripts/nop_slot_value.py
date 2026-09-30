"""What are our dead SELL orders costing?  (14.2% of our sell-only steps bank nothing)

`scripts/tick_oracle.py` measured that of 40,095 steps whose only orders are SELLs,
5,698 (14.2%) moved no cash at all -- the shed was empty and the order could not fill.
A dead order is not free: it still occupies a market slot, and slot index decides how
our orders pair with the rival's in the engine's per-slot lockstep.

This asks the question with the engine's own margin function, evaluated against the
OPPONENT'S ACTUAL list from that game (not against a copy of ourselves, which is what
`_CXD` does, because `_CXD_MODELS` is declared and never populated):

    margin(our list as emitted)   vs   margin(our list with the dead SELLs removed)

both under `_v44y_factor_margin(their_actual_list, ...)`, which replays the engine's
lockstep exactly.

INDEXING: the action taken at observation step j is stored at `steps[j+1]`, and it
fills at the prices in `steps[j]`. Everything below uses that pairing.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/nop_slot_value.py --games 40
"""
import argparse
import glob
import importlib.util
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIRS = ["replays_v56566776", "replays_v56556192", "replays_v56552481", "replays_v56539741"]


def load_host():
    path = os.path.join(ROOT, "experiments", "v45", "v45_adv12.py")
    spec = importlib.util.spec_from_file_location("tickhost", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--min-sells", type=int, default=2)
    args = ap.parse_args()
    m = load_host()
    print("host loaded: %s" % os.path.relpath(m.__file__, ROOT))

    files = []
    for d in DIRS:
        files += sorted(glob.glob(os.path.join(ROOT, d, "episode-*-replay.json")))
    files = files[: args.games]
    print("scanning %d replays\n" % len(files))

    gains, dead_steps, used_steps = [], 0, 0
    skipped = 0
    for f in files:
        try:
            raw = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        rc = L.dossier(raw, L.board())
        if not rc or rc.get("self_match"):
            continue
        names = raw["info"]["TeamNames"]
        me = next(i for i, x in enumerate(names) if x in L.OURS)
        opp = 1 - me
        steps = raw["steps"]
        for j in range(144, len(steps) - 1):
            act = steps[j + 1][me].get("action") or {}
            ours = [list(o) for o in (act.get("market") or [])]
            if len(ours) < args.min_sells:
                continue
            if not any(o and o[0] == "SELL" for o in ours):
                continue
            theirs = [list(o) for o in ((steps[j + 1][opp].get("action") or {}).get("market") or [])]
            obs = steps[j][me]["observation"]
            try:
                stock = {k: max(0, int(v))
                         for k, v in m.projected_shed(act, m.FarmView(obs)).items()}
                params = m._v44y_params(obs)
                inv0 = {k: int(v) for k, v in obs["market"]["inventory"].items()}
                margin = m._v44y_factor_margin(theirs, inv0, stock, params)
                base = margin(ours)
            except Exception:  # noqa: BLE001
                skipped += 1
                continue
            # a SELL is dead when the shed has nothing left for it given the orders
            # ahead of it in the same list; the engine consumes per slot, per unit.
            left = dict(stock)
            pruned = []
            for o in ours:
                if o and o[0] == "SELL" and len(o) >= 3:
                    if left.get(o[1], 0) <= 0:
                        continue
                    left[o[1]] = left[o[1]] - int(o[2])
                pruned.append(o)
            if len(pruned) == len(ours):
                continue
            used_steps += 1
            dead_steps += len(ours) - len(pruned)
            try:
                gains.append(margin(pruned) - base)
            except Exception:  # noqa: BLE001
                skipped += 1
    print("steps with at least one dead SELL: %d   dead orders removed: %d   errors: %d"
          % (used_steps, dead_steps, skipped))
    if gains:
        pos = sum(1 for g in gains if g > 0.5)
        print("margin gained by removing dead SELLs (engine lockstep, vs the rival's ACTUAL list):")
        print("  n=%d  mean $%+.1f  median $%+.1f  min $%+.1f  max $%+.1f"
              % (len(gains), statistics.mean(gains), statistics.median(gains),
                 min(gains), max(gains)))
        print("  improved on %d/%d = %.1f%% of those steps"
              % (pos, len(gains), 100 * pos / len(gains)))
        print("  max loss in margin: $%.1f  (a tail any layer has to be safe against)"
              % min(gains))


if __name__ == "__main__":
    main()
