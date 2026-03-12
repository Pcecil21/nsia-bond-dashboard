"""
Scrape Winnetka Hockey Club weekend schedule (Sep 2025 - Mar 2026)
and extract NSIA events with hours calculation.
"""
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
import csv
import time
import re

BASE_URL = "https://www.winnetkahockey.com/schedule"
NSIA_KEYWORDS = ["north shore ice arena", "nsia"]

def get_weekend_dates(start: date, end: date):
    """Generate all Saturday and Sunday dates in range."""
    d = start
    while d <= end:
        if d.weekday() in (5, 6):  # Saturday=5, Sunday=6
            yield d
        d += timedelta(days=1)

def parse_time(t: str) -> datetime:
    """Parse time string like '8:00 AM' or '8:15 PM'."""
    t = t.strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None

def calc_hours(start_str: str, end_str: str) -> float:
    """Calculate duration in hours between two time strings."""
    s = parse_time(start_str)
    e = parse_time(end_str)
    if s and e:
        diff = (e - s).total_seconds() / 3600
        if diff < 0:
            diff += 24
        return round(diff, 3)
    return 0.0

def scrape_day(d: date) -> list:
    """Scrape schedule for a single day, return list of event dicts."""
    url = f"{BASE_URL}/{d.strftime('%Y-%m-%d')}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    # Look for schedule entries - try multiple selectors
    # The site typically uses table rows or list items for events
    rows = soup.select("tr.schedule-row, tr.game-row, .schedule-item, .event-item")

    if not rows:
        # Try finding all table rows with time-like content
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) >= 3:
                text = tr.get_text()
                if re.search(r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)', text):
                    rows.append(tr)

    if not rows:
        # Try parsing the raw HTML for event patterns
        text = resp.text
        # Look for structured data
        time_pattern = re.findall(
            r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
            text
        )
        if time_pattern:
            # There are time ranges but we couldn't parse structured data
            # Fall back to a more aggressive parse
            pass

    for row in rows:
        cells = row.find_all("td") if row.name == "tr" else [row]
        text = row.get_text(separator=" | ").strip()

        # Extract times
        time_match = re.search(
            r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
            text
        )

        # Extract location
        location = ""
        for cell in cells:
            cell_text = cell.get_text().strip()
            if any(kw in cell_text.lower() for kw in ["arena", "rink", "ice", "nsia", "north shore"]):
                location = cell_text
                break

        if not location:
            # Search entire text
            loc_match = re.search(r'(North Shore Ice Arena|NSIA[^,]*|[^|]*(?:Rink|Arena|Ice)[^|]*)', text, re.I)
            if loc_match:
                location = loc_match.group(1).strip()

        event_name = ""
        event_type = ""
        for cell in cells:
            cell_text = cell.get_text().strip()
            if "practice" in cell_text.lower():
                event_type = "Practice"
            elif "game" in cell_text.lower():
                event_type = "Game"
            if len(cell_text) > 5 and cell_text != location and not time_match:
                event_name = cell_text

        if time_match:
            start_time = time_match.group(1)
            end_time = time_match.group(2)
            hours = calc_hours(start_time, end_time)

            events.append({
                "Date": d.strftime("%Y-%m-%d"),
                "Day": "Saturday" if d.weekday() == 5 else "Sunday",
                "StartTime": start_time.strip(),
                "EndTime": end_time.strip(),
                "Hours": hours,
                "Event": event_name or text[:80],
                "Location": location,
                "Type": event_type or "Unknown",
                "AtNSIA": any(kw in location.lower() for kw in NSIA_KEYWORDS) if location else False,
            })

    return events

def main():
    start = date(2025, 9, 1)
    end = date(2026, 3, 1)
    weekend_dates = list(get_weekend_dates(start, end))
    print(f"Scraping {len(weekend_dates)} weekend days...")

    all_events = []
    for i, d in enumerate(weekend_dates):
        day_name = "Sat" if d.weekday() == 5 else "Sun"
        print(f"  [{i+1}/{len(weekend_dates)}] {d} ({day_name})...", end="")
        events = scrape_day(d)
        print(f" {len(events)} events")
        all_events.extend(events)
        time.sleep(0.3)  # be polite

    print(f"\nTotal events scraped: {len(all_events)}")
    nsia_events = [e for e in all_events if e["AtNSIA"]]
    print(f"NSIA events: {len(nsia_events)}")

    # Save all events
    out_all = "data/winnetka_weekend_all.csv"
    out_nsia = "data/winnetka_weekend_nsia.csv"

    fields = ["Date", "Day", "StartTime", "EndTime", "Hours", "Event", "Location", "Type", "AtNSIA"]

    with open(out_all, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_events)
    print(f"Saved {len(all_events)} events to {out_all}")

    with open(out_nsia, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(nsia_events)
    print(f"Saved {len(nsia_events)} NSIA events to {out_nsia}")

if __name__ == "__main__":
    main()
