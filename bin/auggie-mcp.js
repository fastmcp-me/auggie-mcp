#!/usr/bin/env node
/*
 Lightweight Node wrapper to run the Python MCP server via npx.
 - Creates a local Python venv inside the package if missing
 - Installs requirements
 - Launches the Python server in stdio mode with inherited stdio
*/

const { spawnSync, spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function fail(message, code = 1) {
  console.error(`[auggie-mcp] ${message}`);
  process.exit(code);
}

function assertNodeVersion() {
  try {
    const major = parseInt(process.versions.node.split('.')[0], 10);
    if (Number.isNaN(major) || major < 18) {
      fail(`Node 18+ required. Found ${process.version}.`);
    }
  } catch (e) {
    // Best effort
  }
}

function which(cmd) {
  const isWin = process.platform === 'win32';
  const exts = isWin ? (process.env.PATHEXT || '').split(path.delimiter) : [''];
  const paths = (process.env.PATH || '').split(path.delimiter);
  for (const p of paths) {
    for (const ext of exts) {
      const full = path.join(p, cmd + ext);
      try {
        if (fs.existsSync(full) && fs.statSync(full).isFile()) return full;
      } catch {}
    }
  }
  return null;
}

function detectPython() {
  // Prefer python3, then python, then py -3 (Windows)
  const candidates = ['python3', 'python'];
  for (const c of candidates) {
    const p = which(c);
    if (p) return { cmd: p, args: [] };
  }
  if (which('py')) {
    return { cmd: 'py', args: ['-3'] };
  }
  fail('Python 3 is required but was not found on PATH.');
}

function runSync(cmd, args, options = {}) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...options });
  if (res.status !== 0) {
    fail(`Command failed: ${cmd} ${args.join(' ')}`);
  }
}

function ensureVenv(pkgRoot) {
  const venvDir = path.join(pkgRoot, '.venv');
  const isWin = process.platform === 'win32';
  const pythonBin = isWin ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python3');
  const pipArgs = ['-m', 'pip', 'install', '-r', path.join(pkgRoot, 'requirements.txt')];
  const stamp = path.join(venvDir, '.auggie_mcp_deps_installed');

  if (!fs.existsSync(pythonBin)) {
    const py = detectPython();
    const venvArgs = [...py.args, '-m', 'venv', venvDir];
    runSync(py.cmd, venvArgs, { cwd: pkgRoot });
  }

  if (!fs.existsSync(stamp)) {
    runSync(pythonBin, pipArgs, { cwd: pkgRoot });
    try { fs.writeFileSync(stamp, String(Date.now())); } catch {}
  }

  return pythonBin;
}

function main() {
  assertNodeVersion();
  const pkgRoot = path.resolve(__dirname, '..');
  const serverPy = path.join(pkgRoot, 'auggie_mcp_server.py');
  if (!fs.existsSync(serverPy)) fail(`Server script missing at ${serverPy}`);

  const setupOnly = process.argv.includes('--setup-only');
  const useHttp = process.argv.includes('--http');
  const pythonBin = ensureVenv(pkgRoot);
  if (setupOnly) return;

  // Launch server in stdio mode. Use client's CWD so tools default appropriately.
  const args = useHttp ? [serverPy] : [serverPy, 'stdio'];
  const child = spawn(pythonBin, args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: 'inherit',
  });

  const onSignal = (sig) => {
    if (child && !child.killed) child.kill(sig);
  };
  process.on('SIGINT', onSignal);
  process.on('SIGTERM', onSignal);

  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    else process.exit(code ?? 0);
  });
}

main();


