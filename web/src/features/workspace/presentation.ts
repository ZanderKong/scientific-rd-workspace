import type { JsonObject } from '@/lib/domain';

export function toggleBoundedSelection(ids: string[], id: string, limit = 5): string[] {
  if (ids.includes(id)) return ids.filter((item) => item !== id);
  return ids.length < limit ? [...ids, id] : ids;
}

export function technicalLabel(value: string): string {
  return value
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatStructuredValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.map(formatStructuredValue).join(', ');
  if (typeof value === 'object') {
    return Object.entries(value as JsonObject)
      .map(([key, child]) => `${technicalLabel(key)}: ${formatStructuredValue(child)}`)
      .join(' · ');
  }
  return String(value);
}

export function scoreEntries(scores: JsonObject | null | undefined) {
  return Object.entries(scores ?? {}).map(([key, value]) => ({
    key,
    label: technicalLabel(key),
    value
  }));
}

export type TraceabilityNode = {
  id: string;
  kind: string;
  label: string;
  detail?: string;
  href?: string;
};

export function traceabilityNodes(nodes: TraceabilityNode[]): TraceabilityNode[] {
  return nodes.filter((node, index, all) => {
    if (!node.id || !node.label) return false;
    return all.findIndex((candidate) => candidate.id === node.id) === index;
  });
}
