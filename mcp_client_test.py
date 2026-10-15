"""Print the raw MCP tool schema so we can see what to translate."""
import asyncio
import json

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://127.0.0.1:8000/mcp"


async def fetch_tools():
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


if __name__ == "__main__":
    tools = asyncio.run(fetch_tools())
    for tool in tools:
        print(f"NAME: {tool.name}")
        print(f"DESCRIPTION (first 100 chars): {tool.description[:100]}...")
        print("INPUT SCHEMA:")
        print(json.dumps(tool.inputSchema, indent=2))
        print()