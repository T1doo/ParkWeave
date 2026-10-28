@echo off
setlocal DisableDelayedExpansion
"%~dp0runtime\python\python.exe" -I -B "%~dp0launcher\entry.py" %*
set "pw_exit=%ERRORLEVEL%"
if not "%pw_exit%"=="0" pause
exit /b %pw_exit%
