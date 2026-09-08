'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  createColumnHelper,
  type CellContext,
  flexRender,
  getCoreRowModel,
  type RowSelectionState,
  useReactTable
} from '@tanstack/react-table';
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs';
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet';
import { api } from '@/lib/api-client';
import type {
  DataRecord,
  RecordTableFieldRef,
  RecordTableRow,
  RecordTableValue,
  SampleRecord
} from '@/lib/domain';
import { useProjectScope } from '../project-scope/project-scope-context';
import { DataDetailBody } from '../components/scientific-detail-body';

const pageSize = 50;
const column = createColumnHelper<RecordTableRow>();

declare module '@tanstack/react-table' {
  interface TableMeta<TData extends import('@tanstack/table-core').RowData> {
    openPeek?: (id: string) => void;
  }

  interface ColumnMeta<TData extends import('@tanstack/table-core').RowData, TValue> {
    field?: RecordTableFieldRef;
  }
}

function parseColumns(value: string): RecordTableFieldRef[] {
  const fields: RecordTableFieldRef[] = [];
  for (const token of value.split(',')) {
    const [targetId, encodedFieldKey, valueType] = token.split('~');
    if (
      !targetId ||
      !encodedFieldKey ||
      !['number', 'text', 'boolean', 'select'].includes(valueType)
    )
      continue;
    try {
      fields.push({
        target_id: targetId,
        field_key: decodeURIComponent(encodedFieldKey),
        value_type: valueType as RecordTableFieldRef['value_type']
      });
    } catch {
      // Ignore a malformed shared URL token; valid columns remain usable.
    }
  }
  return fields;
}

function serializeColumns(fields: RecordTableFieldRef[]) {
  return fields
    .map(
      (field) =>
        `${field.target_id}~${encodeURIComponent(field.field_key)}~${field.value_type ?? 'text'}`
    )
    .join(',');
}

type TableFilter = RecordTableFieldRef & {
  operator: 'eq' | 'contains' | 'gte' | 'lte' | 'is_empty' | 'is_not_empty';
  value?: string | number | boolean | null;
};

function parseList(value: string) {
  return value ? value.split(',').filter(Boolean) : [];
}

function parseFilters(value: string): TableFilter[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(decodeURIComponent(value)) as unknown;
    return Array.isArray(parsed) ? (parsed as TableFilter[]) : [];
  } catch {
    return [];
  }
}

function serializeFilters(filters: TableFilter[]) {
  return filters.length ? encodeURIComponent(JSON.stringify(filters)) : '';
}

function serializeSort(field: RecordTableFieldRef | null, direction: 'asc' | 'desc') {
  return field
    ? `${field.target_id}~${encodeURIComponent(field.field_key)}~${field.value_type ?? 'text'}~${direction}`
    : '';
}

function parseSort(
  value: string
): { field: RecordTableFieldRef; direction: 'asc' | 'desc' } | null {
  if (!value) return null;
  const [targetId, encodedFieldKey, valueType, direction] = value.split('~');
  if (!targetId || !encodedFieldKey || !['asc', 'desc'].includes(direction)) return null;
  try {
    return {
      field: {
        target_id: targetId,
        field_key: decodeURIComponent(encodedFieldKey),
        value_type: ['number', 'text', 'boolean', 'select'].includes(valueType)
          ? (valueType as RecordTableFieldRef['value_type'])
          : 'text'
      },
      direction: direction as 'asc' | 'desc'
    };
  } catch {
    return null;
  }
}

function fieldKey(field: RecordTableFieldRef) {
  return `${field.target_id}:${field.field_key}`;
}

function SortableColumnChip({
  field,
  index,
  count,
  move
}: {
  field: RecordTableFieldRef;
  index: number;
  count: number;
  move: (key: string, delta: -1 | 1) => void;
}) {
  const key = fieldKey(field);
  const sortable = useSortable({ id: key });
  return (
    <span
      ref={sortable.setNodeRef}
      style={{
        transform: CSS.Transform.toString(sortable.transform),
        transition: sortable.transition
      }}
      className='inline-flex items-center gap-1 rounded border bg-background px-2 py-1'
    >
      <button
        type='button'
        aria-label={`拖动 ${field.field_key}`}
        {...sortable.attributes}
        {...sortable.listeners}
      >
        ⋮⋮
      </button>
      {field.label ?? field.field_key}
      <button
        type='button'
        aria-label={`上移 ${field.field_key}`}
        disabled={index === 0}
        onClick={() => move(key, -1)}
      >
        ↑
      </button>
      <button
        type='button'
        aria-label={`下移 ${field.field_key}`}
        disabled={index === count - 1}
        onClick={() => move(key, 1)}
      >
        ↓
      </button>
    </span>
  );
}

function renderValue(value: RecordTableValue) {
  if (value.value == null) return '未填';
  const display = typeof value.value === 'boolean' ? (value.value ? '是' : '否') : value.value;
  return `${display}${value.unit ? ` ${value.unit}` : ''}`;
}

function SampleCodeCell(info: CellContext<RecordTableRow, string>, recordKind: 'sample' | 'data') {
  return (
    <Link
      className='font-mono text-xs font-medium text-primary hover:underline'
      href={
        recordKind === 'sample'
          ? `/dashboard/samples/${info.row.original.record.id}`
          : `/dashboard/data/${info.row.original.record.id}`
      }
    >
      {info.getValue()}
    </Link>
  );
}

function SelectionCell(info: CellContext<RecordTableRow, unknown>) {
  return (
    <input
      type='checkbox'
      aria-label={`选择 ${info.row.original.record.title}`}
      checked={info.row.getIsSelected()}
      onChange={(event) => info.row.toggleSelected(event.target.checked)}
    />
  );
}

function PeekCell(info: CellContext<RecordTableRow, unknown>) {
  return (
    <Button
      variant='outline'
      size='sm'
      onClick={() => info.table.options.meta?.openPeek?.(info.row.original.record.id)}
    >
      预览
    </Button>
  );
}

function FieldValuesCell(info: CellContext<RecordTableRow, unknown>) {
  const field = info.column.columnDef.meta?.field;
  if (!field) return null;
  const values = info.row.original.values[fieldKey(field)] ?? [];
  if (values.length) {
    return <span>{values.map(renderValue).join(' · ')}</span>;
  }
  return (
    <span className='text-muted-foreground'>
      {info.row.original.referenced_target_ids.includes(field.target_id)
        ? '已引用，未填'
        : '未引用'}
    </span>
  );
}

function baseColumns(recordKind: 'sample' | 'data') {
  return [
    column.display({ id: 'select', header: '选择', cell: SelectionCell }),
    column.accessor((row) => row.record.code, {
      id: 'code',
      header: '编号',
      cell: (info) => SampleCodeCell(info, recordKind)
    }),
    column.accessor((row) => row.record.title, { id: 'title', header: '名称' }),
    column.accessor((row) => row.record.status, { id: 'status', header: '状态' }),
    column.accessor((row) => row.record.tags.join(' · '), { id: 'tags', header: '标签' }),
    column.display({ id: 'peek', header: '详情', cell: PeekCell })
  ];
}

export function RecordTableList({
  recordKind = 'sample',
  recordIds,
  embedded = false,
  onSelectionChange
}: {
  recordKind?: 'sample' | 'data';
  recordIds?: string[];
  embedded?: boolean;
  onSelectionChange?: (ids: string[]) => void;
}) {
  const { activeProjectId } = useProjectScope();
  const [query, setQuery] = useQueryState('q', parseAsString.withDefault(''));
  const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1));
  const [peek, setPeek] = useQueryState('peek', parseAsString.withOptions({ history: 'push' }));
  const [columnParam, setColumnParam] = useQueryState('columns', parseAsString.withDefault(''));
  const [requiredParam, setRequiredParam] = useQueryState(
    'required_refs',
    parseAsString.withDefault('')
  );
  const [filterParam, setFilterParam] = useQueryState('filters', parseAsString.withDefault(''));
  const [sortParam, setSortParam] = useQueryState('sort', parseAsString.withDefault(''));
  const [tableVersion, setTableVersion] = useQueryState('table_v', parseAsInteger);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [filterFieldKey, setFilterFieldKey] = useState('');
  const [filterOperator, setFilterOperator] = useState<TableFilter['operator']>('contains');
  const [filterValue, setFilterValue] = useState('');
  const selectedColumns = useMemo(() => parseColumns(columnParam), [columnParam]);
  const requiredRefs = useMemo(() => parseList(requiredParam), [requiredParam]);
  const filters = useMemo(() => parseFilters(filterParam), [filterParam]);
  const sort = useMemo(() => parseSort(sortParam), [sortParam]);
  const invalidTableConfig = Boolean(
    (columnParam && selectedColumns.length === 0) ||
    (filterParam && filters.length === 0) ||
    (sortParam && !sort) ||
    (tableVersion !== null && tableVersion !== 1)
  );
  const [columnOrder, setColumnOrder] = useState<string[]>([]);
  const columnSensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );
  useEffect(() => setRowSelection({}), [activeProjectId]);
  useEffect(() => {
    if (tableVersion === null) void setTableVersion(1);
  }, [setTableVersion, tableVersion]);
  const result = useQuery({
    queryKey: [
      'record-table',
      activeProjectId,
      recordKind,
      recordIds,
      query,
      page,
      selectedColumns,
      requiredRefs,
      filters,
      sort
    ],
    queryFn: () =>
      api.queryRecordTable({
        project_scope_id: activeProjectId,
        record_kind: recordKind,
        record_ids: recordIds,
        q: query || null,
        required_refs: requiredRefs,
        filters,
        display_columns: selectedColumns,
        sort: sort ? { ...sort.field, direction: sort.direction } : null,
        limit: pageSize,
        offset: (page - 1) * pageSize
      }),
    enabled: Boolean(activeProjectId) && (recordIds === undefined || recordIds.length > 0),
    placeholderData: (previous) => previous
  });
  const peekRecord = useQuery<SampleRecord | DataRecord>({
    queryKey: ['record-peek', recordKind, peek],
    queryFn: () =>
      recordKind === 'sample'
        ? api.getSampleRecord(peek as string)
        : api.getDataRecord(peek as string),
    enabled: Boolean(peek)
  });
  const catalogColumns = useMemo(() => result.data?.columns ?? [], [result.data?.columns]);
  const targetOptions = result.data?.available_refs ?? [];
  const initializedColumnContext = useRef<string | null>(null);
  useEffect(() => {
    const context = `${activeProjectId}:${recordIds?.join(',') ?? ''}`;
    if (!embedded || !catalogColumns.length) return;
    if (initializedColumnContext.current === context) return;
    initializedColumnContext.current = context;
    if (columnParam) return;
    void setColumnParam(serializeColumns(catalogColumns));
  }, [activeProjectId, catalogColumns, columnParam, embedded, recordIds, setColumnParam]);
  const orderedColumns = useMemo(() => {
    const known = new Map(selectedColumns.map((field) => [fieldKey(field), field]));
    const result: RecordTableFieldRef[] = [];
    for (const key of columnOrder) {
      const field = known.get(key);
      if (field) result.push(field);
    }
    for (const field of selectedColumns)
      if (!columnOrder.includes(fieldKey(field))) result.push(field);
    return result;
  }, [columnOrder, selectedColumns]);
  useEffect(() => setColumnOrder(selectedColumns.map(fieldKey)), [columnParam, selectedColumns]);
  const tableColumns = useMemo(() => {
    const defaults = baseColumns(recordKind);
    const groups = new Map<string, RecordTableFieldRef[]>();
    for (const field of orderedColumns) {
      const current = groups.get(field.target_id) ?? [];
      current.push(field);
      groups.set(field.target_id, current);
    }
    return [
      ...defaults.slice(0, -1),
      ...[...groups.entries()].map(([targetId, fields]) => {
        const first = result.data?.columns.find((candidate) => candidate.target_id === targetId);
        return column.group({
          id: `target:${targetId}`,
          header: first?.label?.split(' · ')[0] ?? 'Ref',
          columns: fields.map((field) => {
            const catalogField = result.data?.columns.find(
              (candidate) => fieldKey(candidate) === fieldKey(field)
            );
            return column.display({
              id: `field:${fieldKey(field)}`,
              header: catalogField?.label?.split(' · ').at(-1) ?? field.field_key,
              meta: { field },
              cell: FieldValuesCell
            });
          })
        });
      }),
      defaults.at(-1)!
    ];
  }, [recordKind, result.data?.columns, orderedColumns]);
  const table = useReactTable({
    data: result.data?.rows ?? [],
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.record.id,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    meta: { openPeek: (id) => void setPeek(id) },
    manualPagination: true,
    rowCount: result.data?.total ?? 0
  });
  const selected = useMemo(
    () => Object.keys(rowSelection).filter((id) => rowSelection[id]),
    [rowSelection]
  );
  useEffect(() => onSelectionChange?.(selected), [onSelectionChange, selected]);
  const totalPages = Math.max(1, Math.ceil((result.data?.total ?? 0) / pageSize));
  const visibleIds = new Set((result.data?.rows ?? []).map((row) => row.record.id));
  const hiddenSelected = selected.filter((id) => !visibleIds.has(id)).length;
  const addFilter = () => {
    const field = catalogColumns.find((candidate) => fieldKey(candidate) === filterFieldKey);
    if (!field) return;
    const value =
      field.value_type === 'number'
        ? Number(filterValue)
        : field.value_type === 'boolean'
          ? filterValue === 'true'
          : filterValue;
    if (
      !['is_empty', 'is_not_empty'].includes(filterOperator) &&
      field.value_type === 'number' &&
      !Number.isFinite(value)
    )
      return;
    const next: TableFilter = {
      ...field,
      operator: filterOperator,
      ...(filterOperator === 'is_empty' || filterOperator === 'is_not_empty' ? {} : { value })
    };
    void setFilterParam(serializeFilters([...filters, next]) || null);
    setFilterValue('');
    setPage(1);
  };
  const moveColumn = (key: string, delta: -1 | 1) => {
    const keys = orderedColumns.map(fieldKey);
    const index = keys.indexOf(key);
    const nextIndex = index + delta;
    if (index < 0 || nextIndex < 0 || nextIndex >= keys.length) return;
    [keys[index], keys[nextIndex]] = [keys[nextIndex], keys[index]];
    setColumnOrder(keys);
    const fields = keys
      .map((item) => orderedColumns.find((field) => fieldKey(field) === item))
      .filter((field): field is RecordTableFieldRef => Boolean(field));
    void setColumnParam(serializeColumns(fields) || null);
  };
  const reorderColumns = (event: DragEndEvent) => {
    if (!event.over || event.active.id === event.over.id) return;
    const keys = orderedColumns.map(fieldKey);
    const from = keys.indexOf(String(event.active.id));
    const to = keys.indexOf(String(event.over.id));
    if (from < 0 || to < 0) return;
    const next = arrayMove(keys, from, to);
    setColumnOrder(next);
    const fields = next
      .map((item) => orderedColumns.find((field) => fieldKey(field) === item))
      .filter((field): field is RecordTableFieldRef => Boolean(field));
    void setColumnParam(serializeColumns(fields) || null);
  };

  const clearFilters = () => {
    void setFilterParam(null);
    setPage(1);
  };

  return (
    <main
      className={embedded ? 'w-full' : 'mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'}
    >
      {!embedded && (
        <div className='mb-6 flex items-start justify-between gap-3'>
          <div>
            <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
              Scientific record table
            </p>
            <h1 className='mt-2 text-3xl font-semibold'>
              {recordKind === 'sample' ? 'Samples' : 'Data'}
            </h1>
            <p className='mt-2 text-sm text-muted-foreground'>
              服务器筛选与分页的 {recordKind === 'sample' ? 'Sample' : 'Data'} 记录。
            </p>
          </div>
          <Link
            href={recordKind === 'sample' ? '/dashboard/samples/new' : '/dashboard/data/new'}
            className='rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground'
          >
            {recordKind === 'sample' ? 'Create sample' : 'Record data'}
          </Link>
        </div>
      )}
      <input
        className='mb-5 h-9 w-full rounded-md border bg-background px-3 text-sm'
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setPage(1);
        }}
        placeholder='Search sample title or code…'
      />
      {invalidTableConfig && (
        <div
          role='alert'
          className='mb-5 flex items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm'
        >
          <span>分享链接中的表格配置无效，已忽略无法识别的部分。</span>
          <Button
            type='button'
            size='sm'
            variant='outline'
            onClick={() => {
              void Promise.all([
                setColumnParam(null),
                setFilterParam(null),
                setSortParam(null),
                setTableVersion(1)
              ]);
            }}
          >
            恢复默认
          </Button>
        </div>
      )}
      {!!filters.length && (
        <div className='mb-5 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-xs'>
          <span className='text-muted-foreground'>当前筛选：</span>
          {filters.map((filter, index) => (
            <button
              type='button'
              key={`${fieldKey(filter)}-active-${index}`}
              className='rounded-full border px-2 py-1 hover:border-destructive'
              onClick={() =>
                void setFilterParam(
                  serializeFilters(filters.filter((_, itemIndex) => itemIndex !== index)) || null
                )
              }
            >
              {(filter.label ?? filter.field_key) + ` ${filter.operator}`}
              {filter.value != null ? ` ${filter.value}` : ''} ×
            </button>
          ))}
          <Button type='button' variant='ghost' size='sm' onClick={clearFilters}>
            清除筛选
          </Button>
        </div>
      )}
      {!!catalogColumns.length && (
        <details className='mb-5 rounded-lg border px-3 py-2'>
          <summary className='cursor-pointer text-sm font-medium'>显示字段列</summary>
          <div className='mt-3 space-y-4'>
            <div>
              <p className='text-xs font-medium text-muted-foreground'>可见字段</p>
              <div className='mt-2 flex flex-wrap gap-3'>
                {catalogColumns.map((field) => {
                  const checked = selectedColumns.some(
                    (selected) => fieldKey(selected) === fieldKey(field)
                  );
                  return (
                    <label key={fieldKey(field)} className='flex items-center gap-2 text-sm'>
                      <input
                        type='checkbox'
                        checked={checked}
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...selectedColumns, field]
                            : selectedColumns.filter(
                                (selected) => fieldKey(selected) !== fieldKey(field)
                              );
                          void setColumnParam(serializeColumns(next) || null);
                        }}
                      />
                      {field.label ?? field.field_key}
                    </label>
                  );
                })}
              </div>
            </div>
            <div>
              <p className='text-xs font-medium text-muted-foreground'>必须包含 Ref</p>
              <div className='mt-2 flex flex-wrap gap-3'>
                {targetOptions.map((target) => {
                  const checked = requiredRefs.includes(target.id);
                  return (
                    <label key={target.id} className='flex items-center gap-2 text-sm'>
                      <input
                        type='checkbox'
                        checked={checked}
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...requiredRefs, target.id]
                            : requiredRefs.filter((id) => id !== target.id);
                          void setRequiredParam(next.join(',') || null);
                          setPage(1);
                        }}
                      />
                      {target.title}
                    </label>
                  );
                })}
              </div>
            </div>
            <div className='flex flex-wrap items-end gap-2'>
              <label className='grid gap-1 text-xs'>
                字段
                <select
                  className='h-8 min-w-44 rounded border bg-background px-2 text-sm'
                  value={filterFieldKey}
                  onChange={(event) => setFilterFieldKey(event.target.value)}
                >
                  <option value=''>选择字段</option>
                  {catalogColumns.map((field) => (
                    <option key={fieldKey(field)} value={fieldKey(field)}>
                      {field.label ?? field.field_key}
                    </option>
                  ))}
                </select>
              </label>
              <label className='grid gap-1 text-xs'>
                条件
                <select
                  className='h-8 rounded border bg-background px-2 text-sm'
                  value={filterOperator}
                  onChange={(event) =>
                    setFilterOperator(event.target.value as TableFilter['operator'])
                  }
                >
                  <option value='contains'>包含</option>
                  <option value='eq'>等于</option>
                  <option value='gte'>≥</option>
                  <option value='lte'>≤</option>
                  <option value='is_empty'>为空</option>
                  <option value='is_not_empty'>非空</option>
                </select>
              </label>
              {!['is_empty', 'is_not_empty'].includes(filterOperator) && (
                <label className='grid gap-1 text-xs'>
                  值
                  <input
                    className='h-8 rounded border bg-background px-2 text-sm'
                    value={filterValue}
                    onChange={(event) => setFilterValue(event.target.value)}
                  />
                </label>
              )}
              <Button type='button' size='sm' variant='outline' onClick={addFilter}>
                添加筛选
              </Button>
            </div>
            <div className='flex flex-wrap items-end gap-2'>
              <label className='grid gap-1 text-xs'>
                排序字段
                <select
                  className='h-8 min-w-44 rounded border bg-background px-2 text-sm'
                  value={sort ? fieldKey(sort.field) : ''}
                  onChange={(event) => {
                    const field = catalogColumns.find(
                      (candidate) => fieldKey(candidate) === event.target.value
                    );
                    void setSortParam(
                      field ? serializeSort(field, sort?.direction ?? 'asc') : null
                    );
                    setPage(1);
                  }}
                >
                  <option value=''>默认顺序</option>
                  {catalogColumns.map((field) => (
                    <option key={fieldKey(field)} value={fieldKey(field)}>
                      {field.label ?? field.field_key}
                    </option>
                  ))}
                </select>
              </label>
              <label className='grid gap-1 text-xs'>
                方向
                <select
                  className='h-8 rounded border bg-background px-2 text-sm'
                  value={sort?.direction ?? 'asc'}
                  disabled={!sort}
                  onChange={(event) => {
                    if (!sort) return;
                    void setSortParam(
                      serializeSort(sort.field, event.target.value as 'asc' | 'desc')
                    );
                    setPage(1);
                  }}
                >
                  <option value='asc'>升序</option>
                  <option value='desc'>降序</option>
                </select>
              </label>
            </div>
            {!!orderedColumns.length && (
              <div className='flex flex-wrap gap-2 text-xs'>
                <span className='py-1 text-muted-foreground'>列顺序：</span>
                <DndContext
                  sensors={columnSensors}
                  collisionDetection={closestCenter}
                  onDragEnd={reorderColumns}
                >
                  <SortableContext items={orderedColumns.map(fieldKey)}>
                    {orderedColumns.map((field, index) => (
                      <SortableColumnChip
                        key={fieldKey(field)}
                        field={field}
                        index={index}
                        count={orderedColumns.length}
                        move={moveColumn}
                      />
                    ))}
                  </SortableContext>
                </DndContext>
              </div>
            )}
          </div>
        </details>
      )}
      {selected.length > 0 && (
        <div className='mb-3 flex items-center justify-between rounded-lg border px-3 py-2 text-sm'>
          <span>
            已选择 {selected.length} 条{hiddenSelected ? `，其中 ${hiddenSelected} 条在其他页` : ''}
          </span>
          <Button variant='outline' size='sm' onClick={() => setRowSelection({})}>
            清空选择
          </Button>
        </div>
      )}
      {result.error ? (
        <p role='alert' className='text-sm text-destructive'>
          {result.error instanceof Error ? result.error.message : 'Request failed'}
        </p>
      ) : (
        <div className='overflow-hidden rounded-xl border'>
          <div className='overflow-x-auto'>
            <table className='w-full text-sm'>
              <thead className='bg-muted/50 text-left'>
                {table.getHeaderGroups().map((group) => (
                  <tr key={group.id}>
                    {group.headers.map((header) => (
                      <th
                        key={header.id}
                        colSpan={header.colSpan}
                        className='border-r px-4 py-3 font-medium last:border-r-0'
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className='border-t'>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className='px-4 py-3'>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!result.isLoading && !result.data?.rows.length && (
            <p className='border-t px-4 py-10 text-center text-sm text-muted-foreground'>
              没有符合条件的 {recordKind === 'sample' ? 'Sample' : 'Data'}。
            </p>
          )}
          <div className='flex items-center justify-between border-t px-4 py-3 text-sm'>
            <span className='text-muted-foreground'>
              共 {result.data?.total ?? 0} 条 · 第 {page}/{totalPages} 页
            </span>
            <span className='flex gap-2'>
              <Button
                variant='outline'
                size='sm'
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                上一页
              </Button>
              <Button
                variant='outline'
                size='sm'
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                下一页
              </Button>
            </span>
          </div>
        </div>
      )}
      <Sheet open={Boolean(peek)} onOpenChange={(open) => !open && setPeek(null)}>
        <SheetContent className='w-full overflow-y-auto sm:max-w-xl'>
          <SheetHeader>
            <SheetTitle>
              {peekRecord.data
                ? 'sample' in peekRecord.data
                  ? peekRecord.data.sample.title
                  : peekRecord.data.data.title
                : recordKind === 'sample'
                  ? 'Sample detail'
                  : 'Data detail'}
            </SheetTitle>
            <SheetDescription>
              {peekRecord.data
                ? 'sample' in peekRecord.data
                  ? `${peekRecord.data.sample.code} · ${peekRecord.data.sample.status}`
                  : `${peekRecord.data.data.code} · ${peekRecord.data.data.status}`
                : 'Loading scientific record…'}
            </SheetDescription>
          </SheetHeader>
          {peekRecord.error && (
            <p className='p-4 text-sm text-destructive'>
              {peekRecord.error instanceof Error ? peekRecord.error.message : 'Request failed'}
            </p>
          )}
          {peekRecord.data && (
            <div className='space-y-4 p-4'>
              {'sample' in peekRecord.data ? (
                <>
                  <p className='text-sm text-muted-foreground'>
                    {peekRecord.data.occurrences.length} Ref · {peekRecord.data.data.length} Data
                  </p>
                  {peekRecord.data.occurrences.map((occurrence) => (
                    <div key={occurrence.occurrence_id} className='rounded-lg border p-3 text-sm'>
                      <p className='font-medium'>{occurrence.label_snapshot}</p>
                      <pre className='mt-2 overflow-auto text-xs'>
                        {JSON.stringify(occurrence.values, null, 2)}
                      </pre>
                    </div>
                  ))}
                </>
              ) : (
                <DataDetailBody record={peekRecord.data} compact />
              )}
              <Link
                className='text-sm text-primary hover:underline'
                href={
                  'sample' in peekRecord.data
                    ? objectPathForSample(peekRecord.data.sample.id)
                    : `/dashboard/data/${peekRecord.data.data.id}`
                }
              >
                打开完整页面
              </Link>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </main>
  );
}

function objectPathForSample(id: string) {
  return `/dashboard/samples/${id}`;
}

export function SampleList() {
  return <RecordTableList recordKind='sample' />;
}
