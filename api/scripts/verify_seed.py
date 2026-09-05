"""Verify the named v0.3 golden fixture after a repeat-safe seed run."""

from app.db import SessionLocal
from app.golden_fixture import GoldenCl2WorkflowFactory


def main() -> None:
    factory = GoldenCl2WorkflowFactory()
    factory.create()
    factory.create()
    with SessionLocal() as db:
        factory.verify(db)
    print("Golden Cl₂ workflow verified")


if __name__ == "__main__":
    main()
