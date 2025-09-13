# Auggie MCP Server

Minimal MCP server exposing Auggie CLI as tools for Q&A and code implementation.

## Tools

- ask_question: Repository Q&A via Auggie’s context engine.
- implement: Implement a change in the repo; dry-run by default.

## Requirements

- Python 3.10+
- Node.js 18+
- Auggie CLI installed and on PATH

Install Python deps:

```bash
pip install -r requirements.txt
```

## Run the server

Stdio (for MCP clients):

```bash
python3 auggie_mcp_server.py stdio
```

HTTP (optional for debugging):

```bash
python3 auggie_mcp_server.py
```

## Configure Clients

### Cursor

Create `~/.cursor/mcp.json` or project `.cursor/mcp.json` with:

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "python3",
      "args": ["/Users/saharmor/Documents/codebase/auggie-mcp/auggie_mcp_server.py", "stdio"],
      "env": { "AUGMENT_API_TOKEN": "YOUR_TOKEN" }
    }
  }
}
```

Or start from `examples/cursor.mcp.json`.

### Cursor via npx (recommended for users)

Use this MCP config in Cursor (global or per-project):

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "npx",
      "args": ["-y", "@saharmor/auggie-mcp"],
      "env": { "AUGMENT_API_TOKEN": "YOUR_TOKEN" }
    }
  }
}
```

This will:
- download the wrapper package,
- create a local Python venv inside the package,
- install `requirements.txt`, and
- launch the Python server in `stdio` mode.

Node 18+ is required by the wrapper.

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "python3",
      "args": ["/Users/saharmor/Documents/codebase/auggie-mcp/auggie_mcp_server.py", "stdio"],
      "env": { "AUGMENT_API_TOKEN": "YOUR_TOKEN" }
    }
  }
}
```

Or start from `examples/claude_desktop_config.json`.

## Security and permissions

- Default runs keep `implement` in dry-run mode by denying write/shell tools via Auggie settings.
- To allow writes, call `implement` with `dry_run=false`. Optionally set `branch` and `commit_message`.

## Notes

- The server checks Auggie availability at tool invocation time.
- `AUGMENT_API_TOKEN` is read from the environment if provided.