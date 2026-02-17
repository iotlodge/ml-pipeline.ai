"""Tests for sandbox execution and code validation."""

from __future__ import annotations

import pytest

from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.sandbox.validators import validate_code


# ── Validator Tests ───────────────────────────────────────────────────────────


class TestCodeValidator:
    def test_valid_pandas_code(self) -> None:
        code = "import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df.shape)"
        result = validate_code(code)
        assert result.valid

    def test_valid_sklearn_code(self) -> None:
        code = "from sklearn.ensemble import RandomForestClassifier\nmodel = RandomForestClassifier()"
        result = validate_code(code)
        assert result.valid

    def test_reject_subprocess(self) -> None:
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = validate_code(code)
        assert not result.valid
        assert "subprocess" in result.error

    def test_reject_exec(self) -> None:
        code = "exec('print(1)')"
        result = validate_code(code)
        assert not result.valid

    def test_reject_eval(self) -> None:
        code = "result = eval('1+1')"
        result = validate_code(code)
        assert not result.valid

    def test_reject_os_system(self) -> None:
        code = "import os\nos.system('rm -rf /')"
        result = validate_code(code)
        assert not result.valid

    def test_reject_socket(self) -> None:
        code = "import socket\ns = socket.socket()"
        result = validate_code(code)
        assert not result.valid

    def test_reject_requests(self) -> None:
        code = "import requests\nrequests.get('http://evil.com')"
        result = validate_code(code)
        assert not result.valid

    def test_syntax_error(self) -> None:
        code = "def foo(\n  print('broken')"
        result = validate_code(code)
        assert not result.valid
        assert "SyntaxError" in result.error

    def test_warn_unknown_import(self) -> None:
        code = "import some_random_module"
        result = validate_code(code)
        assert result.valid  # Not blocked, but warned
        assert result.warnings


# ── Sandbox Execution Tests ───────────────────────────────────────────────────


class TestSubprocessSandbox:
    @pytest.fixture
    def sandbox(self) -> SubprocessSandbox:
        return SubprocessSandbox(timeout_sec=10)

    @pytest.mark.asyncio
    async def test_simple_execution(self, sandbox: SubprocessSandbox) -> None:
        result = await sandbox.execute("print('hello world')")
        assert result.success
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_pandas_execution(self, sandbox: SubprocessSandbox) -> None:
        code = "import pandas as pd\ndf = pd.DataFrame({'a': [1,2,3]})\nprint(df.shape)"
        result = await sandbox.execute(code)
        assert result.success
        assert "(3, 1)" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout(self, sandbox: SubprocessSandbox) -> None:
        code = "import time\ntime.sleep(30)"
        result = await sandbox.execute(code, timeout_sec=2)
        assert result.failed
        assert result.error_type == "TimeoutError"

    @pytest.mark.asyncio
    async def test_validation_blocks_dangerous_code(self, sandbox: SubprocessSandbox) -> None:
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = await sandbox.execute(code)
        assert result.failed
        assert result.error_type == "ValidationError"

    @pytest.mark.asyncio
    async def test_runtime_error(self, sandbox: SubprocessSandbox) -> None:
        code = "x = 1 / 0"
        result = await sandbox.execute(code)
        assert result.failed
        assert "ZeroDivisionError" in (result.error_type or "")
