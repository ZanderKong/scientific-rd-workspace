'use client';

import { useTranslations } from 'next-intl';
import type { JsonObject, UsageFieldDefinition, ValueType } from '@/lib/domain';
import { Button } from '@/components/ui/button';

export function readUsageFields(value: JsonObject): UsageFieldDefinition[] {
  const nested = value.fields;
  const fields = Array.isArray(nested)
    ? nested.filter((field): field is UsageFieldDefinition =>
        Boolean(field && typeof field === 'object' && typeof field.key === 'string')
      )
    : Object.entries(value)
        .filter(([, field]) => Boolean(field && typeof field === 'object'))
        .map(([key, field]) => ({ key, ...(field as Omit<UsageFieldDefinition, 'key'>) }));
  return fields.toSorted((left, right) => (left.order ?? 0) - (right.order ?? 0));
}

export function writeUsageFields(fields: UsageFieldDefinition[]): JsonObject {
  return {
    fields: fields.map((field, order) => ({
      ...field,
      label: field.label.trim(),
      key: field.key.trim(),
      order,
      options: field.value_type === 'select' ? (field.options ?? []).filter(Boolean) : []
    }))
  };
}

function normalizedKey(label: string, fields: UsageFieldDefinition[]) {
  const base =
    label
      .trim()
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, '_')
      .replace(/^_+|_+$/g, '') || 'field';
  let key = base;
  let suffix = 2;
  while (fields.some((field) => field.key === key)) key = `${base}_${suffix++}`;
  return key;
}

export function ScientificFieldEditor({
  value,
  onChange,
  ownerId,
  local = false
}: {
  value: JsonObject;
  onChange: (value: JsonObject) => void;
  ownerId?: string | null;
  local?: boolean;
}) {
  const t = useTranslations('ProductCompletion.fields');
  const fields = readUsageFields(value);
  const update = (index: number, patch: Partial<UsageFieldDefinition>) => {
    const next = fields.map((field, itemIndex) =>
      itemIndex === index ? { ...field, ...patch } : field
    );
    onChange(writeUsageFields(next));
  };
  const move = (index: number, delta: -1 | 1) => {
    const nextIndex = index + delta;
    if (nextIndex < 0 || nextIndex >= fields.length) return;
    const next = [...fields];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    onChange(writeUsageFields(next));
  };
  const add = () => {
    const label = t('newField');
    const fieldId = local ? crypto.randomUUID() : null;
    onChange(
      writeUsageFields([
        ...fields,
        {
          key: local ? `local_${fieldId}` : normalizedKey(label, fields),
          label,
          value_type: 'text',
          source: local ? 'local' : 'template',
          owner_id: local ? null : (ownerId ?? null),
          field_id: fieldId,
          required: false,
          options: [],
          order: fields.length
        }
      ])
    );
  };
  return (
    <div className='space-y-3'>
      {fields.map((field, index) => (
        <div
          key={field.field_id ?? field.key}
          className='grid gap-2 rounded-lg border p-3 md:grid-cols-[1.2fr_1fr_0.8fr_1fr_auto]'
        >
          <label className='grid gap-1 text-xs'>
            {t('label')}
            <input
              className='h-9 rounded border bg-background px-2 text-sm'
              value={field.label}
              onChange={(event) => update(index, { label: event.target.value })}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            {t('key')}
            <input
              className='h-9 rounded border bg-background px-2 font-mono text-xs'
              value={field.key}
              disabled={field.source === 'local'}
              onChange={(event) => update(index, { key: event.target.value })}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            {t('type')}
            <select
              className='h-9 rounded border bg-background px-2 text-sm'
              value={field.value_type}
              onChange={(event) => {
                const valueType = event.target.value as ValueType;
                update(index, {
                  value_type: valueType,
                  options: valueType === 'select' ? [t('newOption')] : []
                });
              }}
            >
              {(['text', 'number', 'boolean', 'select'] as const).map((type) => (
                <option key={type} value={type}>
                  {t(type)}
                </option>
              ))}
            </select>
          </label>
          {field.value_type === 'select' ? (
            <label className='grid gap-1 text-xs'>
              {t('options')}
              <input
                className='h-9 rounded border bg-background px-2 text-sm'
                value={(field.options ?? []).join(', ')}
                onChange={(event) =>
                  update(index, {
                    options: event.target.value
                      .split(',')
                      .map((item) => item.trim())
                      .filter(Boolean)
                  })
                }
              />
            </label>
          ) : (
            <label className='grid gap-1 text-xs'>
              {t('unit')}
              <input
                className='h-9 rounded border bg-background px-2 text-sm'
                value={field.default_unit ?? ''}
                onChange={(event) => update(index, { default_unit: event.target.value || null })}
              />
            </label>
          )}
          <div className='flex items-end gap-1'>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={index === 0}
              onClick={() => move(index, -1)}
              aria-label={t('moveUp')}
            >
              ↑
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={index === fields.length - 1}
              onClick={() => move(index, 1)}
              aria-label={t('moveDown')}
            >
              ↓
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              onClick={() =>
                onChange(writeUsageFields(fields.filter((_, itemIndex) => itemIndex !== index)))
              }
              aria-label={t('remove')}
            >
              ×
            </Button>
          </div>
        </div>
      ))}
      <Button type='button' variant='outline' onClick={add}>
        {t('add')}
      </Button>
    </div>
  );
}

type PropertyRow = { id: string; key: string; value: string };

function propertyRows(value: JsonObject): PropertyRow[] {
  return Object.entries(value).map(([key, item]) => ({
    id: key,
    key,
    value: typeof item === 'string' ? item : JSON.stringify(item)
  }));
}

function propertyObject(rows: PropertyRow[]): JsonObject {
  return Object.fromEntries(
    rows.flatMap((row) => {
      const key = row.key.trim();
      if (!key) return [];
      try {
        return [[key, JSON.parse(row.value) as unknown]];
      } catch {
        return [[key, row.value]];
      }
    })
  );
}

export function StructuredPropertiesEditor({
  value,
  onChange
}: {
  value: JsonObject;
  onChange: (value: JsonObject) => void;
}) {
  const t = useTranslations('ProductCompletion.properties');
  const rows = propertyRows(value);
  const update = (id: string, patch: Partial<PropertyRow>) =>
    onChange(propertyObject(rows.map((row) => (row.id === id ? { ...row, ...patch } : row))));
  return (
    <div className='space-y-2'>
      {rows.map((row) => (
        <div key={row.id} className='flex gap-2'>
          <input
            className='h-9 min-w-0 flex-1 rounded border bg-background px-2 text-sm'
            value={row.key}
            onChange={(event) => update(row.id, { key: event.target.value })}
            placeholder={t('key')}
          />
          <input
            className='h-9 min-w-0 flex-[2] rounded border bg-background px-2 text-sm'
            value={row.value}
            onChange={(event) => update(row.id, { value: event.target.value })}
            placeholder={t('value')}
          />
          <Button
            type='button'
            variant='outline'
            size='sm'
            onClick={() => onChange(propertyObject(rows.filter((item) => item.id !== row.id)))}
            aria-label={t('remove')}
          >
            ×
          </Button>
        </div>
      ))}
      <Button
        type='button'
        variant='outline'
        onClick={() => {
          const id = crypto.randomUUID();
          onChange(
            propertyObject([...rows, { id, key: `property_${rows.length + 1}`, value: '' }])
          );
        }}
      >
        {t('add')}
      </Button>
    </div>
  );
}
