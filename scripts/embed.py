"""Entry point: compute embedding vectors for all players."""

from app.embeddings import build_embeddings

if __name__ == "__main__":
    build_embeddings()