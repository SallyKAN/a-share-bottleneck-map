# Scoring

## Snapshot Score

Use `scripts/pick.py` output as the source of truth. The score is a research-ranking score, not a trading signal.

Components:

```text
bottleneck leverage        25%
supply constraint          20%
A-share purity             15%
evidence momentum          15%
market underpricing        10%
liquidity/tradability       5%
ranking snapshot           10%
risk penalty              subtractive
valuation penalty         subtractive
```

Interpretation:

```text
core_pick:
  Strong bottleneck exposure, usable evidence, OK quote status, and high score.

watchlist:
  Plausible thesis but needs better evidence, financial confirmation, or timing.

speculative_or_wait:
  Weak evidence, high valuation/crowding risk, stale data, or low score.

speculative_candidate:
  Candidate-pool lead that needs official/financial verification before promotion.
```

## Live Score

The live score must separate conviction from timing:

```text
Fundamental Bottleneck Score:
  bottleneck leverage
  supply constraint
  A-share purity
  evidence momentum
  financial confirmation
  risk penalty

Trading Timing Score:
  relative strength
  volume confirmation
  trend quality
  volatility risk
  crowdedness penalty
```

Final labels:

```text
High Conviction / Good Timing
High Conviction / Bad Timing
Low Conviction / Hot Theme
Speculative Early Signal
ETF Alternative
Avoid / Wait
```
