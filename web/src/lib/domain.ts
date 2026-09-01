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

export interface Revision {
  id: string;
  experiment_id: string;
  revision_number: number;
  snapshot_json: JsonObject;
  change_note: string | null;
  created_at: string;
}
