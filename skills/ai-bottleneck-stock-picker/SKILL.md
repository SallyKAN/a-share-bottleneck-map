---
name: ai-bottleneck-stock-picker
description: Use when researching or selecting A-share stocks, ETFs, or listed companies exposed to AI infrastructure expansion bottlenecks. Finds possible rerating candidates by analyzing bottleneck leverage, supply constraints, A-share purity, evidence/news, ranking snapshots, candidate pools, valuation discipline, risk signals, ETF alternatives, and live data readiness. For research/watchlist generation only, not financial advice.
---

# AI Bottleneck Stock Picker

## Purpose

Use this skill to generate research-grade A-share/ETF watchlists from AI infrastructure bottlenecks.

Core thesis:

```text
AI capex growth creates physical supply-chain bottlenecks.
The best opportunities often appear in second- and third-layer suppliers before the market fully prices the constraint.
```

This is a research skill. Do not output buy/sell instructions or position sizing.

## Default Data

Repository root:

```text
/home/snape/github/a-share-bottleneck-map
```

Snapshot files:

```text
data/sectors.json
data/companies.json
data/candidate_pool.json
data/evidence.json
data/quotes.json
data/ranking.json
data/scoring.json
```

## Required Workflow

Before answering stock-picking questions, run the deterministic picker:

```bash
python skills/ai-bottleneck-stock-picker/scripts/pick.py health
python skills/ai-bottleneck-stock-picker/scripts/pick.py top --limit 10
python skills/ai-bottleneck-stock-picker/scripts/pick.py sector optical --limit 10
python skills/ai-bottleneck-stock-picker/scripts/pick.py company 300308
python skills/ai-bottleneck-stock-picker/scripts/pick.py candidates --sector pcb --limit 20
python skills/ai-bottleneck-stock-picker/scripts/pick.py evidence --company 300308 --limit 10
```

Use `--repo-root` only when the repository is not at the default path.

## Strategy

1. Identify the bottleneck layer: optical, package, pcb, power, memory, or cross-bottleneck.
2. Map promoted companies and candidate-pool names.
3. Score names using bottleneck leverage, supply constraint, A-share purity, evidence momentum, underpricing, liquidity, valuation risk, and risk evidence.
4. Split outputs into `core_pick`, `watchlist`, and `speculative_or_wait`.
5. Give disconfirming evidence and next verification questions.
6. Add ETF alternatives only after checking ETF holdings; do not infer from ETF name alone.

Read `references/scoring.md` when explaining scores.
Read `references/bottleneck-thesis.md` when explaining the AI bottleneck logic.
Read `references/data-contracts.md` when implementing V2 live news, financials, ETF holdings, or technicals.
Read `references/output-format.md` for answer templates.

## Guardrails

- Do not recommend based only on an AI concept label.
- Do not treat candidate-pool matches as recommendations; they are discovery leads.
- Do not treat empty evidence/candidate data as absence of opportunity. Check refresh health first.
- Warn if quotes are stale/unavailable or evidence is old.
- Technicals may judge timing and crowding, but cannot replace bottleneck and financial logic.
- Financial confirmation can upgrade or downgrade a thesis; hot news alone is insufficient.
- State that outputs are research hypotheses, not financial advice.

## Refresh Rules

Default behavior is read-only.

Only refresh data or trigger GitHub Actions when the user explicitly asks. If refreshing:

```bash
gh workflow run refresh-data.yml --ref main
gh run list --workflow refresh-data.yml --limit 3
```

If a refresh returns zero evidence or zero candidates, do not overwrite or trust it. Investigate provider health first.
