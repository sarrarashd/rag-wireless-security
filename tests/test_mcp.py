"""Send sample requests to every MCP tool over stdio, the way a real MCP client does."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
SERVER = StdioServerParameters(command=sys.executable, args=[str(ROOT / "src" / "server.py")])

REQUESTS = [
    ("list_documents", {}),
    ("search_documents", {"query": "Is it safe to pair my wireless headphones?", "k": 3}),
    ("search_documents", {"query": "WPA2 encryption on public Wi-Fi", "k": 2, "mode": "keyword"}),
    ("get_document", {"document": "SP 800-121", "page_start": 11, "page_end": 12, "max_chars": 1200}),
    ("get_document", {"document": "SP 800-97", "page_start": 1, "max_chars": 400}),
    ("get_document", {"document": "SP 999-1"}),
    ("provide_feedback", {"question": "Is it safe to pair my wireless headphones?",
                          "answer": "Test answer from test_mcp.py", "rating": 1}),
]


async def main():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools offered by the server:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description.splitlines()[0]}")

            for name, args in REQUESTS:
                print(f"\n=== {name}({json.dumps(args)})")
                result = await session.call_tool(name, args)
                text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                print(("ERROR -> " if result.isError else "") + text[:900])


if __name__ == "__main__":
    asyncio.run(main())
