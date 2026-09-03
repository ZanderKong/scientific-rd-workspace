import { cleanup, render } from '@testing-library/react';
import { fireEvent, screen, waitFor, within } from '@testing-library/dom';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api-client';
import type { ObjectType, ResearchObject, SampleRecord } from '@/lib/domain';
import { ProcessBlock } from './process-block';
import { ProcessCommand } from './process-command';
import { RecordView } from './sample-detail';
import { SampleComposer } from './sample-composer';
import { ResourceResolver } from './resource-resolver';
import { UsageFields } from './usage-fields';
import { recordToDraft, type DraftResource, type DraftStep } from './model';

const projectId = '00000000-0000-0000-0000-000000000001';

function object(kind: ResearchObject['kind'], id: string, title: string): ResearchObject {
  return {
    id,
    code: `${kind.slice(0, 3).toUpperCase()}-001`,
    kind,
    title,
    status: 'active',
    project_scope_id: projectId,
    type_key: `${kind}.generic`,
    type_label_zh: kind,
    type_label_en: kind,
    type_version_id: '00000000-0000-0000-0000-000000000010',
    type_version: 1,
    properties_jsonb: {},
    usage_schema_jsonb:
      kind === 'material'
        ? {
            fields: [
              {
                key: 'quantity',
                label: 'Quantity',
                value_type: 'number',
                default_unit: 'g',
                options: [],
                order: 0
              }
            ]
          }
        : kind === 'equipment'
          ? {
              fields: [
                {
                  key: 'rpm',
                  label: 'RPM',
                  value_type: 'number',
                  default_unit: 'rpm',
                  options: [],
                  order: 0
                }
              ]
            }
          : {},
    content_document: [],
    created_at: '2026-09-03T00:00:00Z',
    updated_at: '2026-09-03T00:00:00Z'
  };
}

function processType(): ObjectType {
  return {
    id: 'type-mix',
    key: 'process.mixing',
    kind: 'process',
    label_zh: '混合',
    label_en: 'Mixing',
    description_zh: null,
    description_en: null,
    is_default: false,
    created_at: '2026-09-03T00:00:00Z',
    versions: [
      {
        id: 'version-mix',
        object_type_id: 'type-mix',
        version: 1,
        json_schema: {},
        ui_schema: null,
        is_active: true,
        created_at: '2026-09-03T00:00:00Z'
      }
    ]
  };
}

function resourceDraft(resource: ResearchObject): DraftResource {
  return {
    clientId: `r-${resource.id}`,
    target_object_id: resource.id,
    role: resource.kind === 'sample' ? 'precursor' : resource.kind,
    usage_values: {},
    usage_schema_additions: [],
    object: resource
  };
}

function step(title: string, resource?: ResearchObject): DraftStep {
  return {
    clientId: `step-${title}`,
    title,
    status: 'active',
    properties_jsonb: {},
    content_document: [],
    resources: resource ? [resourceDraft(resource)] : []
  };
}

function record(editable = true): SampleRecord {
  const sample = object('sample', 'sample-1', 'Finished strip');
  const process = object('process', 'process-1', 'Mixing');
  const material = object('material', 'material-1', 'Potassium iodide');
  return {
    record_sha256: 'test-record-sha256',
    sample,
    steps: [
      {
        process,
        ordinal: 0,
        resources: [
          {
            relation_id: 'relation-1',
            object: material,
            role: 'material',
            usage_values: { quantity: { value: 1, unit: 'g' } }
          }
        ]
      }
    ],
    data: [],
    editable,
    edit_blockers: editable ? [] : ['Process has multiple preceding Process branches']
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('Sample Record interaction contract', () => {
  it('opens the / Process command and selects with Enter', async () => {
    const onSelect = vi.fn();
    render(
      <ProcessCommand
        open
        types={[processType()]}
        query=''
        zh
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onClose={vi.fn()}
      />
    );
    const input = screen.getByRole('textbox', { name: 'Process 命令' });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith({ label: '混合', typeVersionId: 'version-mix' });
  });

  it('opens @ search and moves the right-hand preview with arrows', async () => {
    const material = object('material', 'material-1', 'Potassium iodide');
    const equipment = object('equipment', 'equipment-1', 'Mixer');
    vi.spyOn(api, 'listObjects').mockResolvedValue([material, equipment]);
    render(
      <ResourceResolver projectId={projectId} zh onAttach={vi.fn()} onCreateDraft={vi.fn()} />
    );
    const input = screen.getByRole('textbox', { name: '资源解析器' });
    await userEvent.click(input);
    await waitFor(() => expect(screen.getByTestId('resource-resolver')).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText('Potassium iodide').length).toBeGreaterThan(0));
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(screen.getAllByText('Mixer').length).toBeGreaterThan(0);
    expect(screen.queryByText('asset_number:')).not.toBeInTheDocument();
  });

  it('attaches the selected resolver result with Enter', async () => {
    const material = object('material', 'material-1', 'Potassium iodide');
    vi.spyOn(api, 'listObjects').mockResolvedValue([material]);
    const onAttach = vi.fn();
    render(
      <ResourceResolver projectId={projectId} zh onAttach={onAttach} onCreateDraft={vi.fn()} />
    );
    const input = screen.getByRole('textbox', { name: '资源解析器' });
    await userEvent.click(input);
    await waitFor(() =>
      expect(screen.getByTestId('resource-option-material-1')).toBeInTheDocument()
    );
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onAttach).toHaveBeenCalledWith(material);
  });

  it('keeps Material and Equipment tokens visually distinct without category headings', () => {
    const material = object('material', 'material-1', 'Material A');
    const equipment = object('equipment', 'equipment-1', 'Equipment A');
    render(
      <ProcessBlock
        index={0}
        total={1}
        draft={{
          ...step('Mixing', material),
          resources: [resourceDraft(material), resourceDraft(equipment)]
        }}
        projectId={projectId}
        types={[]}
        zh
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMove={vi.fn()}
      />
    );
    expect(screen.getByTestId('resource-token-material')).toHaveClass('border-amber-500/35');
    expect(screen.getByTestId('resource-token-equipment')).toHaveClass('border-sky-500/35');
    expect(screen.getByTestId('resource-token-strip')).not.toHaveTextContent('原料');
    expect(screen.getByTestId('resource-token-strip')).not.toHaveTextContent('设备');
  });

  it('renders resource-specific usage fields and updates values locally', async () => {
    const material = object('material', 'material-1', 'Material A');
    const onChange = vi.fn();
    render(<UsageFields resource={resourceDraft(material)} zh onChange={onChange} />);
    expect(screen.getByText('Quantity')).toBeInTheDocument();
    await userEvent.type(screen.getByRole('spinbutton'), '4');
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.lastCall?.[0].usage_values.quantity.value).toBe(4);
  });

  it('adds a new usage field to the draft without creating an identity object', async () => {
    const equipment = object('equipment', 'equipment-1', 'Mixer');
    const onChange = vi.fn();
    render(<UsageFields resource={resourceDraft(equipment)} zh onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: '+ 属性' }));
    await userEvent.type(screen.getByRole('textbox', { name: '属性 key' }), 'torque');
    await userEvent.click(screen.getByRole('button', { name: '添加' }));
    expect(onChange.mock.lastCall?.[0].usage_schema_additions[0].key).toBe('torque');
    expect(onChange.mock.lastCall?.[0].object.id).toBe(equipment.id);
  });

  it('keeps Process parameters separate from resource usage fields', () => {
    const material = object('material', 'material-1', 'Material A');
    render(
      <ProcessBlock
        index={0}
        total={1}
        draft={{
          ...step('Mixing', material),
          properties_jsonb: { parameters: { temperature: { value: 25, unit: '°C' } } }
        }}
        projectId={projectId}
        types={[]}
        zh
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMove={vi.fn()}
      />
    );
    expect(screen.getByText('Process 参数')).toBeInTheDocument();
    expect(screen.getByText('本次使用值')).toBeInTheDocument();
    expect(screen.getByDisplayValue('25')).toBeInTheDocument();
  });

  it('renders multiple Process blocks in their ordered chain', () => {
    vi.spyOn(api, 'listTypes').mockResolvedValue([]);
    render(<SampleComposer projectId={projectId} zh />);
    expect(screen.getByTestId('process-block-0')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '添加 Process' }));
    expect(screen.getByTestId('process-block-1')).toBeInTheDocument();
  });

  it('supports keyboard reorder from a Process title', () => {
    const onMove = vi.fn();
    render(
      <ProcessBlock
        index={0}
        total={2}
        draft={step('Mixing')}
        projectId={projectId}
        types={[]}
        zh
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMove={onMove}
      />
    );
    fireEvent.keyDown(screen.getByRole('textbox', { name: '第 1 个 Process' }), {
      key: 'ArrowDown',
      altKey: true
    });
    expect(onMove).toHaveBeenCalledWith(1);
  });

  it('submits with Ctrl+Enter and exposes the three explicit success actions', async () => {
    vi.spyOn(api, 'listTypes').mockResolvedValue([]);
    const saved = record();
    vi.spyOn(api, 'createSampleRecord').mockResolvedValue(saved);
    render(<SampleComposer projectId={projectId} zh />);
    await userEvent.type(screen.getByRole('textbox', { name: 'Sample 标题' }), 'New record');
    await userEvent.type(screen.getByRole('textbox', { name: '第 1 个 Process' }), 'Mixing');
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Sample 标题' }), {
      key: 'Enter',
      ctrlKey: true
    });
    await waitFor(() => expect(screen.getByTestId('sample-success')).toBeInTheDocument());
    expect(screen.getByText('查看样品')).toBeInTheDocument();
    expect(screen.getByText('基于此样品新建')).toBeInTheDocument();
    expect(screen.getByText('录入全新样品')).toBeInTheDocument();
  });

  it('clone draft removes Sample and Process IDs while retaining resource identity and values', () => {
    const cloned = recordToDraft(record());
    expect(cloned.sample.code).toBe('');
    expect(cloned.steps[0].process_id).toBeUndefined();
    expect(cloned.steps[0].resources[0].relation_id).toBeUndefined();
    expect(cloned.steps[0].resources[0].target_object_id).toBe('material-1');
    expect(cloned.steps[0].resources[0].usage_values.quantity.value).toBe(1);
  });

  it('shows a complex graph as viewable but without a destructive edit action', () => {
    const onEdit = vi.fn();
    render(<RecordView record={record(false)} zh onEdit={onEdit} onClone={vi.fn()} />);
    expect(screen.getByText('这是可查看但不可安全编辑的复杂图结构')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '编辑记录' })).not.toBeInTheDocument();
    expect(screen.getByText(/multiple preceding/)).toBeInTheDocument();
  });

  it('opens a token identity preview without changing the resource object', async () => {
    const material = object('material', 'material-1', 'Material A');
    render(
      <ProcessBlock
        index={0}
        total={1}
        draft={{ ...step('Mixing', material) }}
        projectId={projectId}
        types={[]}
        zh
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMove={vi.fn()}
      />
    );
    await userEvent.click(screen.getByTestId('resource-token-material'));
    expect(screen.getByTestId('resource-preview')).toHaveTextContent('Material A');
  });

  it('supports inline resource creation as a draft payload', async () => {
    const onCreateDraft = vi.fn();
    render(
      <ResourceResolver projectId={projectId} zh onAttach={vi.fn()} onCreateDraft={onCreateDraft} />
    );
    await userEvent.click(screen.getByRole('textbox', { name: '资源解析器' }));
    await userEvent.click(screen.getByRole('button', { name: /内联创建/ }));
    await userEvent.type(screen.getByPlaceholderText('名称'), 'New material');
    await userEvent.type(screen.getByPlaceholderText('CAS'), '50-00-0');
    await userEvent.click(screen.getByRole('button', { name: '加入草稿' }));
    expect(onCreateDraft).toHaveBeenCalledWith({
      kind: 'material',
      title: 'New material',
      properties_jsonb: { cas: '50-00-0' }
    });
  });

  it('resource resolver keeps mixed kinds in one ordered stream', async () => {
    const material = object('material', 'material-1', 'Material A');
    const equipment = object('equipment', 'equipment-1', 'Equipment A');
    vi.spyOn(api, 'listObjects').mockResolvedValue([material, equipment]);
    render(
      <ResourceResolver projectId={projectId} zh onAttach={vi.fn()} onCreateDraft={vi.fn()} />
    );
    await userEvent.click(screen.getByRole('textbox', { name: '资源解析器' }));
    await waitFor(() =>
      expect(screen.getByTestId('resource-option-material-1')).toBeInTheDocument()
    );
    const list = screen.getByTestId('resource-resolver');
    expect(within(list).getAllByText('Material A').length).toBeGreaterThan(0);
    expect(within(list).getAllByText('Equipment A').length).toBeGreaterThan(0);
  });
});
