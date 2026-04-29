# Simulation Bench scores database

SQLite database tracking per-reviewer scores against the 100-point rubric in
[`SCORING_GUIDE.md`](../SCORING_GUIDE.md).

## Files

- `scores.db` — SQLite database (gitignored; rebuild from `seed_scores.json`).
- `seed_scores.json` — checked-in source of truth for scores; bulk-loaded
  via `harness/record_score.py --from-json scores/seed_scores.json`.

## Schema

Two tables and one view:

- `submissions` — one row per submission folder, decoded into
  `run_date / benchmark_id / harness / model / run_tag`.
- `scores` — one row per (submission × reviewer × review_date), holding the
  seven category scores, the derived total, and automated-check context.
- `leaderboard` — view sorted by `total_score` desc.

See `harness/scores_db.py` for the full DDL.

## Common commands

```bash
# Rebuild the DB from the JSON seed
python harness/record_score.py --from-json scores/seed_scores.json

# Add a single new score
python harness/record_score.py \
  --submission <folder-name> \
  --reviewer "alice" --review-date 2026-05-01 \
  --conceptual 18 --data 14 --sim 18 --exp 14 --results 14 --code 9 --trace 5 \
  --automated-passed 57 --automated-total 57 --behavioural-passed 6 \
  --recommendation "Strong submission"

# Show the scoreboard
python harness/scoreboard.py

# Per-category detail
python harness/scoreboard.py --detailed

# Filter to one benchmark
python harness/scoreboard.py --benchmark 001_synthetic_mine_throughput
```

## Workflow

1. Reviewer fills in `submissions/<folder>/results/reviewer_form.md`.
2. Append the structured score to `scores/seed_scores.json`.
3. Run `python harness/record_score.py --from-json scores/seed_scores.json` to refresh `scores.db`.
4. Run `python harness/scoreboard.py` to view the updated leaderboard.

The JSON seed is the source of truth; `scores.db` is a derived, queryable
projection of it.
