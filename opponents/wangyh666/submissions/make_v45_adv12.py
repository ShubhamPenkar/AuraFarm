"""Build the `_ADV_LOOK` localization arms (3 / 5 / 8) on the v41 host.

Why this axis, and why it is not settled by v44.

v44 (`_ADV_LOOK` 4 -> 6, ref 56552481) is live. Its justification is a conflict of
evidence, not a consensus:

  * for longer: alperen5252525 moved 3 -> 8 (756 games, worst margin -1,196 ->
    -171) and ghazarosghazaros reports his account's best live score at 6;
  * for shorter: `_ADV_LOOK`'s own original author (Gluzdov E184, via
    `master-engine-v4` section 1) recommends **2-3** -- see claims H3;
  * ghazaros also reports that **9 and 10 reverse live**, so the axis is not
    monotone and 6 is only a local guess between two published turning points.

Our own A/B settled 4 vs 6 (two seed blocks, +6pp each, 400 games, vs
`tetsutani_cha22` -- the family that fingerprinting puts at 71% of the ladder).
It says nothing about where the peak is. 3/5/6/8 bracket it.

First reading (block A = seeds 1000-1249, both seats, 500 games per arm, all
against `tetsutani_cha22`): **39.0% / 52.6% / 62.0% / 86.0%** -- monotonically
rising, and 8 is 24pp above 6, so 6 is nowhere near the peak and ghazaros'
"9/10 reverse" does not reproduce locally on this stack.  `worst margin` also
improves, $-7,211 -> $-4,440.  10/12/16 were added to find the turning point
rather than assume the axis is unbounded.

Usage:
  .venv/Scripts/python experiments/v45/make_v45.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOST = os.path.join(ROOT, "experiments", "v41", "cxd.py")
OUTDIR = os.path.join(ROOT, "experiments", "v45")
OLD = "_ADV_LOOK=4"
ARMS = {4: "v45_adv4", 3: "v45_adv3", 5: "v45_adv5", 6: "v45_adv6", 8: "v45_adv8",
        10: "v45_adv10", 12: "v45_adv12", 16: "v45_adv16"}


def build(value, name):
    src = open(HOST, encoding="utf-8").read()
    if OLD not in src:
        sys.exit(f"{OLD!r} not found in the host -- constant renamed?")
    new = "_ADV_LOOK=%d   # v45 localization arm" % value
    body = src.replace(OLD, new, 1)
    out = os.path.join(OUTDIR, name + ".py")
    open(out, "w", encoding="utf-8").write(body)
    env = {}
    exec(compile(body, out, "exec"), env)  # noqa: S102 - our own generated file
    entry = [v for v in env.values() if callable(v)][-1]
    ok = entry is env["agent"]
    assert ok and env.get("_ADV_LOOK") == value, (name, ok, env.get("_ADV_LOOK"))
    print("  %-10s _ADV_LOOK=%-3d entry=%-6s last-callable-is-agent=%s  %d B"
          % (name, value, entry.__name__, ok, len(body)))
    return out


if __name__ == "__main__":
    print("host : %s" % os.path.relpath(HOST, ROOT))
    for v, n in sorted(ARMS.items()):
        build(v, n)
    print("wrote %d arms to %s" % (len(ARMS), os.path.relpath(OUTDIR, ROOT)))
