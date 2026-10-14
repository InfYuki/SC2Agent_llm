@echo off
call "%~dp0run_rule.cmd" --mode micro_rule %*
exit /b %errorlevel%
