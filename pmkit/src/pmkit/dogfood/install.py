"""Clean-room install runner.

Runs a product's *documented* install/run commands verbatim in a throwaway working
directory and reports what actually happens. A failed documented step is a gap (a
doc-vs-reality finding), never a crash — the run continues so later independent steps
still get exercised. Commands are expected to be self-contained (e.g. `uvx <pkg> ...`,
`uv run --no-project --with <pkg> ...`), which create their own ephemeral environments.

SECURITY: these command strings are executed verbatim through a shell (`shell=True`) with
the operator's local privileges — running them IS the point, so they must come from a
trusted, operator-reviewed source, not directly from untrusted/auto-scraped product docs
without a human in the loop. To limit blast radius, the run gets a minimal allow-listed
environment (no inherited API keys/secrets); callers opt specific vars back in via `env`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Optional

# Only these env vars are passed into the throwaway run; everything else (the operator's
# API keys and secrets) is withheld from the third-party documented commands.
_SAFE_ENV_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR",
    "TEMP", "TMP", "TMPDIR", "HOME", "HOMEDRIVE", "HOMEPATH", "USERPROFILE",
    "LANG", "LC_ALL", "LC_CTYPE", "PYTHONUTF8",
}


def _clean_env(extra: Optional[dict]) -> dict:
    base = {k: v for k, v in os.environ.items() if k.upper() in _SAFE_ENV_KEYS}
    base.update(extra or {})
    return base


@dataclass
class StepResult:
    command: str
    ok: bool
    exit_code: Optional[int]
    output: str
    gap: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InstallReport:
    steps: list[StepResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return bool(self.steps) and all(s.ok for s in self.steps)

    @property
    def gaps(self) -> list[StepResult]:
        return [s for s in self.steps if s.gap]

    def to_dict(self) -> dict:
        return {"all_ok": self.all_ok, "steps": [s.to_dict() for s in self.steps]}


def run_documented_install(
    commands: list[str],
    *,
    workdir: Optional[str] = None,
    timeout: float = 120.0,
    env: Optional[dict] = None,
) -> InstallReport:
    """Run each documented command in a throwaway dir; return a per-step report.

    A non-zero exit, timeout, or spawn failure marks that step as a gap and the run
    proceeds to the next command rather than raising.
    """
    report = InstallReport()
    cleanup = workdir is None
    workdir = workdir or tempfile.mkdtemp(prefix="pmkit-dogfood-")
    run_env = _clean_env(env)
    try:
        for cmd in commands:
            report.steps.append(_run_one(cmd, workdir, timeout, run_env))
    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)
    return report


def _run_one(cmd: str, cwd: str, timeout: float, env: dict) -> StepResult:
    try:
        p = subprocess.run(
            cmd, shell=True, cwd=cwd, env=env,
            capture_output=True, text=True, timeout=timeout,
        )
        output = ((p.stdout or "") + (p.stderr or ""))[-4000:]
        ok = p.returncode == 0
        return StepResult(cmd, ok, p.returncode, output, gap=not ok,
                          reason="" if ok else f"exit {p.returncode}")
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        return StepResult(cmd, False, None, partial[-4000:], gap=True,
                          reason=f"timeout after {timeout}s")
    except Exception as e:  # spawn failure (bad command, missing interpreter, ...)
        return StepResult(cmd, False, None, str(e), gap=True, reason=f"could not run: {e}")
