@echo off
setlocal
cd /d "%~dp0"
rem An explicit ARES_ENV takes priority; otherwise find the named local env.
if not defined ARES_ENV if /i "%CONDA_DEFAULT_ENV%"=="sc2-ares-runtime" set "ARES_ENV=%CONDA_PREFIX%"
if not defined ARES_ENV if exist "%USERPROFILE%\anaconda3\envs\sc2-ares-runtime\python.exe" set "ARES_ENV=%USERPROFILE%\anaconda3\envs\sc2-ares-runtime"
if not defined ARES_ENV if exist "%USERPROFILE%\miniconda3\envs\sc2-ares-runtime\python.exe" set "ARES_ENV=%USERPROFILE%\miniconda3\envs\sc2-ares-runtime"
if not defined ARES_ENV if exist "%LOCALAPPDATA%\miniconda3\envs\sc2-ares-runtime\python.exe" set "ARES_ENV=%LOCALAPPDATA%\miniconda3\envs\sc2-ares-runtime"
if not exist "%ARES_ENV%\python.exe" (
  echo Activate sc2-ares-runtime, or set ARES_ENV to its directory before launch.
  exit /b 2
)
set "PYTHONNOUSERSITE=1"
set "PATH=%ARES_ENV%;%ARES_ENV%\Scripts;%ARES_ENV%\Library\bin;%PATH%"
"%ARES_ENV%\python.exe" -s -u tools\run_logged.py --mode rule %*
set "ARES_CODE=%errorlevel%"
if not "%ARES_CODE%"=="0" (
  echo See artifacts\last-run.log for details.
  pause
)
exit /b %ARES_CODE%
