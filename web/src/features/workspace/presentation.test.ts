import { describe, expect, it } from 'vitest';
import { buildSampleLineageTree, projectXYToPolyline } from './presentation';

const object = (id: string, code: string) =>
  ({ id, code, kind: 'sample', title: code, status: 'active' }) as never;

describe('workspace presentation helpers', () => {
  it('projects real x values without downsampling', () => {
    expect(
      projectXYToPolyline(
        [
          { x_value: 10, y_value: 0 },
          { x_value: 20, y_value: 10 },
          { x_value: 40, y_value: 5 }
        ],
        100,
        100,
        10
      )
    ).toBe('10,90 36.666666666666664,10 90,50');
  });

  it('builds a branched tree from process input/output edges', () => {
    const root = object('s0', 'SMP-001');
    const first = object('s1', 'SMP-002');
    const branch = object('s2', 'SMP-004');
    const tree = buildSampleLineageTree(
      root,
      [first, branch],
      [
        { source: 'p1', target: 's0', type: 'uses', role: 'precursor' },
        { source: 'p1', target: 's1', type: 'produces', role: null },
        { source: 'p2', target: 's0', type: 'uses', role: 'precursor' },
        { source: 'p2', target: 's2', type: 'produces', role: null }
      ],
      'downstream'
    );
    expect(tree.children.map((child) => child.object.code)).toEqual(['SMP-002', 'SMP-004']);
  });
});
