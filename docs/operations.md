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
python server.py
```

Then open:

```text
http://127.0.0.1:5173/
```

## Scheduled Refresh

For low-cost operations, use GitHub Actions or a small VPS to run:

```bash
python -m scripts.refresh_quotes
python -m scripts.refresh_evidence
python -m scripts.refresh_candidates
node scripts/validate-data.mjs
npm run build
```

Do not expose refresh endpoints publicly until they have authentication, rate limits, and job logs.

## GitHub Actions

The repository includes `.github/workflows/refresh-data.yml`.

Default schedule:

- Runs at `08:30 UTC`, every day.
- This is `16:30 Asia/Shanghai`, after the A-share close.
- Scheduled runs refresh candidates, quotes, evidence, and ranking.
- Manual runs refresh the same full snapshot set.

Optional search provider secrets for richer evidence refresh:

```text
AI_PICKER_SERPAPI_API_KEY
AI_PICKER_BRAVE_API_KEY
```

Without search API keys, the refresh scripts use independent built-in fallbacks such as 东方财富公告, 东方财富财务, 腾讯行情, and local snapshots. The refresh pipeline no longer requires a separate `daily_stock_analysis` repository.

Vercel will redeploy automatically after the action commits refreshed `data/*.json` to `main`.

## Future Modules

- `frontend`: public Vite site and read-only visualizations.
- `data`: JSON snapshots now; database or object storage later.
- `jobs`: quote, evidence, candidate, and ranking refresh tasks.
- `admin`: authenticated refresh, review, and data-quality tools.
- `monitoring`: build checks, refresh logs, uptime, and client error tracking.
