# A股AI扩张瓶颈地图

一个参考 `decon-2030` 思路的 A 股版本动态研究系统原型：从 AI 数据中心扩张倒推产业链二三层瓶颈，并映射到可跟踪的 A 股公司、证据和评分。

## 使用

页面通过 Vite React 构建，运行时加载 `data/*.json`，并通过本地 API 点击刷新候选池、行情、证据流和排名。先安装并构建前端：

```bash
npm install
npm run build
```

然后使用项目服务启动：

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python server.py
```

然后访问：

```text
http://127.0.0.1:5173/
```

## 部署

公开站点按只读快照部署到 Vercel：`npm run build` 会把 `data/*.json` 复制到 `dist/data/`，公网默认不展示刷新按钮，避免暴露本地刷新脚本。

详见：

- `docs/deployment.md`
- `docs/operations.md`

GitHub Actions 定时刷新见 `.github/workflows/refresh-data.yml`。默认每天 16:30（Asia/Shanghai）刷新行情和排名；手动运行时选择 `refresh_scope=all` 可刷新候选池和证据流。

## 数据文件

- `data/sectors.json`: 产业链节点。
- `data/companies.json`: 已晋级公司池和评分因子。
- `data/candidate_pool.json`: 自动发现但仍需审核的候选公司池。
- `data/evidence.json`: 证据流，包含情绪、置信度、来源层级和去重键。
- `data/scoring.json`: 观察榜评分权重。
- `data/quotes.json`: 行情快照，由刷新脚本生成。
- `data/ranking.json`: 隐形赢家榜快照，包含 `sectorCount` 和 `appearances`。

维护这些 JSON 后刷新页面，观察榜会自动重新计算。

## 刷新行情

页面上点击 `刷新行情` 会请求：

```text
POST /api/refresh-quotes
```

本地服务会调用 `scripts/refresh_quotes.py` 的刷新逻辑，复用 `/home/snape/github/daily_stock_analysis` 的 `DataFetcherManager` 获取真实行情并写入 `data/quotes.json`。

也可以在命令行单次刷新：

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_quotes
```

旧的循环模式仍可用，但当前推荐通过页面按钮触发：

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_quotes --loop --interval-hours 12
```

## 刷新候选池与排名

页面上点击 `刷新候选池` 会请求：

```text
POST /api/refresh-candidates
```

本地服务会复用 DSA 的 `stocks.index.json` 和 `SearchService`，按产业链关键词发现 A 股候选公司，写入 `data/candidate_pool.json`，并把达到规则阈值的候选晋级到 `data/companies.json`。当前晋级规则是规则先行，不使用 LLM 主导。

页面上点击 `刷新排名` 会请求：

```text
POST /api/refresh-ranking
```

排名由 `companies + sectors + evidence + quotes` 生成，核心字段：

- `sectorCount`: 依赖的去重板块数。
- `appearances`: 命中的依赖路径/节点次数。
- `evidenceScore`: 按来源层级和置信度聚合的证据分。

## 刷新证据流

页面上点击 `刷新证据流` 会请求：

```text
POST /api/refresh-evidence
```

本地服务会调用 `scripts/refresh_evidence.py`，复用 `/home/snape/github/daily_stock_analysis` 的 `SearchService` 搜索公告、新闻、研报、业绩和风险线索，并把真实搜索结果写入 `data/evidence.json`。如果未配置 Bocha、Tavily、Brave、SerpAPI、MiniMax 或 SearXNG，接口会直接返回错误，不生成假证据。

默认会覆盖 `data/companies.json` 中的全部公司；命令行调试时可以用 `--max-companies` 临时抽样，页面按钮不做公司数量限制。

也可以在命令行单次刷新：

```bash
/home/snape/github/daily_stock_analysis/.venv/bin/python -m scripts.refresh_evidence
```

## 校验

```bash
npm run build
node --check app.js
node scripts/validate-data.mjs
/home/snape/github/daily_stock_analysis/.venv/bin/python -c 'import ast, pathlib; files=["server.py","scripts/dsa_bridge.py","scripts/json_utils.py","scripts/refresh_quotes.py","scripts/refresh_evidence.py","scripts/refresh_candidates.py","scripts/refresh_ranking.py"]; [compile(ast.parse(pathlib.Path(f).read_text()), f, "exec") for f in files]; print("python syntax ok")'
```

## 内容边界

- 这是研究框架和产品原型，不构成投资建议。
- 标的列表用于展示“如何拆供应链”，不是买入评级。
- 后续可接入公告、年报、研报摘要、行情和估值数据，把静态观察榜升级为动态研究系统。

## 文档

- `docs/data-model.md`: 一阶段数据模型。
- `docs/product-plan.md`: 一阶段能力和二阶段建议。
