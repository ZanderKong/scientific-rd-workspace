import type { ResearchObject } from '@/lib/domain';

export type XYPoint = { x_value: number; y_value: number };

export function projectXYToPolyline(
  points: XYPoint[],
  width: number,
  height: number,
  padding = 20
): string {
  if (!points.length || width <= padding * 2 || height <= padding * 2) return '';
  const xValues = points.map((point) => point.x_value);
  const yValues = points.map((point) => point.y_value);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  return points
    .map((point) => {
      const x = padding + ((point.x_value - xMin) / xSpan) * plotWidth;
      const y = height - padding - ((point.y_value - yMin) / ySpan) * plotHeight;
      return `${x},${y}`;
    })
    .join(' ');
}

export type LineageTreeNode = {
  object: ResearchObject;
  children: LineageTreeNode[];
};

type LineageEdge = {
  source: string;
  target: string;
  type: string;
  role: string | null;
};

export function buildSampleLineageTree(
  root: ResearchObject,
  relatedSamples: ResearchObject[],
  edges: LineageEdge[],
  direction: 'upstream' | 'downstream'
): LineageTreeNode {
  const objects = new Map([
    [root.id, root],
    ...relatedSamples.map((item) => [item.id, item] as const)
  ]);
  const processInputs = new Map<string, string[]>();
  const processOutputs = new Map<string, string[]>();
  for (const edge of edges) {
    if (edge.type === 'uses' && edge.role === 'precursor') {
      const values = processInputs.get(edge.source) ?? [];
      values.push(edge.target);
      processInputs.set(edge.source, values);
    }
    if (edge.type === 'produces') {
      const values = processOutputs.get(edge.source) ?? [];
      values.push(edge.target);
      processOutputs.set(edge.source, values);
    }
  }
  const adjacent = new Map<string, Set<string>>();
  for (const [processId, inputs] of processInputs) {
    for (const input of inputs) {
      for (const output of processOutputs.get(processId) ?? []) {
        const source = direction === 'upstream' ? output : input;
        const target = direction === 'upstream' ? input : output;
        const values = adjacent.get(source) ?? new Set<string>();
        values.add(target);
        adjacent.set(source, values);
      }
    }
  }
  function visit(id: string, path: Set<string>): LineageTreeNode | null {
    const object = objects.get(id);
    if (!object) return null;
    const nextPath = new Set(path).add(id);
    const children = [...(adjacent.get(id) ?? [])]
      .filter((childId) => !nextPath.has(childId))
      .map((childId) => visit(childId, nextPath))
      .filter((child): child is LineageTreeNode => child !== null);
    return { object, children };
  }
  return visit(root.id, new Set()) ?? { object: root, children: [] };
}
