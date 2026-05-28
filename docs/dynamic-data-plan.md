# 动态真实数据方案

目标：复用 `~/github/daily_stock_analysis` 的行情、基本面、新闻搜索和大模型分析能力，把当前静态 JSON 原型升级为真实数据驱动的 A 股供应链瓶颈研究系统。

## 总体架构

```text
a-share-bottleneck-map
  前端展示
  data/*.json 静态快照
  scripts/*.py 数据刷新脚本
        |
        v
daily_stock_analysis 复用层
  DataFetcherManager
  StockTrendAnalyzer
  SearchService
  GeminiAnalyzer / Agent tools
        |
        v
真实数据源
  efinance / akshare / tushare / pytdx / baostock
  搜索服务: Bocha / Tavily / Anspire / Brave / SerpAPI / SearXNG
  LLM: LiteLLM 配置的模型
```

一阶段保持静态部署能力：刷新脚本生成 `data/quotes.json`、`data/evidence.json`、`data/companies.json` 等快照，前端只读取 JSON。二阶段再加 FastAPI + SQLite。

## 复用 DSA 能力

### 行情与基础数据

复用：

- `data_provider.DataFetcherManager`
- `get_realtime_quote(code)`
- `get_daily_data(code, days=90)`
- `get_chip_distribution(code)`
- `get_fundamental_context(code)`

输出到：

- `data/quotes.json`
- `data/technicals.json`
- `data/fundamentals.json`
- `data/chips.json`

### 技术面

复用：

- `src.stock_analyzer.StockTrendAnalyzer`

流程：

1. `DataFetcherManager.get_daily_data(code, days=90)` 获取 K 线。
2. `StockTrendAnalyzer.analyze(df, code)` 生成趋势、均线、MACD、RSI、买点评分。
3. 写入 `data/technicals.json`。

### 新闻与产业证据

复用：

- `src.search_service.SearchService`
- `src.agent.tools.search_tools.search_comprehensive_intel`

流程：

1. 对每个 `company + sector` 生成搜索 query。
2. 拉取最新新闻、风险、业绩预期、行业趋势。
3. 保存原始搜索结果。
4. 用 LLM 抽取为结构化证据。
5. 写入 `data/evidence.json`。

### LLM 分析

复用：

- `src.analyzer.GeminiAnalyzer`
- LiteLLM 配置、fallback、usage 记录逻辑

建议不要直接复用 DSA 的单股交易报告 prompt，而是新增“供应链证据抽取 prompt”：

```json
{
  "company": "沪电股份",
  "sector": "PCB与高速材料",
  "claim": "AI服务器PCB需求增长",
  "evidence_type": "订单线索",
  "sentiment": "positive",
  "confidence": 0.78,
  "risk_questions": ["是否消费电子周期反弹误判为AI订单"],
  "source_title": "...",
  "source_url": "...",
  "source_date": "..."
}
```

## 刷新脚本设计

建议新增：

```text
scripts/
  refresh_quotes.py
  refresh_technicals.py
  refresh_fundamentals.py
  refresh_evidence.py
  refresh_all.py
```

脚本通过 `PYTHONPATH=/home/snape/github/daily_stock_analysis` 导入 DSA 模块。

示例伪代码：

```python
from data_provider import DataFetcherManager

manager = DataFetcherManager()
quote = manager.get_realtime_quote("300308")
payload = quote.to_dict()
```

## 评分升级

当前评分因子保留，但由真实数据刷新：

- `bottleneckStrength`: 仍以人工产业链节点为主，后续可由证据数量和依赖数量辅助修正。
- `positionCertainty`: 由证据中“客户验证、订单、产能、产品占比”加权。
- `evidenceQuality`: 公告/年报 > 投资者纪要 > 新闻 > 社媒。
- `financialConversion`: 来自 `get_fundamental_context` 的增长、盈利、现金流。
- `valuationDiscipline`: 来自行情估值、涨幅、市值和拥挤度。
- `riskControl`: 来自风险证据、筹码、技术面和减持/融资线索。

## API 二阶段

当静态 JSON 不够用时，加轻量后端：

```text
GET /api/sectors
GET /api/companies
GET /api/quotes
GET /api/evidence
POST /api/refresh/quotes
POST /api/refresh/evidence
POST /api/research/company/{code}
```

后端可以直接复用 DSA 的 `AnalysisService` 或底层组件：

- 单股交易分析：`src.services.analysis_service.AnalysisService.analyze_stock`
- 供应链研究分析：新增本项目自己的 `BottleneckResearchService`

## 实施顺序

1. 保持当前前端 JSON 驱动。
2. 新增 `scripts/refresh_quotes.py`，用 DSA `DataFetcherManager` 更新 `quotes.json`。
3. 新增 `scripts/refresh_technicals.py`，用 DSA `StockTrendAnalyzer` 更新 `technicals.json`。
4. 新增 `scripts/refresh_evidence.py`，用 DSA `SearchService` + LLM 抽取证据。
5. 把 `companies.json.metrics` 改成由刷新脚本生成，人工只维护基础卡位和依赖关系。
6. 二阶段引入 FastAPI + SQLite。

## 风险与边界

- 股票价格必须展示数据时间和来源，避免误以为实时流。
- 搜索结果必须保留 URL 和发布日期。
- LLM 只能抽取和归类证据，不能直接生成买入结论。
- 所有 AI 生成证据默认 `needs_review=true`，人工确认后再影响高权重评分。
