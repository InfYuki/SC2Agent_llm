@echo off
call "%~dp0run_rule.cmd" --mode rule_ppo --ppo-model "%~dp0artifacts\models\marine_ppo_mvp_20261019" %*
exit /b %errorlevel%
