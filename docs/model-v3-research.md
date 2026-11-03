# NBA model v3: evidence and rollout gate

The enhanced challenger uses historical pregame Elo, recent-ten win rate,
recent-ten average point differential, win percentage and rest. Its results
are compared to the four-feature baseline using chronological expanding-window
folds. The production champion remains unchanged until a validated promotion.

## Injury evidence discovery

- NBA official injury reports: https://official.nba.com/nba-injury-report-2026-27-season/
- Public historical parquet documentation: https://py.sportsdataverse.org/docs/nba/reference/loaders/stats
  (nba_stats_injury_report includes report_datetime, game_date, matchup, team,
  player status and reason; timestamps must be converted from US/Eastern).
- Open-source research on report cutoffs: https://github.com/Professor-Pete/2024-2025-injury_analysis

These are **candidate sources**, not proof that the current repo contains
usable historical injuries. Before ingestion, verify actual asset availability,
license/redistribution terms, complete season coverage, ESPN-to-NBA game ID
and team ID mapping, timezone handling, and official report timestamps.
Only use the last published snapshot **before actual tipoff**, never a
postgame final status. Do not treat unreported players as confirmed healthy.

## Injury-aware promotion requirements

1. Archive real pregame reports with source URLs and timestamps.
2. Build per-game availability features and report coverage, including
   separate missing/not-submitted flags.
3. Estimate player impact only using information available before tipoff.
4. Evaluate same folds against the baseline, reporting Brier, log loss,
   calibration, confidence intervals and coverage.
5. Promote only on verified out-of-sample improvement. If the injury
   archive is incomplete, continue displaying unknown and baseline odds.

No synthetic injuries, fake gains or claimed injury-adjusted probabilities.
