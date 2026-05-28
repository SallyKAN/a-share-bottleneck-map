export type Lang = 'zh' | 'en';

const zh = {
  home: '模块',
  ranking: '隐形赢家',
  evidence: '证据流',
  title: '中国AI供应链,谁卡住下一轮扩张',
  lead: '从 AI 数据中心扩张倒推底层瓶颈，再映射到 A 股公司、证据、行情和依赖路径。',
  note: 'A股 · 真实行情快照 · 证据需复核 · 非投资建议',
  hiddenWinner: '隐形赢家榜',
  sectors: '板块',
  appearances: '出现',
  refreshQuotes: '刷新行情',
  refreshEvidence: '刷新证据',
  refreshCandidates: '刷新候选池',
  refreshRanking: '刷新排名',
  readOnlySnapshot: '公开站点只读快照',
  localRefreshHint: '数据刷新在本地服务或后台任务中执行',
};

const en: typeof zh = {
  home: 'Modules',
  ranking: 'Hidden Winners',
  evidence: 'Evidence',
  title: 'China AI supply chain: where does expansion bottleneck next?',
  lead: 'Reverse-map AI data-center expansion into physical bottlenecks, then into A-share companies, evidence, quotes, and dependency paths.',
  note: 'A-share · quote snapshots · evidence needs review · not investment advice',
  hiddenWinner: 'Hidden Winner Ranking',
  sectors: 'sectors',
  appearances: 'appearances',
  refreshQuotes: 'Refresh Quotes',
  refreshEvidence: 'Refresh Evidence',
  refreshCandidates: 'Refresh Candidates',
  refreshRanking: 'Refresh Ranking',
  readOnlySnapshot: 'Public read-only snapshot',
  localRefreshHint: 'Data refresh runs locally or in scheduled jobs',
};

export function dict(lang: Lang) {
  return lang === 'en' ? en : zh;
}
