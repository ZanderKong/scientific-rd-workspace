'use client';

import { en, zh } from '@blocknote/core/locales';
import { BlockNoteView } from '@blocknote/shadcn';
import { useCreateBlockNote, useEditorChange } from '@blocknote/react';
import { useLocale } from 'next-intl';
import { BLOCKNOTE_LOCALE, parseLocale } from '@/i18n/config';

export function RichNoteEditor({
  initialContent,
  onChange
}: {
  initialContent: Array<Record<string, unknown>>;
  onChange: (blocks: Array<Record<string, unknown>>) => void;
}) {
  const locale = parseLocale(useLocale());
  const editor = useCreateBlockNote(
    {
      initialContent: initialContent as never,
      dictionary: BLOCKNOTE_LOCALE[locale] === 'zh' ? zh : en
    },
    [locale]
  );
  useEditorChange((currentEditor) => {
    onChange(currentEditor.document as unknown as Array<Record<string, unknown>>);
  }, editor);
  return (
    <div className='overflow-hidden rounded-lg border'>
      <BlockNoteView editor={editor} />
    </div>
  );
}
