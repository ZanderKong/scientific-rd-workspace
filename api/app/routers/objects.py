from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.capabilities import capabilities
from app.change_set_service import (
    apply_change_set,
    change_set_out,
    list_change_sets,
    propose_change_set,
    review_change_set,
)
from app.claim_service import create_claim, get_claim, update_claim
from app.core.config import get_settings
from app.data_service import (
    create_data_record,
    create_representation,
    get_data_record,
    representation_out,
    set_system_relations,
    update_data_record,
)
from app.db import get_db
from app.experiment_record_service import (
    create_experiment_record,
    get_experiment_record,
    update_experiment_record,
)
from app.graph_query_service import DEFAULT_DEPTH, MAX_DEPTH, graph_query_service
from app.idempotency_service import IdempotencyReplay, run_idempotent
from app.import_service import ImportValidationError, commit_import, create_preview
from app.models import (
    Asset,
    ChangeSet,
    DataImport,
    DataRepresentation,
    ObjectAssetLink,
    ObjectRelation,
    ObjectRevision,
    ObjectType,
    ResearchObject,
)
from app.process_definition_service import (
    create_process_definition,
    create_process_definition_version,
    get_process_definition,
    list_process_definitions,
)
from app.process_execution_service import (
    create_process_execution,
    execution_out,
    get_process_execution,
    list_process_executions_for_data,
    list_process_executions_for_object,
    update_process_execution,
)
from app.project_context_service import (
    create_project_record,
    get_project_context,
    get_project_record,
    search_project,
    update_project_record,
)
from app.relation_semantics import SemanticConflict
from app.sample_record_service import create_sample_record, get_sample_record, update_sample_record
from app.schemas import (
    AssetOut,
    ChangeSetOut,
    ChangeSetProposal,
    ChangeSetReview,
    ClaimCreate,
    ClaimOut,
    ClaimPut,
    DataImportOut,
    DataRecordCreate,
    DataRecordOut,
    DataRecordPut,
    DataRepresentationCreate,
    DataRepresentationOut,
    ExperimentRecordCreate,
    ExperimentRecordOut,
    ExperimentRecordPut,
    ImportCommitMapping,
    ImportPreviewOut,
    ImportPreviewRequest,
    ObjectCreate,
    ObjectKind,
    ObjectPatch,
    ObjectRelationOut,
    ObjectRevisionOut,
    ObjectTypeOut,
    ProcessDefinitionCreate,
    ProcessDefinitionOut,
    ProcessDefinitionVersionCreate,
    ProcessDefinitionVersionOut,
    ProcessExecutionCreate,
    ProcessExecutionOut,
    ProcessExecutionPut,
    ProjectContextOut,
    ProjectRecordCreate,
    ProjectRecordOut,
    ProjectRecordPut,
    ProjectSearchOut,
    RelationCreate,
    RelationPatch,
    ResearchObjectOut,
    RevisionCreate,
    SampleContextOut,
    SampleRecordCreate,
    SampleRecordOut,
    SampleRecordPut,
    ViewCreate,
    ViewOut,
    ViewPut,
    WorkspaceSummaryOut,
)
from app.services import (
    create_object,
    create_relation,
    create_revision,
    get_object,
    get_relation,
    list_relations,
    object_out,
    relation_out,
    serialize_asset,
    sha256_json,
    update_object,
    update_relation,
)
from app.storage import (
    LocalStorageProvider,
    S3StorageProvider,
    StorageProvider,
    StorageRouter,
    sanitise_filename,
)
from app.view_service import create_view, get_view, list_view_revisions, update_view

router = APIRouter(tags=["research-object-graph"])


def _storage() -> StorageRouter:
    settings = get_settings()
    local = LocalStorageProvider(settings.storage_root)
    s3 = None
    if settings.s3_bucket:
        s3 = S3StorageProvider(
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
        )
    return StorageRouter(
        local,
        s3,
        image_to_s3=settings.storage_image_to_s3,
        large_file_threshold=settings.storage_large_file_threshold,
    )


def _provider_for_asset(storage: StorageRouter, asset: Asset) -> StorageProvider:
    if asset.storage_backend == "s3":
        if storage.s3 is None:
            raise RuntimeError("S3 storage is not configured")
        return storage.s3
    return storage.local


def _error(exc: Exception) -> HTTPException:
    raw = str(exc)
    parsed: dict[str, Any] = {}
    if raw.startswith("{"):
        try:
            candidate = json.loads(raw)
            if isinstance(candidate, dict):
                parsed = candidate
        except json.JSONDecodeError:
            pass
    code = getattr(exc, "code", None) or parsed.get("code")
    if not code:
        if isinstance(exc, LookupError):
            code = "not_found"
        elif isinstance(exc, IntegrityError):
            code = "semantic_conflict"
        elif "scope" in raw.lower():
            code = "scope_conflict"
        elif "stale" in raw.lower():
            code = "stale_record"
        else:
            code = "validation_failed" if isinstance(exc, ValueError) else "internal_error"
    if isinstance(exc, LookupError):
        status_code = 404
    elif isinstance(exc, (SemanticConflict, IntegrityError)):
        status_code = 409
    elif isinstance(exc, ValueError):
        status_code = 422
    else:
        status_code = 500
    if code in {"stale_record", "idempotency_conflict", "change_set_stale"}:
        status_code = 409
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": parsed.get("message") or raw or "internal server error",
                "path": None,
                "details": parsed.get("errors") or parsed.get("details") or {},
                "request_id": str(uuid.uuid4()),
            }
        },
    )


def _if_match(current_hash: str, provided: str | None) -> None:
    if provided is not None and provided.strip('"') != current_hash:
        raise HTTPException(
            status_code=412,
            detail={
                "error": {
                    "code": "stale_record",
                    "message": "The record changed after it was loaded.",
                    "details": {"expected": provided, "actual": current_hash},
                }
            },
        )


def _run_idempotent(
    db: Session, key: str | None, payload: Any, operation: Any, response_status: int
) -> dict[str, Any] | JSONResponse:
    try:
        return run_idempotent(db, key, payload, operation, response_status=response_status)
    except IdempotencyReplay as replay:
        return JSONResponse(content=replay.response_json, status_code=replay.status_code)


def _import_out(item: DataImport, *, preview: bool = False) -> dict[str, Any]:
    metadata = item.metadata_jsonb or {}
    result = {
        "id": item.id,
        "data_object_id": item.data_object_id,
        "source_asset_id": item.source_asset_id,
        "representation_id": item.representation_id,
        "status": item.status,
        "source_format": item.source_format,
        "parser_key": item.parser_key,
        "parser_version": item.parser_version,
        "sheet_name": item.sheet_name,
        "source_sha256": item.source_sha256,
        "headers": item.header_json,
        "mapping_json": item.mapping_json,
        "warnings": item.warnings_json,
        "errors": item.errors_json,
        "row_count": item.row_count,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
    }
    if preview:
        result.update(
            {
                "available_sheets": metadata.get("available_sheets", []),
                "preview_rows": metadata.get("preview_rows", []),
                "column_count": metadata.get("column_count", len(item.header_json)),
            }
        )
    return result


@router.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    return capabilities()


@router.get("/object-types", response_model=list[ObjectTypeOut])
def object_types(db: Session = Depends(get_db)) -> list[ObjectType]:
    return list(
        db.scalars(
            select(ObjectType)
            .options(selectinload(ObjectType.versions))
            .order_by(ObjectType.kind, ObjectType.key)
        )
    )


@router.get("/object-types/{type_id}", response_model=ObjectTypeOut)
def object_type(type_id: uuid.UUID, db: Session = Depends(get_db)) -> ObjectType:
    item = db.scalar(
        select(ObjectType)
        .where(ObjectType.id == type_id)
        .options(selectinload(ObjectType.versions))
    )
    if item is None:
        raise HTTPException(status_code=404, detail="object type not found")
    return item


@router.get("/objects", response_model=list[ResearchObjectOut])
def objects(
    kind: ObjectKind | None = None,
    kinds: list[ObjectKind] | None = Query(default=None),
    project_scope_id: uuid.UUID | None = None,
    type_key: str | None = None,
    type_id: uuid.UUID | None = None,
    status: str | None = None,
    q: str | None = None,
    include_global: bool = True,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ResearchObjectOut]:
    items = graph_query_service.search_objects(
        db,
        q=q,
        kind=kind,
        kinds=kinds,
        project_scope_id=project_scope_id,
        type_key=type_key,
        type_id=type_id,
        status=status,
        include_global=include_global,
        limit=limit,
        offset=offset,
    )
    return [ResearchObjectOut.model_validate(object_out(item)) for item in items]


@router.post("/objects", response_model=ResearchObjectOut, status_code=201)
def post_object(payload: ObjectCreate, db: Session = Depends(get_db)) -> ResearchObjectOut:
    try:
        return ResearchObjectOut.model_validate(object_out(create_object(db, payload)))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}", response_model=ResearchObjectOut)
def get_object_route(object_id: uuid.UUID, db: Session = Depends(get_db)) -> ResearchObjectOut:
    item = get_object(db, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return ResearchObjectOut.model_validate(object_out(item))


@router.patch("/objects/{object_id}", response_model=ResearchObjectOut)
def patch_object(
    object_id: uuid.UUID,
    payload: ObjectPatch,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ResearchObjectOut:
    item = get_object(db, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="research object not found")
    try:
        _if_match(sha256_json(object_out(item)), if_match)
        updated = update_object(db, item, payload.model_dump(exclude_unset=True))
        response.headers["ETag"] = f'"{sha256_json(object_out(updated))}"'
        return ResearchObjectOut.model_validate(object_out(updated))
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}/relations", response_model=list[ObjectRelationOut])
def get_object_relations(
    object_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ObjectRelationOut]:
    if get_object(db, object_id) is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return [
        ObjectRelationOut.model_validate(relation_out(item))
        for item in list_relations(db, object_id)
    ]


@router.post("/relations", response_model=ObjectRelationOut, status_code=201)
def post_relation(payload: RelationCreate, db: Session = Depends(get_db)) -> ObjectRelationOut:
    try:
        return ObjectRelationOut.model_validate(relation_out(create_relation(db, payload)))
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.patch("/relations/{relation_id}", response_model=ObjectRelationOut)
def patch_relation(
    relation_id: uuid.UUID, payload: RelationPatch, db: Session = Depends(get_db)
) -> ObjectRelationOut:
    item = get_relation(db, relation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="relation not found")
    try:
        return ObjectRelationOut.model_validate(relation_out(update_relation(db, item, payload)))
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(relation_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    item = db.get(ObjectRelation, relation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="relation not found")
    db.delete(item)
    db.commit()


@router.post("/objects/{object_id}/revisions", response_model=ObjectRevisionOut, status_code=201)
def post_revision(
    object_id: uuid.UUID, payload: RevisionCreate, db: Session = Depends(get_db)
) -> ObjectRevisionOut:
    try:
        return ObjectRevisionOut.model_validate(
            create_revision(db, object_id, payload.change_note), from_attributes=True
        )
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}/revisions", response_model=list[ObjectRevisionOut])
def object_revisions(object_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ObjectRevision]:
    return list(
        db.scalars(
            select(ObjectRevision)
            .where(ObjectRevision.object_id == object_id)
            .order_by(ObjectRevision.revision_number)
        )
    )


@router.get("/objects/{object_id}/revisions/{revision_number}", response_model=ObjectRevisionOut)
def object_revision(
    object_id: uuid.UUID, revision_number: int, db: Session = Depends(get_db)
) -> ObjectRevision:
    item = db.scalar(
        select(ObjectRevision).where(
            ObjectRevision.object_id == object_id, ObjectRevision.revision_number == revision_number
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="revision not found")
    return item


@router.post("/process-definitions", response_model=ProcessDefinitionOut, status_code=201)
def post_process_definition(
    payload: ProcessDefinitionCreate, db: Session = Depends(get_db)
) -> ProcessDefinitionOut:
    try:
        return ProcessDefinitionOut.model_validate(create_process_definition(db, payload))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/process-definitions", response_model=list[ProcessDefinitionOut])
def process_definitions(
    project_scope_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ProcessDefinitionOut]:
    return [
        ProcessDefinitionOut.model_validate(item)
        for item in list_process_definitions(
            db, project_scope_id=project_scope_id, q=q, limit=limit
        )
    ]


@router.get("/process-definitions/{definition_id}", response_model=ProcessDefinitionOut)
def process_definition(
    definition_id: uuid.UUID, db: Session = Depends(get_db)
) -> ProcessDefinitionOut:
    try:
        return ProcessDefinitionOut.model_validate(get_process_definition(db, definition_id))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post(
    "/process-definitions/{definition_id}/versions",
    response_model=ProcessDefinitionVersionOut,
    status_code=201,
)
def post_process_definition_version(
    definition_id: uuid.UUID, payload: ProcessDefinitionVersionCreate, db: Session = Depends(get_db)
) -> ProcessDefinitionVersionOut:
    try:
        return ProcessDefinitionVersionOut.model_validate(
            create_process_definition_version(db, definition_id, payload)
        )
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/process-executions", response_model=ProcessExecutionOut, status_code=201)
def post_process_execution(
    payload: ProcessExecutionCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ProcessExecutionOut | JSONResponse:
    try:
        result = _run_idempotent(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_process_execution(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return ProcessExecutionOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/process-executions/{execution_id}", response_model=ProcessExecutionOut)
def process_execution(
    execution_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> ProcessExecutionOut:
    try:
        result = get_process_execution(db, execution_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProcessExecutionOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/process-executions/{execution_id}", response_model=ProcessExecutionOut)
def put_process_execution(
    execution_id: uuid.UUID,
    payload: ProcessExecutionPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ProcessExecutionOut:
    try:
        current = get_process_execution(db, execution_id)
        _if_match(current["record_sha256"], if_match)
        result = update_process_execution(
            db,
            execution_id,
            payload.model_copy(
                update={
                    "base_record_sha256": payload.base_record_sha256 or current["record_sha256"]
                }
            ),
        )
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProcessExecutionOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}/process-executions", response_model=list[ProcessExecutionOut])
def object_process_executions(
    object_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProcessExecutionOut]:
    return [
        ProcessExecutionOut.model_validate(execution_out(db, item))
        for item in list_process_executions_for_object(db, object_id)
    ]


@router.get("/data/{data_id}/process-executions", response_model=list[ProcessExecutionOut])
def data_process_executions(
    data_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProcessExecutionOut]:
    return [
        ProcessExecutionOut.model_validate(execution_out(db, item))
        for item in list_process_executions_for_data(db, data_id)
    ]


@router.get("/samples/{sample_id}/record", response_model=SampleRecordOut)
def sample_record(
    sample_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> SampleRecordOut:
    try:
        result = get_sample_record(db, sample_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return SampleRecordOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/sample-records", response_model=SampleRecordOut, status_code=201)
def post_sample_record(
    payload: SampleRecordCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SampleRecordOut | JSONResponse:
    try:
        result = _run_idempotent(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_sample_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return SampleRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.put("/samples/{sample_id}/record", response_model=SampleRecordOut)
def put_sample_record(
    sample_id: uuid.UUID,
    payload: SampleRecordPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> SampleRecordOut:
    try:
        current = get_sample_record(db, sample_id)
        _if_match(current["record_sha256"], if_match)
        result = update_sample_record(db, sample_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return SampleRecordOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/samples/{sample_id}/context", response_model=SampleContextOut)
def sample_context(
    sample_id: uuid.UUID,
    depth: int = Query(DEFAULT_DEPTH, ge=0, le=MAX_DEPTH),
    db: Session = Depends(get_db),
) -> SampleContextOut:
    try:
        return SampleContextOut.model_validate(
            graph_query_service.get_sample_context(db, sample_id, depth)
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/objects/{object_id}/lineage")
def object_lineage(
    object_id: uuid.UUID,
    depth: int = Query(DEFAULT_DEPTH, ge=0, le=MAX_DEPTH),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return graph_query_service.trace_object_lineage(db, object_id, depth)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/experiment-records", response_model=ExperimentRecordOut, status_code=201)
def post_experiment_record(
    payload: ExperimentRecordCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ExperimentRecordOut | JSONResponse:
    try:
        result = _run_idempotent(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_experiment_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return ExperimentRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/experiments/{experiment_id}/record", response_model=ExperimentRecordOut)
def experiment_record(
    experiment_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> ExperimentRecordOut:
    try:
        result = get_experiment_record(db, experiment_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExperimentRecordOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/experiments/{experiment_id}/record", response_model=ExperimentRecordOut)
def put_experiment_record(
    experiment_id: uuid.UUID,
    payload: ExperimentRecordPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ExperimentRecordOut:
    try:
        current = get_experiment_record(db, experiment_id)
        _if_match(current["record_sha256"], if_match)
        result = update_experiment_record(db, experiment_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExperimentRecordOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/experiments/{experiment_id}/context", response_model=ExperimentRecordOut)
def experiment_context(
    experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> ExperimentRecordOut:
    return experiment_record(experiment_id, Response(), db)


@router.post("/data-records", response_model=DataRecordOut, status_code=201)
def post_data_record(
    payload: DataRecordCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DataRecordOut | JSONResponse:
    try:
        result = _run_idempotent(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_data_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return DataRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/data/{data_id}/record", response_model=DataRecordOut)
def data_record(
    data_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> DataRecordOut:
    try:
        result = get_data_record(db, data_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return DataRecordOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/data/{data_id}/record", response_model=DataRecordOut)
def put_data_record(
    data_id: uuid.UUID,
    payload: DataRecordPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> DataRecordOut:
    try:
        current = get_data_record(db, data_id)
        _if_match(current["record_sha256"], if_match)
        result = update_data_record(db, data_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return DataRecordOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post(
    "/data/{data_id}/representations", response_model=DataRepresentationOut, status_code=201
)
def post_representation(
    data_id: uuid.UUID, payload: DataRepresentationCreate, db: Session = Depends(get_db)
) -> DataRepresentationOut:
    try:
        return DataRepresentationOut.model_validate(create_representation(db, data_id, payload))
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/data/{data_id}/representations", response_model=list[DataRepresentationOut])
def data_representations(
    data_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[DataRepresentationOut]:
    if get_object(db, data_id) is None:
        raise HTTPException(status_code=404, detail="data not found")
    items = db.scalars(
        select(DataRepresentation)
        .where(DataRepresentation.data_object_id == data_id)
        .options(
            selectinload(DataRepresentation.points),
            selectinload(DataRepresentation.scalar),
            selectinload(DataRepresentation.table_rows),
        )
        .order_by(DataRepresentation.created_at)
    ).all()
    return [DataRepresentationOut.model_validate(representation_out(item)) for item in items]


@router.get(
    "/data/{data_id}/representations/{representation_id}", response_model=DataRepresentationOut
)
def representation(
    data_id: uuid.UUID, representation_id: uuid.UUID, db: Session = Depends(get_db)
) -> DataRepresentationOut:
    item = db.scalar(
        select(DataRepresentation)
        .where(
            DataRepresentation.id == representation_id, DataRepresentation.data_object_id == data_id
        )
        .options(
            selectinload(DataRepresentation.points),
            selectinload(DataRepresentation.scalar),
            selectinload(DataRepresentation.table_rows),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="representation not found")
    return DataRepresentationOut.model_validate(representation_out(item))


@router.put("/data/{data_id}/relations", status_code=204)
def put_data_relations(
    data_id: uuid.UUID,
    subjects: list[uuid.UUID] = Query(default=[]),
    derived_from: list[uuid.UUID] = Query(default=[]),
    db: Session = Depends(get_db),
) -> None:
    try:
        set_system_relations(db, data_id, subject_ids=subjects, derived_from_ids=derived_from)
        db.commit()
    except (LookupError, ValueError, IntegrityError, SemanticConflict) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/views", response_model=ViewOut, status_code=201)
def post_view(payload: ViewCreate, db: Session = Depends(get_db)) -> ViewOut:
    try:
        return ViewOut.model_validate(create_view(db, payload))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/views/{view_id}", response_model=ViewOut)
def view(view_id: uuid.UUID, response: Response, db: Session = Depends(get_db)) -> ViewOut:
    try:
        result = get_view(db, view_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ViewOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/views/{view_id}", response_model=ViewOut)
def put_view(
    view_id: uuid.UUID,
    payload: ViewPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ViewOut:
    try:
        current = get_view(db, view_id)
        _if_match(current["record_sha256"], if_match or payload.base_record_sha256)
        result = update_view(db, view_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ViewOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/views/{view_id}/revisions", response_model=list[dict[str, Any]])
def view_revisions(view_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        return list_view_revisions(db, view_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/claims", response_model=ClaimOut, status_code=201)
def post_claim(payload: ClaimCreate, db: Session = Depends(get_db)) -> ClaimOut:
    try:
        return ClaimOut.model_validate(create_claim(db, payload))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/claims/{claim_id}", response_model=ClaimOut)
def claim(claim_id: uuid.UUID, response: Response, db: Session = Depends(get_db)) -> ClaimOut:
    try:
        result = get_claim(db, claim_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ClaimOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/claims/{claim_id}", response_model=ClaimOut)
def put_claim(
    claim_id: uuid.UUID,
    payload: ClaimPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ClaimOut:
    try:
        current = get_claim(db, claim_id)
        _if_match(current["record_sha256"], if_match or payload.base_record_sha256)
        result = update_claim(db, claim_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ClaimOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/objects/{object_id}/assets", response_model=AssetOut, status_code=201)
def upload_asset(
    object_id: uuid.UUID,
    file: UploadFile = File(...),
    role: str = "attachment",
    db: Session = Depends(get_db),
) -> AssetOut:
    obj = get_object(db, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="research object not found")
    settings = get_settings()
    filename = sanitise_filename(file.filename or "asset")
    mime_type = file.content_type or "application/octet-stream"
    storage = _storage()
    provider = storage.choose(mime_type=mime_type)
    object_key = f"objects/{object_id}/{uuid.uuid4()}-{filename}"
    try:
        size, digest = provider.put(object_key, file.file)
        if size > settings.max_upload_bytes:
            provider.delete(object_key)
            raise ValueError("uploaded asset exceeds size limit")
        asset = Asset(
            storage_backend=provider.backend,
            bucket=getattr(provider, "bucket", None),
            object_key=object_key,
            original_filename=filename,
            mime_type=mime_type,
            size_bytes=size,
            sha256=digest,
        )
        db.add(asset)
        db.flush()
        db.add(ObjectAssetLink(object_id=obj.id, asset_id=asset.id, role=role, order_index=0))
        db.commit()
        db.refresh(asset)
        return AssetOut.model_validate(serialize_asset(asset))
    except Exception as exc:
        db.rollback()
        try:
            provider.delete(object_key)
        except Exception:
            pass
        if isinstance(exc, (LookupError, ValueError, IntegrityError)):
            raise _error(exc) from exc
        raise


@router.get("/objects/{object_id}/assets", response_model=list[AssetOut])
def object_assets(object_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AssetOut]:
    links = db.scalars(
        select(ObjectAssetLink)
        .where(ObjectAssetLink.object_id == object_id)
        .options(selectinload(ObjectAssetLink.asset))
    ).all()
    return [AssetOut.model_validate(serialize_asset(link.asset)) for link in links]


@router.get("/assets/{asset_id}/download", response_model=None)
def download_asset(
    asset_id: uuid.UUID, db: Session = Depends(get_db)
) -> FileResponse | JSONResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    storage = _storage()
    provider = _provider_for_asset(storage, asset)
    if asset.storage_backend == "s3" and hasattr(provider, "presigned_url"):
        return JSONResponse({"url": provider.presigned_url(asset.object_key), "expires_in": 900})
    path = provider.open(asset.object_key)
    if not isinstance(path, Path):
        raise HTTPException(status_code=500, detail="storage provider cannot stream this asset")
    return FileResponse(
        path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.original_filename,
    )


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    try:
        _provider_for_asset(_storage(), asset).delete(asset.object_key)
        db.delete(asset)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/data/{data_id}/imports", response_model=list[DataImportOut])
def data_imports(data_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DataImportOut]:
    items = db.scalars(
        select(DataImport)
        .where(DataImport.data_object_id == data_id)
        .order_by(DataImport.created_at.desc())
    ).all()
    return [DataImportOut.model_validate(_import_out(item)) for item in items]


@router.post("/data/{data_id}/imports/preview", response_model=ImportPreviewOut, status_code=201)
def preview_import(
    data_id: uuid.UUID, payload: ImportPreviewRequest, db: Session = Depends(get_db)
) -> ImportPreviewOut:
    try:
        data = get_object(db, data_id)
        asset = db.get(Asset, payload.source_asset_id)
        if data is None:
            raise LookupError("data not found")
        if asset is None:
            raise LookupError("asset not found")
        result = create_preview(db, data, payload, _provider_for_asset(_storage(), asset))
        return ImportPreviewOut.model_validate(_import_out(result, preview=True))
    except ImportValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": {"errors": exc.errors, "warnings": exc.warnings},
                }
            },
        ) from exc
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/data/{data_id}/imports/{import_id}/commit", response_model=DataRepresentationOut)
def commit_data_import(
    data_id: uuid.UUID,
    import_id: uuid.UUID,
    payload: ImportCommitMapping,
    db: Session = Depends(get_db),
) -> DataRepresentationOut:
    try:
        record = db.get(DataImport, import_id)
        if record is None or record.data_object_id != data_id:
            raise LookupError("data import not found")
        asset = db.get(Asset, record.source_asset_id)
        if asset is None:
            raise LookupError("asset not found")
        result = commit_import(db, import_id, payload, _provider_for_asset(_storage(), asset))
        return DataRepresentationOut.model_validate(representation_out(result))
    except ImportValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": {"errors": exc.errors, "warnings": exc.warnings},
                }
            },
        ) from exc
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/project-records", response_model=ProjectRecordOut, status_code=201)
def post_project_record(
    payload: ProjectRecordCreate, db: Session = Depends(get_db)
) -> ProjectRecordOut:
    try:
        return ProjectRecordOut.model_validate(create_project_record(db, payload))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/projects/{project_id}/record", response_model=ProjectRecordOut)
def project_record(
    project_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> ProjectRecordOut:
    try:
        result = get_project_record(db, project_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProjectRecordOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/projects/{project_id}/record", response_model=ProjectRecordOut)
def put_project_record(
    project_id: uuid.UUID,
    payload: ProjectRecordPut,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ProjectRecordOut:
    try:
        current = get_project_record(db, project_id)
        _if_match(current["record_sha256"], if_match)
        result = update_project_record(db, project_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProjectRecordOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/projects/{project_id}/context", response_model=ProjectContextOut)
def project_context(
    project_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> ProjectContextOut:
    try:
        result = get_project_context(db, project_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProjectContextOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/projects/{project_id}/search", response_model=ProjectSearchOut)
def project_search(
    project_id: uuid.UUID,
    q: str | None = None,
    kinds: list[ObjectKind] | None = Query(default=None),
    status: str | None = None,
    include_global: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ProjectSearchOut:
    try:
        return ProjectSearchOut.model_validate(
            search_project(
                db,
                project_id,
                q=q,
                kinds=kinds,
                status=status,
                include_global=include_global,
                limit=limit,
                offset=offset,
            )
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


def _summary(db: Session, project_id: uuid.UUID | None = None) -> dict[str, int]:
    statement = select(ResearchObject.kind, func.count()).group_by(ResearchObject.kind)
    if project_id is not None:
        statement = statement.where(ResearchObject.project_scope_id == project_id)
    result = {
        kind: 0
        for kind in (
            "research_object",
            "process_definition",
            "data",
            "experiment",
            "project",
            "view",
            "claim",
        )
    }
    result.update({kind: count for kind, count in db.execute(statement)})
    return result


@router.get("/projects/{project_id}/summary", response_model=dict[str, Any])
def project_summary(project_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = get_object(db, project_id)
    if project is None or project.kind != "project":
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "project": object_out(project),
        "counts": _summary(db, project_id),
        "recent": [
            object_out(item)
            for item in graph_query_service.search_objects(
                db, project_scope_id=project_id, include_global=False, limit=8
            )
        ],
    }


@router.get("/workspace/summary", response_model=WorkspaceSummaryOut)
def workspace_summary(db: Session = Depends(get_db)) -> WorkspaceSummaryOut:
    return WorkspaceSummaryOut.model_validate(
        {
            "counts": _summary(db),
            "recent": [
                object_out(item) for item in graph_query_service.search_objects(db, limit=8)
            ],
            "projects": [
                object_out(item)
                for item in graph_query_service.search_objects(db, kind="project", limit=8)
            ],
        }
    )


@router.get("/change-sets", response_model=list[ChangeSetOut])
def change_sets(
    project_scope_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[ChangeSetOut]:
    return [ChangeSetOut.model_validate(item) for item in list_change_sets(db, project_scope_id)]


@router.post("/change-sets/propose", response_model=ChangeSetOut, status_code=201)
def propose(
    payload: ChangeSetProposal,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChangeSetOut | JSONResponse:
    try:
        result = _run_idempotent(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: propose_change_set(db, payload, idempotency_key=idempotency_key),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return ChangeSetOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/change-sets/{change_set_id}", response_model=ChangeSetOut)
def change_set(change_set_id: uuid.UUID, db: Session = Depends(get_db)) -> ChangeSetOut:
    item = db.get(ChangeSet, change_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ChangeSet not found")
    return ChangeSetOut.model_validate(change_set_out(item))


@router.post("/change-sets/{change_set_id}/review", response_model=ChangeSetOut)
def review(
    change_set_id: uuid.UUID, payload: ChangeSetReview, db: Session = Depends(get_db)
) -> ChangeSetOut:
    try:
        return ChangeSetOut.model_validate(review_change_set(db, change_set_id, payload))
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/change-sets/{change_set_id}/apply", response_model=ChangeSetOut)
def apply(change_set_id: uuid.UUID, db: Session = Depends(get_db)) -> ChangeSetOut:
    try:
        apply_change_set(db, change_set_id)
        item = db.get(ChangeSet, change_set_id)
        if item is None:
            raise LookupError("ChangeSet not found")
        return ChangeSetOut.model_validate(change_set_out(item))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc
