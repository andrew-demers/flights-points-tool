---
name: find-flights-points
description: Search for the cheapest award flights in points/miles across multiple dates. User specifies origin, destination, and a date range or list of dates. Searches Google Flights for cash prices AND seats.aero/airline sites for real award availability, then ranks dates by cheapest points cost.
---

# Find Flights in Points

Search flights across multiple dates and return award availability (points/miles) alongside cash prices, ranked by cheapest points.

## When to use this skill

The user wants to fly somewhere and pay with points/miles. They give you:
- Origin and destination (city names or IATA codes)
- A date range like "late July", "July 15-22", or specific dates like "July 18 or July 25"
- Optional: preferred cabin class (economy/business/first), number of passengers

## Step 1 - Resolve inputs

Convert any city names to IATA codes (e.g. "Montreal" → YUL, "Paris" → CDG). If the user gave a date range, expand it to individual dates. For a range wider than 14 days, sample every 2-3 days rather than every single day to keep results manageable.

Ask for missing required info before proceeding:
- If origin or destination is ambiguous (multiple airports), confirm which one.
- If no dates at all were given, ask for a date range or target window.

## Step 2 - Parallel search across all dates

For EACH date in the expanded list, fire TWO tool calls in parallel (in the same message):

1. `mcp__flights__get_cheapest_flights(origin, destination, departure_date)` - get the cheapest cash price for context
2. `mcp__flights__get_real_points_for_route(origin, destination, departure_date)` - get real award availability

**Critical: launch ALL dates in a single message as parallel tool calls.** Do not do dates one at a time.

Example for 5 dates: one message with 10 tool calls (5 flights + 5 points lookups), all in parallel.

If the date window is very wide (15+ dates), split into two batches of parallel calls.

## Step 3 - Parse and rank results

For each date, extract:
- Cheapest cash price (from flights MCP)
- Lowest award cost per loyalty program (American AAdvantage, United MileagePlus, Delta SkyMiles) - from the points table
- Note "No availability" if a program has no award seats

Rank the dates by: lowest points across any program (use the minimum across all programs that have availability).

## Step 4 - Present results

Show a summary table ranked by cheapest points:

```
| Date       | Cash Price | AA Miles | United Miles | Delta Miles | Best Value |
|------------|-----------|----------|--------------|-------------|------------|
| 2026-07-18 | $312      | 15,000   | 20,000       | —           | AA 15k ✓  |
| 2026-07-22 | $289      | —        | 17,500       | 18,000      | UA 17.5k  |
| 2026-07-25 | $341      | 22,000   | 22,000       | 20,000      | DL 20k    |
```

Then call out:
- **Best date for points:** which date and which program has the lowest award cost
- **Best cash price:** which date has the cheapest cash fare (in case they want to compare)
- Any dates with no award availability at all across all programs

## Tips for good results

- seats.aero data covers American, United, and Delta. If `SEATS_AERO_API_KEY` is not set, the tool falls back to browser scrapers which are slower and may return "No availability" more often.
- Chase Ultimate Rewards is not an award program with seats - it transfers to partners. Only show Chase if the user specifically asks about Chase points.
- If a program shows "No availability" on all dates, note it once and exclude it from the table to reduce noise.
- Round-trip: run this skill twice (outbound leg, return leg) and present both together.
- Business/first class: pass `seat="business"` or `seat="first"` to the flights MCP calls. Note that award availability in premium cabins is much more limited.

## Error handling

- If the flights MCP returns no results for a date, mark that date as "No flights" and skip the points lookup.
- If points returns all "No availability" for a date, still show it in the table with dashes so the user knows it was checked.
- If origin/destination lookup fails, ask the user to confirm the IATA codes.
