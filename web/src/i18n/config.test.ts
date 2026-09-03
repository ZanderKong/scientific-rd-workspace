import { describe, expect, it } from 'vitest';
import en from '../../messages/en.json';
import zhCN from '../../messages/zh-CN.json';
import { DEFAULT_LOCALE, FALLBACK_LOCALE, parseLocale } from './config';

function keyTree(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(keyTree);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value as Record<string, unknown>)
        .toSorted()
        .map((key) => [key, keyTree((value as Record<string, unknown>)[key])])
    );
  }
  return typeof value;
}

describe('locale foundation', () => {
  it('defaults to zh-CN and falls back from unknown values', () => {
    expect(DEFAULT_LOCALE).toBe('zh-CN');
    expect(FALLBACK_LOCALE).toBe('en');
    expect(parseLocale(undefined)).toBe('zh-CN');
    expect(parseLocale('fr')).toBe('zh-CN');
    expect(parseLocale('en')).toBe('en');
  });

  it('keeps translation catalog key trees in parity', () => {
    expect(keyTree(zhCN)).toEqual(keyTree(en));
  });
});
