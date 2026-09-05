const HAN_RE = /[\u3400-\u9fff]/g;
const LATIN_WORD_RE = /[A-Za-z]+/g;
const FALLBACK_RE = /[A-Za-z0-9\u3400-\u9fff]/g;

export function generateProjectAvatar(title: string, fallbackCode?: string | null) {
  const value = title.trim();
  const startsWithHan = HAN_RE.test(value[0] ?? '');
  HAN_RE.lastIndex = 0;
  if (startsWithHan) {
    const chinese = value.match(HAN_RE)?.slice(0, 2).join('');
    if (chinese) return chinese;
  }

  const words = value.match(LATIN_WORD_RE) ?? [];
  if (words.length)
    return words
      .slice(0, 5)
      .map((word) => word[0])
      .join('')
      .toUpperCase();

  const fallback = fallbackCode?.match(FALLBACK_RE)?.slice(0, 5).join('');
  return fallback ? fallback.toUpperCase() : 'PRJ';
}

export function validateProjectLabel(value: string) {
  const label = value.trim();
  if (/^[\u3400-\u9fff]{1,2}$/.test(label)) return { valid: true, value: label };
  if (/^[A-Za-z]{1,5}$/.test(label)) return { valid: true, value: label.toUpperCase() };
  return { valid: false, value: label };
}
