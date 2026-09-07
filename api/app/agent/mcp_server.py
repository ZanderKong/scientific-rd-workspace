from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Sequence
from typing import Any

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.capabilities import capabilities
from app.change_set_service import propose_change_set
from app.claim_service import get_claim, get_claim_revision, list_claims_referencing
from app.core.config import get_settings
from app.data_service import get_data_record, get_data_record_revision
from app.db import SessionLocal
from app.experiment_record_service import get_experiment_record
from app.graph_query_service import DEFAULT_DEPTH, graph_query_service
from app.models import ObjectType, ObjectTypeVersion
from app.process_definition_service import get_process_definition
from app.process_execution_service import get_process_execution, get_process_execution_revision
from app.project_context_service import get_project_context, search_project
from app.record_table_service import query_record_table
from app.sample_record_service import get_sample_record, get_sample_record_revision
from app.schemas import ChangeSetProposal, RecordTableQuery
from app.services import get_object, get_type_version, object_out
from app.view_service import get_view, get_view_revision


class BearerTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        configured = get_settings().mcp_bearer_token
        if configured and token == configured:
            return AccessToken(
                token=token,
                client_id="configured-agent",
                scopes=["scientific:read", "scientific:propose"],
            )
        return None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _call(function: Any, *args: Any, **kwargs: Any) -> Any:
    with SessionLocal() as db:
        return function(db, *args, **kwargs)


def _revision_json(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "object_id": getattr(item, "object_id", None),
        "execution_id": getattr(item, "execution_id", None),
        "view_id": getattr(item, "view_id", None),
        "claim_id": getattr(item, "claim_id", None),
        "revision_number": item.revision_number,
        "snapshot_jsonb": item.snapshot_jsonb,
        "snapshot_sha256": item.snapshot_sha256,
        "change_note": item.change_note,
        "created_at": item.created_at,
    }


settings = get_settings()
auth: dict[str, Any] = {}
if settings.mcp_bearer_token:
    auth = {
        "auth": AuthSettings(
            issuer_url="http://localhost:8001",
            resource_server_url="http://localhost:8001/mcp",
            required_scopes=["scientific:read"],
        ),
        "token_verifier": BearerTokenVerifier(),
    }

mcp = FastMCP(
    "Scientific Workspace",
    instructions="Use the canonical v1.5 scientific record tools. Search before creating resources; writes from agents are proposal-first.",
    streamable_http_path="/mcp",
    stateless_http=True,
    **auth,
)
http_app = mcp.streamable_http_app()


@mcp.tool()
def workspace_capabilities() -> dict[str, Any]:
    return capabilities()


@mcp.tool()
def project_context(project_id: str) -> dict[str, Any]:
    return _call(get_project_context, uuid.UUID(project_id))


@mcp.tool()
def project_search(
    project_id: str,
    q: str = "",
    kinds: list[str] | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    return _call(
        search_project,
        uuid.UUID(project_id),
        q=q or None,
        kinds=kinds,
        status=status,
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )


@mcp.tool()
def research_object_record(object_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        item = get_object(db, uuid.UUID(object_id))
        if item is None:
            raise LookupError("research object not found")
        return object_out(item)


@mcp.tool()
def object_type_schema(kind: str, type_id: str | None = None) -> dict[str, Any]:
    with SessionLocal() as db:
        version = get_type_version(db, kind, uuid.UUID(type_id) if type_id else None)
        return {
            "kind": kind,
            "type_id": str(version.object_type_id),
            "type_key": version.object_type.key,
            "version": version.version,
            "json_schema": version.json_schema,
            "ui_schema": version.ui_schema,
        }


@mcp.tool()
def process_definition(definition_id: str) -> dict[str, Any]:
    return _call(get_process_definition, uuid.UUID(definition_id))


@mcp.tool()
def process_execution(execution_id: str) -> dict[str, Any]:
    return _call(get_process_execution, uuid.UUID(execution_id))


@mcp.tool()
def process_execution_revision(execution_id: str, revision_number: int) -> dict[str, Any]:
    return _call(
        lambda db, execution, number: _revision_json(
            get_process_execution_revision(db, execution, number)
        ),
        uuid.UUID(execution_id),
        revision_number,
    )


@mcp.tool()
def sample_record(sample_id: str) -> dict[str, Any]:
    return _call(get_sample_record, uuid.UUID(sample_id))


@mcp.tool()
def sample_record_revision(sample_id: str, revision_number: int) -> dict[str, Any]:
    return _call(get_sample_record_revision, uuid.UUID(sample_id), revision_number)


@mcp.tool()
def sample_lineage(sample_id: str, depth: int = DEFAULT_DEPTH) -> dict[str, Any]:
    return _call(
        graph_query_service.trace_sample_lineage, uuid.UUID(sample_id), min(max(depth, 0), 8)
    )


@mcp.tool()
def experiment_record(experiment_id: str) -> dict[str, Any]:
    return _call(get_experiment_record, uuid.UUID(experiment_id))


@mcp.tool()
def data_record(data_id: str) -> dict[str, Any]:
    return _call(get_data_record, uuid.UUID(data_id))


@mcp.tool()
def data_record_revision(data_id: str, revision_number: int) -> dict[str, Any]:
    return _call(
        lambda db, data, number: _revision_json(get_data_record_revision(db, data, number)),
        uuid.UUID(data_id),
        revision_number,
    )


@mcp.tool()
def view_record(view_id: str) -> dict[str, Any]:
    return _call(get_view, uuid.UUID(view_id))


@mcp.tool()
def view_revision(view_id: str, revision_number: int) -> dict[str, Any]:
    return _call(
        lambda db, view, number: _revision_json(get_view_revision(db, view, number)),
        uuid.UUID(view_id),
        revision_number,
    )


@mcp.tool()
def claim_record(claim_id: str) -> dict[str, Any]:
    return _call(get_claim, uuid.UUID(claim_id))


@mcp.tool()
def claim_revision(claim_id: str, revision_number: int) -> dict[str, Any]:
    return _call(
        lambda db, claim, number: _revision_json(get_claim_revision(db, claim, number)),
        uuid.UUID(claim_id),
        revision_number,
    )


@mcp.tool()
def record_table_query(payload: dict[str, Any]) -> dict[str, Any]:
    return _call(query_record_table, RecordTableQuery.model_validate(payload))


@mcp.tool()
def claims_referencing(object_id: str) -> list[dict[str, Any]]:
    return _call(list_claims_referencing, uuid.UUID(object_id))


def _proposal(
    operation_kind: str,
    project_id: str,
    payload: dict[str, Any],
    target_id: str | None = None,
    base_record_sha256: str | None = None,
) -> dict[str, Any]:
    proposal = ChangeSetProposal(
        operation_kind=operation_kind,
        project_scope_id=uuid.UUID(project_id),
        target_id=uuid.UUID(target_id) if target_id else None,
        base_record_sha256=base_record_sha256,
        request_payload_jsonb=payload,
        source_client_name="mcp-agent",
        source_transport="mcp",
    )
    return _call(propose_change_set, proposal)


@mcp.tool()
def propose_create_research_object(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_research_object", project_id, payload)


@mcp.tool()
def propose_update_research_object(
    project_id: str, object_id: str, base_record_sha256: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return _proposal("update_research_object", project_id, payload, object_id, base_record_sha256)


@mcp.tool()
def propose_create_process_definition(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_process_definition", project_id, payload)


@mcp.tool()
def propose_create_process_execution(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_process_execution", project_id, payload)


@mcp.tool()
def propose_create_sample_record(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_sample_record", project_id, payload)


@mcp.tool()
def propose_update_sample_record(
    project_id: str,
    sample_id: str,
    base_record_sha256: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _proposal("update_sample_record", project_id, payload, sample_id, base_record_sha256)


@mcp.tool()
def propose_create_data_record(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_data_record", project_id, payload)


@mcp.tool()
def propose_create_experiment_record(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_experiment_record", project_id, payload)


@mcp.tool()
def propose_create_view(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_view", project_id, payload)


@mcp.tool()
def propose_create_claim(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_claim", project_id, payload)


@mcp.resource("workspace://capabilities")
def capabilities_resource() -> str:
    return _json(capabilities())


@mcp.resource("project://{project_id}/context")
def project_context_resource(project_id: str) -> str:
    return _json(project_context(project_id))


@mcp.resource("project://{project_id}/schemas")
def project_schemas_resource(project_id: str) -> str:
    with SessionLocal() as db:
        project = get_object(db, uuid.UUID(project_id))
        if project is None or project.kind != "project":
            raise LookupError("project not found")
        versions = db.scalars(
            select(ObjectTypeVersion)
            .join(ObjectType)
            .where(ObjectTypeVersion.is_active.is_(True))
            .options(selectinload(ObjectTypeVersion.object_type))
            .order_by(ObjectType.kind, ObjectTypeVersion.version.desc())
        ).all()
        return _json(
            [
                {
                    "kind": version.object_type.kind,
                    "type_key": version.object_type.key,
                    "version": version.version,
                    "json_schema": version.json_schema,
                    "ui_schema": version.ui_schema,
                }
                for version in versions
            ]
        )


@mcp.resource("sample://{sample_id}/record")
def sample_record_resource(sample_id: str) -> str:
    return _json(sample_record(sample_id))


@mcp.resource("sample://{sample_id}/lineage")
def sample_lineage_resource(sample_id: str) -> str:
    return _json(sample_lineage(sample_id))


@mcp.resource("experiment://{experiment_id}/record")
def experiment_record_resource(experiment_id: str) -> str:
    return _json(experiment_record(experiment_id))


@mcp.resource("data://{data_id}/record")
def data_record_resource(data_id: str) -> str:
    return _json(data_record(data_id))


@mcp.resource("view://{view_id}/record")
def view_record_resource(view_id: str) -> str:
    return _json(view_record(view_id))


@mcp.resource("claim://{claim_id}/record")
def claim_record_resource(claim_id: str) -> str:
    return _json(claim_record(claim_id))


def run(transport: str = "stdio", *, host: str = "127.0.0.1", port: int = 8001) -> None:
    if transport == "stdio":
        mcp.run("stdio")
        return
    if host not in {"127.0.0.1", "localhost", "::1"} and not get_settings().mcp_bearer_token:
        raise RuntimeError("non-loopback MCP HTTP requires MCP_BEARER_TOKEN")
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run("streamable-http")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scientific Workspace MCP server")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    run(args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
