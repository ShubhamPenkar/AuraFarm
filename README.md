# AuraFarm: Autonomous Industrial Economic & Planning Agent for Kaggle Kaggriculture

AuraFarm is an autonomous economic planning agent designed for the Kaggle Kaggriculture simulation competition. Built on empirical reverse-engineering of the environment's official market mechanics, labor cost curves, and livestock production equations, AuraFarm V3 implements an industrial capital-compounding architecture.

## Strategy Highlights (AuraFarm V3)

1. **Aggressive Day-0 Capital Allocation**: Allocates ~$2,912 of starting $3,000 cash on Day 0:
   - 2 Pastures + 2 Coops
   - 2 Cows + 2 Sheep
   - 12 Melons planted across NW quadrant
   - Initial wheat buffer
   - 5 farm hands hired immediately
2. **Permanent Livestock Protection Engine**:
   - Dedicated caretaker assignments
   - 20+ unit pocket feed reservation
   - **Zero animal escapes / zero starvation deaths** across 720 turns (30 days)
3. **Dynamic Fertilizer Economics**:
   - Upward yield acceleration with organic manure and fertilizer application
   - Premium market timing capturing peak price windows ($70–$90)
4. **Town-Drained Wheat Production Engine**:
   - 25–35 dedicated tiles producing continuous wheat
   - Batch deliveries (60–90 units) timed to town demand drains and scarcity spikes
5. **Scaled Industrial Workforce**:
   - Scales to 11 active hands daily across 3 unlocked quadrants (75 tiles)
   - Spatial-clustered dispatch minimizing movement penalties and preventing task contention
6. **Terminal Liquidation**:
   - Orderly liquidation of all livestock, inventory, and produce before step 718

---

## Benchmark & Tournament Results

### Head-to-Head Benchmark vs Top Opponents
- **vs Starter Agent**:
  - AuraFarm V3 Mean Score: **$45,266** (Peak: **$54,005**)
  - Win Rate: **100%**
- **vs wangyh666 V48 (Head-to-Head Competition)**:
  - AuraFarm V3 Mean Score: **$23,061** (Peak: **$37,430**)
  - Animal Escapes / Starvations: **0** across all 20 seeds
  - Sustained continuous high-volume milk, wool, egg, and melon sales

See [`v3_benchmark.md`](v3_benchmark.md) and [`tools/v3_benchmark_results.json`](tools/v3_benchmark_results.json) for full match telemetry.

---

## Repository Structure

```
.
├── main.py                          # Official Kaggle submission entry point (AuraFarm V3)
├── main_v3.py                       # AuraFarm V3 strategy implementation
├── main_v2.py                       # AuraFarm V2 baseline (Town-shop focused)
├── main_v1.py                       # AuraFarm V1 baseline (Carrot-focused)
├── v3_strategy.md                   # Full V3 architectural specification
├── v3_benchmark.md                  # Comprehensive benchmark report (70 matches)
├── v3_ablation.md                   # Controlled ablation study (50 matches)
├── v48_reverse_engineering.md       # Empirical decomposition of top-tier strategy
├── kaggriculture/                   # Official Kaggriculture simulator environment
│   ├── kaggriculture.py             # Environment engine, market mechanics, rules
│   ├── kaggriculture.json           # Environment schema definition
│   └── ...
├── opponents/                       # Reference and opponent agents
│   ├── wangyh666/                   # V48 benchmark opponent
│   └── vicky0718/                   # Public reference agent
└── tools/                           # Verification, ablation, and tournament tooling
    ├── run_v3_matches.py            # Reproduce the 70-match tournament
    ├── run_v3_ablations.py          # Reproduce the 50-match ablation suite
    ├── run_v3_head_to_head.py       # Direct head-to-head match runner
    ├── v3_benchmark_results.json    # Complete tournament logs & scores
    └── v3_ablation_results.json     # Complete ablation telemetry
```

---

## Running Locally & Reproducing Benchmarks

### Prerequisites
- Python 3.10+
- Standard library only (no external dependencies required for `main.py` or `kaggriculture`)

### 1. Test Entry Point
Verify the standalone Kaggle submission agent:
```bash
python -c "import main; print('Submission agent loaded successfully')"
```

### 2. Run Head-to-Head Match
Simulate a direct 30-day match between AuraFarm V3 and the Starter agent:
```bash
python tools/run_v3_head_to_head.py --seed 1000
```

### 3. Run Full Benchmark Suite
Execute the multi-seed evaluation suite:
```bash
python tools/run_v3_matches.py
```

---

## Kaggle Submission Entry Point

The entry point for Kaggle submissions is [`main.py`](main.py):
```python
def agent(observation, configuration=None):
    # Returns: {"farmer": [...], "hands": [[...], ...], "market": [...]}
```
Standard library only, zero external pip dependencies.
