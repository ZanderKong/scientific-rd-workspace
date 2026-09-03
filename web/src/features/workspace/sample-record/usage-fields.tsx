'use client';

import { useMemo, useState } from 'react';
import type { UsageFieldDefinition, UsageSchema, UsageValue, UsageValueType } from '@/lib/domain';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { usageValueText, usageSchema, type DraftResource, usageDefinition } from './model';

type UsageFieldsProps = {
  resource: DraftResource;
  zh: boolean;
  onChange: (resource: DraftResource) => void;
};

function rawSchema(resource: DraftResource): UsageSchema {
  if (resource.object) return usageSchema(resource.object);
  const value = resource.create_target?.usage_schema_jsonb;
  if (!value || !Array.isArray(value.fields)) return { fields: [] };
  return { fields: value.fields as UsageFieldDefinition[] };
}

function mergeFields(resource: DraftResource) {
  const fields = [...rawSchema(resource).fields];
  const seen = new Set(fields.map((field) => field.key));
  for (const field of resource.usage_schema_additions ?? []) {
    if (!seen.has(field.key)) {
      fields.push(field);
      seen.add(field.key);
    }
  }
  return fields.toSorted((left, right) => (left.order ?? 0) - (right.order ?? 0));
}

function valueForField(
  resource: DraftResource,
  field: UsageFieldDefinition
): UsageValue | undefined {
  return resource.usage_values?.[field.key];
}

export function UsageFields({ resource, zh, onChange }: UsageFieldsProps) {
  const fields = useMemo(() => mergeFields(resource), [resource]);
  const [adding, setAdding] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newType, setNewType] = useState<UsageValueType>('number');
  const [newUnit, setNewUnit] = useState('');
  const [newOptions, setNewOptions] = useState('');

  function setValue(field: UsageFieldDefinition, raw: string) {
    let value: unknown = raw;
    if (field.value_type === 'number') value = raw === '' ? '' : Number(raw);
    if (field.value_type === 'boolean') value = raw === 'true';
    onChange({
      ...resource,
      usage_values: {
        ...resource.usage_values,
        [field.key]: {
          value,
          unit: valueForField(resource, field)?.unit ?? field.default_unit ?? undefined
        }
      }
    });
  }

  function setUnit(field: UsageFieldDefinition, unit: string) {
    const previous = valueForField(resource, field);
    if (!previous) return;
    onChange({
      ...resource,
      usage_values: { ...resource.usage_values, [field.key]: { ...previous, unit } }
    });
  }

  function suggest(field: UsageFieldDefinition) {
    if (field.default_value === null || field.default_value === undefined) return;
    onChange({
      ...resource,
      usage_values: {
        ...resource.usage_values,
        [field.key]: { value: field.default_value, unit: field.default_unit ?? undefined }
      }
    });
  }

  function addField() {
    const definition = usageDefinition(newKey, newLabel || newKey, newType, newUnit, newOptions);
    if (
      !definition.key ||
      fields.some((field) => field.key === definition.key) ||
      (newType === 'select' && !definition.options?.length)
    )
      return;
    const nextAdditions = [...(resource.usage_schema_additions ?? []), definition];
    const nextCreateTarget = resource.create_target
      ? {
          ...resource.create_target,
          usage_schema_jsonb: {
            fields: [...rawSchema(resource).fields, definition]
          }
        }
      : resource.create_target;
    onChange({
      ...resource,
      usage_schema_additions: nextAdditions,
      create_target: nextCreateTarget
    });
    setNewKey('');
    setNewLabel('');
    setNewUnit('');
    setNewOptions('');
    setAdding(false);
  }

  return (
    <div className='mt-3 border-t border-dashed pt-3' data-testid='usage-fields'>
      <div className='mb-2 flex items-center justify-between gap-2'>
        <span className='text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground'>
          {zh ? '本次使用值' : 'This use'}
        </span>
        <Button
          type='button'
          variant='ghost'
          size='xs'
          onClick={() => setAdding((value) => !value)}
        >
          + {zh ? '属性' : 'field'}
        </Button>
      </div>
      {fields.length === 0 && !adding && (
        <p className='text-xs text-muted-foreground'>
          {zh
            ? '暂无字段；可添加一个本资源的使用字段。'
            : 'No fields yet; add a field for this resource.'}
        </p>
      )}
      <div className='grid gap-2 sm:grid-cols-2'>
        {fields.map((field) => {
          const current = valueForField(resource, field);
          const text = usageValueText(current);
          return (
            <div key={field.key} className='grid grid-cols-[minmax(0,1fr)_4.5rem] gap-1.5'>
              <label className='grid gap-1 text-xs text-muted-foreground'>
                <span className='flex items-center justify-between gap-2'>
                  <span>{field.label}</span>
                  {field.default_value !== null &&
                    field.default_value !== undefined &&
                    !current && (
                      <button
                        type='button'
                        onClick={() => suggest(field)}
                        className='text-[10px] text-primary hover:underline'
                      >
                        {zh ? '建议' : 'suggest'} {String(field.default_value)}
                      </button>
                    )}
                </span>
                {field.value_type === 'select' ? (
                  <select
                    value={text}
                    onChange={(event) => setValue(field, event.target.value)}
                    className='h-8 rounded-lg border bg-background px-2 text-xs'
                  >
                    <option value=''>{zh ? '选择…' : 'Choose…'}</option>
                    {(field.options ?? []).map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : field.value_type === 'boolean' ? (
                  <select
                    value={text}
                    onChange={(event) => setValue(field, event.target.value)}
                    className='h-8 rounded-lg border bg-background px-2 text-xs'
                  >
                    <option value=''>{zh ? '未记录' : 'Not recorded'}</option>
                    <option value='true'>{zh ? '是' : 'Yes'}</option>
                    <option value='false'>{zh ? '否' : 'No'}</option>
                  </select>
                ) : (
                  <Input
                    type={field.value_type === 'number' ? 'number' : 'text'}
                    value={text}
                    onChange={(event) => setValue(field, event.target.value)}
                    placeholder={
                      field.default_value !== null && field.default_value !== undefined
                        ? String(field.default_value)
                        : ''
                    }
                  />
                )}
              </label>
              <label className='grid gap-1 text-xs text-muted-foreground'>
                <span>{zh ? '单位' : 'Unit'}</span>
                <Input
                  value={current?.unit ?? field.default_unit ?? ''}
                  onChange={(event) => setUnit(field, event.target.value)}
                  disabled={!current}
                  placeholder={field.default_unit ?? '—'}
                />
              </label>
            </div>
          );
        })}
      </div>
      {adding && (
        <div className='mt-3 grid gap-2 rounded-xl border border-dashed bg-muted/30 p-3 sm:grid-cols-[1fr_1fr_7rem_5rem_auto]'>
          <Input
            value={newKey}
            onChange={(event) => setNewKey(event.target.value)}
            required
            placeholder={zh ? '稳定 key' : 'Stable key'}
            aria-label={zh ? '属性 key' : 'Field key'}
          />
          <Input
            value={newLabel}
            onChange={(event) => setNewLabel(event.target.value)}
            placeholder={zh ? '显示名称' : 'Label'}
            aria-label={zh ? '属性名称' : 'Field label'}
          />
          <select
            value={newType}
            onChange={(event) => setNewType(event.target.value as UsageValueType)}
            className='h-8 rounded-lg border bg-background px-2 text-xs'
            aria-label={zh ? '值类型' : 'Value type'}
          >
            <option value='number'>number</option>
            <option value='text'>text</option>
            <option value='boolean'>boolean</option>
            <option value='select'>select</option>
          </select>
          <Input
            value={newUnit}
            onChange={(event) => setNewUnit(event.target.value)}
            placeholder={zh ? '单位' : 'Unit'}
          />
          {newType === 'select' && (
            <Input
              value={newOptions}
              onChange={(event) => setNewOptions(event.target.value)}
              placeholder={zh ? '选项，用逗号分隔' : 'Options, comma separated'}
              aria-label={zh ? '选项' : 'Options'}
            />
          )}
          <Button type='button' onClick={addField} size='sm'>
            {zh ? '添加' : 'Add'}
          </Button>
        </div>
      )}
    </div>
  );
}
