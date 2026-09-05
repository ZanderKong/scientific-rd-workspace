import { describe, expect, it } from 'vitest';
import { generateProjectAvatar, validateProjectLabel } from './project-avatar';

describe('project avatar', () => {
  it('uses the first two Chinese characters', () => {
    expect(generateProjectAvatar('氯气显色项目')).toBe('氯气');
    expect(generateProjectAvatar('半导体气敏材料')).toBe('半导');
  });

  it('uses up to five English word initials', () => {
    expect(generateProjectAvatar('Gas Sensor Development')).toBe('GSD');
    expect(generateProjectAvatar('Scientific R&D Workspace')).toBe('SRDW');
    expect(generateProjectAvatar('One Two Three Four Five Six')).toBe('OTTFF');
  });

  it('handles punctuation, mixed titles, and code fallback', () => {
    expect(generateProjectAvatar('R&D: 氯气')).toBe('RD');
    expect(generateProjectAvatar('---', 'prj-007')).toBe('PRJ00');
    expect(generateProjectAvatar('')).toBe('PRJ');
  });

  it('validates custom labels', () => {
    expect(validateProjectLabel('氯')).toEqual({ valid: true, value: '氯' });
    expect(validateProjectLabel('氯气')).toEqual({ valid: true, value: '氯气' });
    expect(validateProjectLabel('氯气显')).toMatchObject({ valid: false });
    expect(validateProjectLabel('g s')).toMatchObject({ valid: false });
    expect(validateProjectLabel('gsrd')).toEqual({ valid: true, value: 'GSRD' });
    expect(validateProjectLabel('GSRD12')).toMatchObject({ valid: false });
  });
});
