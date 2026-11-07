#!/usr/bin/env python3
"""M0: fetch the fixed 60-day USGS window (M5+) and write data/usgs_60d.csv.
Window is UTC dates [2026-09-08, 2026-11-07). Needs no API key."""
import csv, json, urllib.request, sys, datetime
START, END, MINMAG = "2026-09-08", "2026-11-07", 5
URL = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
       f"&starttime={START}&endtime={END}&minmagnitude={MINMAG}&orderby=time-asc")
with urllib.request.urlopen(URL, timeout=60) as r:
    d = json.load(r)
rows = []
for f in d["features"]:
    p = f["properties"]
    if p["mag"] is None or p["type"] != "earthquake":
        continue
    eid = f["id"]
    assert eid.isascii() and 0 < len(eid) <= 32, eid
    lon, lat = f["geometry"]["coordinates"][:2]
    rows.append((eid, int(round(p["mag"] * 10)), p["time"] // 1000, p["status"], p["place"], round(lat, 2), round(lon, 2)))
out = sys.argv[1] if len(sys.argv) > 1 else "data/usgs_60d.csv"
with open(out, "w", newline="") as fh:
    fh.write(f"# Source: U.S. Geological Survey, Earthquake Hazards Program, ANSS ComCat (FDSN event web service)\n")
    fh.write(f"# Query: {URL}\n")
    fh.write(f"# Retrieved: {datetime.datetime.now(datetime.timezone.utc).date()}  Window (UTC dates): {START} to {END} (end exclusive)\n")
    fh.write("# Citation: please credit the U.S. Geological Survey. licence terms NOT yet verified (see docs/NOTES.md); see https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits\n")
    w = csv.writer(fh); w.writerow(["event_id", "mag_x10", "origin_s", "status", "place", "lat", "lon"]); w.writerows(rows)
print(len(rows), "events;", sum(1 for r in rows if r[1] >= 60), "of M6.0+")
