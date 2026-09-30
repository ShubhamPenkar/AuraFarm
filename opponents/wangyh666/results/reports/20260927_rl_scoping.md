# RL scoping for Kaggriculture — is reinforcement learning a realistic way to improve our score before 2026-09-30?

**Date:** 2026-09-26 · **Type:** scoping study, read-only (no agent code touched, no experiments/v47, no route_headroom*)

Every number below is tagged **[MEASURED]** (taken on this box during this study),
**[LOCAL]** (already in `insights/`, with its claim ID) or **[SOURCED]** (external, with a link).

---

## 1. Throughput — measured, not guessed

Hardware: **24 logical cores** (Intel64 Family 6 Model 183), **RTX 5070 Laptop 8 GB**. [MEASURED]

### 1.1 Official engine, end-to-end (`env.run`), single core

| Configuration | s / 720-step game | games/hr on 24 cores |
|---|---|---|
| trivial vs trivial (best of 3) | **1.113** | 77,609 |
| fieldcraft vs trivial | 7.730 | 11,177 |
| ours (`main.py`) vs trivial | 10.596 | 8,154 |
| ours vs fieldcraft | **15.594** | 5,538 |
| fieldcraft vs fieldcraft | ~15 | ~5,700 |

The first number corroborates the community figure for the official engine
(**815 ms / 720 steps ≈ 1.02 episodes/s**) [SOURCED:
`destbreso/from-1-to-24k-episodes-a-second`].

### 1.2 The number that matters for a *training loop* — step the env directly

`env.run` carries harness bookkeeping. Stepping the engine directly with a
policy-shaped agent (featurize observation → argmax over a discrete action set) in
self-play:

| Path | ms / step / core | steps/s / core | steps/s on 24 cores |
|---|---|---|---|
| raw `env.step`, PASS agents | 1.300 | 769 | 18,467 |
| `env.step` + policy-like agent, self-play | **0.900** | **1,112** | **26,678** (= 37.1 eps/s = **133,391 episodes/hr**) |

A policy's own cost is negligible: featurizing the real 720-step observation is
**0.007 ms**, a 256-wide pure-Python dot product **0.008 ms** — against a 0.9–1.3 ms
env step. [MEASURED] The engine, not the network, is the bottleneck.

**Derated training-loop estimate.** A real PPO loop adds a torch forward/backward and a
batching/gradient phase. Take **⅓ of the measured ceiling**: **~8,900 steps/s** on 24
cores ≈ **12.4 episodes/s ≈ 44,500 episodes/hr**. This is an engineering estimate, not a
measurement — flagged as such.

### 1.3 How many episodes are needed, and how long here

Published budgets for this genre [SOURCED]:

| System | Env steps | Hardware / time |
|---|---|---|
| Lux AI 2021 winner (IMPALA, Toad Brigade) | 20M shaped steps, then sparse | personal dual-GPU PC |
| Lux AI S2 PPO (arXiv:2304.13004) | **220M steps** | 8× RTX8000, 124 h (env runs at **60 steps/s**) |
| Lux S2 NeurIPS PPO (Jux) | ~240M (80M × 3 curricula) | Lambda A10/A100 |
| OpenAI Five | 2M frames / 2 s, 10 months | up to 1,536 GPUs |
| AlphaStar | ~600 agents, 14 days | 16 TPUs / agent |

The defensible framing, in the Lux-v2 paper's own words: **on-policy MARL in these sims
needs 10^8 environment steps** [SOURCED: arXiv:2304.13004].

**Arithmetic on our box** (10^8 steps = 138,889 episodes):

| Rate | 10^8 steps | 220M steps (Lux S2 budget) |
|---|---|---|
| measured ceiling 26,678 steps/s | **1.0 h** | **2.3 h** |
| derated 8,900 steps/s | **3.1 h** | **6.9 h** |

**This is the single most important finding of the study, and it contradicts the usual
intuition: compute is NOT the blocker here.** Kaggriculture's engine costs ~1 ms/step;
Lux AI's cost 60 steps/s — a ~60× handicap that does not apply to us. A
community bit-exact C++ port reaches **3,300–5,600 eps/s single-core** and
**~24,442 eps/s on 10 cores** (≈23,910× official) [SOURCED], which would make 10^9 steps
take seconds. So there is no sampling-cost argument against RL in this environment.

---

## 2. What the action space actually is

From `env/kaggriculture.py` + `env/kaggriculture.json` [MEASURED].

**Per-turn tuple:** `{"farmer": [op, ...args], "hands": [[op, ...args], ...], "market": [[op, ...args], ...]}`

- **Unit ops (17 documented):** `NORTH` `SOUTH` `EAST` `WEST` `PASS` `PICKUP <item> [n]`
  `PLANT <crop>` `WATER` `HARVEST` `FERTILIZE` `BUILD_COOP` `BUILD_PASTURE` `DIG`
  `PLACE <item> [n]` `FEED` `COLLECT_FERTILIZER` `CARE`.
  The interpreter also handles an **undocumented** 18th, `DROP` (shed deposit),
  which is absent from the JSON schema's description string.
- **Market ops (6):** `BUY_SEED <crop> <n>` `BUY_PRODUCT <item> <n>` `BUY_ANIMAL <animal> <n>`
  `SELL <item> <n>` `HIRE` `BUY_LAND`.
- **Total: 23 documented op types** (24 in code).

**Everything is discrete.** There is no continuous action anywhere. The arguments are
finite categoricals: crops ∈ 5, products ∈ 9, animals ∈ 3, and `n` an integer (market
orders are **truncated to the first 10**, `maxMarketOrdersPerTurn=10`; `HIRE`/`BUY_LAND`
are atomic and take no argument).

**The joint action is a tuple of variable length**: one unit action for the farmer, plus
one per hired hand. There is **no cap on hands in the interpreter** (`_do_hire` just
appends; cost is Fibonacci, so money is the only limit). So the policy is a
*factorised* object over `H + 1` units, not a flat `MultiDiscrete`. A policy network is
expressible, but it must be a per-unit factorised head plus a market head — a flat
softmax over the joint space is not.

**Market resolution is a per-unit lockstep.** `_process_market` quotes *both* players'
current unit price, then commits both, then advances (`env/kaggriculture.py:544`). This
is a real simultaneous-move auction, and it is the reason `_CXD` exists (§6).

**Private (only revealed to the acting player)**, per `kaggriculture.json`:
`private.shed`, `private.inventories` (per-farmer), `private.seeds`. Public/shared:
`farms` (tiles, money, positions, unlocked quadrants, hire count — **opponent shed and
per-farmer inventories excluded**), `market` (inventory + price), `town` (unlocked
shops), `day`, `hour`, `player`, `step`. Full observation JSON is only **2,759 bytes** at
step 1 [MEASURED] — observation size is not a constraint.

**Reward is a single terminal scalar.** There is exactly **one** reward assignment in the
whole interpreter (`kaggriculture.py:963`), fired when `step >= episodeSteps - 2`:
`s.reward = float(obs0.farms[s.observation.player]["money"])`. [MEASURED] No intermediate
reward exists. A 720-step credit-assignment problem with a single number at the end is
the structural difficulty, and it is the one the Lux S2 winner had to solve with
20M steps of hand-designed shaping before sparse reward worked.

---

## 3. Per-step constraints on the ladder — both confirmed from the environment config

Read live from the constructed environment [MEASURED]:

```
actTimeout = 1        (s per turn)
runTimeout = 1200     (s for the whole episode)
episodeSteps = 720
remainingOverageTime = 60
```

Also confirmed in `env/kaggriculture.json` (`episodeSteps: 720`, `actTimeout: 1`).

**What this rules out:** any decision procedure needing > 1 s per turn. Measured budget
usage by our current stack, per turn, over a full episode vs fieldcraft [MEASURED]:
**mean 3.95 ms, p50 3.02 ms, p99 20.67 ms, max 212.47 ms** against a 1,000 ms limit.
So we currently use **~0.4% of the budget on average and ~2% at p99**.

This is worth stating plainly: the 1 s budget permits roughly **50–250× more computation
per decision** than we use. It rules out nothing we would plausibly want — a 41-rollout
lookahead (23,616 env steps ≈ 21 s single-core) is too slow, but a **single** forward
simulation of ~500 steps (~0.5 s) fits inside the budget, and 24 cores are available to
the agent at decision time only if the ladder grants them (it does not, per-seat —
only 1 s wall clock regardless of core count).

---

## 4. What is already known locally

### 4.1 (a) What the top teams do — and none of them learn

**A1** (`insights/claims.md:12`):
> 打赢我们的 top 队**在第 12–18 天抛弃磁带**：路线吻合度从 0.95 掉到 **0.12–0.14**，优势 **+$5–7k**

**A4** (`insights/claims.md:15`):
> 手工**贪心**调度器亏 −$4.4k ~ −$16.8k（"缺少磁带的逐回合路由密度"）

**A9** (`insights/claims.md:20`):
> 配方：**Fixed→录磁带 / Conditional→按商店查表 / Flexible→读实时状态的规则** …
> 我们的 agent 是**几乎纯 Fixed**（全 720 步磁带）；我们已有的 Conditional 是"按前两家店选 route"（41 条）；
> Flexible 只有约 40 层局部反射

The `metav4` source (§6) is the primary evidence for A1, with a route-match table by
6-day phase: mtmr_s1 `0.95/0.95/0.95/0.12/0.12 → +$5.2k`; feel the agi
`0.47/0.81/0.14/0.13/0.14 → +$7.0k`; keiz/DeeperNet `0.32/0.51/0.13/0.12/0.14 → +$5.5k`.
Its own conclusion:
> **Replicating this handover is the primary open research question in Kaggriculture today.**

**Direct answer to the question asked: NO source describes machine learning,
reinforcement learning or a neural network.** All 18 files in `insights/sources/` plus
`claims.md` and `local_findings.md` describe hand-engineering — recorded tapes,
conditional shop lookups, hand-coded price models, hand-coded reflection layers. A grep
for `neural|reinforcement|机器学习|强化学习|神经网络|RL|train|learn|GPU` across the whole
`insights/` tree returns **zero hits describing a top team**. The only ML-adjacent item in
the corpus is our *own* behaviour-cloning experiment (M5, below). Tape counts:
`yhay81` = **13 deterministic 719-turn tapes** selected at step 144; our own stack = **41
routes = 13 classic V39 + 28 specialized EXP240**, selected at step 144 by the first two
unlocked shops as an ordered pair, with a plan-2 liquidation transition at step 648
(`leoprovorov`, `guruprasaathas111_master_engine_v4`).

### 4.2 (b) The behaviour-cloning result — M5

`insights/local_findings.md:45`, **[LOCAL]**:
> **行为克隆的可行性上限**：种植选择从公开状态可预测 **69.3% vs 多数类 60.5%（+8.8pp）**，
> 且泛化到没见过的队伍（+8.5pp）；**但番茄的召回率只有 8.0%**——最有区分度的那个决策学不到

Evidence base: `scripts/extract_plant_choices.py` + `fit_plant_choice.py`,
**60,460 real decisions / 120 games / 19 teams**, from
`ashok205/kaggriculture-top10-replay-archive`.

Read this carefully, because it is the closest thing to a local RL-relevant measurement:
a *supervised* model on top teams' **easiest** decision (which crop to plant, from public
state) beats the majority class by only **+8.8pp**, and gets **TOMATO recall 8.0%** —
i.e. it fails exactly on the decision that carries the information. If supervised
learning on the easiest sub-decision barely clears the base rate, a learned
*when-to-deviate* policy over 720 steps should be assumed harder until shown otherwise.

### 4.3 (c) How little a single decision matters

- **M1'** (`claims.md:211`) — and this is decisive for candidate (i):
  > **U1 标签**（某状态下哪盘磁带最好）**回放给不了**——每局只跑了一盘，其余 40 盘是**反事实**，只能靠模拟造

- **M1** (`local_findings.md:41`): the early-death bug — 5/62 games (8.1%), and precisely
  the 5 largest losses (−$30,092 / −$29,389 / −$24,403 / −$16,601 / −$8,346); fix moved
  median step-24 cash **$12 → $18**.
- **M2** (`local_findings.md:42`): TOMATO yields exactly 4 times regardless of planting
  day — "planting earlier" only moves the sales window, not the yield.
- **"Few hundred dollars" cluster:** `guruprasaathas111_master_engine_v4`: mean margin
  **+$1,649, worst +$2**; "赢 60 局不等于领先很多：最差那局只赢两块钱"; this band is decided
  by **几百块（有时是几块钱）**. `nathanjacob_turn1_clusters`: pipe-4 nets **+$26** at step 2.
  `claims.md L5'`: mirror-vs-true model ordering differs on 442 decision steps, mirror
  choice worse on **261/261**, but only **$9.9/step mean (median $4, max $125)** ≈
  **$50–80/game — below our A/B resolution**. `claims.md M2'`: **80% of games differ by
  <$100 at day 6**.
- **K5** (`claims.md:181`): no sharp loss signature exists; **天梯胜负主要由对手强度 + 大随机分量决定**.
- **K3** (`claims.md:179`): shop unlocks before day 21 are seed-determined; play cannot
  influence them. Confirmed independently in `results/reports/20260926_retro_and_directions.md`
  F-3: 0/15 seeds changed the first shop under three different opponents.
- **F-5** (`retro_and_directions.md`): same-code re-submission spreads **62–675 ladder
  points** — the ladder noise is larger than most version differences.
- **F-1** (`retro_and_directions.md`): **52% of revenue comes through the town-shop
  channel**, and none of our existing layers (`_ADV`/`_CXD`/`_MPX`/`_E402`/`_E410`/`_IG`/`_R42`)
  optimise it.

### 4.4 The noise floor, measured this session

Because this determines what any learned component would have to beat [MEASURED]:

| Comparison | n | margin mean | **sd** | range |
|---|---|---|---|---|
| fieldcraft vs fieldcraft (**identical policy**, seed varies) | 8 | +$1,076 | **$767** | $2,565 |
| ours vs fieldcraft | 8 | +$5,515 | **$5,913** | $21,829 |

With the *same agent on both sides*, the seed alone swings the margin by **$2,565**. The
paired sd of **$767** is the conservative noise floor for an A/B; the unpaired sd is $5,913.

**Sample sizes to detect an effect** (two-sided α=0.05, 80% power, paired, σ=$767):

| Effect size | n per arm | total games | wall clock on 24 cores (5,538 games/hr) |
|---|---|---|---|
| $204 (the community shop-channel swap, §6) | 222 | 444 | **4.8 min** |
| $61 (the `_CXD` upper bound, §6) | 2,482 | 4,964 | 54 min |
| $5,000 (the A1 prize) | 1 | 2 | seconds |

**Experiment throughput is not a constraint either.** We can resolve a $204 effect in
under five minutes. The problem is not that we cannot measure — it is that the measured
headroom for the learnable sub-decisions is small.

---

## 5. Prior art — how RL did in this genre, and at what cost

### 5.1 The genre verdict is split, and the split is informative

| Competition | Winner's method | Source |
|---|---|---|
| **Lux AI 2021** | **Deep RL** — IMPALA/TorchBeast + UPGO + TD-λ + KL distillation from a fixed teacher; sparse terminal ±1 with 20M steps of shaping first; 8→16→24-block ResNets; personal dual-GPU PC | [Toad Brigade writeup](https://www.kaggle.com/competitions/lux-ai-2021/writeups/toad-brigade-toad-brigade-s-approach-deep-reinforc) |
| **Lux AI Season 2** (NeurIPS 2023) | **Hand-coded heuristics + forward simulation.** Winner's repo `ryandy/Lux-S2-public`, 40 `.py` files, **grep for torch/tensorflow/stable_baselines/gym/neural/`.pt` returns ZERO hits** | [1st place writeup](https://www.kaggle.com/competitions/lux-ai-season-2/discussion/407982) |
| **Halite** (Kaggle, = Halite IV 2020) | **Rule-based.** Winner's repo has the winning artefacts under `Rule agents/Leaderboard agents/`, individual rule files up to **558,105 bytes**; the `Deep Learning Agents/` folder is separate and exploratory | [github.com/ttvand/Halite](https://github.com/ttvand/Halite) |
| **Kore 2022** | **Rule-based** 1st place ("simple rules-based agent", fixed op sequence). 3rd place on RL: **"preparing RL took about three weeks, but the benefit seemed not to be very large"** — abandoned it | [1st place](https://www.kaggle.com/competitions/kore-2022-beta/writeups/adg4b-1st-place-solution) |
| **Lux AI S3 (HORIZON, arXiv:2609.12422)** | **RL beats the rule bot** — MWR 0.72 vs RuleBot 0.41 — but in a **JAX simulator running "several thousand concurrent environment instances on a single GPU"** | [arXiv:2609.12422](https://arxiv.org/abs/2609.12422) |

The pattern is legible: **RL wins when the environment can be vectorised onto a GPU to
10^3–10^4× the reference throughput; hand-coding wins when it cannot.** Lux S2's winner
shipped zero ML dependencies. Halite's winner shipped a 558 KB rule file.

### 5.2 RL vs the built-in rule bot, when measured

- **Lux AI S3 (Jönköping thesis, 1,500-match tournament)** [SOURCED]: against a scripted
  rule-based opponent — **MASAC 20.4%, MAPPO 9.2%, QMIX 2.3%** win rate. Cross-play
  against other learners: MAPPO 61.3%. Conclusion: *"neither algorithm consistently
  outperformed a simple rule-based scripted opponent."* (Medium confidence on exact
  digits — page unreachable by direct fetch.)
- **USC Lux project**: tried rules, deep RL from scratch, evolution strategies and
  imitation. Best result was a **hybrid imitation + ES agent at 89th/1,122 (top 8%)**;
  pure RL-from-scratch and pure rules both finished lower.
- **Halite III ML study** (UPenn, 500 games) [SOURCED]: *"the genetically-tuned bot
  outperforms all other bots across all map densities. Our DQN bot outperforms the
  rule-based bot for low halite maps, but achieves similar performance for medium and
  high density maps"* — and overall *"performed significantly worse than the
  genetically-tuned"* rule bot.
- **Lund thesis on Halite IV**: *"incredibly difficult to solve with RL"* — huge strategy
  space, huge state.

### 5.3 Kaggriculture specifically — there IS prior art, and it is negative

This is the most directly relevant evidence found, and it post-dates a lot of the
planning in `insights/`.

- **Meta-analysis, 161 public notebooks, snapshot 2026-08-08** [SOURCED:
  `ocean240812/kaggress-meta-rl-vs-deterministic`], titled *"Why Clones Beat RL on
  Kaggriculture"*, verbatim:
  > **Is anyone doing RL?** Effectively no. Zero of the top-30 public notebooks implement
  > a true RL update loop. The few that mention RL … ship a deterministic rule-based agent
  > and call the environment "an RL problem".

  Their own numbers: deterministic variants peaked at **684.1 LB**; clone/fork variants at
  **1,357.4 LB** — ~2× for ¼ the effort. Named structural reasons: the **720-turn
  horizon, terminal-only reward, and a ladder that scores the mean of your latest 2
  submissions** — so refreshing a route tape beats weeks of training.
- **A concrete RL post-mortem** [SOURCED: Kaggle discussion 738079]: 50,000 optimizer
  steps, training accuracy **99.84% Land / 98.73% Production AP / 80.31% Market-item**.
  In closed loop, across **300 genuine day-start branches** the model rejected the next
  land purchase **187 times**, failed the same-step financing check **100 times**, and
  **confirmed only 7 expansions**. Average final cash over ten closed-loop games:
  **2,671 — below its own intermediate deterministic baselines.** Diagnosis: the headline
  accuracy was the majority class; expansion intent never became a persistent commitment.
- **"RL is a variance tax"** [SOURCED: Kaggle discussion 741320]: argues closed-loop
  adaptation loses to static macro-schedules because opponent interaction here is a
  *negative externality through shared market inventory*, not spatial combat, so
  closed-loop branching optimises variance rather than expected reward.
- Live competition state [SOURCED, Kaggle API]: **10,035 teams, $50,000, deadline
  2026-09-30**. Leader **Boey 3112.8**. Existing RL-attempt notebooks
  (`rafifariqrabbani/…staged-frozen-rl` — 8 small REINFORCE/PPO controllers, one economic
  dial each, trained sequentially and frozen; `saitejabandaruin/…pytorch-dqn-baseline` —
  **its EDA uses `np.random.randn` mock data, i.e. a template not a result**) are not
  competitive. **No published competitive RL agent for Kaggriculture exists.**

**Read the frozen-controllers notebook as the shape of the only RL that has not obviously
failed here**: small, staged, frozen, one dial each — i.e. RL as a *tuner of a handful of
scalars inside a hand-built stack*, not as a policy over the game.

---

## 6. The honest verdict

### 6.1 Is end-to-end RL from scratch realistic before 2026-09-30?

**No — but not for the reason usually given, and the reason matters.**

The compute arithmetic, measured on this box, does *not* rule it out:

```
10^8 env steps (the genre's standard budget) = 138,889 episodes
  at the measured ceiling of 26,678 steps/s on 24 cores  ->  1.0 hour
  at a derated 8,900 steps/s for a real PPO loop        ->  3.1 hours
220M steps (the actual Lux AI S2 PPO budget)            ->  2.3–6.9 hours
a community bit-exact C++ port (~24,442 eps/s on 10 cores) ->  seconds
```

So the five things that actually rule it out:

1. **Terminal-only reward over 720 steps.** One reward site in the whole interpreter
   (`kaggriculture.py:963`). The one RL success in this genre (Lux S2) needed 20M steps of
   *hand-designed* shaping before sparse reward worked — shaping is itself a
   hand-engineering project, and there are 5 crops × 3 animals × 9 products × 4 quadrants
   of it to get right.
2. **The locally measured headroom for the learnable sub-decisions is $61–$204/game,
   against a $767 (paired) to $5,913 (unpaired) noise floor.** We *can* measure those
   effects (444 games, 4.8 min), but a learned component would have to beat a
   hand-built exact method to capture them (§6.2 ii–iv).
3. **The one large prize is a planner, not a policy.** A1's +$5–7k is for *abandoning the
   tape at days 12–18*. A4 reports the hand-coded version of exactly that behaviour loses
   **−$4.4k to −$16.8k**, and our own v15–v20 rule variants all lost (Elo stuck at 565).
   The target behaviour is hard for humans; RL has to find it from a single terminal
   scalar, and M5 says supervised learning on the *easier* decision gets +8.8pp over
   majority with 8.0% TOMATO recall.
4. **The direct empirical record on this competition is negative and recent**: zero of the
   top-30 public notebooks implement an RL update loop; the one documented attempt ended
   at cash 2,671, below its own deterministic baseline; clones (1,357 LB) beat
   deterministic (684 LB) 2:1 for ¼ the effort.
5. **The ladder scores the mean of the latest 2 submissions**, which rewards refreshing a
   validated tape over a training run of uncertain sign.

Add the plumbing gap: **the `.venv` has 39 packages and zero of numpy, torch, scipy,
pandas, sklearn, jax or tensorflow** [MEASURED]. The system Python has numpy 2.5.1 and
sklearn 1.9.0 but no torch. The 8 GB RTX 5070 is unused. Installing torch is a
10-minute fix and is *not* a real blocker — it is listed only so nobody mistakes the
current setup for being RL-ready.

**One-line verdict:** RL here is affordable to *run* and very unlikely to *pay*, because
the measured value of the decisions it could plausibly improve ($61–$204/game) sits below
the noise floor, while the only decision worth $5–7k is a re-planning problem that
hand-coding has already failed at four separate times.

### 6.2 The narrowest learned component that could still help — assessed in order

**(i) A value function over states to choose among the 41 tapes.**
*Labels must be simulated.* M1' is explicit: a replay only ever ran one tape, so the other
40 outcomes are **counterfactual** and must be generated. [LOCAL, `claims.md:211`]
*Cost:* one labelled state at step 144 = 41 rollouts × 576 steps = **23,616 env steps**
≈ 21 s single-core, ≈ 0.9 s on 24 cores. 10,000 labels = 2.4×10^8 steps = **~2.5 h** on 24
cores. Affordable.
*Ceiling:* **low.** Choosing among 41 tapes cannot produce the +$5–7k that A1 attributes
to *leaving* the Fixed tier — all 41 are Fixed-tier. And the existing Conditional table
already selects a route from the first two shops, a feature M5' calls **"判别力完美"**
(129 signatures / 981 games; each opponent has exactly one value across 40 seeds). So the
learner must beat a near-perfect lookup, at 2.5 h per 10k labels.
**Verdict: affordable, low ceiling, not recommended.**

**(ii) A learned market-order policy, against `_CXD`'s exact search.**
*Measured this session* (`scripts/cxd_model_value.py --games 12`, host
`experiments/v45/v45_adv12.py`, `_CXD_MODELS=[]`):

```
steps evaluated: 133   ordering identical under both models: 1   errors: 0
margin lost to the mirror assumption (upper bound, rival list known):
  n=58  mean $+12.6  median $+6.0  min $+1.0  max $+104.0
  strictly better on 58/58 = 100.0% of the differing steps
```

58 differing steps over 12 games ≈ 4.8/game × $12.6 ≈ **$61/game upper bound** — and that
upper bound *grants us the rival's simultaneous order list at decision time*, which is
unavailable by construction.
*Can learning beat exact local search here?* **No, and the reason is structural.** `_CXD`
searches orderings of our SELL orders over the free market slots (BUDGET = 800 candidates)
and evaluates each with **the engine's own exact per-slot lockstep evaluator**. The search
space is small and the objective is exactly computable. A learned model can only
*approximate* that evaluator while holding strictly less information. Learning wins over
search when the evaluator is unknown, slow, or the space is intractable — none holds here.
The one genuinely learned slot (`_CXD_MODELS`, the rival's order list) is capped at the
$61/game upper bound above, so a realistic predictor captures perhaps $12–25/game.
**Verdict: dead end, measured. Do not spend here.**

**(iii) A learned opponent model.**
Same ceiling as (ii) if used to fill `_CXD_MODELS`: **$61/game upper bound**, and
`_CXD_MODELS` is currently `[]` and never appended, so the search always assumes the rival
submits our own orders [MEASURED: `_CXD_MODELS=[]` confirmed at runtime]. As a *route*
conditioning feature, the opponent signature is already near-perfect and needs a **lookup,
not learning** (M5', M4'). **Verdict: the useful part is a lookup; the learnable part is
worth ≤$61/game. Not recommended.**

**(iv) Fine-tuning a policy that decides *when* to deviate from the tape.**
This is the **only candidate with a positive expected value**, because it is the only one
aimed at the only large measured prize (A1: **+$5–7k**, route-match 0.95 → 0.12–0.14 at
days 12–18). Narrowest useful form: a **gate** ("stay on tape" vs "hand control to a
planner") confined to the day 12–18 window, plus a planner that is at least break-even.
*Cost:* data is cheap — 981 curated replay files already exist, and simulated labels run
~2.5 h per 10k decisions. A gate is a small classifier. Total build ~1–2 days.
*Why it is still a long shot:* A4 says the planner loses **−$4.4k to −$16.8k** when
hand-coded, and M5 says cloning top-team decisions on the *easier* problem gets +8.8pp
over majority with 8.0% TOMATO recall. The gate's labels ("should we have deviated here")
are counterfactual again and need simulation. So you need a gate *and* a good planner, and
the local evidence says the planner is the hard half.
**Verdict: the best available bet, with low probability. If RL is attempted at all, this
is the shape — a frozen scalar/dial tuner inside the existing stack (cf. the community's
`…staged-frozen-rl` notebook), not a policy over the game.**

**Ranking:** (iv) > (i) > (iii) ≈ (ii). Note (ii)/(iii) are not merely risky, they are
*measured* to be capped at ~$61/game.

### 6.3 What would have to be true for the answer to change

1. **A vectorised/GPU engine.** The community C++ port already reaches ~24,442 eps/s
   (~23,910× official) [SOURCED]. This removes the *sampling* constraint entirely — but
   sampling is not the binding constraint (10^8 steps is ~1–3 h even on the official
   engine), so this alone would **not** flip the verdict. It is necessary, not sufficient.
2. **A dense or shaped reward.** Terminal-only reward over 720 steps is the real
   algorithmic obstacle. If a cheap, well-behaved shaping term existed (e.g. terminal
   money decomposed into the 52% shop channel and the 48% own-orders channel), RL would
   become substantially more tractable.
3. **A cheap exact oracle for a *large* sub-decision.** Everything measured so far is
   small ($61/game market ordering; $204/game shop-channel swap; $50–80/game mirror
   ordering). RL becomes worth it when a sub-decision's *oracle* value is large **and** its
   space is too big to enumerate. Finding one is the actual research problem.
4. **Evidence the tape is weak.** It is not: we beat fieldcraft 86.7%, and the obvious
   headroom experiments are closed. RL competes with a strong prior.
5. **A stationary opponent population.** M3' shows ladder composition shifted from
   3–8% to 30–38% tetsutani in a single day [LOCAL], so any learned policy needs constant
   re-training — which the latest-2-submissions ladder rule actively penalises.

**Converse, worth stating:** if the stack were still at Elo 565 with rule agents (as
v15–v20 were), RL-from-scratch would be a *reasonable* bet, because the alternative
baseline would be weak and the compute is cheap. The verdict is negative here **because
the incumbent is strong** — a 720-step expert demonstration plus ~40 hand-coded layers
beating fieldcraft 86.7% — not because the environment is unfriendly to learning. Anyone
arguing for RL should be asked which of items 1–5 they have changed.

---

## Appendix — measurement provenance

| Number | How obtained |
|---|---|
| 1.113 / 7.730 / 10.596 / 15.594 s per game | `make('kaggriculture', configuration={'seed':…}, debug=False)` + `env.run([a,b])`, best of 2–3 seeds |
| 1.300 ms/step, 0.900 ms/step | direct `env.step` loop, 200 and 719 steps |
| mean 3.95 / p50 3.02 / p99 20.67 / max 212.47 ms | wall-clock wrapper around our `main.py` agent, 719 calls |
| 2,759 B observation | `json.dumps` of `env.steps[1][0].observation` |
| 0.007 / 0.008 ms | `time.perf_counter` over 2,000 iterations |
| actTimeout / runTimeout / episodeSteps | live `env.configuration` after `make(...)` |
| one reward site | `grep -n reward env/kaggriculture.py` → line 963 only |
| $767 / $5,913 sd | 8 seeds each, fc-vs-fc and ours-vs-fc, margins `steps[-1][0].reward - steps[-1][1].reward` |
| `_CXD` $12.6/$6.0/$104, n=58/133 | `scripts/cxd_model_value.py --games 12` |
| 24 logical cores | `os.cpu_count()` |
| no numpy/torch in `.venv` | `importlib.import_module` + `pip list` (39 packages) |

**Not measured / not verifiable here:** GPU-hours for any published system (none
published for Lux S1); the exact Lux S3 thesis win rates (page unreachable, medium
confidence); Lux leaderboard positions (read via the Kaggle v1 API, not a rendered page);
the C++ port's throughput (community-reported, not reproduced on this box); and the
realistic PPO loop rate (~8,900 steps/s), which is an engineering derating of the measured
ceiling, not a measurement.
