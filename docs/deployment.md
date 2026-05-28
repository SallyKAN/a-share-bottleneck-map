# Deployment

This project deploys as a read-only Vite site on Vercel. The public site serves the latest committed JSON snapshots from `data/*.json`.

## Vercel

1. Push this project to a GitHub repository.
2. Import the repository in Vercel.
3. Use the default Vite settings:
   - Build command: `npm run build`
   - Output directory: `dist`
4. Do not set `VITE_ENABLE_REFRESH=true` for the public deployment.
5. Use the free Vercel project domain, for example `a-share-bottleneck-map.vercel.app`.

Vercel project domains are free and use the `*.vercel.app` suffix. The exact subdomain depends on availability and the project name.

## Build Behavior

`npm run build` compiles the React app and copies `data/*.json` into `dist/data/`, so the deployed site can load:

- `/data/sectors.json`
- `/data/companies.json`
- `/data/candidate_pool.json`
- `/data/evidence.json`
- `/data/quotes.json`
- `/data/ranking.json`
- `/data/scoring.json`

## Refresh Mode

Refresh APIs are local-only by default:

- Enabled on `localhost` and `127.0.0.1`
- Disabled on public domains

For a private deployment that has compatible backend APIs, set:

```text
VITE_ENABLE_REFRESH=true
```

For a local read-only preview, set:

```text
VITE_ENABLE_REFRESH=false
```
