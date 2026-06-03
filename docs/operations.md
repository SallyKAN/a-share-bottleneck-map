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
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_quotes
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_evidence
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_candidates
node scripts/validate-data.mjs
npm run build
```

Do not expose refresh endpoints publicly until they have authentication, rate limits, and job logs.

## GitHub Actions

The repository includes `.github/workflows/refresh-data.yml`.

Default schedule:

- Runs at `08:30 UTC`, every day.
- This is `16:30 Asia/Shanghai`, after the A-share close.
- Scheduled runs refresh quotes and rebuild ranking.
- Manual runs can choose `refresh_scope=all` to also refresh candidates and evidence.

Required repository variable:

```text
DSA_REPOSITORY
```

Set it to the GitHub repository that contains `daily_stock_analysis`, for example:

```text
SallyKAN/daily_stock_analysis
```

If that repository is private, add a repository secret with read access:

```text
DSA_REPO_TOKEN
```

Optional search provider secrets for `refresh_scope=all`:

```text
BOCHA_API_KEY
TAVILY_API_KEY
BRAVE_API_KEY
SERPAPI_API_KEY
MINIMAX_API_KEY
SEARXNG_URL
```

Vercel will redeploy automatically after the action commits refreshed `data/*.json` to `main`.

## Future Modules

- `frontend`: public Vite site and read-only visualizations.
- `data`: JSON snapshots now; database or object storage later.
- `jobs`: quote, evidence, candidate, and ranking refresh tasks.
- `admin`: authenticated refresh, review, and data-quality tools.
- `monitoring`: build checks, refresh logs, uptime, and client error tracking.
