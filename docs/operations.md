# Operations

## Production Model

The public website is a static read-only research snapshot. Data refreshes should run outside the browser and outside public unauthenticated APIs.

Recommended first-stage flow:

1. Run refresh scripts locally or from GitHub Actions.
2. Validate generated JSON.
3. Build the site.
4. Deploy through Vercel.

## Routine Checks

Before deployment:

```bash
node scripts/validate-data.mjs
npm run build
```

For the local full server:

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python server.py
```

Then open:

```text
http://127.0.0.1:5173/
```

## Scheduled Refresh

For low-cost operations, use GitHub Actions or a small VPS to run:

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python scripts/refresh_quotes.py
/home/snape/github/daily_stock_analysis/.venv/bin/python scripts/refresh_evidence.py
/home/snape/github/daily_stock_analysis/.venv/bin/python scripts/refresh_candidates.py
node scripts/validate-data.mjs
npm run build
```

Do not expose refresh endpoints publicly until they have authentication, rate limits, and job logs.

## Future Modules

- `frontend`: public Vite site and read-only visualizations.
- `data`: JSON snapshots now; database or object storage later.
- `jobs`: quote, evidence, candidate, and ranking refresh tasks.
- `admin`: authenticated refresh, review, and data-quality tools.
- `monitoring`: build checks, refresh logs, uptime, and client error tracking.
