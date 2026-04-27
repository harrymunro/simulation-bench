.PHONY: ingest dashboard preview deploy test clean

PYTHON ?= python3

ingest:
	$(PYTHON) harness/normalize_tokens.py
	$(PYTHON) harness/record_score.py --from-json scores/seed_scores.json

dashboard: ingest
	$(PYTHON) harness/build_dashboard.py
	cd dashboard && npm install --no-audit --no-fund
	cd dashboard && npm run build

preview: dashboard
	cd dashboard && npm run preview -- --host 127.0.0.1 --port 4321

deploy: dashboard
	flyctl deploy --remote-only

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -rf dashboard/dist dashboard/.astro
	rm -f dashboard/src/data/leaderboard.json
	rm -rf dashboard/src/content/submissions
	rm -rf dashboard/public/submissions
	rm -f dashboard/src/content/methodology/scoring.md dashboard/src/content/methodology/protocol.md
