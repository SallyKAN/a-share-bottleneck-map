# 动态真实数据方案

目标：使用本仓库内置的独立 provider，把静态 JSON 原型升级为真实数据驱动的 A 股供应链瓶颈研究系统。刷新链路不依赖外部 `daily_stock_analysis` checkout。

## 总体架构

```text
a-share-bottleneck-map
  前端展示
  data/*.json 静态快照
  scripts/*.py 数据刷新脚本
  skills/ai-bottleneck-stock-picker/scripts/providers
        |
        v
独立 provider
  行情: 东方财富 -> 腾讯 fallback
  财务: 东方财富财务 -> quotes.json fallback
  新闻/公告: SerpAPI/Brave(可选) -> 东方财富公告 fallback
  ETF持仓: 东方财富基金持仓 -> akshare(可选) fallback
        |
        v
data/*.json 快照
```

一阶段保持静态部署能力：刷新脚本生成 `data/quotes.json`、`data/evidence.json`、`data/companies.json`、`data/candidate_pool.json`、`data/ranking.json` 等快照，前端只读取 JSON。二阶段再考虑 API 服务和数据库。

## Provider 能力

### 行情

- `scripts.refresh_quotes`
- 优先东方财富实时行情接口。
- 东方财富失败时回退腾讯行情接口。
- 单标的失败时保留上一版 quote，并标记 `stale`。

输出到：

- `data/quotes.json`

### 新闻与证据

- `scripts.refresh_evidence`
- 配置 `AI_PICKER_SERPAPI_API_KEY` 或 `AI_PICKER_BRAVE_API_KEY` 时使用搜索 API。
- 没有搜索 API key 时使用东方财富公告 fallback。
- 证据保留 URL、发布日期、来源层级、情绪、风险标记和 `needsReview`。

输出到：

- `data/evidence.json`

### 候选池

- `scripts.refresh_candidates`
- 使用本地公司池和行业映射作为 seed。
- 可选搜索 API 增强新候选发现。
- 可选 `akshare` 概念板块增强，但不是运行前置依赖。
- 刷新返回 0 时不覆盖旧候选池。

输出到：

- `data/candidate_pool.json`
- 必要时追加 `data/companies.json`

### 财务与 ETF

这些能力主要服务 `ai-bottleneck-stock-picker --live`：

- 财务：东方财富财务接口 + `quotes.json` 估值 fallback。
- ETF：东方财富基金持仓页解析，检查持仓后再计算瓶颈纯度。

输出到：

- `.cache/ai-bottleneck-stock-picker/financials.json`
- `.cache/ai-bottleneck-stock-picker/etf_holdings.json`

## 刷新脚本

```text
scripts/
  refresh_quotes.py
  refresh_evidence.py
  refresh_candidates.py
  refresh_ranking.py
```

常用命令：

```bash
python -m scripts.refresh_quotes
python -m scripts.refresh_evidence
python -m scripts.refresh_candidates
python -m scripts.refresh_ranking
```

## 评分升级

当前评分因子保留，但由真实数据刷新：

- `bottleneckStrength`: 仍以人工产业链节点为主，后续可由证据数量和依赖数量辅助修正。
- `positionCertainty`: 由证据中“客户验证、订单、产能、产品占比”加权。
- `evidenceQuality`: 公告/年报 > 投资者纪要 > 新闻 > 社媒。
- `financialConversion`: 来自财报增长、盈利、现金流。
- `valuationDiscipline`: 来自行情估值、涨幅、市值和拥挤度。
- `riskControl`: 来自风险证据、问询函、减持、诉讼等线索。

## 风险与边界

- 股票价格必须展示数据时间和来源，避免误以为实时流。
- 搜索结果必须保留 URL 和发布日期。
- LLM 只能抽取和归类证据，不能直接生成买入结论。
- 所有非官方高影响证据默认 `needsReview=true`，人工确认后再影响高权重评分。
- Provider 失败时保留旧缓存或旧快照，不写空数据。
