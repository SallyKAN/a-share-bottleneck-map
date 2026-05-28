# 数据模型

一阶段先用静态 JSON，把页面从写死数据升级为数据驱动。后续接后端时，这些 JSON 字段可以直接映射为数据库表。

## `data/sectors.json`

产业链节点。

- `id`: 稳定节点 ID。
- `title`: 页面展示名称。
- `subtitle`: 节点摘要。
- `thesis`: 节点投资研究假设。
- `bottlenecks`: 可能卡住的物理环节。
- `checks`: 节点级反证问题。

## `data/companies.json`

公司池。

- `id`: 稳定公司 ID。
- `name`: 公司名称。
- `code`: 股票代码。
- `sectorIds`: 关联产业链节点。
- `role`: 公司在瓶颈中的角色。
- `metrics`: 评分原始因子，范围 0-100。

## `data/evidence.json`

证据流。

- `companyId`: 关联公司。
- `sectorId`: 关联产业链节点。
- `date`: 证据日期。
- `type`: 证据类型。
- `sentiment`: `positive` / `neutral` / `negative`。
- `confidence`: 置信度，范围 0-1。
- `title`: 证据标题。
- `summary`: 证据摘要。
- `source`: 来源。当前为示例数据，后续应替换为公告、新闻、财报或调研来源。

## `data/scoring.json`

观察榜评分规则。

当前总分计算：

```text
总分 = 瓶颈强度 * 25%
     + 卡位确定性 * 20%
     + 证据质量 * 20%
     + 财务兑现 * 15%
     + 估值纪律 * 10%
     + 风险控制 * 10%
```
