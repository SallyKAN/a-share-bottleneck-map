export type Sentiment = 'positive' | 'neutral' | 'negative';
export type QuoteStatus = 'ok' | 'stale' | 'unavailable';

export type DependencyNode = {
  nodeId?: string;
  name: string;
  role: string;
  keywords?: string[];
  children?: DependencyNode[];
};

export type Sector = {
  id: string;
  title: string;
  subtitle: string;
  thesis: string;
  layer: string;
  flagship: string;
  blindspots: string[];
  dependencies: DependencyNode[];
  bottlenecks: string[];
  checks: string[];
};

export type Company = {
  id: string;
  name: string;
  code: string;
  sectorIds: string[];
  role: string;
  dependencyRefs?: DependencyRef[];
  admission?: {
    source: string;
    score: number;
    promotedAt: string;
    curated: boolean;
  };
  metrics: Record<string, number>;
};

export type DependencyRef = {
  sectorId: string;
  nodeId: string;
  role: string;
  evidenceIds?: string[];
  confidence?: number;
};

export type Evidence = {
  id: string;
  companyId: string;
  sectorId: string;
  date: string;
  type: string;
  evidenceKind?: string;
  sourceTier?: string;
  sentiment: Sentiment;
  confidence: number;
  title: string;
  summary: string;
  source: string;
  url?: string;
};

export type Quote = {
  code: string;
  name: string;
  price: number | null;
  changePercent: number | null;
  high?: number | null;
  low?: number | null;
  marketCap?: number | null;
  source?: string;
  updatedAt?: string;
  status?: QuoteStatus;
  stale?: boolean;
  error?: string;
};

export type QuotesPayload = {
  source: string;
  updatedAt: string;
  itemCount: number;
  failureCount: number;
  items: Quote[];
};

export type CandidatePool = {
  source: string;
  updatedAt: string | null;
  itemCount: number;
  promotedCount: number;
  items: Candidate[];
};

export type Candidate = {
  id: string;
  code: string;
  name: string;
  matchedSectors: string[];
  matchedKeywords: string[];
  sourceTiers: Record<string, number>;
  evidenceCounts: { total: number };
  status: string;
  admissionScore: number;
};

export type RankingPayload = {
  source: string;
  asOf: string | null;
  totalTickers: number;
  rows: RankingRow[];
};

export type RankingRow = {
  companyId: string;
  name: string;
  code: string;
  sectors: string[];
  sectorNames: string[];
  sectorCount: number;
  appearances: number;
  dependencyRefs: DependencyRef[];
  score: number;
  evidenceScore: number;
  evidenceCount: number;
  quote?: Quote;
  quoteStatus: QuoteStatus;
};

export type Scoring = {
  updatedAt: string;
  weights: Record<string, number>;
  labels: Record<string, string>;
};

export type AppData = {
  sectors: Sector[];
  companies: Company[];
  evidence: Evidence[];
  quotes: QuotesPayload;
  scoring: Scoring;
  candidates: CandidatePool;
  ranking: RankingPayload;
};
