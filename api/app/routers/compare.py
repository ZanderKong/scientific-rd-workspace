from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.compare_service import build_compare
from app.db import get_db
from app.schemas import CompareOut, CompareRequest

router = APIRouter(tags=["compare"])


@router.post("/comparisons/experiments", response_model=CompareOut)
def compare_experiments(payload: CompareRequest, db: Session = Depends(get_db)) -> CompareOut:
    try:
        return build_compare(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
