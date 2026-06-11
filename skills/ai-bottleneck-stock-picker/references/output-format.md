# Output Formats

## Default Research Report

Use this as the default format for broad stock-picking requests such as
"帮我选股", "给我一个观察池", or "验证这些标的". The answer should read like
a structured research memo, not a loose list of names.

```text
# AI 基础设施瓶颈 A 股调研报告

## 0. 报告边界
- 数据口径：本地快照 / live cache / 手动验证；写清楚截至日期和生成日期。
- 数据健康：sectors、companies、candidates、evidence、quotes、rankingRows 数量。
- 重要限制：是否实时盘中；是否刷新外部数据；缺失的 live/news/financial/ETF holdings 数据。
- 合规提示：研究观察池，不是投资建议；不输出买卖指令或仓位建议。

## 1. 一页结论
- 主结论：最值得跟踪的瓶颈层，例如 AI服务器、先进封装、光通信/CPO、PCB/高速材料、电力。
- 当前市场状态：低估挖掘 / 高景气高预期 / 拥挤交易 / 等财报确认。
- 优先级排序：
  1. 核心锚点：Name code - 一句话理由。
  2. 重点观察：Name code - 一句话理由。
  3. 等待/投机：Name code - 一句话理由。
- 本轮不纳入核心的原因：估值、证据不足、AI纯度不足、风险事件、流动性不足等。

## 2. 瓶颈层判断
| 瓶颈层 | 供给约束 | A股映射 | 当前结论 | 主要风险 |
| --- | --- | --- | --- | --- |
| optical | ... | ... | ... | ... |
| package | ... | ... | ... | ... |
| pcb | ... | ... | ... | ... |

## 3. 筛选结果总表
| 分组 | 股票 | 代码 | 评分 | 瓶颈层 | 快照估值/交易 | 核心判断 |
| --- | --- | --- | ---: | --- | --- | --- |
| core_pick | ... | ... | ... | ... | PE/PB/涨跌幅 | ... |
| watchlist | ... | ... | ... | ... | PE/PB/涨跌幅 | ... |
| speculative_or_wait | ... | ... | ... | ... | PE/PB/涨跌幅 | ... |

## 4. 核心标的拆解
For each core/watchlist name:

### Name code
- 分组：core_pick / watchlist / speculative_or_wait / speculative_candidate
- 评分：stockPickerScore；必要时列出 bottleneckLeverage、evidenceMomentum、valuationPenalty、riskPenalty。
- 瓶颈逻辑：公司处在哪个物理瓶颈层，为什么可能被重估。
- 证据摘要：最新证据、财报/公告/互动/新闻的可信度，注明日期和来源类型。
- 财务验证：营收、净利、扣非、毛利率、现金流、订单/产能，缺什么就明确写缺口。
- 估值/交易：PE、PB、涨跌幅、成交额、换手率；判断是低估、正常、还是拥挤。
- 反证/风险：客户集中、技术替代、减持/解禁、海外链波动、订单不可持续、AI纯度不足。
- 下一步验证：列 2-4 个可执行问题。

## 5. 验证矩阵
| 股票 | 官方财报/公告 | 业务纯度 | 订单/产能 | 盈利质量 | 估值拥挤 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| ... | 已验证/部分/缺失 | 高/中/低 | ... | ... | ... | ... |

## 6. 候选池与剔除理由
- 候选池线索只作为 discovery lead，不当作推荐。
- 列出 3-8 个被降级或等待的标的，以及具体原因：
  - 证据只是关键词匹配
  - 暂无当前证据
  - 财务未兑现
  - 估值已过高
  - 风险证据或拥挤交易

## 7. ETF 替代
- 只有检查过 ETF holdings 后才写。
- 若未检查，明确写：本轮未纳入 ETF 替代，因为未验证持仓纯度。

## 8. 跟踪清单
- 未来 1-4 周要看的数据：公告、季报、月度营收、机构调研、订单、产能、海外链指标。
- 触发上调的条件：财务确认、订单确认、毛利率改善、风险释放。
- 触发降级的条件：证据证伪、估值进一步拥挤、现金流恶化、客户/政策/海外链风险。
```

Length guidance:

- For normal chat answers, keep the full report concise: 5-8 names, 1-3 lines per table cell.
- For "详细报告", include all sections.
- For "只要结论", include sections 0, 1, 3, and the disclaimer.

## Top Pick Answer

```text
Conclusion:
The strongest current AI bottleneck opportunities are concentrated in [layers].

Core Picks:
1. Name code
   - Bottleneck:
   - Why it could rerate:
   - Evidence:
   - Quote/timing:
   - Risks:
   - Next verification:

Watchlist:
...

Speculative Candidates:
...

ETF Alternative:
Only include ETFs after checking holdings.

Important:
This is a research watchlist, not financial advice.
```

## Company Answer

```text
Name code
Classification:
Stock Picker Score:
Bottleneck thesis:
Evidence:
Quote/valuation signals:
Risks:
What to verify next:
```

## Verification Answer

Use this format when the user asks to validate, verify, or fact-check a previous
watchlist. Prefer official filings, exchange disclosures, company investor
relations, and reputable financial media. Separate "verified", "partially
verified", and "not verified".

```text
# 候选股验证报告

## 0. 验证边界
- 待验证名单：
- 使用来源：本地快照 / 官方公告 / 交易所披露 / 公司互动 / 权威财经媒体。
- 日期口径：
- 限制：

## 1. 验证结论
| 股票 | 原始假设 | 验证状态 | 关键证据 | 调整后分组 |
| --- | --- | --- | --- | --- |
| ... | ... | 通过/部分/未通过 | ... | ... |

## 2. 单票验证
### Name code
- 原始假设：
- 已验证事实：
- 未验证/冲突信息：
- 财务质量：
- 风险事件：
- 调整判断：
- 下一步证据：

## 3. 调整后优先级
1. 核心锚点：
2. 重点观察：
3. 等待/投机：
4. 剔除/暂不跟踪：

## 4. 后续跟踪
- 上调条件：
- 降级条件：
- 下次刷新建议：
```

## Sector Answer

```text
Sector:
Bottleneck:
Why this layer matters:
Core mapped companies:
Candidate-pool leads:
Risks/反证:
Next data to check:
```

## ETF Answer

```text
ETF name/code:
Covered bottleneck:
Top holdings:
Matched companies:
Purity score:
What single-stock risk it reduces:
What exposure it dilutes:
```

Never say "buy", "sell", "must buy", or "guaranteed". Use research language:

```text
worth tracking
watchlist candidate
needs confirmation
rerating hypothesis
timing risk
crowded trade
```
