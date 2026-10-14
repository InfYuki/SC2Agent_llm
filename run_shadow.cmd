@echo off
call "%~dp0run_rule.cmd" --mode shadow %*
exit /b %errorlevel%
