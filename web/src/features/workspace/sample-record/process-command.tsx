'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { ObjectType, ObjectTypeVersion } from '@/lib/domain';
import { cn } from '@/lib/utils';

type ProcessCommandProps = {
  open: boolean;
  types: ObjectType[];
  query: string;
  zh: boolean;
  onQueryChange: (query: string) => void;
  onSelect: (selection: { typeVersionId?: string; label: string }) => void;
  onClose: () => void;
};

function activeVersion(type: ObjectType): ObjectTypeVersion | undefined {
  return (
    type.versions.find((version) => version.is_active) ??
    type.versions.toSorted((left, right) => right.version - left.version)[0]
  );
}

export function ProcessCommand({
  open,
  types,
  query,
  zh,
  onQueryChange,
  onSelect,
  onClose
}: ProcessCommandProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const options = useMemo(
    () =>
      [
        { key: 'custom', label: zh ? '自定义过程' : 'Custom Process', version: undefined },
        ...types.map((type) => ({
          key: type.id,
          label: zh ? type.label_zh : type.label_en,
          version: activeVersion(type)
        }))
      ].filter((option) => option.label.toLowerCase().includes(query.trim().toLowerCase())),
    [query, types, zh]
  );

  useEffect(() => {
    if (!open) return;
    setSelectedIndex(0);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    setSelectedIndex((index) => Math.min(index, Math.max(0, options.length - 1)));
  }, [options.length]);

  if (!open) return null;

  function selectCurrent() {
    const option = options[selectedIndex];
    if (!option) return;
    onSelect({ label: option.label, typeVersionId: option.version?.id });
  }

  return (
    <div
      className='absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-foreground/10 bg-popover shadow-xl shadow-black/10'
      data-testid='process-command'
    >
      <div className='flex items-center gap-2 border-b px-3 py-2'>
        <span className='font-mono text-sm text-muted-foreground'>/</span>
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              setSelectedIndex((index) => Math.min(index + 1, options.length - 1));
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              setSelectedIndex((index) => Math.max(index - 1, 0));
            } else if (event.key === 'Enter') {
              event.preventDefault();
              selectCurrent();
            } else if (event.key === 'Escape') {
              event.preventDefault();
              onClose();
            }
          }}
          className='h-8 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground'
          placeholder={zh ? '选择一个 Process 定义…' : 'Choose a Process definition…'}
          aria-label={zh ? 'Process 命令' : 'Process command'}
        />
        <kbd className='rounded border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground'>
          esc
        </kbd>
      </div>
      <div className='grid max-h-64 overflow-y-auto p-1'>
        {options.length === 0 ? (
          <p className='px-3 py-6 text-center text-xs text-muted-foreground'>
            {zh ? '没有匹配的 Process 定义' : 'No matching Process definitions'}
          </p>
        ) : (
          options.map((option, index) => (
            <button
              type='button'
              key={option.key}
              className={cn(
                'flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition',
                index === selectedIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-muted'
              )}
              onMouseEnter={() => setSelectedIndex(index)}
              onClick={() => onSelect({ label: option.label, typeVersionId: option.version?.id })}
              data-testid={`process-option-${option.key}`}
            >
              <span>{option.label}</span>
              <span className='font-mono text-[10px] text-muted-foreground'>
                {option.version ? `v${option.version.version}` : 'instance'}
              </span>
            </button>
          ))
        )}
      </div>
      <div className='flex items-center justify-between border-t bg-muted/30 px-3 py-2 text-[10px] text-muted-foreground'>
        <span>{zh ? '↑↓ 移动 · Enter 选择' : '↑↓ move · Enter select'}</span>
        <span className='font-mono'>PROCESS</span>
      </div>
    </div>
  );
}
