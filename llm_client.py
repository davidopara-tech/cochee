"""LLM client: conversational FPL advisor using Groq + MCP tools."""
import asyncio
import json
import os
import time

import groq
from dotenv import load_dotenv
from groq import Groq
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from llm_tools import to_groq_tool

load_dotenv()

MCP_URL = "http://127.0.0.1:8000/mcp"
MODEL = "openai/gpt-oss-120b"
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = (
    "You are a professional FPL advisor writing for a client. "
    "Answer ONLY using data returned by the tools. "
    "Never mention a player who is not in the tool result. "
    "If the tool returns no data, say so. Do not use your own knowledge of football. "
    "\n\n"
    "For captain questions, write a short analyst-style briefing: "
    "- Open with a one-sentence summary of the week's picture. "
    "- Present a numbered shortlist of the top 3-5 candidates returned by the tool. "
    "- For each candidate, write 2-3 sentences: what their form says, "
    "what their fixtures say, and what kind of manager they suit. "
    "- Close with a clear top recommendation and one sentence on why. "
    "\n\n"
    "Write in plain football language a fan would use. "
    "Do not quote raw numbers or labels like 'form 5.5 (solid)'. "
    "Do not use emojis. No citation markers or bracketed references like 【...】. "
    "\n\n"
    "For captain questions, focus on form and fixtures — value is not relevant to captaincy. "
    "\n\n"
    "When calling tools, include ONLY the arguments you need. "
    "Never include a field with value null. "
    "\n\n"
    "For captain questions, call top_players with position=3 and position=4 "
    "as TWO SEPARATE CALLS (never an array). "
    "Pass weights={'form': 0.5, 'fixtures': 0.5, 'value': 0.0}, min_price=80, limit=5. "
    "For non-captain questions, do not pass weights or min_price. "
    "\n\n"
    "Use player_fixtures when the user asks about a specific player's upcoming games."
)


def ask_groq(messages: list, tools: list, max_retries: int = 3):
    """Call Groq, retrying on connection blips and garbled tool-call output."""
    for attempt in range(max_retries):
        try:
            return groq_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
            )
        except groq.APIConnectionError:
            if attempt == max_retries - 1:
                raise
            print(f"[connection blip — retry {attempt + 1}/{max_retries}]")
            time.sleep(2)
        except groq.BadRequestError as e:
            msg = str(e)
            if "<|channel|>" not in msg and "tool_use_failed" not in msg:
                raise
            if attempt == max_retries - 1:
                raise
            print(f"[model glitch — retry {attempt + 1}/{max_retries}]")
            time.sleep(1)


async def main() -> None:
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            groq_tools = [to_groq_tool(t) for t in response.tools]

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            print("Cochee ready. Type 'quit' to exit.\n")

            while True:
                user_input = input("You: ").strip()
                if user_input.lower() in {"quit", "exit"}:
                    break
                if not user_input:
                    continue

                messages.append({"role": "user", "content": user_input})

                while True:
                    reply = ask_groq(messages, groq_tools)
                    msg = reply.choices[0].message
                    messages.append(msg)

                    if not msg.tool_calls:
                        print(f"\nCochee: {msg.content}\n")
                        break

                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        arguments = {k: v for k, v in arguments.items() if v is not None}

                        result = await session.call_tool(tool_name, arguments)
                        result_text = result.content[0].text

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        })


if __name__ == "__main__":
    asyncio.run(main())