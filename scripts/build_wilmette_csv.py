"""Build wilmette_weekend_nsia.csv from scraped data."""
from datetime import datetime
import csv

def calc_hours(start_str, end_str):
    for fmt in ("%I:%M %p", "%I:%M%p"):
        try:
            s = datetime.strptime(start_str.strip(), fmt)
            e = datetime.strptime(end_str.strip(), fmt)
            diff = (e - s).total_seconds() / 3600
            if diff < 0:
                diff += 24
            return round(diff, 3)
        except:
            continue
    return 0.0

events = [
    ("2025-09-06","Saturday","8:00 AM","9:00 AM","NSIA NHL","Practice","Private"),
    ("2025-09-06","Saturday","9:10 AM","10:10 AM","NSIA NHL","Practice","Private"),
    ("2025-09-06","Saturday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2025-09-06","Saturday","11:30 AM","12:40 PM","NSIA NHL","Practice","Private"),
    ("2025-09-07","Sunday","12:40 PM","1:40 PM","NSIA NHL","Practice","Private"),
    ("2025-09-07","Sunday","1:50 PM","2:50 PM","NSIA NHL","Practice","Private"),
    ("2025-09-07","Sunday","3:00 PM","4:00 PM","NSIA NHL","Practice","Private"),
    ("2025-09-07","Sunday","4:10 PM","5:20 PM","NSIA NHL","Practice","Private"),
    ("2025-09-13","Saturday","4:20 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-09-14","Sunday","9:00 AM","10:00 AM","NSIA NHL","Game","Private"),
    ("2025-09-14","Sunday","9:30 AM","10:50 AM","NSIA NHL","Game","Private"),
    ("2025-09-20","Saturday","8:00 AM","9:00 AM","NSIA NHL","Practice","Private"),
    ("2025-09-20","Saturday","9:10 AM","10:10 AM","NSIA NHL","Practice","Private"),
    ("2025-09-20","Saturday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2025-09-20","Saturday","11:30 AM","12:40 PM","NSIA NHL","Practice","Private"),
    ("2025-09-21","Sunday","2:20 PM","3:50 PM","NSIA NHL","Game","Private"),
    ("2025-09-21","Sunday","4:10 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-09-28","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-09-28","Sunday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-09-28","Sunday","10:30 AM","11:30 AM","NSIA NHL","Game","Private"),
    ("2025-10-04","Saturday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-10-04","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-10-05","Sunday","12:40 PM","1:50 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2025-10-11","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","2:20 PM","3:50 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","4:00 PM","5:10 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","5:20 PM","6:30 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","6:40 PM","7:50 PM","NSIA NHL","Game","Private"),
    ("2025-10-11","Saturday","8:00 PM","9:20 PM","NSIA NHL","Game","Private"),
    ("2025-10-12","Sunday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-10-18","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2025-10-18","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-10-19","Sunday","2:00 PM","3:00 PM","NSIA NHL","Game","Private"),
    ("2025-10-19","Sunday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-10-19","Sunday","4:20 PM","5:20 PM","NSIA NHL","Practice","Private"),
    ("2025-10-25","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-10-26","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-10-26","Sunday","9:30 AM","10:30 AM","NSIA NHL","Game","Private"),
    ("2025-10-26","Sunday","10:50 AM","12:20 PM","NSIA NHL","Game","Private"),
    ("2025-10-26","Sunday","3:10 PM","4:10 PM","North Shore Ice Arena","Game","Private"),
    ("2025-11-01","Saturday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","2:40 PM","3:40 PM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","3:50 PM","4:50 PM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","5:00 PM","6:10 PM","NSIA NHL","Game","Private"),
    ("2025-11-01","Saturday","6:20 PM","7:40 PM","NSIA NHL","Game","Private"),
    ("2025-11-02","Sunday","12:40 PM","1:40 PM","NSIA NHL","Game","Private"),
    ("2025-11-02","Sunday","1:50 PM","2:50 PM","NSIA NHL","Game","Private"),
    ("2025-11-02","Sunday","3:00 PM","4:00 PM","NSIA NHL","Game","Private"),
    ("2025-11-02","Sunday","4:10 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-11-08","Saturday","4:10 PM","5:20 PM","North Shore Ice Arena","Game","Private"),
    ("2025-11-09","Sunday","10:50 AM","11:50 AM","North Shore Ice Arena","Game","Private"),
    ("2025-11-15","Saturday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-11-16","Sunday","12:40 PM","1:40 PM","NSIA NHL","Game","Private"),
    ("2025-11-16","Sunday","1:50 PM","2:50 PM","NSIA NHL","Game","Private"),
    ("2025-11-16","Sunday","3:00 PM","4:00 PM","NSIA NHL","Game","Private"),
    ("2025-11-16","Sunday","4:10 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-11-22","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-11-22","Saturday","4:30 PM","5:30 PM","NSIA NHL","Game","Private"),
    ("2025-11-23","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-11-23","Sunday","9:10 AM","10:10 AM","North Shore Ice Arena","Game","Private"),
    ("2025-11-23","Sunday","10:40 AM","12:00 PM","NSIA NHL","Game","Private"),
    ("2025-11-29","Saturday","8:00 AM","9:00 AM","NSIA NHL","Practice","Private"),
    ("2025-11-30","Sunday","2:10 PM","3:30 PM","NSIA NHL","Game","Private"),
    ("2025-12-06","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-12-06","Saturday","4:20 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-12-06","Saturday","5:30 PM","6:30 PM","NSIA NHL","Game","Private"),
    ("2025-12-06","Saturday","7:50 PM","9:20 PM","NSIA NHL","Game","Private"),
    ("2025-12-07","Sunday","7:40 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-12-07","Sunday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-12-07","Sunday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2025-12-07","Sunday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-12-07","Sunday","4:20 PM","5:20 PM","NSIA NHL","Game","Private"),
    ("2025-12-13","Saturday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-12-13","Saturday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-12-13","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2025-12-13","Saturday","11:40 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-12-14","Sunday","1:10 PM","2:20 PM","NSIA NHL","Game","Private"),
    ("2025-12-14","Sunday","2:00 PM","3:10 PM","NSIA NHL","Game","Private"),
    ("2025-12-14","Sunday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-12-20","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2025-12-20","Saturday","6:30 PM","7:40 PM","NSIA NHL","Game","Private"),
    ("2025-12-21","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2025-12-21","Sunday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2025-12-21","Sunday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2025-12-21","Sunday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2025-12-27","Saturday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2025-12-27","Saturday","11:30 AM","12:40 PM","NSIA NHL","Practice","Private"),
    ("2025-12-28","Sunday","12:40 PM","1:40 PM","NSIA NHL","Practice","Private"),
    ("2026-01-03","Saturday","3:10 PM","4:10 PM","NSIA NHL","Practice","Private"),
    ("2026-01-03","Saturday","4:20 PM","5:50 PM","NSIA NHL","Practice","Private"),
    ("2026-01-03","Saturday","6:00 PM","7:30 PM","NSIA NHL","Practice","Private"),
    ("2026-01-04","Sunday","8:00 AM","9:00 AM","NSIA NHL","Practice","Private"),
    ("2026-01-04","Sunday","9:10 AM","10:10 AM","NSIA NHL","Practice","Private"),
    ("2026-01-04","Sunday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2026-01-04","Sunday","11:30 AM","12:40 PM","NSIA NHL","Practice","Private"),
    ("2026-01-10","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2026-01-10","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2026-01-11","Sunday","12:40 PM","1:40 PM","NSIA NHL","Game","Private"),
    ("2026-01-11","Sunday","2:20 PM","3:20 PM","NSIA NHL","Practice","Private"),
    ("2026-01-11","Sunday","3:30 PM","5:00 PM","NSIA NHL","Game","Private"),
    ("2026-01-17","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2026-01-17","Saturday","4:50 PM","6:00 PM","NSIA NHL","Practice","Private"),
    ("2026-01-17","Saturday","6:20 PM","7:50 PM","NSIA NHL","Game","Private"),
    ("2026-01-17","Saturday","7:50 PM","9:20 PM","NSIA NHL","Game","Private"),
    ("2026-01-18","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2026-01-18","Sunday","9:20 AM","10:40 AM","NSIA NHL","Game","Private"),
    ("2026-01-18","Sunday","10:50 AM","11:50 AM","NSIA NHL","Practice","Private"),
    ("2026-01-24","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2026-01-24","Saturday","8:00 PM","9:20 PM","NSIA NHL","Game","Private"),
    ("2026-01-25","Sunday","12:40 PM","1:40 PM","NSIA NHL","Game","Private"),
    ("2026-01-25","Sunday","2:10 PM","3:10 PM","NSIA NHL","Game","Private"),
    ("2026-01-25","Sunday","4:10 PM","5:10 PM","NSIA NHL","Game","Private"),
    ("2026-01-31","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2026-01-31","Saturday","4:20 PM","5:20 PM","NSIA NHL","Practice","Private"),
    ("2026-01-31","Saturday","5:40 PM","6:50 PM","NSIA NHL","Game","Private"),
    ("2026-02-01","Sunday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2026-02-01","Sunday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2026-02-01","Sunday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2026-02-01","Sunday","11:40 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2026-02-07","Saturday","8:00 AM","9:00 AM","NSIA NHL","Game","Private"),
    ("2026-02-07","Saturday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2026-02-07","Saturday","10:20 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2026-02-07","Saturday","11:30 AM","12:40 PM","NSIA NHL","Game","Private"),
    ("2026-02-08","Sunday","12:40 PM","1:40 PM","NSIA NHL","Game","Private"),
    ("2026-02-14","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2026-02-14","Saturday","4:40 PM","6:00 PM","NSIA NHL","Game","Private"),
    ("2026-02-15","Sunday","8:50 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2026-02-15","Sunday","10:20 AM","11:30 AM","NSIA NHL","Practice","Private"),
    ("2026-02-21","Saturday","8:40 AM","9:50 AM","NSIA NHL","Game","Private"),
    ("2026-02-21","Saturday","10:00 AM","11:20 AM","NSIA NHL","Game","Private"),
    ("2026-02-21","Saturday","11:20 AM","12:40 PM","NSIA NHL","Practice","Private"),
    ("2026-02-21","Saturday","8:00 PM","9:20 PM","NSIA NHL","Game","Private"),
    ("2026-02-22","Sunday","1:30 PM","2:50 PM","NSIA NHL","Game","Private"),
    ("2026-02-22","Sunday","3:00 PM","4:00 PM","NSIA NHL","Practice","Private"),
    ("2026-02-28","Saturday","3:10 PM","4:10 PM","NSIA NHL","Game","Private"),
    ("2026-02-28","Saturday","4:20 PM","5:20 PM","NSIA NHL","Practice","Private"),
    ("2026-02-28","Saturday","5:30 PM","7:00 PM","NSIA NHL","Game","Private"),
    ("2026-03-01","Sunday","9:10 AM","10:10 AM","NSIA NHL","Game","Private"),
    ("2026-03-01","Sunday","10:20 AM","11:20 AM","NSIA NHL","Practice","Private"),
    ("2026-03-01","Sunday","11:30 AM","12:40 PM","NSIA NHL","Practice","Private"),
]

fields = ["Date","Day","StartTime","EndTime","Hours","Location","Type","Event"]
rows = []
for e in events:
    date, day, start, end, loc, typ, evt = e
    hours = calc_hours(start, end)
    rows.append({"Date":date,"Day":day,"StartTime":start,"EndTime":end,
                 "Hours":hours,"Location":loc,"Type":typ,"Event":evt})

with open("data/wilmette_weekend_nsia.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

total = sum(r["Hours"] for r in rows)
games = sum(1 for r in rows if r["Type"] == "Game")
practices = sum(1 for r in rows if r["Type"] == "Practice")
print(f"Total events: {len(rows)}")
print(f"Total hours: {total:.1f}")
print(f"Games: {games}, Practices: {practices}")
print(f"Date range: {rows[0]['Date']} to {rows[-1]['Date']}")
