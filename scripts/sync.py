"""Entry point: fetch FPL data and sync the database."""

from app.ingest import sync_all

if __name__ == "__main__":
    sync_all()