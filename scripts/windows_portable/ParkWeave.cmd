@echo off
setlocal DisableDelayedExpansion
if "%~1"=="" goto desktop
"%~dp0runtime\python\python.exe" -I -B "%~dp0launcher\entry.py" %*
set "pw_exit=%ERRORLEVEL%"
if not "%pw_exit%"=="0" pause
exit /b %pw_exit%
:desktop
if not exist "%~dp0ParkWeave.exe" goto missing_desktop
"%~dp0ParkWeave.exe"
exit /b %ERRORLEVEL%
:missing_desktop
echo ParkWeave desktop executable is missing. This is an engineering candidate, not a desktop delivery.
pause
exit /b 2
