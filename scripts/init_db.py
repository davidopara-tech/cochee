"""
One-time script: creates the tables in Postgres.

Run once with:  python -m scripts.init_db
"""

# This import looks unused, but it's required. Importing models.py tells
# SQLAlchemy "here are the four tables." Without it, create_all() would
# create nothing.
from app import models  # noqa: F401

from app.database import Base, engine


def main() -> None:
    # Create every table that doesn't exist yet. Existing tables are skipped.
    Base.metadata.create_all(bind=engine)
    print("Tables ready:")
    for name in Base.metadata.tables.keys():
        print(f"  - {name}")


if __name__ == "__main__":
    main()