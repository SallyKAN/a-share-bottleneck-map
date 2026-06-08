# Data Contracts

Live data is cached separately from the committed snapshot. Do not write live data back to `data/*.json` by default.

Recommended cache directory:

```text
.cache/ai-bottleneck-stock-picker/
```

## live_news.json

```json
{
  "source": "Anspire/SearchService",
  "updatedAt": "2026-06-08T10:00:00+08:00",
  "items": [
    {
      "symbol": "300308",
      "name": "中际旭创",
      "title": "...",
      "url": "...",
      "source": "...",
      "publishedAt": "...",
      "summary": "...",
      "signalType": "order|capacity|earnings|risk|industry|customer|price|policy",
      "sentiment": "positive|neutral|negative",
      "confidence": 0.72
    }
  ]
}
```

Rules:

```text
Official filings > financial media > research notes > generic search.
Search failure must not erase previous live cache.
Risk news must be preserved even when positive news exists.
```

## financials.json

```json
{
  "source": "financial-provider",
  "updatedAt": "2026-06-08T10:00:00+08:00",
  "items": [
    {
      "symbol": "300308",
      "period": "2026Q1",
      "revenueYoY": 0.0,
      "netProfitYoY": 0.0,
      "grossMargin": 0.0,
      "operatingCashFlow": 0.0,
      "inventory": 0.0,
      "contractLiabilities": 0.0,
      "capex": 0.0,
      "rdExpense": 0.0,
      "peRatio": 0.0,
      "pbRatio": 0.0,
      "marketCap": 0.0,
      "financialConfirmation": 0.0
    }
  ]
}
```

Rules:

```text
Revenue/profit acceleration upgrades conviction.
Margin compression, weak cash flow, or inventory stress downgrades conviction.
Financials must be treated as confirmation, not initial theme discovery.
```

## etf_holdings.json

```json
{
  "source": "etf-provider",
  "updatedAt": "2026-06-08T10:00:00+08:00",
  "items": [
    {
      "etfCode": "512480",
      "etfName": "半导体ETF",
      "theme": "semiconductor",
      "holdings": [
        {"symbol": "300308", "name": "中际旭创", "weight": 0.0}
      ],
      "top10Weight": 0.0,
      "matchedCompanies": ["300308"],
      "bottleneckExposure": {"optical": 0.0, "pcb": 0.0},
      "purityScore": 0.0
    }
  ]
}
```

Rules:

```text
Do not recommend ETFs by name only.
Always inspect holdings and bottleneck exposure.
ETF alternatives reduce single-stock risk but dilute bottleneck purity.
```

## technicals.json

```json
{
  "source": "quote-provider",
  "updatedAt": "2026-06-08T10:00:00+08:00",
  "items": [
    {
      "symbol": "300308",
      "change20d": 0.0,
      "change60d": 0.0,
      "turnoverRate": 0.0,
      "amount": 0.0,
      "volumeRatio": 0.0,
      "newHigh": false,
      "drawdown": 0.0,
      "relativeStrength": 0.0,
      "volatility": 0.0,
      "trendState": "early|momentum|crowded|broken"
    }
  ]
}
```

Rules:

```text
Technicals judge timing and crowding only.
Never let technicals override a weak bottleneck/financial thesis.
High conviction + bad timing is a valid output.
```

## pick.py --live Output

When `pick.py` runs with `--live`, company results keep the deterministic `stockPickerScore` and add:

```json
{
  "live": {
    "news": {"count": 0, "positiveCount": 0, "riskCount": 0, "latest": []},
    "financials": {"status": "ok|missing", "financialConfirmation": 50.0},
    "technicals": {"trendState": "early|momentum|crowded|broken|unknown", "tradingTimingScore": 50.0}
  },
  "liveScores": {
    "fundamentalBottleneckScore": 0.0,
    "tradingTimingScore": 0.0,
    "compositeScore": 0.0,
    "finalLabel": "High Conviction / Good Timing"
  }
}
```

Rules:

```text
Keep stockPickerScore deterministic and explain live fields as current-data context.
fundamentalBottleneckScore is thesis strength.
tradingTimingScore is timing/crowding only.
Missing live cache means limited data, not a bearish signal.
```
