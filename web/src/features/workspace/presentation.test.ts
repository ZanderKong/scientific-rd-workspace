import { describe, expect, it } from 'vitest';
import {
  formatStructuredValue,
  scoreEntries,
  toggleBoundedSelection,
  traceabilityNodes
} from './presentation';

describe('workspace presentation helpers', () => {
  it('keeps compare selection bounded to five experiments', () => {
    expect(toggleBoundedSelection(['a', 'b', 'c', 'd', 'e'], 'f')).toEqual([
      'a',
      'b',
      'c',
      'd',
      'e'
    ]);
    expect(toggleBoundedSelection(['a', 'b'], 'a')).toEqual(['b']);
  });

  it('renders structured values as readable table content', () => {
    expect(formatStructuredValue({ concentration: 2, solvent: 'water' })).toBe(
      'Concentration: 2 · Solvent: water'
    );
    expect(formatStructuredValue(['control', 'replicate'])).toBe('control, replicate');
  });

  it('exposes score fields without requiring raw JSON rendering', () => {
    expect(scoreEntries({ gate_pass: true, score: 0.8 })).toEqual([
      { key: 'gate_pass', label: 'Gate Pass', value: true },
      { key: 'score', label: 'Score', value: 0.8 }
    ]);
  });

  it('deduplicates traceability nodes and does not invent links', () => {
    expect(
      traceabilityNodes([
        { id: 'run-1', kind: 'run', label: 'Run' },
        { id: 'run-1', kind: 'run', label: 'Duplicate' },
        { id: 'finding-1', kind: 'finding', label: 'Finding', href: '#finding-1' },
        { id: '', kind: 'unknown', label: 'Invalid' }
      ])
    ).toEqual([
      { id: 'run-1', kind: 'run', label: 'Run' },
      { id: 'finding-1', kind: 'finding', label: 'Finding', href: '#finding-1' }
    ]);
  });
});
