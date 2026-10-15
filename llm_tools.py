"""Translate MCP tool definitions into Groq's function-calling format."""


def to_groq_tool(mcp_tool) -> dict:
    """Convert one MCP Tool into the dict shape Groq expects."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema,
        },
    }