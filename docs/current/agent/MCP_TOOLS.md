# MCP Tools v1.5

The official adapter is `api/app/agent/mcp_server.py`. It calls canonical services and does not contain a second domain model.

Read tools:

- `workspace_capabilities`
- `project_context`, `project_search`
- `research_object_record`, `object_type_schema`
- `process_definition`, `process_execution`
- `sample_record`, `sample_lineage`
- `sample_record_revision`
- `experiment_record`, `data_record`
- `view_record`, `claim_record`
- `record_table_query`, `claims_referencing`

Proposal tools:

- `propose_create_research_object`
- `propose_update_research_object`
- `propose_create_process_definition`
- `propose_create_process_execution`
- `propose_create_sample_record`, `propose_update_sample_record`
- `propose_create_data_record`
- `propose_create_experiment_record`
- `propose_create_view`
- `propose_create_claim`

All proposal tools persist a ChangeSet preview and do not mutate scientific records. Review/apply remains an explicit REST or human action. Search limits and lineage depth are bounded.

The contract suite compares `workspace_capabilities` and `project_context` over MCP with their canonical REST counterparts. It also discovers the published tools and resource templates through a real stdio MCP session and exercises `workspace_capabilities` over Streamable HTTP.
