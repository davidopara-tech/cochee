#!/bin/bash
set -e

echo "=========================================="
echo " Initialising database schema..."
echo "=========================================="
python -m scripts.init_db

echo ""
echo "=========================================="
echo " Syncing FPL data (first run: ~30s)..."
echo "=========================================="
python -m scripts.sync

echo ""
echo "=========================================="
echo " Computing player embeddings..."
echo "=========================================="
python -m scripts.embed

echo ""
echo "=========================================="
echo " Starting MCP server on :8000"
echo "=========================================="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000