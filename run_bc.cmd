@echo off
call "%~dp0run_rule.cmd" --mode rule_bc --bc-model "%~dp0artifacts\models\marine_bc_mvp_20261018_seed42" %*
exit /b %errorlevel%
