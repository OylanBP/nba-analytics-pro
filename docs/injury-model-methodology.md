# Injury-aware NBA prediction: evidence requirements

The production baseline is a logistic regression using pregame win percentage and rest.
**Injury reports are NOT yet model inputs.** This branch adds strict injury archive
validation and rolling out-of-sample backtests, not a claimed injury-aware model.

## Historical injury evidence

A past injury report is usable only when it has a reliable source, publication or
capture timestamp, player identity, team identity, and official availability status
known **before that game's tipoff**. Current injury pages cannot be used to reconstruct
past game statuses. Missing reports must be marked unknown, not interpreted as healthy.

An optional archive at `data/injuries/snapshots.json` is a JSON array with entries:
```json
[
  {
    "observed_utc": "2026-10-20T15:00:00Z",
    "source_url": "https://example.org/actual-original-report",
    "players": [
      {"team_id": "1", "name": "Actual player name", "status": "Out"}
    ]
  }
]
```
This is a schema illustration, **not actual evidence**. Do not commit invented
entries. The supported statuses are Out, Doubtful, Questionable, Probable, Available.
Snapshots older than 48 hours are treated as unknown.

## Before using injuries to adjust probabilities

1. Identify a lawful, stable, timestamped historical injury-report archive and
   validate source coverage and team/player IDs.
2. Link archived reports to each game's actual pre-tipoff cutoff; track unknown
   coverage separately from confirmed availability.
3. Add injury-availability features using only archived pre-tipoff information.
   Player impact requires pregame-known minutes/role estimates, not final box scores.
4. Compare injury-aware challenger against the same rolling chronological splits,
   baseline logistic regression, Brier score, log loss and calibration.
5. Publish a challenger only after objective out-of-sample improvement and
   sufficient injury coverage. Otherwise retain baseline and display unknown.

**No injury effect or performance improvement is asserted by this change.**
