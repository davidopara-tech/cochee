from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from app.routers.health import router as health_router
from app.routers.tools_router import router as tools_router

app = FastAPI(title="Cochee")

app.include_router(health_router)
app.include_router(tools_router)

mcp = FastApiMCP(
    app,
    include_operations=["top_players", "similar_players", "compare_players", "player_fixtures"],
)
mcp.mount_http()