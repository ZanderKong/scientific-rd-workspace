from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.capabilities import capabilities
from app.change_set_service import propose_change_set
from app.core.config import get_settings
from app.data_service import get_data_record
from app.db import SessionLocal
from app.execution_service import get_execution
from app.experiment_comparison_service import compare_experiment
from app.experiment_record_service import get_experiment_record
from app.graph_query_service import DEFAULT_DEPTH, graph_query_service
from app.models import ObjectType, ObjectTypeVersion
from app.project_context_service import get_project_context, search_project
from app.sample_record_service import get_sample_record
from app.schemas import ChangeSetProposal
from app.services import get_object, get_type_version


class BearerTokenVerifier:
    """Minimal token verifier for explicitly configured local/reverse-proxy tokens."""

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


_settings = get_settings()
_auth: dict[str, Any] = {}
if _settings.mcp_bearer_token:
    _auth = {
        "auth": AuthSettings(
            issuer_url="http://localhost:8001",
            resource_server_url="http://localhost:8001/mcp",
            required_scopes=["scientific:read"],
        ),
        "token_verifier": BearerTokenVerifier(),
    }

mcp = FastMCP(
    "Scientific Workspace",
    instructions=(
        "Use high-level scientific domain tools. Search before creating resources; "
        "writes are proposal-first and never silently overwrite records."
    ),
    streamable_http_path="/mcp",
    stateless_http=True,
    **_auth,
)
http_app = mcp.streamable_http_app()


@mcp.tool()
def workspace_capabilities() -> dict[str, Any]:
    return capabilities()


@mcp.tool()
def project_context(project_id: str) -> dict[str, Any]:
    import uuid

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
    import uuid

    bounded_limit = min(max(limit, 1), 200)
    return _call(
        search_project,
        uuid.UUID(project_id),
        q=q or None,
        kinds=kinds,
        status=status,
        limit=bounded_limit,
        offset=max(offset, 0),
    )


@mcp.tool()
def sample_record(sample_id: str) -> dict[str, Any]:
    import uuid

    return _call(get_sample_record, uuid.UUID(sample_id))


@mcp.tool()
def sample_lineage(sample_id: str, depth: int = DEFAULT_DEPTH) -> dict[str, Any]:
    import uuid

    return _call(
        graph_query_service.trace_sample_lineage, uuid.UUID(sample_id), min(max(depth, 0), 8)
    )


@mcp.tool()
def sample_execution(sample_id: str) -> dict[str, Any]:
    import uuid

    return _call(get_execution, uuid.UUID(sample_id))


@mcp.tool()
def experiment_record(experiment_id: str) -> dict[str, Any]:
    import uuid

    return _call(get_experiment_record, uuid.UUID(experiment_id))


@mcp.tool()
def experiment_comparison(experiment_id: str, differences_only: bool = False) -> dict[str, Any]:
    import uuid

    return _call(compare_experiment, uuid.UUID(experiment_id), differences_only=differences_only)


@mcp.tool()
def data_record(data_id: str) -> dict[str, Any]:
    import uuid

    return _call(get_data_record, uuid.UUID(data_id))


@mcp.tool()
def object_schema(kind: str, type_id: str | None = None) -> dict[str, Any]:
    import uuid

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


def _proposal(
    operation_kind: str,
    project_id: str,
    payload: dict[str, Any],
    target_id: str | None,
    base_record_sha256: str | None,
) -> dict[str, Any]:
    import uuid

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
def propose_create_sample(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_sample_record", project_id, payload, None, None)


@mcp.tool()
def propose_update_sample(
    project_id: str, sample_id: str, base_record_sha256: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return _proposal("update_sample_record", project_id, payload, sample_id, base_record_sha256)


@mcp.tool()
def propose_create_experiment(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_experiment_record", project_id, payload, None, None)


@mcp.tool()
def propose_update_experiment(
    project_id: str, experiment_id: str, base_record_sha256: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return _proposal(
        "update_experiment_record", project_id, payload, experiment_id, base_record_sha256
    )


@mcp.tool()
def propose_create_data(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _proposal("create_data_record", project_id, payload, None, None)


@mcp.tool()
def propose_update_execution(
    project_id: str, sample_id: str, base_record_sha256: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return _proposal("update_execution", project_id, payload, sample_id, base_record_sha256)


@mcp.resource("workspace://capabilities")
def capabilities_resource() -> str:
    return _json(capabilities())


@mcp.resource("project://{project_id}/context")
def project_context_resource(project_id: str) -> str:
    return _json(project_context(project_id))


@mcp.resource("project://{project_id}/schemas")
def project_schemas_resource(project_id: str) -> str:
    import uuid

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


@mcp.resource("sample://{sample_id}/execution")
def sample_execution_resource(sample_id: str) -> str:
    return _json(sample_execution(sample_id))


@mcp.resource("sample://{sample_id}/lineage")
def sample_lineage_resource(sample_id: str) -> str:
    return _json(sample_lineage(sample_id))


@mcp.resource("experiment://{experiment_id}/record")
def experiment_record_resource(experiment_id: str) -> str:
    return _json(experiment_record(experiment_id))


@mcp.resource("experiment://{experiment_id}/comparison")
def experiment_comparison_resource(experiment_id: str) -> str:
    return _json(experiment_comparison(experiment_id))


@mcp.resource("data://{data_id}/record")
def data_record_resource(data_id: str) -> str:
    return _json(data_record(data_id))


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
