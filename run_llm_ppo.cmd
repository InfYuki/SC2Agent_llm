@echo off
call "%~dp0run_rule.cmd" --mode llm_ppo --ppo-model "%~dp0artifacts\models\marine_ppo_curriculum256_20261019" %*
exit /b %errorlevel%
