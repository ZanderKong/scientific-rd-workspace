import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ExperimentTemplate
from app.schemas import TemplateOut

router = APIRouter(prefix="/experiment-templates", tags=["experiment-templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[ExperimentTemplate]:
    return list(
        db.scalars(
            select(ExperimentTemplate)
            .where(ExperimentTemplate.is_active)
            .order_by(ExperimentTemplate.name)
        )
    )


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> ExperimentTemplate:
    template = db.get(ExperimentTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="experiment template not found")
    return template
