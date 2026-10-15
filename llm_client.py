"""LLM client: sends questions to Groq, runs tools via MCP, loops until an answer."""
import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from llm_tools import to_groq_tool

load_dotenv()

MCP_URL = "http://127.0.0.1:8000/mcp"
MODEL = "openai/gpt-oss-120b"
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])


async def main() -> None:
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            groq_tools = [to_groq_tool(t) for t in response.tools]

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an FPL advisor. Answer ONLY using data returned by the tools. "
                        "Never mention a player who is not in the tool result. "
                        "If the tool returns no data, say so. Do not use your own knowledge of football. "
                        "When calling a tool, include ONLY the arguments you need. "
                        "Never include a field with value null. "
                        "For captain questions, only consider midfielders and forwards. "
                        "Pass position=3 (MID) or position=4 (FWD) to top_players."
                    )
                },
                {"role": "user", "content": "who should I captain?"}
            ]

            while True:
                reply = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=groq_tools,
                )
                msg = reply.choices[0].message
                messages.append(msg)

                if not msg.tool_calls:
                    print(msg.content)
                    break

                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    arguments = {k: v for k, v in arguments.items() if v is not None}

                    print(f"=== CALLING {tool_name} with {arguments} ===")
                    result = await session.call_tool(tool_name, arguments)
                    result_text = result.content[0].text

                    print("=== TOOL RESULT ===")
                    print(result_text[:500])
                    print("=== END ===")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    })


if __name__ == "__main__":
    asyncio.run(main())