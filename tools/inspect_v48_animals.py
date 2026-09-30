import json

with open(r"C:\Users\Sanjana\.gemini\antigravity\scratch\tools\v48_telemetry_seed1000.json", "r") as f:
    data = json.load(f)

print("V48 Daily Snapshots:")
for entry in data:
    day = entry["day"]
    hour = entry["hour"]
    if hour == 23 and day in (0, 1, 2, 3, 5, 8, 10, 12, 15, 18, 20, 25, 29):
        print(f"Day {day:02d}: Money={entry['money']:,.0f} | Hands={entry['workers']} | Animals={entry['animals']} | Crops={entry['crops']}")
