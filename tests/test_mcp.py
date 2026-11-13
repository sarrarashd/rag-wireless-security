"""Send sample requests to every MCP tool over stdio, the way a real MCP client does.

Each request states what it expects (a successful result or an error), so the script
reports PASS/FAIL and exits with a non-zero status if anything fails. The server runs
against a temporary copy of the database, so the test never changes db/metadata.db.

Run:  python tests/test_mcp.py        (add -v to print every response)
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
VERBOSE = "-v" in sys.argv

# (tool, arguments, expect an error?, check on the parsed result)
REQUESTS = [
    ("list_documents", {}, False, lambda r: len(r) == 11),
    ("search_documents", {"query": "Is it safe to pair my wireless headphones?", "k": 3}, False,
     lambda r: len(r["results"]) == 3 and all("citation" in h for h in r["results"])),
    ("search_documents", {"query": "WPA2 encryption on public Wi-Fi", "k": 2, "mode": "keyword"}, False,
     lambda r: r["results"][0]["citation"].startswith("CSI U/OO/166417-21")),
    ("search_documents", {"query": "rogue base station", "k": 2, "chunk_size": 1500}, False,
     lambda r: len(r["results"]) == 2),
    ("search_documents", {"query": "minimum WPA2 encryption for public Wi-Fi", "k": 3, "mode": "hybrid"}, False,
     lambda r: len(r["results"]) == 3 and r["mode"] == "hybrid"),
    ("search_documents", {"query": "bluetooth", "mode": "fuzzy"}, True, None),
    ("get_document", {"document": "SP 800-121", "page_start": 11, "page_end": 12, "max_chars": 1200}, False,
     lambda r: r["series"] == "SP 800-121 Rev. 2" and r["pages_returned"] == "11-12" and len(r["text"]) <= 1200),
    ("get_document", {"document": "SP 800-97", "page_start": 1, "max_chars": 400}, False,
     lambda r: r["status"] == "withdrawn" and "warning" in r),
    ("get_document", {"document": "SP 999-1"}, True, None),
    ("provide_feedback", {"question": "Is it safe to pair my wireless headphones?",
                          "answer": "Test answer from test_mcp.py", "rating": 1}, False,
     lambda r: r["saved"] is True),
    ("provide_feedback", {"rating": 5, "question": "x"}, True, None),
]


def parse(result):
    """Tool results arrive as one JSON text block, or one block per list item."""
    texts = [c.text for c in result.content if hasattr(c, "text")]
    if result.isError:
        return "\n".join(texts)
    if result.structuredContent is not None:
        data = result.structuredContent
        return data["result"] if set(data) == {"result"} else data
    return json.loads(texts[0]) if len(texts) == 1 else [json.loads(t) for t in texts]


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="wisec-test-"))
    shutil.copy(ROOT / "db" / "metadata.db", tmp / "metadata.db")
    server = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "src" / "server.py")],
        env={**os.environ, "WISEC_DB": str(tmp / "metadata.db")},
    )
    failures = 0
    try:
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                print("Tools offered by the server:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description.splitlines()[0]}")
                print()

                for name, args, expect_error, check in REQUESTS:
                    result = await session.call_tool(name, args)
                    data = parse(result)
                    if expect_error:
                        ok = result.isError
                    else:
                        ok = not result.isError and bool(check(data))
                    failures += not ok
                    print(f"{'PASS' if ok else 'FAIL'}  {name}({json.dumps(args)})")
                    if result.isError:
                        print(f"      error -> {data}")
                    if VERBOSE or not ok:
                        print("      " + json.dumps(data, indent=2)[:900].replace("\n", "\n      "))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(REQUESTS) - failures}/{len(REQUESTS)} requests behaved as expected")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(main())
