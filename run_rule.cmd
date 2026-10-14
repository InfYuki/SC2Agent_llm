@echo off
setlocal
cd /d "%~dp0"
set "ARES_ENV=C:\Users\27932\anaconda3\envs\sc2-ares-runtime"
set "PYTHONNOUSERSITE=1"
set "PATH=%ARES_ENV%;%ARES_ENV%\Scripts;%ARES_ENV%\Library\bin;%PATH%"
"%ARES_ENV%\python.exe" -s -u tools\run_logged.py --mode rule %*
set "ARES_CODE=%errorlevel%"
if not "%ARES_CODE%"=="0" (
  echo See artifacts\last-run.log for details.
  pause
)
exit /b %ARES_CODE%
