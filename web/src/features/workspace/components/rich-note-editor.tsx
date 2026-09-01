'use client';

import { useCreateBlockNote, useEditorChange } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/shadcn';

export function RichNoteEditor({
  initialContent,
  editable = true,
  onChange
}: {
  initialContent: Array<Record<string, unknown>>;
  editable?: boolean;
  onChange?: (blocks: Array<Record<string, unknown>>) => void;
}) {
  const editor = useCreateBlockNote({ initialContent: initialContent as never });
  useEditorChange((currentEditor) => {
    onChange?.(currentEditor.document as unknown as Array<Record<string, unknown>>);
  }, editor);
  return (
    <div className='overflow-hidden rounded-lg border'>
      <BlockNoteView editor={editor} editable={editable} />
    </div>
  );
}
