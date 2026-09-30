# AuraFarm: Strategic Architecture & Theoretical Grounding

## 1. System Architecture
AuraFarm is an autonomous economic planning agent designed for the Kaggle Kaggriculture competition. It operates across 5 integrated functional layers:

```
+--------------------------------------------------------------------------+
|                       Observation & Opponent Parser                      |
| - Extracts farm grid tiles[y][x], bank balance, worker coordinates       |
| - Scans opponent tiles to forecast ripening harvest waves                |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Exact Economic & Market Model                      |
| - Grounded directly in official MARKET_PARAMS and market_price()         |
| - Projects future inventory: ProjectedInv = CurrentInv + Supply - Demand |
| - Evaluates Net Marginal ROI per tile per day                            |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Capital & Land Expansion Manager                   |
| - Controlled land purchase (NE quadrant for $1000) when bank >= $2000    |
| - Fibonacci labor hiring: Hires 2–3 hands daily at Hour 0 ($2–$4/day)    |
| - Yields 96 worker actions per day at negligible capital cost            |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Multi-Worker Task Dispatch Engine                  |
| - BFS pathfinding over grid (passable through locked quadrants)          |
| - Priority stack: On-tile Harvest/Water > Weed Clear > Plant > Move      |
| - Spatial assignment prevents worker thrashing and avoids lost turns     |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Market Order & Liquidation Engine                  |
| - Respects maxMarketOrdersPerTurn limit (capped <= 10)                   |
| - Normal phase: Sells when price >= 0.70 * BasePrice                     |
| - Day 26: Cut off new planting to prevent stranded immature crops        |
| - Day 28–29: 100% liquidation of shed inventory into cash                |
+--------------------------------------------------------------------------+
```

## 2. Core Economic Insights

### Why 3-Day Carrots Outperform Livestock & Melons
In empirical testing, long-cycle production (Melons taking 12 days, Cows taking 8 days + daily wheat feed overhead) restricts early-stage capital velocity.
- **Carrot Economics**:
  - Seed cost: $20.
  - Maturation: Day 3 (bonus watering window on days 2 and 3 yields 3 carrots).
  - Revenue: 3 carrots $\times$ ~$35–$45 = $105–$135.
  - Net Profit: +$85 to +$115 per tile every 3 days ($28.3–$38.3 profit/tile/day).
  - Across 45 arable tiles, this generates **~$4,500 every 3 days**, rapidly compounding into tens of thousands of dollars without animal starvation failure modes.

### Labor Hiring Arbitrage
Hiring costs scale via Fibonacci:
- Hand 1: $1
- Hand 2: $1
- Hand 3: $2
Total cost for 3 hands = $4 per day. 3 hands provide 72 actions per day, meaning each action costs **$0.055**. Since watering a carrot tile yields +$35 in bonus produce, the return on hired labor exceeds **600x**.
