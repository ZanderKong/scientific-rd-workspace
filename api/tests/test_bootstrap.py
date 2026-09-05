from __future__ import annotations

from sqlalchemy import select

from app.models import ObjectType, ObjectTypeVersion, ResearchObject
from app.seed import TYPE_DEFINITIONS, ensure_default_object_types


def test_default_object_type_catalog_is_canonical(db):
    ensure_default_object_types(db)
    types = db.scalars(select(ObjectType).order_by(ObjectType.kind, ObjectType.key)).all()
    versions = db.scalars(select(ObjectTypeVersion)).all()
    assert {(item.key, item.kind) for item in types} == {
        (key, kind) for key, kind, _zh, _en in TYPE_DEFINITIONS
    }
    assert len(versions) == len(TYPE_DEFINITIONS)
    assert db.scalar(select(ResearchObject.id)) is None
