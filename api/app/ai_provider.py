from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.core.config import Settings

T = TypeVar("T", bound=BaseModel)


class ProviderFailure(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ModelProfile:
    key: str
    model: str
    label: str
    provider: str
    structured_output_mode: str
    native_schema_verified: bool = False
    json_object_verified: bool = False
    available: bool = True
    capability_reason: str | None = None


@dataclass(frozen=True)
class AIRequest:
    model: str
    structured_output_mode: str
    messages: list[dict[str, str]]
    response_schema: dict[str, Any]
    timeout: float
    max_output_tokens: int
    temperature: float = 0.0
    seed: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIResult:
    parsed: dict[str, Any]
    raw_output: str
    requested_model: str
    resolved_model: str | None
    response_id: str | None
    provider_model_version: str | None
    usage: dict[str, Any]
    finish_reason: str | None
    latency_ms: int


class AIProvider(Protocol):
    def generate_structured(self, request: AIRequest, response_model: type[T]) -> AIResult: ...


def _profile_provider(model: str) -> str:
    if model.startswith("fixture://"):
        return "fixture"
    return model.split("/", 1)[0] if "/" in model else "fixture"


def load_model_profiles(settings: Settings) -> dict[str, ModelProfile]:
    try:
        raw = json.loads(settings.ai_model_profiles_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, ModelProfile] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            continue
        model = item.get("model")
        label = item.get("label")
        mode = item.get("structured_output_mode")
        if not all(isinstance(value, str) and value.strip() for value in (model, label, mode)):
            continue
        if mode not in {"native_schema", "json_object"}:
            continue
        result[key] = ModelProfile(
            key=key,
            model=model,
            label=label,
            provider=item.get("provider") or _profile_provider(model),
            structured_output_mode=mode,
            native_schema_verified=bool(item.get("native_schema_verified", False)),
            json_object_verified=bool(item.get("json_object_verified", False)),
        )
    return result


class FixtureProvider:
    """Deterministic provider used by tests, local demo, and CI."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response

    def generate_structured(self, request: AIRequest, response_model: type[T]) -> AIResult:
        started = time.perf_counter()
        payload = self.response or self._default_response(request.metadata.get("context", {}))
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        response_model.model_validate(payload)
        return AIResult(
            parsed=payload,
            raw_output=raw,
            requested_model=request.model,
            resolved_model=request.model,
            response_id=f"fixture-{uuid.uuid4()}",
            provider_model_version="fixture-v1",
            usage={"prompt_tokens": 0, "completion_tokens": len(raw)},
            finish_reason="stop",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _default_response(context: dict[str, Any]) -> dict[str, Any]:
        measurements = context.get("measurements", [])
        experiments = context.get("experiments", [])
        findings: list[dict[str, Any]] = []
        if len(measurements) >= 2:
            left = measurements[0]
            right = measurements[-1]
            left_id = left["id"]
            right_id = right["id"]
            left_value = left.get("summary_json", {}).get("y_mean")
            right_value = right.get("summary_json", {}).get("y_mean")
            relation = "greater_than" if right_value > left_value else "less_than"
            findings.append(
                {
                    "claim": (
                        f"{right.get('name', right_id)} has a "
                        f"{relation.replace('_', ' ')} frozen y_mean than "
                        f"{left.get('name', left_id)}."
                    ),
                    "claim_type": "comparative_finding",
                    "confidence_label": "high",
                    "confidence_rationale": (
                        "The relation is recomputed from frozen Measurement summaries."
                    ),
                    "applicability_scope": "Selected frozen Measurements only.",
                    "evidence_links": [],
                    "structured_support_assertions": [
                        {
                            "kind": "measurement_comparison",
                            "left_measurement_id": left_id,
                            "right_measurement_id": right_id,
                            "metric": "y_mean",
                            "relation": relation,
                            "rationale": "Direct comparison of frozen summaries.",
                        }
                    ],
                    "limitations": [],
                    "risks": [],
                    "missing_evidence": [],
                    "comparison_assertions": [],
                    "causal_target": None,
                    "suggested_next_experiment": None,
                    "proposed_gate": {
                        "status": "supported",
                        "rationale": "The comparison is directly verifiable.",
                    },
                }
            )
            if len(experiments) >= 3:
                changed_paths = [
                    item["path"]
                    for item in context.get("factor_differences", [])
                    if item.get("differs")
                ]
                findings.append(
                    {
                        "claim": "Starch caused the improvement from the baseline formulation.",
                        "claim_type": "causal_claim",
                        "confidence_label": "medium",
                        "confidence_rationale": (
                            "The outcome comparison is clear but the design is confounded."
                        ),
                        "applicability_scope": "Selected frozen experiments only.",
                        "evidence_links": [],
                        "structured_support_assertions": [
                            {
                                "kind": "measurement_comparison",
                                "left_measurement_id": left_id,
                                "right_measurement_id": right_id,
                                "metric": "y_mean",
                                "relation": relation,
                                "rationale": "Outcome comparison only; not causal proof.",
                            }
                        ],
                        "limitations": [
                            {
                                "code": "confounded_variables",
                                "description": "KI and starch changed together.",
                            }
                        ],
                        "risks": [],
                        "missing_evidence": [
                            {
                                "code": "missing_isolating_control",
                                "description": "Need baseline plus starch without KI.",
                            }
                        ],
                        "comparison_assertions": [],
                        "causal_target": {
                            "factor_paths": changed_paths or ["/additives"],
                            "baseline_experiment_id": experiments[0]["experiment_id"],
                            "outcome_experiment_id": experiments[-1]["experiment_id"],
                            "outcome_measurement_ids": [right_id],
                        },
                        "suggested_next_experiment": None,
                        "proposed_gate": {
                            "status": "supported",
                            "rationale": "The output comparison appears clear.",
                        },
                    }
                )
        if not findings:
            raise ProviderFailure(
                "fixture_context_insufficient", "fixture needs at least two measurements"
            )
        return {"analysis_summary": "Deterministic fixture analysis.", "findings": findings}


class LiteLLMProvider:
    def __init__(self, profile: ModelProfile) -> None:
        self.profile = profile

    @staticmethod
    def capability(profile: ModelProfile) -> tuple[bool, str | None]:
        try:
            import litellm

            params = litellm.get_supported_openai_params(model=profile.model)
        except Exception as exc:  # provider metadata is best-effort during preflight
            return False, f"capability lookup failed: {type(exc).__name__}"
        if profile.structured_output_mode == "native_schema":
            if not profile.native_schema_verified:
                return False, "native_schema requires profile smoke validation"
            supported = "response_format" in (params or [])
        else:
            supported = "response_format" in (params or [])
        return supported, None if supported else "provider does not advertise response_format"

    def generate_structured(self, request: AIRequest, response_model: type[T]) -> AIResult:
        try:
            import litellm
        except ImportError as exc:
            raise ProviderFailure("provider_unavailable", "LiteLLM SDK is not installed") from exc
        response_format: dict[str, Any]
        if request.structured_output_mode == "native_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "scientific_analysis_response_v1",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }
        elif request.structured_output_mode == "json_object":
            response_format = {"type": "json_object"}
        else:
            raise ProviderFailure("unsupported_structured_output", "unknown structured output mode")
        started = time.perf_counter()
        try:
            response = litellm.completion(
                model=request.model,
                messages=request.messages,
                response_format=response_format,
                timeout=request.timeout,
                max_tokens=request.max_output_tokens,
                temperature=request.temperature,
                seed=request.seed,
            )
        except Exception as exc:
            error_name = exc.__class__.__name__.lower()
            status_code = getattr(exc, "status_code", None)
            if status_code is None:
                response_obj = getattr(exc, "response", None)
                status_code = getattr(response_obj, "status_code", None)
            if isinstance(status_code, int) and status_code >= 500:
                code = "provider_server_error"
            elif "timeout" in error_name:
                code = "provider_timeout"
            elif "auth" in error_name or "permission" in error_name:
                code = "provider_auth"
            elif "rate" in error_name or "thrott" in error_name:
                code = "provider_rate_limit"
            elif "connection" in error_name or "unavailable" in error_name:
                code = "provider_unavailable"
            else:
                code = "provider_error"
            raise ProviderFailure(
                code,
                str(exc)[:1000],
                retryable=code
                in {
                    "provider_timeout",
                    "provider_rate_limit",
                    "provider_unavailable",
                    "provider_server_error",
                },
            ) from exc
        try:
            choice = response.choices[0]
            content = choice.message.content
            if isinstance(content, dict):
                payload = content
                raw = json.dumps(content, sort_keys=True)
            elif isinstance(content, str):
                raw = content
                payload = json.loads(content)
            else:
                raise TypeError("provider content was not a JSON object")
            if not isinstance(payload, dict):
                raise TypeError("provider JSON value was not an object")
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderFailure(
                "invalid_provider_json", "provider did not return a JSON object"
            ) from exc
        usage = getattr(response, "usage", None)
        usage_json = (
            usage.model_dump() if hasattr(usage, "model_dump") else (dict(usage) if usage else {})
        )
        return AIResult(
            parsed=payload,
            raw_output=raw,
            requested_model=request.model,
            resolved_model=getattr(response, "model", None),
            response_id=getattr(response, "id", None),
            provider_model_version=getattr(response, "system_fingerprint", None),
            usage=usage_json,
            finish_reason=getattr(choice, "finish_reason", None),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class PromptRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, key: str, version: int) -> tuple[str, str]:
        path = self.root / key / f"v{version}.md"
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ProviderFailure("prompt_not_found", f"prompt {key} v{version} not found") from exc
        import hashlib

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return content, digest


class LangfuseAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.langfuse_enabled
            and self.settings.langfuse_public_key
            and self.settings.langfuse_secret_key
        )

    def trace_id(self, analysis_run_id: uuid.UUID) -> str:
        # The SDK creates a valid trace ID while preserving deterministic seed correlation.
        return f"analysis-run:{analysis_run_id}"

    def record_analysis(
        self, run_id: uuid.UUID, request: AIRequest, result: AIResult
    ) -> str | None:
        trace_id = self.trace_id(run_id)
        if not self.enabled:
            return None
        try:
            from langfuse import Langfuse

            client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                base_url=self.settings.langfuse_base_url,
            )
            sdk_trace_id = client.create_trace_id(seed=trace_id)
            safe_metadata = {
                "analysis_run_id": str(run_id),
                "model": request.model,
                "structured_output_mode": request.structured_output_mode,
                "usage": result.usage,
                "latency_ms": result.latency_ms,
                "finish_reason": result.finish_reason,
                "status": "completed",
                **{
                    key: value
                    for key, value in request.metadata.items()
                    if key.endswith("_sha256") or key.endswith("_version") or key.endswith("_key")
                },
            }
            content = request.messages if self.settings.langfuse_capture_content else None
            output = result.parsed if self.settings.langfuse_capture_content else None
            observation = client.start_observation(
                trace_context={"trace_id": sdk_trace_id},
                name="scientific-analysis",
                as_type="generation",
                input=content,
                output=output,
                metadata=safe_metadata,
                model=request.model,
                usage_details=result.usage,
            )
            observation.end()
            client.flush()
            return sdk_trace_id
        except Exception as exc:
            raise ProviderFailure("langfuse_sync_failed", str(exc)[:1000]) from exc
