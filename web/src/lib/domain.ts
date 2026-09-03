export type ResearchObjectKind =
  | 'material'
  | 'sample'
  | 'equipment'
  | 'process'
  | 'data'
  | 'experiment'
  | 'project';

export type RelationType =
  | 'contains'
  | 'includes'
  | 'uses'
  | 'produces'
  | 'precedes'
  | 'related_to';
export type JsonObject = Record<string, unknown>;
export type UsageValueType = 'number' | 'text' | 'boolean' | 'select';

export interface UsageFieldDefinition {
  key: string;
  label: string;
  value_type: UsageValueType;
  default_value?: unknown;
  default_unit?: string | null;
  required?: boolean;
  options?: string[];
  order?: number;
}

export interface UsageSchema {
  fields: UsageFieldDefinition[];
}

export interface UsageValue {
  value: unknown;
  unit?: string | null;
}

export interface ObjectTypeVersion {
  id: string;
  object_type_id: string;
  version: number;
  json_schema: JsonObject;
  ui_schema: JsonObject | null;
  is_active: boolean;
  created_at: string;
}

export interface ObjectType {
  id: string;
  key: string;
  kind: ResearchObjectKind;
  label_zh: string;
  label_en: string;
  description_zh: string | null;
  description_en: string | null;
  is_default: boolean;
  created_at: string;
  versions: ObjectTypeVersion[];
}

export interface ResearchObject {
  id: string;
  code: string;
  kind: ResearchObjectKind;
  title: string;
  status: string;
  project_scope_id: string | null;
  type_key: string;
  type_label_zh: string;
  type_label_en: string;
  type_version_id: string;
  type_version: number;
  properties_jsonb: JsonObject;
  usage_schema_jsonb: JsonObject;
  content_document: Array<JsonObject>;
  created_at: string;
  updated_at: string;
}

export interface ObjectRelation {
  id: string;
  source_object_id: string;
  target_object_id: string;
  relation_type: RelationType;
  role: string | null;
  properties_jsonb: JsonObject;
  source: ObjectSummary;
  target: ObjectSummary;
  created_at: string;
  updated_at: string;
}

export interface ProcessCompositionCreateTarget {
  kind: 'sample' | 'data';
  title: string;
  status?: string;
  type_version_id?: string | null;
  properties_jsonb?: JsonObject;
  content_document?: Array<JsonObject>;
}

export interface ProcessCompositionItem {
  relation_id?: string | null;
  relation_type: 'uses' | 'produces';
  target_object_id?: string | null;
  create_target?: ProcessCompositionCreateTarget | null;
  role?: string | null;
  properties_jsonb?: JsonObject;
}

export interface ProcessComposition {
  process: ResearchObject;
  uses: ObjectRelation[];
  produces: ObjectRelation[];
}

export interface SampleRecordResourceCreateTarget {
  kind: 'material' | 'equipment';
  title: string;
  code?: string | null;
  status?: string;
  type_version_id?: string | null;
  properties_jsonb?: JsonObject;
  usage_schema_jsonb?: JsonObject;
}

export interface SampleRecordResourceDraft {
  relation_id?: string | null;
  target_object_id?: string | null;
  create_target?: SampleRecordResourceCreateTarget | null;
  role?: string | null;
  usage_values?: Record<string, UsageValue>;
  usage_schema_additions?: UsageFieldDefinition[];
}

export interface SampleRecordProcessDraft {
  process_id?: string | null;
  title: string;
  status?: string;
  type_version_id?: string | null;
  properties_jsonb?: JsonObject;
  content_document?: Array<JsonObject>;
  resources: SampleRecordResourceDraft[];
}

export interface SampleRecordSampleCreate {
  title: string;
  code?: string | null;
  status?: string;
  type_version_id?: string | null;
  properties_jsonb?: JsonObject;
  content_document?: Array<JsonObject>;
}

export interface SampleRecordSampleUpdate {
  title?: string;
  status?: string;
  properties_jsonb?: JsonObject;
  content_document?: Array<JsonObject>;
}

export interface SampleRecordCreatePayload {
  project_scope_id: string;
  sample: SampleRecordSampleCreate;
  steps: SampleRecordProcessDraft[];
  change_note?: string | null;
}

export interface SampleRecordPutPayload {
  sample?: SampleRecordSampleUpdate;
  steps: SampleRecordProcessDraft[];
  change_note?: string | null;
}

export interface SampleRecordResource {
  relation_id: string;
  object: ResearchObject;
  role: string;
  usage_values: Record<string, UsageValue>;
}

export interface SampleRecordStep {
  process: ResearchObject;
  ordinal: number;
  resources: SampleRecordResource[];
}

export interface SampleRecord {
  record_sha256: string;
  sample: ResearchObject;
  steps: SampleRecordStep[];
  data: ResearchObject[];
  editable: boolean;
  edit_blockers: string[];
}

export interface ExperimentMember {
  membership_id: string;
  ordinal: number;
  note: string | null;
  sample: ResearchObject;
}

export interface ExperimentRecord {
  record_sha256: string;
  experiment: ResearchObject;
  members: ExperimentMember[];
  member_count: number;
  legacy_ownership_context: { process_count: number; sample_count: number; data_count: number };
}

export interface ComparisonValue {
  value: unknown;
  unit: string | null;
  available: boolean;
}

export interface ComparisonDimension {
  key: string;
  label: string;
  group: string;
  values: Record<string, ComparisonValue>;
  state: 'same' | 'different' | 'missing' | 'unit_conflict';
  unit_conflict: boolean;
}

export interface XYComparisonSeries {
  sample_id: string;
  sample_code: string;
  data_id: string;
  data_code: string;
  payload_id: string;
  name: string;
  x_unit: string | null;
  y_unit: string | null;
  points: DataPoint[];
}

export interface ExperimentComparison {
  experiment: ResearchObject;
  members: ResearchObject[];
  dimensions: ComparisonDimension[];
  xy_series: XYComparisonSeries[];
  differences_only: boolean;
}

export interface ProjectContext {
  record_sha256: string;
  project: ResearchObject;
  counts: Record<string, number>;
  recent_samples: ResearchObject[];
  recent_experiments: ResearchObject[];
  recent_data: ResearchObject[];
  resource_summary: Record<string, { count: number }>;
  capabilities: Record<string, unknown>;
}

export interface ProjectRecord {
  record_sha256: string;
  project: ResearchObject;
  context: ProjectContext;
}

export interface ProjectSearch {
  items: ResearchObject[];
  total: number;
  limit: number;
  offset: number;
}

export type ObjectSummary = Pick<
  ResearchObject,
  | 'id'
  | 'code'
  | 'kind'
  | 'title'
  | 'status'
  | 'project_scope_id'
  | 'type_key'
  | 'type_label_zh'
  | 'type_label_en'
>;

export interface ObjectRevision {
  id: string;
  object_id: string;
  revision_number: number;
  snapshot_jsonb: JsonObject;
  snapshot_sha256: string;
  change_note: string | null;
  created_at: string;
}

export interface Attachment {
  id: string;
  object_id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface DataPayload {
  id: string;
  data_object_id: string;
  payload_kind: 'scalar' | 'xy_series' | 'table' | 'file';
  name: string;
  schema_key: string;
  schema_version: number;
  metadata_jsonb: JsonObject;
  summary_jsonb: JsonObject;
  source_attachment_id: string | null;
  payload_sha256: string;
  points_count: number;
  table_rows_count: number;
  table_columns: Array<{
    key: string;
    label: string;
    value_type: 'number' | 'text' | 'boolean';
    unit?: string | null;
  }>;
  table_rows: Array<{
    payload_id: string;
    ordinal: number;
    source_row_number: number | null;
    values: Record<string, unknown>;
  }>;
  scalar: { payload_id: string; value: number; unit: string | null } | null;
  created_at: string;
}

export interface DataRecord {
  record_sha256: string;
  data: ResearchObject;
  payloads: DataPayload[];
  imports: DataImport[];
}

export interface DataPoint {
  payload_id: string;
  ordinal: number;
  source_row_number: number;
  x_value: number;
  y_value: number;
}

export interface DataImport {
  id: string;
  data_object_id: string;
  source_attachment_id: string;
  payload_id: string | null;
  status: 'preview_ready' | 'completed' | 'failed';
  source_format: 'csv' | 'xlsx';
  parser_key: string;
  parser_version: number;
  sheet_name: string | null;
  source_sha256: string;
  headers: string[];
  mapping_json: JsonObject | null;
  warnings: Array<{ row?: number | null; column?: string | null; message: string }>;
  errors: Array<{ row?: number | null; column?: string | null; message: string }>;
  row_count: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface ImportPreview extends DataImport {
  available_sheets: string[];
  preview_rows: unknown[][];
  column_count: number;
}

export interface SampleContext {
  current: ResearchObject;
  direct: {
    producing_processes: ResearchObject[];
    precursor_samples: ResearchObject[];
    materials: ResearchObject[];
    equipment: ResearchObject[];
    testing_processes: ResearchObject[];
    sample_inputs: Array<{
      object: ResearchObject;
      role: string;
      relation_id: string;
    }>;
    data: ResearchObject[];
  };
  upstream: LineageContext;
  downstream: LineageContext;
  experiment_context: ExperimentContext | null;
}

export interface LineageContext {
  samples: ResearchObject[];
  data: ResearchObject[];
  edges: Array<{
    id: string | null;
    source: string;
    target: string;
    type: RelationType;
    role: string | null;
  }>;
  depth: number;
  truncated: boolean;
}

export interface ExperimentContext {
  experiment: ResearchObject;
  processes: ResearchObject[];
  samples: ResearchObject[];
  input_samples: ResearchObject[];
  data: ResearchObject[];
  materials: ResearchObject[];
  equipment: ResearchObject[];
}

export interface ProjectSummary {
  project: ResearchObject;
  counts: Record<ResearchObjectKind, number>;
  recent: ResearchObject[];
}

export interface WorkspaceSummary {
  counts: Record<ResearchObjectKind, number>;
  recent: ResearchObject[];
  projects: ResearchObject[];
}

export interface ExecutionRead {
  record_sha256: string;
  execution: {
    id: string;
    sample_id: string;
    status: 'planned' | 'running' | 'completed' | 'cancelled';
    plan_snapshot_jsonb: Record<string, unknown>;
    plan_snapshot_sha256: string;
    observations: Array<Record<string, unknown>>;
    deviation_notes: Array<Record<string, unknown>>;
    started_at: string;
    completed_at: string | null;
    created_at: string;
    updated_at: string;
  };
  planned: Record<string, unknown>;
  as_run: SampleRecord;
  diff: ComparisonDimension[];
  observations: Array<Record<string, unknown>>;
  deviation_notes: Array<Record<string, unknown>>;
}

export interface ChangeSet {
  id: string;
  project_scope_id: string;
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'stale' | 'failed';
  operation_kind: string;
  target_kind: ResearchObjectKind;
  target_id: string | null;
  base_record_sha256: string | null;
  request_payload_jsonb: JsonObject;
  preview_jsonb: JsonObject;
  diff_jsonb: Array<Record<string, unknown>>;
  source_client_name: string;
  source_client_version: string | null;
  source_transport: string;
  idempotency_key: string | null;
  created_at: string;
  reviewed_at: string | null;
  applied_at: string | null;
  failure_jsonb: JsonObject | null;
}
