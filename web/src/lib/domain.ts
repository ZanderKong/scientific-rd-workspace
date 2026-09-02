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

export type StructuredOutputMode = 'native_schema' | 'json_object';
export type FindingClaimType =
  | 'scientific_observation'
  | 'hypothesis'
  | 'comparative_finding'
  | 'causal_claim'
  | 'recommendation';
export type EvidenceGateStatus =
  | 'supported'
  | 'partially_supported'
  | 'insufficient_evidence'
  | 'contradicted';
export type ReviewDecisionType = 'accept' | 'reject' | 'needs_evidence';

export interface ModelProfile {
  key: string;
  provider: string;
  model: string;
  label: string;
  structured_output_mode: StructuredOutputMode;
  available: boolean;
  capability_reason: string | null;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  purpose: 'interactive' | 'evaluation_replay';
  status: 'building_context' | 'running' | 'completed' | 'failed' | 'interrupted';
  provider_key: 'litellm' | 'fixture';
  model_profile_key: string;
  structured_output_mode: StructuredOutputMode;
  requested_model: string;
  resolved_model: string | null;
  provider_response_id: string | null;
  provider_model_version: string | null;
  prompt_key: string;
  prompt_version: number;
  prompt_sha256: string;
  output_schema_version: number;
  workflow_version: number;
  generation_parameters_json: JsonObject;
  model_metadata_json: JsonObject;
  validated_output_json: JsonObject | null;
  error_code: string | null;
  error_message: string | null;
  langfuse_trace_id: string | null;
  langfuse_sync_status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  context_snapshot: AnalysisContext | null;
  findings: Finding[];
}

export interface AnalysisContext {
  id: string;
  analysis_run_id: string;
  schema_version: number;
  snapshot_json: JsonObject;
  snapshot_sha256: string;
  size_bytes: number;
  created_at: string;
}

export interface FindingEvidenceLink {
  id: string;
  evidence_record_id: string;
  role: 'supporting' | 'contradicting' | 'contextual';
  rationale: string;
  evidence_snapshot_json: JsonObject;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  finding_id: string;
  sequence_number: number;
  decision: ReviewDecisionType;
  reviewer_name: string;
  reason_code: string | null;
  comment: string | null;
  supersedes_review_id: string | null;
  created_at: string;
}

export interface Finding {
  id: string;
  project_id: string;
  analysis_run_id: string;
  ordinal: number;
  claim: string;
  claim_type: FindingClaimType;
  confidence_label: 'low' | 'medium' | 'high';
  confidence_rationale: string;
  applicability_scope: string;
  limitations_json: Array<{ code: string; description: string }>;
  risks_json: Array<{ code: string; description: string }>;
  missing_evidence_json: Array<{ code: string; description: string }>;
  comparison_assertions_json: Array<JsonObject>;
  structured_support_json: Array<JsonObject>;
  causal_target_json: JsonObject | null;
  suggested_next_experiment_json: JsonObject | null;
  model_proposed_gate_status: EvidenceGateStatus;
  model_proposed_gate_rationale: string;
  evidence_gate_status: EvidenceGateStatus;
  evidence_gate_rationale_json: JsonObject;
  gate_policy_version: number;
  review_status: 'pending_review' | 'accepted' | 'rejected' | 'needs_evidence';
  evidence_links: FindingEvidenceLink[];
  reviews: ReviewDecision[];
  created_at: string;
}

export type EvaluationCaseType = 'bad_case' | 'reference_case';
export interface EvaluationCase {
  id: string;
  project_id: string;
  case_type: EvaluationCaseType;
  source_finding_id: string;
  source_review_decision_id: string;
  context_schema_version: number;
  context_snapshot_json: JsonObject;
  model_output_snapshot_json: JsonObject;
  finding_snapshot_json: JsonObject;
  gate_snapshot_json: JsonObject;
  review_snapshot_json: JsonObject;
  expected_behavior_json: JsonObject;
  case_tags_json: string[];
  source_model_config_json: JsonObject;
  source_prompt_snapshot_json: JsonObject;
  case_hash: string;
  langfuse_dataset_item_id: string | null;
  langfuse_sync_status: string;
  langfuse_error: string | null;
  created_at: string;
}

export interface EvaluationResult {
  id: string;
  evaluation_run_id: string;
  evaluation_case_id: string;
  ordinal: number;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'error' | 'cancelled';
  replay_analysis_run_id: string | null;
  deterministic_scores_json: JsonObject;
  judge_scores_json: JsonObject | null;
  judge_metadata_json: JsonObject | null;
  failure_tags_json: string[];
  error_code: string | null;
  error_message: string | null;
  langfuse_trace_id: string | null;
  langfuse_sync_status: string;
  created_at: string;
  completed_at: string | null;
  evaluation_case: EvaluationCase | null;
}

export interface EvaluationRun {
  id: string;
  project_id: string;
  status:
    | 'queued'
    | 'running'
    | 'completed'
    | 'completed_with_errors'
    | 'failed'
    | 'interrupted'
    | 'cancel_requested'
    | 'cancelled';
  dataset_version: string;
  model_profile_key: string;
  structured_output_mode: StructuredOutputMode;
  requested_model: string;
  prompt_key: string;
  prompt_version: number;
  prompt_sha256: string;
  prompt_snapshot_json: JsonObject;
  workflow_version: number;
  output_schema_version: number;
  generation_parameters_json: JsonObject;
  judge_enabled: boolean;
  judge_model_profile_key: string | null;
  judge_structured_output_mode: string | null;
  judge_prompt_version: number | null;
  baseline_run_id: string | null;
  total_cases: number;
  completed_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
  aggregate_scores_json: JsonObject;
  regression_summary_json: JsonObject;
  error_code: string | null;
  error_message: string | null;
  langfuse_experiment_name: string | null;
  langfuse_sync_status: string;
  langfuse_error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  results: EvaluationResult[];
}
