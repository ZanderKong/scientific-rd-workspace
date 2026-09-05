export type ResearchObjectKind =
  | 'research_object'
  | 'process_definition'
  | 'data'
  | 'experiment'
  | 'project'
  | 'view'
  | 'claim';

export type RelationType = 'references' | 'subject' | 'derived_from' | 'related_to';
export type JsonObject = Record<string, unknown>;
export type BindingDirection = 'input' | 'context' | 'output';
export type RepresentationKind = 'raw_file' | 'table' | 'image' | 'description' | 'structured';
export type ValueType = 'number' | 'text' | 'boolean' | 'select';

export interface UsageFieldDefinition {
  key: string;
  label: string;
  value_type: ValueType;
  default_value?: unknown;
  default_unit?: string | null;
  required?: boolean;
  options?: string[];
  order?: number;
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
  type_version_id: string | null;
  type_version: number | null;
  tags: string[];
  properties_jsonb: JsonObject;
  process_field_definitions: JsonObject;
  content_document: JsonObject[];
  created_at: string;
  updated_at: string;
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

export interface ObjectRevision {
  id: string;
  object_id: string;
  revision_number: number;
  snapshot_jsonb: JsonObject;
  snapshot_sha256: string;
  change_note: string | null;
  created_at: string;
}

export interface ProcessDefinitionVersion {
  id: string;
  process_definition_id: string;
  version: number;
  description: string | null;
  execution_field_definitions: JsonObject;
  ui_schema: JsonObject | null;
  created_at: string;
}

export interface ProcessDefinition {
  process_definition: ResearchObject;
  current_version: ProcessDefinitionVersion;
  versions: ProcessDefinitionVersion[];
}

export interface ProcessExecutionObjectBinding {
  id: string;
  research_object_id: string;
  direction: BindingDirection;
  role: string | null;
  field_definition_snapshot: JsonObject;
  values: Record<string, { value: unknown; unit?: string | null }>;
  order_index: number;
  object: ResearchObject;
}

export interface ProcessExecutionDataBinding {
  id: string;
  data_id: string;
  direction: 'input' | 'output';
  role: string | null;
  values: JsonObject;
  order_index: number;
  data: ResearchObject;
}

export interface ProcessExecution {
  record_sha256: string;
  id: string;
  project_scope_id: string | null;
  process_definition_id: string;
  process_definition_version_id: string;
  title_snapshot: string | null;
  status: string;
  execution_field_definitions: JsonObject;
  values: JsonObject;
  note: string | null;
  occurred_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  source_view_id?: string | null;
  source_view_revision_id?: string | null;
  object_bindings: ProcessExecutionObjectBinding[];
  data_bindings: ProcessExecutionDataBinding[];
  precedes_execution_ids: string[];
}

export interface ProcessExecutionObjectBindingDraft {
  research_object_id: string;
  direction: BindingDirection;
  role?: string | null;
  values?: Record<string, { value: unknown; unit?: string | null }>;
  order_index?: number;
}

export interface ProcessExecutionDataBindingDraft {
  data_id: string;
  direction: 'input' | 'output';
  role?: string | null;
  values?: JsonObject;
  order_index?: number;
}

export interface ProcessExecutionDraft {
  execution_id?: string | null;
  process_definition_id: string;
  process_definition_version_id?: string | null;
  project_scope_id?: string | null;
  title_snapshot?: string | null;
  status?: 'draft' | 'running' | 'completed' | 'cancelled';
  values?: JsonObject;
  note?: string | null;
  object_bindings: ProcessExecutionObjectBindingDraft[];
  data_bindings?: ProcessExecutionDataBindingDraft[];
  precedes_execution_ids?: string[];
  source_view_id?: string | null;
  source_view_revision_id?: string | null;
}

export interface SampleRecordStep {
  execution: ProcessExecution;
  ordinal: number;
}
export interface SampleRecord {
  record_sha256: string;
  sample: ResearchObject;
  steps: SampleRecordStep[];
  data: ResearchObject[];
  editable: boolean;
  edit_blockers: string[];
}

export interface SampleRecordCreatePayload {
  project_scope_id: string;
  sample: {
    title: string;
    code?: string | null;
    status?: string;
    tags?: string[];
    properties_jsonb?: JsonObject;
    process_field_definitions?: JsonObject;
    content_document?: JsonObject[];
  };
  steps: ProcessExecutionDraft[];
  change_note?: string | null;
}
export interface SampleRecordPutPayload {
  sample?: JsonObject;
  steps: ProcessExecutionDraft[];
  change_note?: string | null;
}

export interface ExperimentReference {
  relation_id: string;
  role: string | null;
  note: string | null;
  order_index: number;
  object: ResearchObject;
}
export interface ExperimentRecord {
  record_sha256: string;
  experiment: ResearchObject;
  references: Record<string, ExperimentReference[]>;
}
export interface ExperimentReferenceDraft {
  target_id: string;
  target_kind?: ResearchObjectKind;
  role?: string | null;
  note?: string | null;
  order_index?: number;
}

export interface DataRepresentation {
  id: string;
  data_object_id: string;
  kind: RepresentationKind;
  name: string;
  format: string | null;
  schema_jsonb: JsonObject;
  metadata_jsonb: JsonObject;
  summary_jsonb: JsonObject;
  inline_payload_jsonb: JsonObject | null;
  asset_id: string | null;
  source_representation_id: string | null;
  provenance_jsonb: JsonObject;
  representation_sha256: string;
  points_count: number;
  table_rows_count: number;
  table_rows: Array<{ ordinal: number; values: JsonObject }>;
  scalar: { value: number; unit: string | null } | null;
  created_at: string;
}
export interface DataRecord {
  record_sha256: string;
  data: ResearchObject;
  scientific_type: string | null;
  description: string | null;
  origin_representation_id: string | null;
  representations: DataRepresentation[];
  subjects: ResearchObject[];
  derived_from: ResearchObject[];
  imports: DataImport[];
}
export interface Asset {
  id: string;
  storage_backend: string;
  bucket: string | null;
  object_key: string;
  original_filename: string;
  mime_type: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
}
export interface DataImport {
  id: string;
  data_object_id: string;
  source_asset_id: string;
  representation_id: string | null;
  status: string;
  source_format: string;
  parser_key: string;
  parser_version: number;
  sheet_name: string | null;
  source_sha256: string;
  headers: string[];
  mapping_json: JsonObject | null;
  warnings: JsonObject[];
  errors: JsonObject[];
  row_count: number | null;
  created_at: string;
  completed_at: string | null;
  available_sheets?: string[];
  preview_rows?: unknown[][];
  column_count?: number;
}

export interface ViewRevision {
  id: string;
  view_id: string;
  revision_number: number;
  snapshot_jsonb: JsonObject;
  snapshot_sha256: string;
  change_note: string | null;
  created_at: string;
}
export interface ViewRecord {
  record_sha256: string;
  view: ResearchObject;
  description: string | null;
  config: JsonObject;
  data: ResearchObject[];
  current_revision_id: string | null;
  revisions: ViewRevision[];
}
export interface ClaimEvidence {
  id: string;
  evidence_kind: 'data' | 'view' | 'claim' | 'external';
  evidence_id: string | null;
  external_ref: string | null;
  polarity: 'support' | 'counter';
  note: string | null;
  order_index: number;
  object: ResearchObject | null;
}
export interface ClaimRecord {
  record_sha256: string;
  claim: ResearchObject;
  statement: string;
  source_type: string;
  source_ref: string | null;
  confidence: string | null;
  metadata_jsonb: JsonObject;
  evidence: ClaimEvidence[];
  current_revision_id: string | null;
  revisions: JsonObject[];
}

export interface ProjectContext {
  record_sha256: string;
  project: ResearchObject;
  counts: Record<string, number>;
  recent_research_objects: ResearchObject[];
  recent_experiments: ResearchObject[];
  recent_data: ResearchObject[];
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
export interface ProjectSummary {
  project: ResearchObject;
  counts: Record<string, number>;
  recent: ResearchObject[];
}
export interface WorkspaceSummary {
  counts: Record<string, number>;
  recent: ResearchObject[];
  projects: ResearchObject[];
}
export interface ChangeSet {
  id: string;
  project_scope_id: string;
  status: string;
  operation_kind: string;
  target_kind: ResearchObjectKind;
  target_id: string | null;
  base_record_sha256: string | null;
  request_payload_jsonb: JsonObject;
  preview_jsonb: JsonObject;
  diff_jsonb: JsonObject[];
  source_client_name: string;
  source_client_version: string | null;
  source_transport: string;
  idempotency_key: string | null;
  created_at: string;
  reviewed_at: string | null;
  applied_at: string | null;
  failure_jsonb: JsonObject | null;
}
