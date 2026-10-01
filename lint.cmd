@echo off
setlocal
set PY=%~dp0.venv\Scripts\python.exe
set TARGETS=src tests
"%PY%" -m ruff check %TARGETS% || exit /b 1
"%PY%" -m pycodestyle --max-line-length=140 %TARGETS% || exit /b 1
"%PY%" -m flake8 --max-line-length=140 %TARGETS% || exit /b 1
"%PY%" -m pylint %TARGETS% || exit /b 1
"%PY%" -m mypy src || exit /b 1
echo lint OK
