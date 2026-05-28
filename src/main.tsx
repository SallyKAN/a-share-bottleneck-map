import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Moon, RefreshCw, Sun } from 'lucide-react';
import { loadAppData, postRefresh } from './data';
import { dict, type Lang } from './i18n';
import { formatMarketCap, formatPercent, formatPrice, quoteClass } from './format';
import type { AppData, Company, DependencyNode, Evidence, Quote, RankingRow, Sector } from './types';
import './styles.css';

type Theme = 'dark' | 'light';

const refreshMode = import.meta.env.VITE_ENABLE_REFRESH;

function canUseRefreshApi() {
  if (refreshMode === 'true') return true;
  if (refreshMode === 'false') return false;
  return ['localhost', '127.0.0.1'].includes(window.location.hostname);
}

function useHashRoute() {
  const [route, setRoute] = useState(() => window.location.pathname + window.location.search);
  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname + window.location.search);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  const navigate = (path: string) => {
    window.history.pushState({}, '', path);
    setRoute(path);
  };
  return { route, navigate };
}

function App() {
  const [data, setData] = useState<AppData | null>(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem('lang') === 'en' ? 'en' : 'zh'));
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('theme') === 'light' ? 'light' : 'dark'));
  const { route, navigate } = useHashRoute();
  const t = dict(lang);
  const refreshEnabled = canUseRefreshApi();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('lang', lang);
  }, [lang]);

  const reload = async () => {
    setData(await loadAppData());
  };

  useEffect(() => {
    reload().catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const refresh = async (path: string, label: string) => {
    setStatus(`${label}...`);
    try {
      await postRefresh(path);
      await reload();
      setStatus(`${label}完成`);
    } catch (err) {
      setStatus(`${label}失败: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  if (error) return <Shell t={t} navigate={navigate} lang={lang} setLang={setLang} theme={theme} setTheme={setTheme}><div className="load-error">{error}</div></Shell>;
  if (!data) return <Shell t={t} navigate={navigate} lang={lang} setLang={setLang} theme={theme} setTheme={setTheme}><div className="load-error">Loading...</div></Shell>;

  const search = new URLSearchParams(route.split('?')[1] || '');
  const sectorId = search.get('s') || data.sectors[0]?.id || '';
  const page = route.startsWith('/tree') ? 'tree' : route.startsWith('/ranking') ? 'ranking' : 'home';

  return (
    <Shell t={t} navigate={navigate} lang={lang} setLang={setLang} theme={theme} setTheme={setTheme}>
      <section className="hero">
        <h1>{t.title}</h1>
        <p>{t.lead}</p>
        <p className="note">{t.note}</p>
        {refreshEnabled ? (
          <div className="hero-actions">
            <ActionButton label={t.refreshCandidates} onClick={() => refresh('/api/refresh-candidates', t.refreshCandidates)} />
            <ActionButton label={t.refreshQuotes} onClick={() => refresh('/api/refresh-quotes', t.refreshQuotes)} />
            <ActionButton label={t.refreshEvidence} onClick={() => refresh('/api/refresh-evidence', t.refreshEvidence)} />
            <ActionButton label={t.refreshRanking} onClick={() => refresh('/api/refresh-ranking', t.refreshRanking)} />
          </div>
        ) : (
          <div className="snapshot-banner">
            <span>{t.readOnlySnapshot}</span>
            <small>{t.localRefreshHint}</small>
          </div>
        )}
        <p className="meta-line">{status || `行情 ${data.quotes.updatedAt || '--'} · 排名 ${data.ranking.asOf || '--'}`}</p>
      </section>
      {page === 'home' && <HomePage data={data} navigate={navigate} />}
      {page === 'tree' && <TreePage data={data} sectorId={sectorId} />}
      {page === 'ranking' && <RankingPage data={data} t={t} />}
    </Shell>
  );
}

function Shell({
  children,
  t,
  navigate,
  lang,
  setLang,
  theme,
  setTheme,
}: {
  children: React.ReactNode;
  t: ReturnType<typeof dict>;
  navigate: (path: string) => void;
  lang: Lang;
  setLang: (lang: Lang) => void;
  theme: Theme;
  setTheme: (theme: Theme) => void;
}) {
  return (
    <>
      <header className="topbar">
        <button className="brand as-link" onClick={() => navigate('/')}>
          <span className="brand-mark">⌗</span>
          <span>A股AI扩张瓶颈地图</span>
        </button>
        <nav className="topnav">
          <button onClick={() => navigate('/')}>{t.home}</button>
          <button onClick={() => navigate('/ranking')}>{t.ranking}</button>
          <button onClick={() => document.querySelector('#evidence')?.scrollIntoView({ behavior: 'smooth' })}>{t.evidence}</button>
          <button className="theme-btn" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>{lang === 'zh' ? 'EN' : '中'}</button>
          <button className="theme-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="theme">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </nav>
      </header>
      <main>{children}</main>
      <footer className="footer"><span>A股AI扩张瓶颈地图</span><span>研究框架原型 · 非投资建议</span></footer>
    </>
  );
}

function ActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button className="rank-link" type="button" onClick={onClick}><RefreshCw size={14} /> {label}</button>;
}

function HomePage({ data, navigate }: { data: AppData; navigate: (path: string) => void }) {
  const grouped = useMemo(() => {
    const map = new Map<string, Sector[]>();
    data.sectors.forEach((sector) => {
      if (!map.has(sector.layer)) map.set(sector.layer, []);
      map.get(sector.layer)!.push(sector);
    });
    return [...map.entries()];
  }, [data.sectors]);

  return (
    <section className="sectors">
      {grouped.map(([layer, sectors]) => (
        <section className="layer" key={layer}>
          <div className="layer-h"><span className="lk">{layer.split(' ')[0]}</span> {layer}</div>
          <div className="cards">
            {sectors.map((sector) => {
              const companies = data.companies.filter((company) => company.sectorIds.includes(sector.id));
              const leader = topRankedForSector(data.ranking.rows, sector.id);
              const quote = leader?.quote;
              const candidates = data.candidates.items.filter((item) => item.matchedSectors.includes(sector.id));
              return (
                <button className="sc live" type="button" key={sector.id} onClick={() => navigate(`/tree?s=${sector.id}`)}>
                  <div className="sc-head">
                    <span className="ic-dot on" />
                    <div><div className="sc-name">{sector.title}</div><div className="sc-en">{sector.subtitle}</div></div>
                    <span className="st live">LIVE</span>
                  </div>
                  <div className="sc-flag">旗舰 · {sector.flagship}</div>
                  <div className="sc-bs"><span className="bl">BLINDSPOTS</span>{sector.blindspots.map((item) => <span className="bs" key={item}>{item}</span>)}</div>
                  <div className="sc-quote">
                    <span>{leader?.name || companies[0]?.name || '待映射'} · {companies.length} 家 / 候选 {candidates.length}</span>
                    <strong>¥{formatPrice(quote?.price)}</strong>
                    <em className={quoteClass(quote)}>{formatPercent(quote?.changePercent)}</em>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </section>
  );
}

function TreePage({ data, sectorId }: { data: AppData; sectorId: string }) {
  const sector = data.sectors.find((item) => item.id === sectorId) || data.sectors[0];
  const companies = data.companies.filter((company) => company.sectorIds.includes(sector.id));
  return (
    <section className="tree-shell">
      <div className="tree-heading">
        <div><p className="eyebrow">Dependency tree</p><h2>{sector.title}</h2><p>{sector.thesis}</p></div>
        <span className="tag">{companies.length} 只A股</span>
      </div>
      <div className="dependency-layout">
        <section className="tree-card"><h3>依赖树</h3><div className="tree"><TreeNodes nodes={sector.dependencies} companies={companies} sector={sector} /></div></section>
        <section className="tree-card"><h3>关键反证</h3><ul>{sector.checks.map((item) => <li key={item}>{item}</li>)}</ul></section>
      </div>
      <section className="detail-block full">
        <h3>依赖股票与价格</h3>
        <div className="stocks">
          {companies.map((company) => <CompanyCard key={company.id} company={company} quote={data.quotes.items.find((q) => q.code === company.code)} evidence={data.evidence.filter((ev) => ev.companyId === company.id && ev.sectorId === sector.id)} />)}
        </div>
      </section>
      <EvidenceFeed data={data} />
    </section>
  );
}

function TreeNodes({ nodes, companies, sector }: { nodes: DependencyNode[]; companies: Company[]; sector: Sector }) {
  return (
    <>
      {nodes.map((node) => {
        const nodeCompanies = companies.filter((company) => (company.dependencyRefs || []).some((ref) => ref.sectorId === sector.id && (ref.nodeId === node.nodeId || ref.nodeId === sector.id)));
        return (
          <div className="node open" key={`${node.name}-${node.role}`}>
            <div className="row has-kids"><span className="tw">▾</span><span className="nm">{node.name}</span><span className="role">{node.role}</span></div>
            {nodeCompanies.length > 0 && <div className="node-companies">{nodeCompanies.slice(0, 6).map((company) => <span className="bs" key={company.id}>{company.name}</span>)}</div>}
            {node.children && <div className="kids"><TreeNodes nodes={node.children} companies={companies} sector={sector} /></div>}
          </div>
        );
      })}
    </>
  );
}

function CompanyCard({ company, quote, evidence }: { company: Company; quote?: Quote; evidence: Evidence[] }) {
  return (
    <article className="stock-card">
      <div className="stock-heading"><div><strong>{company.name}</strong><span className="stock-code"> {company.code}</span></div><span className="stock-score">{company.sectorIds.length}×</span></div>
      <p>{company.role}</p>
      <div className={`quote-panel ${quoteClass(quote)}`}>
        <span>{quote?.status || 'unavailable'}</span><strong>¥{formatPrice(quote?.price)}</strong><em>{formatPercent(quote?.changePercent)}</em>
        <small>高 {formatPrice(quote?.high)} · 低 {formatPrice(quote?.low)} · 市值 {formatMarketCap(quote?.marketCap)}</small>
      </div>
      <div className="evidence-list">
        {evidence.slice(0, 3).map((item) => <div className={`evidence-pill ${item.sentiment}`} key={item.id}><span>{item.date} · {item.type} · {item.sourceTier || 'search'}</span><strong>{item.title}</strong></div>)}
      </div>
    </article>
  );
}

function RankingPage({ data, t }: { data: AppData; t: ReturnType<typeof dict> }) {
  return (
    <section className="rank">
      <div className="section-heading compact"><p className="eyebrow">Cross-sector</p><h2>{t.hiddenWinner}</h2><p>按依赖板块数和依赖节点出现次数排序。共 {data.ranking.totalTickers} 家，更新时间 {data.ranking.asOf || '--'}。</p></div>
      {data.ranking.rows.map((row, index) => <RankingItem key={row.companyId} row={row} index={index} t={t} />)}
      <EvidenceFeed data={data} />
    </section>
  );
}

function RankingItem({ row, index, t }: { row: RankingRow; index: number; t: ReturnType<typeof dict> }) {
  return (
    <article className={`rk ${row.sectorCount >= 2 ? 'winner' : ''}`}>
      <div className="rk-no">{String(index + 1).padStart(2, '0')}</div>
      <div className="rk-main">
        <div className="rk-top"><span className="cn">{row.name}</span><span className="tk">{row.code}</span><span className={`px ${quoteClass(row.quote)}`}>¥{formatPrice(row.quote?.price)} {formatPercent(row.quote?.changePercent)}</span></div>
        <div className="rk-sec">{row.sectorNames.map((name) => <span className="bs" key={name}>{name}</span>)}</div>
      </div>
      <div className="rk-stat"><b>{row.sectorCount}</b><span>{t.sectors}</span><i>×{row.appearances} {t.appearances}</i></div>
    </article>
  );
}

function EvidenceFeed({ data }: { data: AppData }) {
  const companyById = new Map(data.companies.map((company) => [company.id, company]));
  return (
    <section className="section" id="evidence">
      <div className="section-heading compact"><p className="eyebrow">Evidence feed</p><h2>研究证据流</h2></div>
      <div className="feed-list">
        {data.evidence.slice(0, 30).map((item) => (
          <article className={`feed-item ${item.sentiment}`} key={item.id}>
            <div className="feed-meta"><span>{item.date}</span><span>{companyById.get(item.companyId)?.name || item.companyId}</span><span>{item.sourceTier || 'search'}</span><span>{Math.round(item.confidence * 100)}%</span></div>
            <h3>{item.title}</h3><p>{item.summary}</p>
            <small>来源：{item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.source}</a> : item.source}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function topRankedForSector(rows: RankingRow[], sectorId: string): RankingRow | undefined {
  return rows.find((row) => row.sectors.includes(sectorId));
}

createRoot(document.getElementById('root')!).render(<App />);
