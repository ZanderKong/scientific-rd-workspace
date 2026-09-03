from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
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
from app.composition_service import get_process_composition, put_process_composition
from app.core.config import get_settings
from app.data_service import (
    create_data_record,
    create_file_payload,
    create_scalar_payload,
    create_table_payload,
    get_data_record,
)
from app.data_service import (
    payload_out as data_payload_out,
)
from app.db import get_db
from app.execution_service import finish_execution, get_execution, start_execution, update_execution
from app.experiment_comparison_service import compare_experiment
from app.experiment_record_service import (
    create_experiment_record,
    get_experiment_record,
    update_experiment_record,
)
from app.graph_query_service import DEFAULT_DEPTH, MAX_DEPTH, graph_query_service
from app.idempotency_service import IdempotencyReplay, run_idempotent
from app.import_service import ImportValidationError, commit_import, create_preview
from app.models import (
    OBJECT_KINDS,
    Attachment,
    ChangeSet,
    DataImport,
    DataPayload,
    DataPoint,
    ObjectRelation,
    ObjectRevision,
    ObjectType,
    ResearchObject,
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
    AttachmentOut,
    ChangeSetOut,
    ChangeSetProposal,
    ChangeSetReview,
    DataFileCreate,
    DataImportOut,
    DataPayloadOut,
    DataPointOut,
    DataRecordCreate,
    DataRecordOut,
    DataScalarCreate,
    DataTableCreate,
    ExecutionReadOut,
    ExperimentComparisonOut,
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
    ProcessCompositionOut,
    ProcessCompositionPut,
    ProjectContextOut,
    ProjectRecordCreate,
    ProjectRecordOut,
    ProjectRecordPut,
    ProjectSearchOut,
    ProjectSummaryOut,
    RelationCreate,
    RelationPatch,
    ResearchObjectOut,
    RevisionCreate,
    SampleContextOut,
    SampleExecutionUpdate,
    SampleRecordCreate,
    SampleRecordOut,
    SampleRecordPut,
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
    serialize_attachment,
    update_object,
    update_relation,
)
from app.storage import LocalStorageAdapter, sanitise_filename

router = APIRouter(tags=["research-object-graph"])


def _storage() -> LocalStorageAdapter:
    return LocalStorageAdapter(get_settings().storage_root)


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
        code = {
            "duplicate relation": "semantic_conflict",
            "stale_record": "stale_record",
            "change_set_stale": "change_set_stale",
            "idempotency_conflict": "idempotency_conflict",
            "sample execution already exists": "semantic_conflict",
        }.get(raw)
    if not code:
        if isinstance(exc, LookupError):
            code = "not_found"
        elif any(
            marker in raw
            for marker in (
                "project scope",
                "project_scope",
                "crosses project",
                "outside the Data project scope",
            )
        ):
            code = "scope_conflict"
        else:
            code = "validation_failed" if isinstance(exc, ValueError) else "internal_error"
    message = parsed.get("message") or raw or "internal server error"
    details = parsed.get("errors") or parsed.get("details") or {}
    if isinstance(exc, LookupError):
        status_code = 404
    elif isinstance(exc, (SemanticConflict, IntegrityError)):
        status_code = 409
    elif isinstance(exc, ValueError):
        status_code = 422
    else:
        status_code = 500
    if code in {"idempotency_conflict", "change_set_stale"}:
        status_code = 409
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "path": None,
                "details": details,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


def _if_match(current_hash: str, provided: str | None) -> None:
    if provided is None:
        return
    if provided.strip('"') != current_hash:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={
                "error": {
                    "code": "stale_record",
                    "message": "The record changed after it was loaded.",
                    "path": None,
                    "details": {"expected": provided, "actual": current_hash},
                    "request_id": str(uuid.uuid4()),
                }
            },
        )


def _run_idempotent_or_replay(
    db: Session, key: str | None, payload: Any, operation: Any, response_status: int
) -> dict[str, Any] | JSONResponse:
    try:
        return run_idempotent(db, key, payload, operation, response_status=response_status)
    except IdempotencyReplay as replay:
        return JSONResponse(content=replay.response_json, status_code=replay.status_code)


def _payload_out(payload: DataPayload) -> dict[str, Any]:
    return data_payload_out(payload)


def _import_error(exc: ImportValidationError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "path": None,
                "details": {"errors": exc.errors, "warnings": exc.warnings},
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@router.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    return capabilities()


@router.post("/project-records", response_model=ProjectRecordOut, status_code=201)
def post_project_record(
    payload: ProjectRecordCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ProjectRecordOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_project_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ProjectRecordOut.model_validate(result)
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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
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


def _import_out(record: DataImport, *, preview: bool = False) -> dict[str, Any]:
    metadata = record.metadata_jsonb or {}
    result = {
        "id": record.id,
        "data_object_id": record.data_object_id,
        "source_attachment_id": record.source_attachment_id,
        "payload_id": record.payload_id,
        "status": record.status,
        "source_format": record.source_format,
        "parser_key": record.parser_key,
        "parser_version": record.parser_version,
        "sheet_name": record.sheet_name,
        "source_sha256": record.source_sha256,
        "headers": record.header_json,
        "mapping_json": record.mapping_json,
        "warnings": record.warnings_json,
        "errors": record.errors_json,
        "row_count": record.row_count,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
    }
    if preview:
        result.update(
            {
                "available_sheets": metadata.get("available_sheets", []),
                "preview_rows": metadata.get("preview_rows", []),
                "column_count": metadata.get("column_count", len(record.header_json)),
            }
        )
    return result


@router.get("/object-types", response_model=list[ObjectTypeOut])
def list_object_types(db: Session = Depends(get_db)) -> list[ObjectType]:
    return list(
        db.scalars(
            select(ObjectType)
            .options(selectinload(ObjectType.versions))
            .order_by(ObjectType.kind, ObjectType.key)
        )
    )


@router.get("/object-types/{type_id}", response_model=ObjectTypeOut)
def get_object_type(type_id: uuid.UUID, db: Session = Depends(get_db)) -> ObjectType:
    obj_type = db.scalar(
        select(ObjectType)
        .where(ObjectType.id == type_id)
        .options(selectinload(ObjectType.versions))
    )
    if obj_type is None:
        raise HTTPException(status_code=404, detail="object type not found")
    return obj_type


def _counts(db: Session, *, project_scope_id: uuid.UUID | None = None) -> dict[str, int]:
    statement = select(ResearchObject.kind, func.count()).group_by(ResearchObject.kind)
    if project_scope_id is not None:
        statement = statement.where(ResearchObject.project_scope_id == project_scope_id)
    counts = {kind: 0 for kind in OBJECT_KINDS}
    counts.update({kind: count for kind, count in db.execute(statement)})
    return counts


@router.get("/projects/{project_id}/summary", response_model=ProjectSummaryOut)
def project_summary(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectSummaryOut:
    project = get_object(db, project_id)
    if project is None or project.kind != "project":
        raise HTTPException(status_code=404, detail="project not found")
    recent = graph_query_service.search_objects(
        db, project_scope_id=project_id, include_global=False, limit=8
    )
    counts = _counts(db, project_scope_id=project_id)
    counts["project"] = 1
    return ProjectSummaryOut.model_validate(
        {
            "project": object_out(project),
            "counts": counts,
            "recent": [object_out(item) for item in recent],
        }
    )


@router.get("/workspace/summary", response_model=WorkspaceSummaryOut)
def workspace_summary(db: Session = Depends(get_db)) -> WorkspaceSummaryOut:
    recent = graph_query_service.search_objects(db, limit=8)
    projects = graph_query_service.search_objects(db, kind="project", limit=8)
    return WorkspaceSummaryOut.model_validate(
        {
            "counts": _counts(db),
            "recent": [object_out(item) for item in recent],
            "projects": [object_out(item) for item in projects],
        }
    )


@router.get("/objects", response_model=list[ResearchObjectOut])
def list_objects(
    kind: ObjectKind | None = None,
    kinds: list[ObjectKind] | None = Query(default=None),
    project_scope_id: uuid.UUID | None = None,
    type_key: str | None = None,
    type_id: uuid.UUID | None = None,
    status: str | None = None,
    q: str | None = None,
    include_global: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ResearchObjectOut]:
    objects = graph_query_service.search_objects(
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
    return [ResearchObjectOut.model_validate(object_out(item)) for item in objects]


@router.post("/objects", response_model=ResearchObjectOut, status_code=status.HTTP_201_CREATED)
def post_object(payload: ObjectCreate, db: Session = Depends(get_db)) -> ResearchObjectOut:
    try:
        return ResearchObjectOut.model_validate(object_out(create_object(db, payload)))
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}", response_model=ResearchObjectOut)
def get_object_route(object_id: uuid.UUID, db: Session = Depends(get_db)) -> ResearchObjectOut:
    obj = get_object(db, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return ResearchObjectOut.model_validate(object_out(obj))


@router.patch("/objects/{object_id}", response_model=ResearchObjectOut)
def patch_object(
    object_id: uuid.UUID, payload: ObjectPatch, db: Session = Depends(get_db)
) -> ResearchObjectOut:
    obj = get_object(db, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="research object not found")
    try:
        updated = update_object(db, obj, payload.model_dump(exclude_unset=True))
        return ResearchObjectOut.model_validate(object_out(updated))
    except ValueError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}/relations", response_model=list[ObjectRelationOut])
def get_relations(object_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ObjectRelationOut]:
    if get_object(db, object_id) is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return [
        ObjectRelationOut.model_validate(relation_out(item))
        for item in list_relations(db, object_id)
    ]


@router.post("/relations", response_model=ObjectRelationOut, status_code=status.HTTP_201_CREATED)
def post_relation(payload: RelationCreate, db: Session = Depends(get_db)) -> ObjectRelationOut:
    try:
        return ObjectRelationOut.model_validate(relation_out(create_relation(db, payload)))
    except (LookupError, ValueError) as exc:
        db.rollback()
        response = _error(exc)
        if isinstance(exc, ValueError) and str(exc) == "duplicate relation":
            response.status_code = 409
        raise response from exc


@router.patch("/relations/{relation_id}", response_model=ObjectRelationOut)
def patch_relation(
    relation_id: uuid.UUID, payload: RelationPatch, db: Session = Depends(get_db)
) -> ObjectRelationOut:
    relation = get_relation(db, relation_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="relation not found")
    try:
        return ObjectRelationOut.model_validate(
            relation_out(update_relation(db, relation, payload))
        )
    except ValueError as exc:
        db.rollback()
        response = _error(exc)
        if str(exc) == "duplicate relation":
            response.status_code = 409
        raise response from exc


@router.get(
    "/processes/{process_id}/composition",
    response_model=ProcessCompositionOut,
)
def get_composition(process_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessCompositionOut:
    try:
        return ProcessCompositionOut.model_validate(get_process_composition(db, process_id))
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put(
    "/processes/{process_id}/composition",
    response_model=ProcessCompositionOut,
)
def put_composition(
    process_id: uuid.UUID,
    payload: ProcessCompositionPut,
    db: Session = Depends(get_db),
) -> ProcessCompositionOut:
    try:
        return ProcessCompositionOut.model_validate(
            put_process_composition(db, process_id, payload)
        )
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.delete("/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    relation = db.get(ObjectRelation, relation_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="relation not found")
    db.delete(relation)
    db.commit()


@router.post("/objects/{object_id}/revisions", response_model=ObjectRevisionOut, status_code=201)
def post_revision(
    object_id: uuid.UUID, payload: RevisionCreate, db: Session = Depends(get_db)
) -> ObjectRevisionOut:
    try:
        revision = create_revision(db, object_id, payload.change_note)
        return ObjectRevisionOut.model_validate(revision, from_attributes=True)
    except LookupError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/objects/{object_id}/revisions", response_model=list[ObjectRevisionOut])
def list_revisions(object_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ObjectRevision]:
    if get_object(db, object_id) is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return list(
        db.scalars(
            select(ObjectRevision)
            .where(ObjectRevision.object_id == object_id)
            .order_by(ObjectRevision.revision_number.desc())
        )
    )


@router.get("/objects/{object_id}/revisions/{revision_number}", response_model=ObjectRevisionOut)
def get_revision(
    object_id: uuid.UUID, revision_number: int, db: Session = Depends(get_db)
) -> ObjectRevision:
    revision = db.scalar(
        select(ObjectRevision).where(
            ObjectRevision.object_id == object_id,
            ObjectRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="revision not found")
    return revision


@router.post("/objects/{object_id}/attachments", response_model=AttachmentOut, status_code=201)
def upload_attachment(
    object_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AttachmentOut:
    obj = get_object(db, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="research object not found")
    safe_name = sanitise_filename(file.filename or "attachment")
    attachment_id = uuid.uuid4()
    key = f"{object_id}/{attachment_id}/{safe_name}"
    adapter = _storage()
    size, digest = adapter.put(key, file.file)
    if size > get_settings().max_upload_bytes:
        adapter.delete(key)
        raise HTTPException(status_code=413, detail="attachment exceeds the configured size limit")
    attachment = Attachment(
        id=attachment_id,
        object_id=object_id,
        original_filename=safe_name,
        storage_key=key,
        content_type=file.content_type,
        size_bytes=size,
        sha256=digest,
    )
    try:
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        adapter.delete(key)
        raise
    return AttachmentOut.model_validate(serialize_attachment(attachment))


@router.get("/objects/{object_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(object_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Attachment]:
    if get_object(db, object_id) is None:
        raise HTTPException(status_code=404, detail="research object not found")
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.object_id == object_id)
            .order_by(Attachment.created_at.desc())
        )
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    try:
        path = _storage().open(attachment.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="attachment bytes not found") from exc
    return FileResponse(
        path,
        filename=attachment.original_filename,
        media_type=attachment.content_type or "application/octet-stream",
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    referenced = (
        db.scalar(
            select(func.count(DataImport.id)).where(
                DataImport.source_attachment_id == attachment_id
            )
        )
        or 0
    )
    referenced += (
        db.scalar(
            select(func.count(DataPayload.id)).where(
                DataPayload.source_attachment_id == attachment_id
            )
        )
        or 0
    )
    if referenced:
        raise HTTPException(status_code=409, detail="attachment is referenced by data provenance")
    key = attachment.storage_key
    db.delete(attachment)
    db.commit()
    _storage().delete(key)


@router.get("/samples/{sample_id}/context", response_model=SampleContextOut)
def sample_context(
    sample_id: uuid.UUID,
    depth: int = Query(default=DEFAULT_DEPTH, ge=0, le=MAX_DEPTH),
    db: Session = Depends(get_db),
) -> SampleContextOut:
    try:
        return SampleContextOut.model_validate(
            graph_query_service.get_sample_context(db, sample_id, depth)
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


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


@router.post("/sample-records", response_model=SampleRecordOut, status_code=status.HTTP_201_CREATED)
def post_sample_record(
    payload: SampleRecordCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> SampleRecordOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_sample_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return SampleRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
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


@router.post("/experiment-records", response_model=ExperimentRecordOut, status_code=201)
def post_experiment_record(
    payload: ExperimentRecordCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ExperimentRecordOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_experiment_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExperimentRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
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
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/experiments/{experiment_id}/comparison", response_model=ExperimentComparisonOut)
def experiment_comparison(
    experiment_id: uuid.UUID,
    differences_only: bool = False,
    db: Session = Depends(get_db),
) -> ExperimentComparisonOut:
    try:
        return ExperimentComparisonOut.model_validate(
            compare_experiment(db, experiment_id, differences_only=differences_only)
        )
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.post("/data-records", response_model=DataRecordOut, status_code=201)
def post_data_record(
    payload: DataRecordCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> DataRecordOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_data_record(db, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return DataRecordOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
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


@router.post("/data/{data_id}/payloads/scalar", response_model=DataPayloadOut, status_code=201)
def post_scalar_payload(
    data_id: uuid.UUID,
    payload: DataScalarCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> DataPayloadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_scalar_payload(db, data_id, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return DataPayloadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/data/{data_id}/payloads/table", response_model=DataPayloadOut, status_code=201)
def post_table_payload(
    data_id: uuid.UUID,
    payload: DataTableCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> DataPayloadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_table_payload(db, data_id, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return DataPayloadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/data/{data_id}/payloads/file", response_model=DataPayloadOut, status_code=201)
def post_file_payload(
    data_id: uuid.UUID,
    payload: DataFileCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> DataPayloadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            payload.model_dump(mode="json"),
            lambda: create_file_payload(db, data_id, payload),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        return DataPayloadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post(
    "/samples/{sample_id}/execution/start", response_model=ExecutionReadOut, status_code=201
)
def post_execution_start(
    sample_id: uuid.UUID,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ExecutionReadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            {"sample_id": str(sample_id), "operation": "start"},
            lambda: start_execution(db, sample_id),
            201,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExecutionReadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/samples/{sample_id}/execution", response_model=ExecutionReadOut)
def sample_execution(
    sample_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> ExecutionReadOut:
    try:
        result = get_execution(db, sample_id)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExecutionReadOut.model_validate(result)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.put("/samples/{sample_id}/execution", response_model=ExecutionReadOut)
def put_sample_execution(
    sample_id: uuid.UUID,
    payload: SampleExecutionUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ExecutionReadOut:
    try:
        current = get_execution(db, sample_id)
        _if_match(current["record_sha256"], if_match)
        result = update_execution(db, sample_id, payload)
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExecutionReadOut.model_validate(result)
    except HTTPException:
        raise
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/samples/{sample_id}/execution/complete", response_model=ExecutionReadOut)
def complete_sample_execution(
    sample_id: uuid.UUID,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ExecutionReadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            {"sample_id": str(sample_id), "operation": "complete"},
            lambda: finish_execution(db, sample_id, cancelled=False),
            200,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExecutionReadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/samples/{sample_id}/execution/cancel", response_model=ExecutionReadOut)
def cancel_sample_execution(
    sample_id: uuid.UUID,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ExecutionReadOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
            db,
            idempotency_key,
            {"sample_id": str(sample_id), "operation": "cancel"},
            lambda: finish_execution(db, sample_id, cancelled=True),
            200,
        )
        if isinstance(result, JSONResponse):
            return result
        response.headers["ETag"] = f'"{result["record_sha256"]}"'
        return ExecutionReadOut.model_validate(result)
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/change-sets", response_model=list[ChangeSetOut])
def get_change_sets(
    project_scope_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[ChangeSetOut]:
    return [ChangeSetOut.model_validate(item) for item in list_change_sets(db, project_scope_id)]


@router.post("/change-sets/propose", response_model=ChangeSetOut, status_code=201)
def post_change_set_proposal(
    payload: ChangeSetProposal,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> ChangeSetOut | JSONResponse:
    try:
        result = _run_idempotent_or_replay(
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
def get_change_set(change_set_id: uuid.UUID, db: Session = Depends(get_db)) -> ChangeSetOut:
    item = db.get(ChangeSet, change_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ChangeSet not found")
    return ChangeSetOut.model_validate(change_set_out(item))


@router.post("/change-sets/{change_set_id}/review", response_model=ChangeSetOut)
def review_change_set_route(
    change_set_id: uuid.UUID, payload: ChangeSetReview, db: Session = Depends(get_db)
) -> ChangeSetOut:
    try:
        return ChangeSetOut.model_validate(review_change_set(db, change_set_id, payload))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/change-sets/{change_set_id}/apply", response_model=ChangeSetOut)
def apply_change_set_route(change_set_id: uuid.UUID, db: Session = Depends(get_db)) -> ChangeSetOut:
    try:
        apply_change_set(db, change_set_id)
        item = db.get(ChangeSet, change_set_id)
        if item is None:
            raise LookupError("ChangeSet not found")
        return ChangeSetOut.model_validate(change_set_out(item))
    except (LookupError, ValueError, IntegrityError) as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/experiments/{experiment_id}/context")
def experiment_context(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return graph_query_service.get_experiment_context(db, experiment_id)
    except (LookupError, ValueError) as exc:
        raise _error(exc) from exc


@router.get("/data/{data_id}/payloads", response_model=list[DataPayloadOut])
def list_payloads(data_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DataPayloadOut]:
    data_object = get_object(db, data_id)
    if data_object is None or data_object.kind != "data":
        raise HTTPException(status_code=404, detail="data object not found")
    payloads = db.scalars(
        select(DataPayload)
        .where(DataPayload.data_object_id == data_id)
        .options(
            selectinload(DataPayload.points),
            selectinload(DataPayload.scalar),
            selectinload(DataPayload.table_rows),
        )
        .order_by(DataPayload.created_at.desc())
    ).all()
    return [DataPayloadOut.model_validate(_payload_out(item)) for item in payloads]


@router.get("/data/{data_id}/imports", response_model=list[DataImportOut])
def list_data_imports(data_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DataImportOut]:
    data_object = get_object(db, data_id)
    if data_object is None or data_object.kind != "data":
        raise HTTPException(status_code=404, detail="data object not found")
    rows = db.scalars(
        select(DataImport)
        .where(DataImport.data_object_id == data_id)
        .order_by(DataImport.created_at.desc())
    ).all()
    return [DataImportOut.model_validate(_import_out(item)) for item in rows]


@router.post("/data/{data_id}/imports/preview", response_model=ImportPreviewOut, status_code=201)
def preview_data_import(
    data_id: uuid.UUID, payload: ImportPreviewRequest, db: Session = Depends(get_db)
) -> ImportPreviewOut:
    data_object = get_object(db, data_id)
    if data_object is None or data_object.kind != "data":
        raise HTTPException(status_code=404, detail="data object not found")
    try:
        record = create_preview(db, data_object, payload, _storage())
        return ImportPreviewOut.model_validate(_import_out(record, preview=True))
    except (LookupError, ValueError, ImportValidationError) as exc:
        db.rollback()
        if isinstance(exc, ImportValidationError):
            raise _import_error(exc) from exc
        raise _error(exc) from exc


@router.post(
    "/data/{data_id}/imports/{import_id}/commit", response_model=DataPayloadOut, status_code=201
)
def commit_data_import(
    data_id: uuid.UUID,
    import_id: uuid.UUID,
    payload: ImportCommitMapping,
    db: Session = Depends(get_db),
) -> DataPayloadOut:
    record = db.get(DataImport, import_id)
    if record is None or record.data_object_id != data_id:
        raise HTTPException(status_code=404, detail="data import not found")
    try:
        result = commit_import(db, import_id, payload, _storage())
        result = (
            db.scalar(
                select(DataPayload)
                .where(DataPayload.id == result.id)
                .options(
                    selectinload(DataPayload.points),
                    selectinload(DataPayload.scalar),
                    selectinload(DataPayload.table_rows),
                )
            )
            or result
        )
        return DataPayloadOut.model_validate(_payload_out(result))
    except ImportValidationError as exc:
        db.rollback()
        record = db.get(DataImport, import_id)
        if record is not None and record.status == "preview_ready":
            record.status = "failed"
            record.errors_json = exc.errors
            record.warnings_json = exc.warnings
            db.commit()
        raise _import_error(exc) from exc
    except (LookupError, ValueError) as exc:
        db.rollback()
        response = _error(exc)
        if isinstance(exc, ValueError) and "no longer available" in str(exc):
            response.status_code = 409
        raise response from exc


@router.get("/data-payloads/{payload_id}", response_model=DataPayloadOut)
def get_payload(payload_id: uuid.UUID, db: Session = Depends(get_db)) -> DataPayloadOut:
    payload = db.scalar(
        select(DataPayload)
        .where(DataPayload.id == payload_id)
        .options(
            selectinload(DataPayload.points),
            selectinload(DataPayload.scalar),
            selectinload(DataPayload.table_rows),
        )
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="data payload not found")
    return DataPayloadOut.model_validate(_payload_out(payload))


@router.get("/data-payloads/{payload_id}/points", response_model=list[DataPointOut])
def get_payload_points(payload_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DataPoint]:
    if db.get(DataPayload, payload_id) is None:
        raise HTTPException(status_code=404, detail="data payload not found")
    return list(
        db.scalars(
            select(DataPoint).where(DataPoint.payload_id == payload_id).order_by(DataPoint.ordinal)
        )
    )
