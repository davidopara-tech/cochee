from sqlalchemy import text
from app.database import engine   # ← this line changed

with engine.connect() as conn:
    version = conn.execute(text("SELECT version();")).scalar()
    print("Postgres version:", version)

    row = conn.execute(
        text("SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';")
    ).fetchone()

    if row is None:
        print("pgvector NOT available")
    else:
        print(f"pgvector available - name={row[0]}, default_version={row[1]}")