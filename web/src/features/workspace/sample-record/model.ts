import type {
  JsonObject,
  ResearchObject,
  SampleRecord,
  SampleRecordProcessDraft,
  SampleRecordResourceDraft,
  UsageFieldDefinition,
  UsageSchema,
  UsageValue,
  UsageValueType
} from '@/lib/domain';

export type DraftResource = Omit<
  SampleRecordResourceDraft,
  'usage_values' | 'usage_schema_additions'
> & {
  clientId: string;
  object?: ResearchObject;
  usage_values: Record<string, UsageValue>;
  usage_schema_additions: UsageFieldDefinition[];
};

export type DraftStep = Omit<SampleRecordProcessDraft, 'resources'> & {
  clientId: string;
  resources: DraftResource[];
};

export type SampleRecordDraft = {
  sample: {
    title: string;
    code?: string;
    status: string;
  };
  steps: DraftStep[];
};

let nextClientId = 0;

export function clientId(prefix: string) {
  nextClientId += 1;
  return `${prefix}-${nextClientId}`;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

export function usageSchema(object?: ResearchObject): UsageSchema {
  const raw = object?.usage_schema_jsonb;
  if (!raw || !Array.isArray(raw.fields)) return { fields: [] };
  return {
    fields: raw.fields.filter((field): field is UsageFieldDefinition => {
      if (!field || typeof field !== 'object') return false;
      const candidate = field as Record<string, unknown>;
      return typeof candidate.key === 'string' && typeof candidate.label === 'string';
    })
  };
}

export function usageValueText(value?: UsageValue) {
  if (value === undefined || value.value === null || value.value === '') return '';
  if (typeof value.value === 'boolean') return value.value ? 'true' : 'false';
  return String(value.value);
}

export function resourceLabel(object?: ResearchObject, fallback?: SampleRecordResourceDraft) {
  if (object) return object.title;
  if (fallback?.create_target) return `${fallback.create_target.title} · draft`;
  return 'Resource';
}

export function objectKindLabel(kind: ResearchObject['kind'], zh: boolean) {
  const labels: Record<ResearchObject['kind'], [string, string]> = {
    material: ['原料', 'Material'],
    equipment: ['设备', 'Equipment'],
    sample: ['前驱样品', 'Precursor Sample'],
    process: ['过程', 'Process'],
    data: ['数据', 'Data'],
    experiment: ['实验', 'Experiment'],
    project: ['项目', 'Project']
  };
  return labels[kind][zh ? 0 : 1];
}

export function processParameters(properties?: JsonObject): Record<string, UsageValue> {
  const candidate = properties?.parameters;
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return {};
  return Object.fromEntries(
    Object.entries(candidate as Record<string, unknown>).filter(([, value]) => {
      return Boolean(
        value && typeof value === 'object' && !Array.isArray(value) && 'value' in value
      );
    })
  ) as Record<string, UsageValue>;
}

export function withProcessParameters(
  properties: JsonObject | undefined,
  parameters: Record<string, UsageValue>
): JsonObject {
  const next = clone(properties ?? {});
  next.parameters = parameters;
  return next;
}

export function buildNewDraft(projectId: string): SampleRecordDraft {
  void projectId;
  return {
    sample: { title: '', code: '', status: 'draft' },
    steps: [
      {
        clientId: clientId('step'),
        title: '',
        status: 'active',
        properties_jsonb: {},
        content_document: [],
        resources: []
      }
    ]
  };
}

export function recordToDraft(record: SampleRecord): SampleRecordDraft {
  return {
    sample: {
      title: record.sample.title,
      code: '',
      status: record.sample.status
    },
    steps: record.steps.map((step) => ({
      clientId: clientId('step'),
      process_id: undefined,
      title: step.process.title,
      status: step.process.status,
      type_version_id: step.process.type_version_id,
      properties_jsonb: clone(step.process.properties_jsonb),
      content_document: clone(step.process.content_document),
      resources: step.resources.map((resource) => ({
        clientId: clientId('resource'),
        relation_id: undefined,
        target_object_id: resource.object.id,
        role: resource.role,
        usage_values: clone(resource.usage_values),
        usage_schema_additions: [],
        object: clone(resource.object)
      }))
    }))
  };
}

export function draftToCreatePayload(projectId: string, draft: SampleRecordDraft) {
  return {
    project_scope_id: projectId,
    sample: {
      title: draft.sample.title,
      code: draft.sample.code?.trim() || undefined,
      status: draft.sample.status
    },
    steps: draft.steps.map(
      ({ clientId: _clientId, process_id: _processId, resources, ...step }) => ({
        ...step,
        resources: resources.map(
          ({ clientId: _resourceId, object: _object, ...resource }) => resource
        )
      })
    )
  };
}

export function draftToPutPayload(draft: SampleRecordDraft) {
  return {
    sample: {
      title: draft.sample.title,
      status: draft.sample.status
    },
    steps: draft.steps.map(({ clientId: _clientId, resources, ...step }) => ({
      ...step,
      resources: resources.map(
        ({ clientId: _resourceId, object: _object, ...resource }) => resource
      )
    }))
  };
}

export function usageDefinition(
  key: string,
  label: string,
  valueType: UsageValueType,
  unit: string,
  optionsText = ''
): UsageFieldDefinition {
  const options = optionsText
    .split(',')
    .map((option) => option.trim())
    .filter(Boolean);
  return {
    key: key.trim(),
    label: label.trim(),
    value_type: valueType,
    default_unit: unit.trim() || undefined,
    required: false,
    options: valueType === 'select' ? options : [],
    order: 0
  };
}
