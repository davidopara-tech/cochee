"""
One-time script: creates the tables in Postgres.

Enables the pgvector extension first (required for the `embedding` column).

Run once with:  python -m scripts.init_db
"""

from sqlalchemy import text

# This import looks unused, but it's required. Importing models.py tells
# SQLAlchemy "here are the four tables." Without it, create_all() would
# create nothing.
from app import models  # noqa: F401

from app.database import Base, engine


def main() -> None:
    # Enable pgvector in this database. The `vector` column type needs
    # this extension. IF NOT EXISTS makes it safe to re-run.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create every table that doesn't exist yet. Existing tables are skipped.
    Base.metadata.create_all(bind=engine)

    print("Tables ready:")
    for name in Base.metadata.tables.keys():
        print(f"  - {name}")


if __name__ == "__main__":
    main()