from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


async def _stdio_contract(project_id: str) -> dict[str, object]:
    api_root = Path(__file__).resolve().parents[1]
    database_url = os.environ["TEST_DATABASE_URL"]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.agent.mcp_server", "--transport", "stdio"],
        cwd=str(api_root),
        env={**os.environ, "DATABASE_URL": database_url},
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {
                "workspace_capabilities",
                "project_context",
                "sample_record",
                "data_record",
                "view_record",
                "claim_record",
            }.issubset(names)
            templates = await session.list_resource_templates()
            assert {template.uriTemplate for template in templates.resourceTemplates} >= {
                "project://{project_id}/context",
                "sample://{sample_id}/record",
                "data://{data_id}/record",
            }
            capabilities = await session.call_tool("workspace_capabilities", {})
            context = await session.call_tool("project_context", {"project_id": project_id})
            return {
                "capabilities": json.loads(capabilities.content[0].text),
                "context": json.loads(context.content[0].text),
            }


def test_mcp_stdio_contract_matches_rest_capabilities_and_project_context(client):
    project = client.post(
        "/api/v1/project-records",
        json={"project": {"code": "PRJ-MCP", "title": "MCP contract"}},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["project"]["id"]

    mcp = asyncio.run(_stdio_contract(project_id))
    rest_capabilities = client.get("/api/v1/capabilities")
    rest_context = client.get(f"/api/v1/projects/{project_id}/context")
    assert rest_capabilities.status_code == 200
    assert rest_context.status_code == 200
    assert mcp["capabilities"] == rest_capabilities.json()
    assert mcp["context"] == rest_context.json()


async def _http_capabilities(url: str) -> dict[str, object]:
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool("workspace_capabilities", {})
            return json.loads(response.content[0].text)


def test_mcp_streamable_http_smoke_matches_rest_capabilities(client):
    api_root = Path(__file__).resolve().parents[1]
    port = 8017
    environment = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.agent.mcp_server",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=api_root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(30):
            try:
                httpx.get(url, timeout=0.25)
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise AssertionError("MCP streamable HTTP server did not start")
        assert asyncio.run(_http_capabilities(url)) == client.get("/api/v1/capabilities").json()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
