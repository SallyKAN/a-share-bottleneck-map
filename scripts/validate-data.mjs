import { readFile } from "node:fs/promises";

const files = {
  sectors: new URL("../data/sectors.json", import.meta.url),
  companies: new URL("../data/companies.json", import.meta.url),
  evidence: new URL("../data/evidence.json", import.meta.url),
  scoring: new URL("../data/scoring.json", import.meta.url),
  quotes: new URL("../data/quotes.json", import.meta.url),
  candidates: new URL("../data/candidate_pool.json", import.meta.url),
  ranking: new URL("../data/ranking.json", import.meta.url),
};

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const [sectors, companies, evidence, scoring, quotes, candidates, ranking] = await Promise.all([
  readJson(files.sectors),
  readJson(files.companies),
  readJson(files.evidence),
  readJson(files.scoring),
  readJson(files.quotes),
  readJson(files.candidates),
  readJson(files.ranking),
]);

const sectorIds = new Set(sectors.map((sector) => sector.id));
const companyIds = new Set(companies.map((company) => company.id));
const companyCodes = new Set(companies.map((company) => company.code));
const quoteCodes = new Set((quotes.items || []).map((quote) => quote.code));
const metricKeys = Object.keys(scoring.weights);

assert(sectorIds.size === sectors.length, "sectors.json contains duplicate sector ids");
assert(companyIds.size === companies.length, "companies.json contains duplicate company ids");

for (const company of companies) {
  assert(company.sectorIds.length > 0, `${company.id} must have at least one sector`);
  for (const sectorId of company.sectorIds) {
    assert(sectorIds.has(sectorId), `${company.id} references unknown sector ${sectorId}`);
  }
  for (const key of metricKeys) {
    assert(Number.isFinite(company.metrics[key]), `${company.id} missing numeric metric ${key}`);
    assert(company.metrics[key] >= 0 && company.metrics[key] <= 100, `${company.id}.${key} must be 0-100`);
  }
  assert(quoteCodes.has(company.code), `${company.id} (${company.code}) missing quote`);
  if (company.dependencyRefs) {
    assert(Array.isArray(company.dependencyRefs), `${company.id}.dependencyRefs must be an array`);
    for (const ref of company.dependencyRefs) {
      assert(sectorIds.has(ref.sectorId), `${company.id} dependency ref references unknown sector ${ref.sectorId}`);
    }
  }
}

for (const item of evidence) {
  assert(companyIds.has(item.companyId), `${item.id} references unknown company ${item.companyId}`);
  assert(sectorIds.has(item.sectorId), `${item.id} references unknown sector ${item.sectorId}`);
  assert(["positive", "neutral", "negative"].includes(item.sentiment), `${item.id} has invalid sentiment`);
  assert(item.confidence >= 0 && item.confidence <= 1, `${item.id}.confidence must be 0-1`);
}

for (const sector of sectors) {
  assert(sector.layer, `${sector.id} missing layer`);
  assert(sector.flagship, `${sector.id} missing flagship`);
  assert(Array.isArray(sector.dependencies), `${sector.id} dependencies must be an array`);
}

for (const quote of quotes.items || []) {
  assert(companyCodes.has(quote.code), `quote references unknown company code ${quote.code}`);
  if (quote.status) {
    assert(["ok", "stale", "unavailable"].includes(quote.status), `${quote.code} quote.status invalid`);
  }
  if (quote.status !== "unavailable") {
    assert(Number.isFinite(quote.price), `${quote.code} quote.price must be numeric`);
    assert(Number.isFinite(quote.changePercent), `${quote.code} quote.changePercent must be numeric`);
  }
}

assert(Array.isArray(candidates.items), "candidate_pool.items must be an array");
assert(Array.isArray(ranking.rows), "ranking.rows must be an array");
for (const row of ranking.rows) {
  assert(companyIds.has(row.companyId), `ranking references unknown company ${row.companyId}`);
  assert(row.sectorCount === new Set(row.sectors || []).size, `${row.companyId} sectorCount mismatch`);
  assert(Number.isFinite(row.appearances), `${row.companyId} appearances must be numeric`);
}

const weightTotal = Object.values(scoring.weights).reduce((total, value) => total + value, 0);
assert(Math.abs(weightTotal - 1) < 0.0001, "scoring weights must add up to 1");

console.log(
  `Data OK: ${sectors.length} sectors, ${companies.length} companies, ${evidence.length} evidence items, ${quotes.items.length} quotes.`
);
