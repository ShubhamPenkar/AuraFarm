"""What does `_CXD`'s mirror assumption cost?

`_CXD` searches orderings of our SELL orders over the free market slots and keeps the
one that maximises our margin in the engine's exact per-slot lockstep.  The rival's
list enters that calculation through `_CXD_MODELS`, and:

    models = [m for m in _CXD_MODELS if m] or [orders]

`_CXD_MODELS` is declared as `[]` and never appended to anywhere in the stack, so the
model always falls back to `orders` -- **our own list**.  The search therefore picks
the ordering that is best against a rival who submits exactly our own orders.

Both `shiiin9`'s layer D and the V48 donor make the same assumption and say so
("Against a copy of V48 that assumption is exact"), which is fine for a mirror and
unjustified on a ladder where 49 of the 64 shop worlds meet a different tape.

This measures the size of the gap against the rival's ACTUAL list from each replay:

    value of a perfect rival model
        = margin_true(best ordering under the true list)
        - margin_true(ordering chosen under the mirror assumption)

both evaluated with `_v44y_factor_margin(their_actual_list, ...)`.  It is an UPPER
BOUND on what filling `_CXD_MODELS` could buy, since it grants us the rival's list
at decision time -- which we do not have, the moves being simultaneous.  Its purpose
is to decide whether looking for a predictor is worth any effort at all.

INDEXING: the action taken at observation step j is stored at `steps[j+1]`, and it
fills at the prices in `steps[j]`.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/cxd_model_value.py --games 40
"""
import argparse
import glob
import importlib.util
import itertools
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladder_dossier as L  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIRS = ["replays_v56566776", "replays_v56556192", "replays_v56552481", "replays_v56539741"]
BUDGET = 800


def load_host():
    path = os.path.join(ROOT, "experiments", "v45", "v45_adv12.py")
    spec = importlib.util.spec_from_file_location("cxdhost", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def candidates(orders, slots, sells, fixed):
    for positions in itertools.permutations(slots, len(sells)):
        out = list(orders)
        rest = [i for i in slots if i not in positions]
        for i, order in zip(positions, sells):
            out[i] = order
        for i, order in zip(rest, fixed):
            out[i] = order
        yield out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    args = ap.parse_args()
    m = load_host()
    print("host: %s   _CXD_MODELS=%r" % (os.path.relpath(m.__file__, ROOT), m._CXD_MODELS))

    files = []
    for d in DIRS:
        files += sorted(glob.glob(os.path.join(ROOT, d, "episode-*-replay.json")))
    files = files[: args.games]

    vals, n_steps, n_same, skipped = [], 0, 0, 0
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
            orders = [list(o) if isinstance(o, (list, tuple)) else o
                      for o in (act.get("market") or [])]
            if len(orders) < 2:
                continue
            theirs = [list(o) for o in ((steps[j + 1][opp].get("action") or {}).get("market") or [])]
            obs = steps[j][me]["observation"]
            try:
                stock = {k: max(0, int(v))
                         for k, v in m.projected_shed(act, m.FarmView(obs)).items()}
                params = m._v44y_params(obs)
                inv0 = {k: int(v) for k, v in obs["market"]["inventory"].items()}
                m_true = m._v44y_factor_margin(theirs, inv0, stock, params)
                m_mirror = m._v44y_factor_margin(orders, inv0, stock, params)
            except Exception:  # noqa: BLE001
                skipped += 1
                continue
            bought = {o[1] for o in orders if o and len(o) > 1 and o[0] == "BUY_PRODUCT"}
            slots, sells, fixed = [], [], []
            for i, o in enumerate(orders):
                if not o:
                    continue
                if o[0] in m._CXD_FIXED:
                    slots.append(i); fixed.append(o)
                elif o[0] == "SELL" and len(o) > 1 and o[1] not in bought:
                    slots.append(i); sells.append(o)
            if not sells or len(slots) < 2:
                continue
            base = m_true(orders)
            best_mirror, best_true, best_true_val = None, None, base
            mv = base
            ev = 0
            for cand in candidates(orders, slots, sells, fixed):
                ev += 1
                if ev > BUDGET:
                    break
                if cand == orders:
                    continue
                vt = m_true(cand)
                if vt > best_true_val:
                    best_true_val, best_true = vt, cand
                vm = m_mirror(cand)
                if vm > mv:
                    mv, best_mirror = vm, cand
            if best_mirror is None and best_true is None:
                continue
            n_steps += 1
            if best_true is None:
                continue
            chosen_mirror = best_mirror if best_mirror is not None else orders
            if chosen_mirror == best_true:
                n_same += 1
                continue
            try:
                vals.append(m_true(best_true) - m_true(chosen_mirror))
            except Exception:  # noqa: BLE001
                skipped += 1
    print("\nsteps evaluated: %d   ordering identical under both models: %d   errors: %d"
          % (n_steps, n_same, skipped))
    if vals:
        pos = sum(1 for v in vals if v > 0.5)
        print("margin lost to the mirror assumption (upper bound, rival list known):")
        print("  n=%d  mean $%+.1f  median $%+.1f  min $%+.1f  max $%+.1f"
              % (len(vals), statistics.mean(vals), statistics.median(vals),
                 min(vals), max(vals)))
        print("  strictly better on %d/%d = %.1f%% of the differing steps"
              % (pos, len(vals), 100 * pos / len(vals)))


if __name__ == "__main__":
    main()
