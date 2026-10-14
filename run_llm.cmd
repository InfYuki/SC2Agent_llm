@echo off
call "%~dp0run_rule.cmd" --mode llm %*
exit /b %errorlevel%
