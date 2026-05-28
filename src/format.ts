import type { Quote } from './types';

export function formatPrice(value: number | null | undefined): string {
  return Number.isFinite(value) ? Number(value).toFixed(2) : '--';
}

export function formatPercent(value: number | null | undefined): string {
  if (!Number.isFinite(value)) return '--';
  return `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
}

export function quoteClass(quote: Quote | undefined): string {
  if (!quote || quote.status === 'stale' || quote.status === 'unavailable' || !Number.isFinite(quote.changePercent)) {
    return 'flat';
  }
  return Number(quote.changePercent) >= 0 ? 'up' : 'down';
}

export function formatMarketCap(value: number | null | undefined): string {
  if (!Number.isFinite(value)) return '--';
  if (Number(value) >= 1_000_000_000_000) return `${(Number(value) / 1_000_000_000_000).toFixed(2)}万亿`;
  return `${(Number(value) / 100_000_000).toFixed(0)}亿`;
}
