@echo off
REM ---------------------------------------------------------------------------
REM Windows helper: run Python without quoting problems.
REM
REM This machine's shell mangles quoted absolute paths (the space in
REM "C:\Users\Jay Sharma\..." breaks them), and the POSIX commands in
REM COVEXCODE.md (.venv/bin/python) do not exist on Windows.
REM
REM Usage, from the repository root:
REM   scripts\py.cmd -m pytest -q
REM   scripts\py.cmd scripts\check_sample_data.py
REM
REM It uses .venv\Scripts\python.exe when the virtualenv exists, otherwise the
REM user-level Python 3.12 install. Local dev convenience only; not used by the
REM app, the tests, or any deployment.
REM ---------------------------------------------------------------------------
setlocal
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYEXE=%~dp0..\.venv\Scripts\python.exe"
"%PYEXE%" %*
exit /b %ERRORLEVEL%
