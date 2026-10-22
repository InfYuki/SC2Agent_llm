@echo off
call "%~dp0run_rule.cmd" --mode llm_ppo --ppo-model "%~dp0artifacts\models\marine_ppo_two_enemy448_20261021" --ppo-engagement-gate %*
exit /b %errorlevel%
