import type { AppData } from './types';

const files = {
  sectors: '/data/sectors.json',
  companies: '/data/companies.json',
  evidence: '/data/evidence.json',
  quotes: '/data/quotes.json',
  scoring: '/data/scoring.json',
  candidates: '/data/candidate_pool.json',
  ranking: '/data/ranking.json',
};

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path} load failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function loadAppData(): Promise<AppData> {
  const [sectors, companies, evidence, quotes, scoring, candidates, ranking] = await Promise.all([
    loadJson<AppData['sectors']>(files.sectors),
    loadJson<AppData['companies']>(files.companies),
    loadJson<AppData['evidence']>(files.evidence),
    loadJson<AppData['quotes']>(files.quotes),
    loadJson<AppData['scoring']>(files.scoring),
    loadJson<AppData['candidates']>(files.candidates),
    loadJson<AppData['ranking']>(files.ranking),
  ]);
  return { sectors, companies, evidence, quotes, scoring, candidates, ranking };
}

export async function postRefresh(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(path, { method: 'POST', cache: 'no-store' });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    throw new Error(String(payload.error || `request failed: ${response.status}`));
  }
  return payload;
}
