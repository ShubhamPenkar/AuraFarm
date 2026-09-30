# 2026-09-27 — the adv4/adv12 A/B has resolved on replay evidence (not on score)

Window now = **max(2361.3, 2069.6) = 2361.3** (v48 adv12 / v47 adv4).
So the displayed score took no damage — but slot 2 fell below 2200, and that is
what triggered this check.

```
ref 56578913  v48  adv12   2361.3   (09-26 12:12, sha ff772c068a63d570)
ref 56576495  v47  adv4    2069.6   (09-26 10:08, sha 0719065c227ffb11)   <- was 2190.6 at 2h
ref 56566776  v46  adv12   2273.2
ref 56556192  v45  adv8    2281.8
```

## Answer to the 判据: v47 will not climb to 2450 — the 200 points were the draw

Full replay pull, both arms, same era, same field:
`replays_v56576495` 164/164, `replays_v56578913` 157/157.

| | v47 (adv4) | v48 (adv12) |
|---|---|---|
| overall | 74W-90L = **45.1%** | 89W-68L = **56.7%** |
| vs `tetsutani_cha22` family (58%/54% of draw) | n=86, **38%**, mean margin $-393 | n=84, **63%**, mean margin **+$596** |
| vs no-race families | 60% | 53% |
| RACE share of draw | 58% | 57% |

- race family: 38% -> 63% = **+25pp, z=3.22** (p~0.001)
- overall: 45.1% -> 56.7% = **+11.6pp, z=2.07**

The draw mix is the same in both (`RACE 58%` vs `57%`), so this is not a
different-field artifact — it is the same bracket, and adv12 wins the layer that
dominates it. The direction matches the local two-block result (adv12 93.2/93.0
vs adv4 ~48 against that family); the ladder just compresses it, because the
ladder version of "that family" is many teams, not one donor.

## The identical-bytes spread settles it independently

- adv4 bytes `0719065c227ffb11`: **v40 2476.6** vs **v47 2069.6** -> spread **407**
- adv12 bytes `ff772c068a63d570`: v46 2273.2 vs **v48 2361.3** -> spread 88

v40's 2476.6 and v47's 2069.6 are the *same file*. So "adv4 is the family that
converges above 2440" was one favourable draw out of two, and the 200-point
"ladder-score gap" that the 09-29 decision rested on does not survive.

## Consequence for 09-29

Per the stated 判据 — *"不会（停在 2250 附近）⇒ 按本地证据投 adv12"* — the endgame
arm is **adv12**, i.e. rebuild the v48/v46 bytes (`_ADV_LOOK=12` on the v41 host,
sha `ff772c068a63d570`) and re-submit it **twice** so both final slots hold it.

Timing note for the 09-29 window: start it **early in the day**, since a re-submit
resets toward a low initial rating and needs hours to converge.

## Not done now, deliberately

No third submission went out: it is 09-27 (endgame condition not met), and
re-submitting now would evict v47 and destroy the arm before it is formally
finished. v47 has no reason to be rescued — the window keeps 2361.3 either way,
and v47's own record (45.1%, 38% on its dominant family) is not a score artifact
that a fresh draw would fix.
