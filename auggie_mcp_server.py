#!/usr/bin/env python3
import asyncio
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path
from typing import List, Optional, TypedDict

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession


SERVER_NAME = "Auggie MCP"
DEFAULT_TIMEOUT = 120

mcp = FastMCP(SERVER_NAME)


def _env(base_env: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    # Pass through Augment auth if present.
    # Requires AUGMENT_API_TOKEN or an existing Auggie session.
    return env


async def _run(cmd: List[str], cwd: Optional[str], timeout: int) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


def _auggie_base_args(
    instruction: str,
    workspace_root: Optional[str],
    model: Optional[str],
    rules_path: Optional[str],
    quiet: bool = True,
) -> List[str]:
    args = ["auggie"]
    args += ["--quiet"] if quiet else ["--print"]
    if workspace_root:
        args += ["--workspace-root", workspace_root]
    if model:
        args += ["--model", model]
    if rules_path:
        args += ["--rules", rules_path]
    args += [instruction]
    return args


@mcp.tool()
async def ask_question(
    question: str,
    workspace_root: Optional[str] = None,
    model: Optional[str] = None,
    rules_path: Optional[str] = None,
    timeout_sec: int = DEFAULT_TIMEOUT,
    ctx: Context[ServerSession, None] | None = None,
) -> dict:
    """Q&A over a repository using Auggie's context engine."""
    # Ensure dependencies are available at call-time, not startup, so tools list even if missing.
    try:
        await _preflight()
    except Exception as e:
        raise RuntimeError(f"Preflight failed: {e}")
    t0 = time.time()
    cmd = _auggie_base_args(question, workspace_root, model, rules_path, quiet=True)
    if ctx is not None:
        await ctx.info(f"Running: {' '.join(shlex.quote(c) for c in cmd)}")
    code, out, err = await _run(cmd, cwd=workspace_root, timeout=timeout_sec)
    if code != 0:
        raise RuntimeError(f"Auggie failed: {err.strip() or out.strip()}")
    return {"answer": out.strip(), "usage": {"duration_ms": int((time.time() - t0) * 1000)}}


class ImplementResult(TypedDict, total=False):
    summary: str
    files_changed: List[str]
    diff: str
    committed: bool
    commit_sha: Optional[str]
    usage: dict


async def _git(args: List[str], cwd: str, timeout: int = 60) -> str:
    code, out, err = await _run(["git"] + args, cwd=cwd, timeout=timeout)
    if code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip() or out.strip()}")
    return out


def _read_only_settings(tmp_dir: Path) -> Path:
    # Minimal read-only Auggie settings to deny writes and shell
    data = {
        "tool-permissions": [
            {"tool-name": "save-file", "permission": {"type": "deny"}},
            {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
            {"tool-name": "remove-files", "permission": {"type": "deny"}},
            {"tool-name": "launch-process", "permission": {"type": "deny"}},
        ]
    }
    p = tmp_dir / "settings.json"
    p.write_text(json.dumps(data))
    return p


@mcp.tool()
async def implement(
    prompt: str,
    workspace_root: Optional[str] = None,
    branch: Optional[str] = None,
    commit_message: Optional[str] = None,
    scope: Optional[List[str]] = None,
    dry_run: bool = True,
    timeout_sec: int = 300,
    model: Optional[str] = None,
    rules_path: Optional[str] = None,
    ctx: Context[ServerSession, None] | None = None,
) -> ImplementResult:
    """Implement a change in the repo. Optionally commit."""
    # Ensure dependencies are available at call-time, not startup, so tools list even if missing.
    try:
        await _preflight()
    except Exception as e:
        raise RuntimeError(f"Preflight failed: {e}")
    if not workspace_root:
        workspace_root = os.getcwd()

    t0 = time.time()

    # Optional branch
    if branch:
        await _git(["checkout", "-B", branch], cwd=workspace_root)

    # Prepare permissions for dry_run
    tmp = Path(workspace_root) / ".augment" / ".mcp-temp"
    tmp.mkdir(parents=True, exist_ok=True)
    extra_env = dict(os.environ)
    if dry_run:
        # Use AUGMENT_CACHE_DIR to point Auggie at a directory with read-only policy
        settings_path = _read_only_settings(tmp)
        extra_env["AUGMENT_CACHE_DIR"] = str(tmp)
        os.environ.update(extra_env)

    # Scope hinting
    scope_hint = ""
    if scope:
        scope_hint = "\nScope: limit edits to " + ", ".join(scope)

    instruction = f"{prompt.strip()}{scope_hint}"

    cmd = _auggie_base_args(instruction, workspace_root, model, rules_path, quiet=True)
    if ctx is not None:
        await ctx.info(f"Running: {' '.join(shlex.quote(c) for c in cmd)}")
    code, out, err = await _run(cmd, cwd=workspace_root, timeout=timeout_sec)
    if code != 0:
        raise RuntimeError(f"Auggie failed: {err.strip() or out.strip()}")

    # Collect results
    files_changed: List[str] = []
    status = await _git(["status", "--porcelain"], cwd=workspace_root)
    for line in status.splitlines():
        m = re.match(r"^\s*[AMDR?]{1,2}\s+(.*)$", line)
        if m:
            files_changed.append(m.group(1))

    diff = ""
    if files_changed:
        diff = await _git(["diff"], cwd=workspace_root)

    committed = False
    commit_sha: Optional[str] = None
    if not dry_run and files_changed:
        await _git(["add", "-A"], cwd=workspace_root)
        if not commit_message:
            commit_message = f"Implement: {prompt[:72]}"
        await _git(["commit", "-m", commit_message], cwd=workspace_root)
        committed = True
        commit_sha = (await _git(["rev-parse", "HEAD"], cwd=workspace_root)).strip()

    return {
        "summary": out.strip(),
        "files_changed": files_changed,
        "diff": diff if len(diff) <= 200_000 else "",
        "committed": committed,
        "commit_sha": commit_sha,
        "usage": {"duration_ms": int((time.time() - t0) * 1000)},
    }


async def _preflight() -> None:
    try:
        code, out, _ = await _run(["node", "-v"], cwd=None, timeout=5)
        assert code == 0 and out.strip()
        ver = out.strip().lstrip("v").split(".")
        assert int(ver[0]) >= 18, f"Node 18+ required, found v{out.strip()}"
        code, _, _ = await _run(["auggie", "--version"], cwd=None, timeout=5)
        assert code == 0
    except Exception as e:
        print(f"[{SERVER_NAME}] Preflight failed: {e}", file=sys.stderr)
        sys.exit(1)


def _main() -> None:
    # Defer dependency checks to tool invocation so the server can advertise tools
    # even if Auggie/Node are not yet installed on the host.
    # Run stdio or HTTP per argv
    transport = "stdio" if len(sys.argv) > 1 and sys.argv[1] == "stdio" else "streamable-http"
    mcp.run(transport)


if __name__ == "__main__":
    # Run without preflight so the server can start and advertise tools even if deps are missing.
    _main()


