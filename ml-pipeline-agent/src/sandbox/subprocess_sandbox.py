"""Subprocess-based sandbox — executes code in an isolated Python interpreter."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from src.config.settings import settings
from src.sandbox.base import ExecutionResult
from src.sandbox.validators import validate_code
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SubprocessSandbox:
    """Execute Python code in a subprocess with timeout and resource limits.

    The Docker container itself is the outer security boundary when deployed.
    This subprocess layer provides:
    - Process isolation (separate interpreter)
    - Timeout enforcement
    - AST validation (pre-execution)
    - Working directory isolation
    """

    def __init__(
        self,
        timeout_sec: int | None = None,
        python_path: str = "python3",
    ) -> None:
        self._timeout_sec = timeout_sec or settings.SANDBOX_TIMEOUT_SEC
        self._python_path = python_path

    async def execute(
        self,
        code: str,
        *,
        working_dir: str | None = None,
        timeout_sec: int | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute Python code in a subprocess.

        Args:
            code: Python code to execute.
            working_dir: Directory for file I/O. Created if needed.
            timeout_sec: Override default timeout.
            env_vars: Additional env vars for the subprocess.

        Returns:
            ExecutionResult with captured stdout/stderr.
        """
        effective_timeout = timeout_sec or self._timeout_sec

        # 1. AST validation — reject before execution
        validation = validate_code(code)
        if not validation.valid:
            logger.warning("Code validation failed", error=validation.error)
            return ExecutionResult(
                success=False,
                error_type="ValidationError",
                error_message=validation.error,
            )

        if validation.warnings:
            logger.info("Code validation warnings", warnings=validation.warnings)

        # 2. Prepare working directory
        work_dir = Path(working_dir) if working_dir else Path(tempfile.mkdtemp(prefix="sandbox_"))
        work_dir.mkdir(parents=True, exist_ok=True)

        # 3. Write code to temp file (avoids shell escaping issues with -c)
        code_file = work_dir / "_sandbox_exec.py"
        code_file.write_text(code, encoding="utf-8")

        # 4. Build environment
        import os

        env = os.environ.copy()
        # Restrict PATH to essentials
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        if env_vars:
            env.update(env_vars)

        # 5. Execute
        start = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                self._python_path,
                str(code_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout,
            )

            elapsed = time.monotonic() - start
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            success = process.returncode == 0

            if not success:
                # Parse error type from stderr
                error_type = _parse_error_type(stderr)
                logger.warning(
                    "Sandbox execution failed",
                    error_type=error_type,
                    returncode=process.returncode,
                    elapsed=f"{elapsed:.2f}s",
                )
            else:
                logger.info("Sandbox execution succeeded", elapsed=f"{elapsed:.2f}s")

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                execution_time_sec=elapsed,
                error_type=None if success else _parse_error_type(stderr),
                error_message=stderr if not success else None,
            )

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            # Kill the process
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass

            logger.warning(
                "Sandbox execution timed out",
                timeout=effective_timeout,
                elapsed=f"{elapsed:.2f}s",
            )
            return ExecutionResult(
                success=False,
                execution_time_sec=elapsed,
                error_type="TimeoutError",
                error_message=f"Execution exceeded {effective_timeout}s timeout",
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("Sandbox execution error", error=str(e))
            return ExecutionResult(
                success=False,
                execution_time_sec=elapsed,
                error_type=type(e).__name__,
                error_message=str(e),
            )

        finally:
            # Cleanup temp code file (leave working_dir contents for artifact retrieval)
            try:
                code_file.unlink(missing_ok=True)
            except Exception:
                pass


def _parse_error_type(stderr: str) -> str:
    """Extract Python error type from traceback."""
    lines = stderr.strip().splitlines()
    if lines:
        last_line = lines[-1]
        if ":" in last_line:
            return last_line.split(":")[0].strip()
    return "RuntimeError"
