import json

with open('tools/v48_telemetry_seed1000.json') as f:
    d = json.load(f)

events = [e for e in d['sales_events'] if e['day'] in (9, 10)]
print(f"Total sales on Day 9-10: {len(events)}")
tot = 0
for e in events:
    rev = e['revenue']
    tot += rev
    print(f"Day {e['day']:02d} H{e['hour']:02d}: Sold {e['quantity']} {e['commodity']} @ {e['unit_price']:.1f} = {rev:.1f}")
print(f"Total rev Day 9-10: {tot:.1f}")
