# MCP Tools

The official Python MCP SDK adapter is `api/app/agent/mcp_server.py`.

Read tools: `workspace_capabilities`, `project_context`, `project_search`, `sample_record`, `sample_lineage`, `sample_execution`, `experiment_record`, `experiment_comparison`, `data_record`, and `object_schema`.

Proposal tools: `propose_create_sample`, `propose_update_sample`, `propose_create_experiment`, `propose_update_experiment`, `propose_create_data`, and `propose_update_execution`.

Proposal tools validate the same Pydantic payloads and canonical services used by REST. They create a persisted ChangeSet preview and do not mutate scientific objects. Apply/review is performed through REST or the human review surface; the MCP adapter contains no separate graph mutation path and no embedded LLM.

All list/search inputs are bounded. Sample lineage depth is capped at 8 and project search limit at 200.
