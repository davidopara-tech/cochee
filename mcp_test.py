import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession


async def main():
    async with sse_client("http://127.0.0.1:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"\n{len(tools.tools)} tools available:\n")
            for t in tools.tools:
                print(f"  • {t.name}")
                print(f"    {t.description[:80]}...")
                print()


asyncio.run(main())