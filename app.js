const DATA_FILES = {
  sectors: "./data/sectors.json",
  companies: "./data/companies.json",
  evidence: "./data/evidence.json",
  scoring: "./data/scoring.json",
  quotes: "./data/quotes.json",
};

const sectorGrid = document.querySelector("#sectorGrid");
const sectorDetail = document.querySelector("#sectorDetail");
const watchTable = document.querySelector("#watchTable");
const evidenceFeed = document.querySelector("#evidenceFeed");
const scoringMeta = document.querySelector("#scoringMeta");
const quoteMeta = document.querySelector("#quoteMeta");
const refreshButton = document.querySelector("#refreshQuotes");
const refreshStatus = document.querySelector("#refreshStatus");
const refreshEvidenceButton = document.querySelector("#refreshEvidence");
const evidenceStatus = document.querySelector("#evidenceStatus");

const state = {
  sectors: [],
  companies: [],
  evidence: [],
  scoring: null,
  quotes: { items: [] },
  activeSectorId: "",
};

const sentimentLabels = {
  positive: "利多",
  neutral: "待验证",
  negative: "风险",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`加载失败：${path} (${response.status})`);
  }
  return response.json();
}

function getSector(sectorId) {
  return state.sectors.find((sector) => sector.id === sectorId);
}

function getQuote(code) {
  return state.quotes.items.find((item) => item.code === code);
}

function getCompanyEvidence(companyId, sectorId) {
  return state.evidence
    .filter((item) => item.companyId === companyId && (!sectorId || item.sectorId === sectorId))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function getCompanySectors(company) {
  return company.sectorIds.map(getSector).filter(Boolean);
}

function calculateScore(company) {
  const weights = state.scoring.weights;
  const rawScore = Object.entries(weights).reduce((total, [key, weight]) => {
    return total + Number(company.metrics[key] || 0) * weight;
  }, 0);
  const dependencyBonus = Math.max(0, (company.sectorIds?.length || 1) - 1) * 4;
  return Math.round(rawScore + dependencyBonus);
}

function getScoredCompanies() {
  return state.companies
    .map((company) => ({
      ...company,
      quote: getQuote(company.code),
      score: calculateScore(company),
      sectors: getCompanySectors(company),
      evidenceItems: getCompanyEvidence(company.id),
    }))
    .sort((a, b) => b.score - a.score);
}

function formatPrice(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "--";
}

function formatPercent(value) {
  if (!Number.isFinite(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatMarketCap(value) {
  if (!Number.isFinite(value)) return "--";
  if (value >= 1000000000000) return `${(value / 1000000000000).toFixed(2)}万亿`;
  return `${(value / 100000000).toFixed(0)}亿`;
}

function quoteClass(quote) {
  if (!quote || !Number.isFinite(quote.changePercent)) return "flat";
  if (quote.stale) return "flat";
  return quote.changePercent >= 0 ? "up" : "down";
}

function renderSectorGrid() {
  const grouped = state.sectors.reduce((groups, sector) => {
    const key = sector.layer || "未分层";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(sector);
    return groups;
  }, new Map());

  sectorGrid.innerHTML = [...grouped.entries()]
    .map(([layer, sectors]) => {
      const cards = sectors
        .map((sector) => {
          const companies = getScoredCompanies().filter((company) => company.sectorIds.includes(sector.id));
          const leader = companies[0];
          const chips = (sector.blindspots || [])
            .map((item) => `<span class="bs">${escapeHtml(item)}</span>`)
            .join("");
          const quote = leader?.quote;
          return `
            <button class="sc live ${sector.id === state.activeSectorId ? "is-active" : ""}" data-sector="${escapeHtml(sector.id)}" type="button">
              <div class="sc-head">
                <span class="ic-dot on"></span>
                <div>
                  <div class="sc-name">${escapeHtml(sector.title)}</div>
                  <div class="sc-en">${escapeHtml(sector.subtitle)}</div>
                </div>
                <span class="st live">LIVE</span>
              </div>
              <div class="sc-flag">旗舰 · ${escapeHtml(sector.flagship || sector.title)}</div>
              <div class="sc-bs"><span class="bl">BLINDSPOTS</span>${chips}</div>
              <div class="sc-quote">
                <span>${escapeHtml(leader?.name || "待映射")}</span>
                <strong>¥${formatPrice(quote?.price)}</strong>
                <em class="${quoteClass(quote)}">${formatPercent(quote?.changePercent)}</em>
              </div>
            </button>
          `;
        })
        .join("");
      return `
        <section class="layer">
          <div class="layer-h"><span class="lk">${escapeHtml(layer.split(" ")[0])}</span> ${escapeHtml(layer)}</div>
          <div class="cards">${cards}</div>
        </section>
      `;
    })
    .join("");

  sectorGrid.querySelectorAll("button[data-sector]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeSectorId = button.dataset.sector;
      renderSectorGrid();
      renderSectorDetail();
      document.querySelector("#map")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderAll() {
  renderScoringMeta();
  renderSectorGrid();
  renderSectorDetail();
  renderWatchTable();
  renderEvidenceFeed();
}

function renderTreeNodes(nodes) {
  return nodes
    .map((node) => {
      const children = node.children || [];
      return `
        <div class="node open">
          <div class="row ${children.length ? "has-kids" : ""}">
            <span class="tw">${children.length ? "▾" : "•"}</span>
            <span class="nm">${escapeHtml(node.name)}</span>
            <span class="role">${escapeHtml(node.role)}</span>
          </div>
          ${children.length ? `<div class="kids">${renderTreeNodes(children)}</div>` : ""}
        </div>
      `;
    })
    .join("");
}

function renderMetricBars(company) {
  return Object.entries(state.scoring.weights)
    .map(([key]) => {
      const label = state.scoring.labels[key] || key;
      const value = Number(company.metrics[key] || 0);
      return `
        <div class="metric-row">
          <span>${escapeHtml(label)}</span>
          <div class="metric-track"><i style="width: ${value}%"></i></div>
          <strong>${value}</strong>
        </div>
      `;
    })
    .join("");
}

function renderEvidencePills(evidenceItems) {
  if (evidenceItems.length === 0) {
    return '<p class="muted-text">暂无证据，需补充公告、财报或调研来源。</p>';
  }

  return evidenceItems
    .slice(0, 2)
    .map(
      (item) => `
        <div class="evidence-pill ${escapeHtml(item.sentiment)}">
          <span>${escapeHtml(item.date)} · ${escapeHtml(item.type)} · ${escapeHtml(sentimentLabels[item.sentiment] || item.sentiment)}</span>
          <strong>${escapeHtml(item.title)}</strong>
        </div>
      `
    )
    .join("");
}

function renderQuoteBlock(quote) {
  const staleText = quote?.stale ? " · 旧快照" : "";
  return `
    <div class="quote-panel ${quoteClass(quote)}">
      <span>当前价</span>
      <strong>¥${formatPrice(quote?.price)}</strong>
      <em>${formatPercent(quote?.changePercent)}</em>
      <small>高 ${formatPrice(quote?.high)} · 低 ${formatPrice(quote?.low)} · 市值 ${formatMarketCap(quote?.marketCap)}${staleText}</small>
    </div>
  `;
}

function renderSectorDetail() {
  const sector = getSector(state.activeSectorId) || state.sectors[0];
  const companies = getScoredCompanies().filter((company) => company.sectorIds.includes(sector.id));

  sectorDetail.innerHTML = `
    <div class="detail-top">
      <div>
        <span class="tag">${escapeHtml(sector.layer)}</span>
        <h2>${escapeHtml(sector.title)}</h2>
        <p>${escapeHtml(sector.thesis)}</p>
      </div>
      <span class="tag">${companies.length} 只A股</span>
    </div>
    <div class="dependency-layout">
      <section class="tree-card">
        <h3>依赖树</h3>
        <div class="tree">${renderTreeNodes(sector.dependencies || [])}</div>
      </section>
      <section class="tree-card">
        <h3>关键反证</h3>
        <ul>${sector.checks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>
    </div>
    <section class="detail-block full">
      <h3>依赖股票与价格</h3>
      <div class="stocks">
        ${companies
          .map((company) => {
            const evidenceItems = getCompanyEvidence(company.id, sector.id);
            return `
              <article class="stock-card">
                <div>
                  <div class="stock-heading">
                    <div>
                      <strong>${escapeHtml(company.name)}</strong>
                      <span class="stock-code"> ${escapeHtml(company.code)}</span>
                    </div>
                    <span class="stock-score">${company.score}</span>
                  </div>
                  <p>${escapeHtml(company.role)}</p>
                  ${renderQuoteBlock(company.quote)}
                  <div class="metric-grid">${renderMetricBars(company)}</div>
                  <div class="evidence-list">${renderEvidencePills(evidenceItems)}</div>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;

  sectorDetail.querySelectorAll(".row.has-kids").forEach((row) => {
    row.addEventListener("click", () => {
      row.closest(".node")?.classList.toggle("open");
    });
  });
}

function renderWatchTable() {
  const rows = getScoredCompanies();

  watchTable.innerHTML = rows
    .map((company) => {
      const sectors = company.sectors.map((sector) => sector.title).join(" / ");
      const dependencyCount = company.sectorIds.length;
      const primarySector = company.sectors[0];
      const primaryCheck = primarySector?.checks[0] || "补充反证问题";
      const latestEvidence = company.evidenceItems[0];
      const latestText = latestEvidence
        ? `${latestEvidence.date} · ${latestEvidence.type} · ${latestEvidence.title}`
        : "暂无证据";

      return `
        <tr>
          <td><strong>${escapeHtml(company.name)}</strong><br><span class="stock-code">${escapeHtml(company.code)}</span></td>
          <td>${escapeHtml(sectors)}</td>
          <td><strong>${dependencyCount}</strong><br><span class="stock-code">${escapeHtml(company.sectors.map((sector) => sector.flagship || sector.title).join(" / "))}</span></td>
          <td>${escapeHtml(company.role)}</td>
          <td>
            <span class="price-cell">¥${formatPrice(company.quote?.price)}</span>
            <span class="${quoteClass(company.quote)}">${formatPercent(company.quote?.changePercent)}</span>
          </td>
          <td><span class="stock-score">${company.score}</span></td>
          <td>${escapeHtml(latestText)}</td>
          <td>${escapeHtml(primaryCheck)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderEvidenceFeed() {
  const companiesById = new Map(state.companies.map((company) => [company.id, company]));
  const sectorsById = new Map(state.sectors.map((sector) => [sector.id, sector]));
  const rows = [...state.evidence].sort((a, b) => b.date.localeCompare(a.date));

  evidenceFeed.innerHTML = rows
    .map((item) => {
      const company = companiesById.get(item.companyId);
      const sector = sectorsById.get(item.sectorId);
      const confidence = Math.round(Number(item.confidence || 0) * 100);
      return `
        <article class="feed-item ${escapeHtml(item.sentiment)}">
          <div class="feed-meta">
            <span>${escapeHtml(item.date)}</span>
            <span>${escapeHtml(company?.name || item.companyId)}</span>
            <span>${escapeHtml(sector?.title || item.sectorId)}</span>
            <span>${escapeHtml(item.type)}</span>
            <span>置信度 ${confidence}%</span>
          </div>
          <h3>${escapeHtml(item.title)}</h3>
          <p>${escapeHtml(item.summary)}</p>
          <small>来源：${renderEvidenceSource(item)}</small>
        </article>
      `;
    })
    .join("");
}

function renderEvidenceSource(item) {
  const label = escapeHtml(item.source || item.provider || "search");
  if (!item.url) return label;
  return `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${label}</a>`;
}

function renderScoringMeta() {
  scoringMeta.textContent = `评分日期：${state.scoring.updatedAt} · 动态加载 ${state.sectors.length} 个节点、${state.companies.length} 家公司、${state.evidence.length} 条证据`;
  quoteMeta.textContent = `行情：${state.quotes.updatedAt} · ${state.quotes.source}`;
}

async function refreshQuotesFromServer() {
  if (!refreshButton || !refreshStatus) return;

  refreshButton.disabled = true;
  refreshButton.textContent = "刷新中...";
  refreshStatus.textContent = "正在通过本地服务拉取真实行情，这可能需要几十秒。";

  try {
    const response = await fetch("/api/refresh-quotes", {
      method: "POST",
      cache: "no-store",
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) {
      throw new Error(result.error || `刷新失败 (${response.status})`);
    }
    state.quotes = await loadJson(DATA_FILES.quotes);
    renderAll();
    refreshStatus.textContent = `行情已刷新：${result.updatedAt}，${result.itemCount} 只股票，失败 ${result.failureCount} 只。`;
  } catch (error) {
    refreshStatus.textContent = `刷新失败：${error.message || error}。请确认使用 server.py 启动，而不是 python -m http.server。`;
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "↻ 刷新行情";
  }
}

async function refreshEvidenceFromServer() {
  if (!refreshEvidenceButton || !evidenceStatus) return;

  refreshEvidenceButton.disabled = true;
  refreshEvidenceButton.textContent = "刷新中...";
  evidenceStatus.textContent = "正在通过 daily_stock_analysis 搜索公告、新闻、研报与风险线索。";

  try {
    const response = await fetch("/api/refresh-evidence", {
      method: "POST",
      cache: "no-store",
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) {
      throw new Error(result.error || `刷新失败 (${response.status})`);
    }
    state.evidence = await loadJson(DATA_FILES.evidence);
    renderAll();
    evidenceStatus.textContent = `证据流已刷新：${result.updatedAt}，覆盖 ${result.companyCount} 家公司，生成 ${result.itemCount} 条，失败 ${result.failureCount} 条。`;
  } catch (error) {
    evidenceStatus.textContent = `证据流刷新失败：${error.message || error}`;
  } finally {
    refreshEvidenceButton.disabled = false;
    refreshEvidenceButton.textContent = "↻ 刷新证据流";
  }
}

function renderError(error) {
  const message = escapeHtml(error.message || "数据加载失败");
  sectorGrid.innerHTML = `<div class="load-error">${message}</div>`;
  sectorDetail.innerHTML = `
    <div class="load-error">
      <strong>无法加载研究数据</strong>
      <p>请使用静态服务器打开页面，例如 <code>python3 -m http.server 5173</code>，不要直接用 file:// 打开。</p>
    </div>
  `;
}

async function boot() {
  try {
    const [sectors, companies, evidence, scoring, quotes] = await Promise.all([
      loadJson(DATA_FILES.sectors),
      loadJson(DATA_FILES.companies),
      loadJson(DATA_FILES.evidence),
      loadJson(DATA_FILES.scoring),
      loadJson(DATA_FILES.quotes),
    ]);

    state.sectors = sectors;
    state.companies = companies;
    state.evidence = evidence;
    state.scoring = scoring;
    state.quotes = quotes;
    state.activeSectorId = sectors[0]?.id || "";

    renderAll();
    refreshButton?.addEventListener("click", refreshQuotesFromServer);
    refreshEvidenceButton?.addEventListener("click", refreshEvidenceFromServer);
  } catch (error) {
    renderError(error);
  }
}

boot();
