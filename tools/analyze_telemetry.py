"""
Analysis script for V48 telemetry data.
"""
import json
import collections

with open(r"C:\Users\Sanjana\.gemini\antigravity\scratch\tools\v48_telemetry_seed1000.json") as f:
    data = json.load(f)

print("=================================================================")
print(f"V48 TELEMETRY ANALYSIS (Final Score: ${data['final_score']:,.2f})")
print("=================================================================")

print("\n--- 1. REVENUE DECOMPOSITION BY COMMODITY ---")
total_rev = sum(data['revenue_by_commodity'].values())
for k, v in sorted(data['revenue_by_commodity'].items(), key=lambda x: -x[1]):
    qty = data['qty_sold_by_commodity'].get(k, 0)
    avg_p = v / max(1, qty)
    pct = (v / total_rev * 100) if total_rev > 0 else 0
    print(f"{k:<12}: ${v:10,.2f} ({pct:5.1f}%) | Qty: {qty:4d} | AvgPrice: ${avg_p:7.2f}")
print(f"{'TOTAL':<12}: ${total_rev:10,.2f}")

print("\n--- 2. CAPITAL & ASSET TRAJECTORY (Daily at Hour 23) ---")
print(f"{'Day':<4} | {'Money':<10} | {'Hands':<5} | {'Quads':<5} | {'Pens':<5} | {'Animals':<15} | {'Crops':<30}")
print("-" * 85)
for snap in data['daily_snapshots']:
    d = snap['day']
    m = snap['money']
    h = snap['hands']
    q = snap['unlocked_quadrants']
    p = snap['pens']
    a = str(snap['animals']) if snap['animals'] else "None"
    c = str(dict(snap['crops'])) if snap['crops'] else "None"
    print(f"{d:<4} | ${m:9,.0f} | {h:<5} | {q:<5} | {p:<5} | {a:<15} | {c:<30}")

print("\n--- 3. TOP 10 HIGHEST-VALUE SALES ---")
events = sorted(data['sales_events'], key=lambda x: -x['revenue'])
print(f"{'Step':<5} | {'Day':<4} | {'Commodity':<11} | {'Qty':<4} | {'Price':<7} | {'Revenue':<10} | {'PreInv':<7} | {'PostInv':<7} | {'Shops'}")
print("-" * 90)
for ev in events[:10]:
    s = ev['step']
    d = ev['day']
    comm = ev['commodity']
    qty = ev['quantity']
    p = ev['unit_price']
    rev = ev['revenue']
    pre_i = ev['pre_inv']
    post_i = ev['post_inv']
    shops = ",".join(ev['unlocked_shops'])
    print(f"{s:<5} | {d:<4} | {comm:<11} | {qty:<4} | ${p:<6.1f} | ${rev:9,.1f} | {pre_i:<7} | {post_i:<7} | {shops}")

print("\n--- 4. SHOP UNLOCK TIMELINE ---")
seen_shops = []
for snap in data['daily_snapshots']:
    d = snap['day']
    shops = snap['unlocked_shops']
    if len(shops) > len(seen_shops):
        new_shops = shops[len(seen_shops):]
        print(f"Day {d:02d}: Unlocked new shop(s): {new_shops} (Total: {len(shops)})")
        seen_shops = list(shops)
