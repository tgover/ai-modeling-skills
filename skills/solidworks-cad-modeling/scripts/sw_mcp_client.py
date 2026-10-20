"""Call one configured local SolidWorks MCP tool, or inspect its live schemas.

Useful for diagnostics and for the installation turn before Codex reloads tools.
Reads only the named MCP entry from local config; never prints other config data.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tomllib


async def run(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    config_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    with config_path.open("rb") as stream:
        config = tomllib.load(stream)["mcp_servers"][args.server]
    if config.get("enabled") is False:
        raise RuntimeError(f"MCP server {args.server} is disabled")
    if "command" not in config:
        raise RuntimeError("This diagnostic supports configured local STDIO servers only")
    parameters = StdioServerParameters(
        command=config["command"], args=config.get("args", []),
        cwd=config.get("cwd"), env={**os.environ, **config.get("env", {})},
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            if args.list:
                return {"server": args.server, "tool_count": len(tools),
                        "tools": [tool.model_dump(mode="json", exclude_none=True) for tool in tools]}
            if args.tool not in {tool.name for tool in tools}:
                raise ValueError(f"Unknown tool: {args.tool}")
            arguments = json.loads(Path(args.arguments_file).read_text(encoding="utf-8-sig")) if args.arguments_file else json.loads(args.arguments)
            result = await session.call_tool(args.tool, arguments)
            return result.model_dump(mode="json", exclude_none=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="solidworks")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true")
    action.add_argument("--tool")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--arguments", default="{}", help="Exact tool arguments as JSON, including params when required")
    inputs.add_argument("--arguments-file", help="Read exact tool arguments from a UTF-8 JSON file")
    parser.add_argument("--output", help="Optional new JSON result file (refuses overwrite)")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if args.output and Path(args.output).exists():
        parser.error("Result file already exists; choose a new output path before executing a tool")
    result = asyncio.run(asyncio.wait_for(run(args), timeout=args.timeout))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with Path(args.output).open("x", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    else:
        print(rendered)
    return 2 if result.get("isError") else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
