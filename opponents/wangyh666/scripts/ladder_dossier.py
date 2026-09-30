"""Game-by-game dossier of one submission's ladder episodes.

Answers "did this version actually get better" from the episodes themselves rather
than from the displayed score: the score is the mean rating of the field we were
drawn into plus ~300 (R1/R2, `results/score_is_opponent_draw.md`), so two versions
with the same score can have very different records, and a version can be better
and score lower.

For each episode: opponent team, their leaderboard rating, our/theirs reward,
margin, and the opponent's opening signature (step 0-2 market lists), which is the
code fingerprint from `claims.md` section 16.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python -u scripts/ladder_dossier.py \
        replays_v56552481 replays_v56539741 --label v44,v41
"""
import argparse
import glob
import json
import os
import statistics
import sys

sys.stdout.reconfigure(errors="replace")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OURS = ["ReD_MooN_rise", "redmooonrise", "ReD_MooN_riSe"]


def board():
    p = os.path.join(ROOT, "replays_ladder", "leaderboard.json")
    if not os.path.exists(p):
        return {}
    return {r["teamName"]: r["score"] for r in json.load(open(p, encoding="utf-8"))}


def opening_sig(steps, who):
    """First non-empty market lists over the first few steps = code fingerprint."""
    out = []
    for k in range(0, 4):
        try:
            act = steps[k][who].get("action") or {}
        except Exception:
            break
        mk = act.get("market") or []
        if mk:
            out.append("%s" % ([[o[0], o[1], o[2]] for o in mk if len(o) >= 3],))
    return out


def dossier(d, ratings):
    steps = d["steps"]
    names = d["info"].get("TeamNames") or []
    ours = [i for i, n in enumerate(names) if n in OURS]
    if not ours:
        return None
    # A submission can be matched against ANOTHER submission of ours: both team
    # names are then "ReD_MooN_rise" and the replay does not say which index is
    # which version.  Picking index 0 silently attributes an arbitrary side to
    # "us" and an arbitrary margin sign, so mark it instead of guessing.
    self_match = len(ours) > 1
    me = ours[0]
    opp = 1 - me
    r = d["rewards"]
    margin = r[me] - r[opp]
    # our cash at the day-0/1 boundary (the M1 early-death window) and at the end
    cash = {}
    for k in (24, 48, 719):
        try:
            cash[k] = steps[k][me]["observation"]["farms"][me]["money"]
        except Exception:
            cash[k] = None
    return {
        "self_match": self_match,
        "eid": d["info"].get("EpisodeId"),
        "opp": names[opp] if opp < len(names) else "?",
        "opp_rating": ratings.get(names[opp], None),
        "our": r[me], "theirs": r[opp], "margin": margin,
        "win": margin > 0,
        "seed": d["info"].get("seed"),
        "sig": opening_sig(steps, opp),
        "cash24": cash[24], "cash48": cash[48], "cash_end": cash[719],
        "status": d["statuses"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    labels = (args.label.split(",") + [""] * len(args.dirs))[:len(args.dirs)]
    ratings = board()
    print("leaderboard entries: %d" % len(ratings))

    summary = []
    for d, lab in zip(args.dirs, labels):
        p = d if os.path.isabs(d) else os.path.join(ROOT, d)
        recs = []
        for f in sorted(glob.glob(os.path.join(p, "episode-*-replay.json"))):
            try:
                rec = dossier(json.load(open(f, encoding="utf-8")), ratings)
            except Exception as e:  # noqa: BLE001
                print("  skip %s (%s)" % (os.path.basename(f), e))
                continue
            if rec:
                recs.append(rec)
        if not recs:
            print("%s: no episodes" % p)
            continue
        sm = [x for x in recs if x.get("self_match")]
        recs = [x for x in recs if not x.get("self_match")]
        if sm:
            print("\n(%s: %d self-match episodes excluded -- both sides are ours, "
                  "the replay does not say which index is which version)"
                  % (lab or d, len(sm)))
        if not recs:
            print("%s: no scored episodes" % (lab or d))
            continue
        w = sum(1 for x in recs if x["win"])
        m = [x["margin"] for x in recs]
        rated = [x for x in recs if x["opp_rating"]]
        print("\n=== %s (%s) ===" % (lab or d, os.path.basename(p)))
        print("episodes %d   %dW-%dL  %.1f%%   mean margin $%+.0f   worst $%+.0f"
              % (len(recs), w, len(recs) - w, 100 * w / len(recs),
                 sum(m) / len(m), min(m)))
        if rated:
            print("opponent rating: mean %.0f  median %.0f  min %.0f  max %.0f"
                  % (statistics.mean(x["opp_rating"] for x in rated),
                     statistics.median(x["opp_rating"] for x in rated),
                     min(x["opp_rating"] for x in rated),
                     max(x["opp_rating"] for x in rated)))
            hi = [x for x in rated if x["opp_rating"] >= 2000]
            lo = [x for x in rated if x["opp_rating"] < 2000]
            for tag, grp in (("vs >=2000", hi), ("vs  <2000", lo)):
                if grp:
                    ww = sum(1 for x in grp if x["win"])
                    print("  %-10s n=%-3d %dW-%dL  %.1f%%  mean margin $%+.0f"
                          % (tag, len(grp), ww, len(grp) - ww, 100 * ww / len(grp),
                             sum(x["margin"] for x in grp) / len(grp)))
        sigs = {}
        for x in recs:
            key = json.dumps(x["sig"][:1])
            sigs.setdefault(key, []).append(x)
        print("  opponent opening signatures:")
        for k, grp in sorted(sigs.items(), key=lambda kv: -len(kv[1])):
            ww = sum(1 for x in grp if x["win"])
            print("    %-72s n=%-3d %dW-%dL %.0f%%" % (k[:72], len(grp), ww,
                                                       len(grp) - ww, 100 * ww / len(grp)))
        print("  worst 5:")
        for x in sorted(recs, key=lambda y: y["margin"])[:5]:
            print("    %-28s rating %-8s margin $%+9.0f  cash@24 $%-6s cash_end $%s"
                  % (x["opp"][:28], str(x["opp_rating"]), x["margin"],
                     ("%.0f" % x["cash24"]) if x["cash24"] is not None else "?",
                     ("%.0f" % x["cash_end"]) if x["cash_end"] is not None else "?"))
        summary.append((lab or d, recs))
    return summary


if __name__ == "__main__":
    main()
