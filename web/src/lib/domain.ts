export type ProjectStatus = 'active' | 'paused' | 'completed' | 'archived';
export type ExperimentStatus = 'draft' | 'planned' | 'running' | 'completed' | 'cancelled';

export type JsonObject = { [key: string]: unknown };

export interface Project {
  id: string;
  code: string;
  title: string;
  description: string | null;
  status: ProjectStatus;
  experiment_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExperimentTemplate {
  id: string;
  key: string;
  name: string;
  version: number;
  json_schema: JsonObject;
  ui_schema: JsonObject | null;
  is_active: boolean;
  created_at: string;
}

export interface Experiment {
  id: string;
  code: string;
  project_id: string;
  template_id: string;
  template_version: number;
  parent_experiment_id: string | null;
  title: string;
  status: ExperimentStatus;
  objective: string | null;
  structured_data: JsonObject;
  note_document: Array<JsonObject>;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  id: string;
  experiment_id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface RevisionExperimentSnapshot {
  title: string;
  status: ExperimentStatus;
  objective: string | null;
  template_id: string;
  template_version: number;
  structured_data: JsonObject;
  note_document: Array<JsonObject>;
}

export interface RevisionAttachmentSnapshot {
  id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number;
  sha256: string;
}

export interface RevisionSnapshot {
  snapshot_schema_version?: number;
  experiment: RevisionExperimentSnapshot;
  attachments: Array<RevisionAttachmentSnapshot>;
  measurements?: Array<{
    id: string;
    name: string;
    measurement_type: string;
    x_label: string;
    x_unit: string;
    y_label: string;
    y_unit: string;
    row_count: number;
    summary_json: JsonObject;
    points_sha256: string;
    import_id: string;
    source_attachment_id: string;
    source_sha256: string;
  }>;
  literature_links?: Array<{
    id: string;
    literature_id: string;
    relationship_type: string;
    title: string;
    authors: unknown[];
    publication_year: number | null;
    doi: string | null;
  }>;
  evidence?: Array<{
    id: string;
    claim_text: string;
    stance: string;
    source_type: string;
    source_snapshot_json: JsonObject;
    status: string;
  }>;
}

export interface Revision {
  id: string;
  experiment_id: string;
  revision_number: number;
  snapshot_json: RevisionSnapshot;
  change_note: string | null;
  created_at: string;
}

export type MeasurementType = 'spectral_response' | 'time_series' | 'other_xy';
export type ChartType = 'line' | 'scatter';
export type ImportStatus = 'preview_ready' | 'completed' | 'failed';

export interface ImportPreview {
  id: string;
  experiment_id: string;
  source_attachment_id: string;
  status: ImportStatus;
  source_format: 'csv' | 'xlsx';
  parser_key: string;
  parser_version: number;
  sheet_name: string | null;
  available_sheets: string[];
  headers: string[];
  preview_rows: unknown[][];
  row_count: number | null;
  column_count: number;
  source_sha256: string;
  warnings: Array<{ row?: number | null; column?: string | null; message: string }>;
  errors: Array<{ row?: number | null; column?: string | null; message: string }>;
  created_at: string;
}

export interface Measurement {
  id: string;
  experiment_id: string;
  import_id: string;
  name: string;
  measurement_type: MeasurementType;
  schema_key: string;
  schema_version: number;
  default_chart_type: ChartType;
  x_label: string;
  x_unit: string;
  y_label: string;
  y_unit: string;
  row_count: number;
  summary_json: { x_min: number; x_max: number; y_min: number; y_max: number; y_mean: number };
  points_sha256: string;
  source_attachment_id: string;
  source_sha256: string;
  created_at: string;
}

export interface MeasurementPoint {
  ordinal: number;
  source_row_number: number;
  x_value: number;
  y_value: number;
}

export interface Literature {
  id: string;
  project_id: string;
  item_type: string;
  title: string;
  authors: Array<{ family?: string; given?: string; literal?: string }>;
  publication_year: number | null;
  container_title: string | null;
  doi: string | null;
  url: string | null;
  abstract: string | null;
  provider: string | null;
  external_id: string | null;
  provider_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface LiteratureLink {
  id: string;
  experiment_id: string;
  literature_id: string;
  relationship_type: string;
  notes: string | null;
  created_at: string;
  literature: Literature | null;
}

export interface Evidence {
  id: string;
  project_id: string;
  context_experiment_id: string | null;
  claim_text: string;
  stance: 'supports' | 'contradicts' | 'context';
  source_type: string;
  literature_id: string | null;
  measurement_id: string | null;
  experiment_revision_id: string | null;
  locator: string | null;
  notes: string | null;
  source_snapshot_json: JsonObject;
  status: 'active' | 'withdrawn';
  withdrawal_reason: string | null;
  created_at: string;
  withdrawn_at: string | null;
}

export interface CompareResult {
  project_id: string;
  experiments: Array<
    Pick<
      Experiment,
      | 'id'
      | 'code'
      | 'title'
      | 'status'
      | 'template_id'
      | 'template_version'
      | 'parent_experiment_id'
    >
  >;
  structured_differences: Array<{
    path: string;
    label: string;
    values: Record<string, unknown>;
    differs: boolean;
  }>;
  measurements: Array<Measurement & { compatible: boolean; incompatibility_reason: string | null }>;
}
