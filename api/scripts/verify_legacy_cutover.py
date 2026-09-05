"""Assert that a database upgraded from v0.2 0006 is canonical v0.3 only."""

from __future__ import annotations

from sqlalchemy import text

from app.db import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        kinds = dict(
            db.execute(
                text(
                    "SELECT code, kind FROM research_objects "
                    "WHERE code IN ('SMP-LEGACY-001', 'DAT-LEGACY-001')"
                )
            ).all()
        )
        if kinds != {"SMP-LEGACY-001": "research_object", "DAT-LEGACY-001": "data"}:
            raise AssertionError(f"legacy records did not migrate to canonical kinds: {kinds}")
        sample_tags = db.scalar(
            text("SELECT tags_jsonb FROM research_objects WHERE code = 'SMP-LEGACY-001'")
        )
        if "样品" not in (sample_tags or []):
            raise AssertionError("migrated legacy sample is missing its canonical tag")
        remaining = db.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE 'legacy_%'"
            )
        )
        if remaining:
            raise AssertionError("legacy runtime tables remain after the v0.3 cutover")
    print("Legacy 0006 to v0.3 cutover verified")


if __name__ == "__main__":
    main()
