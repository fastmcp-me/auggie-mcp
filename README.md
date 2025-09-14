# Auggie MCP Server

Minimal MCP server exposing Auggie CLI as tools for Q&A and code implementation.

## Tools

- ask_question: Repository Q&A via Auggie’s context engine.
- implement: Implement a change in the repo; dry-run by default.

## Requirements

- Node.js 18+
- Python 3.10+ available on the system (used internally; no manual setup needed)
- Auggie CLI installed (check by running `auggie --version`) - _see [installation guide](https://docs.augmentcode.com/cli/overview)_

## Authentication (AUGMENT_API_TOKEN)

Retrieve your token via the Auggie CLI:

```bash
# Ensure Auggie CLI is installed and on PATH
auggie --version

# Sign in (opens browser flow)
auggie login

# Print your token
auggie --print-augment-token
```

Provide the token in either of these ways:

- Cursor/Claude config (recommended): set it under `env` for the server

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "npx",
      "args": ["-y", "auggie-mcp@latest"],
      "env": { "AUGMENT_API_TOKEN": "YOUR_TOKEN" }
    }
  }
}
```

- Shell environment (macOS/Linux)

One-off for a single command:

```bash
AUGMENT_API_TOKEN=YOUR_TOKEN npx -y auggie-mcp --setup-only
```

Persist for future shells (zsh):

```bash
echo 'export AUGMENT_API_TOKEN=YOUR_TOKEN' >> ~/.zshrc
source ~/.zshrc
```

Security tip: never commit tokens to source control. Prefer per-machine environment variables or your client's secure config store.

## Configure Clients

### Cursor via npx

Use this MCP config in Cursor (global or per-project):

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "npx",
      "args": ["-y", "auggie-mcp@latest"],
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


### Quick test via npx (terminal)

```bash
# Install deps into the package's local venv (no global installs)
npx -y auggie-mcp --setup-only

# Run the server (stdio). Useful for quick smoke-tests.
npx -y auggie-mcp

# Optional: start HTTP mode for manual debugging
npx -y auggie-mcp -- --http
```

### Claude Desktop (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "auggie-mcp": {
      "command": "npx",
      "args": ["-y", "auggie-mcp@latest"],
      "env": { "AUGMENT_API_TOKEN": "YOUR_TOKEN" }
    }
  }
}
```

## Security and permissions

- Default: `implement` runs in dry‑run mode. No files are written, no shell runs; you get a proposed diff.
- Enable writes: set `dry_run: false`.
- Recommendation: use a feature branch and review the diff before merging.