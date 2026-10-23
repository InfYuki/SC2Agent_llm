# 真人学习批准与退出局排除

## 2026-10-23 真人赛后学习改为人工确认

照常运行 `.\run_human_training.cmd --human-fullscreen`。对局结束后终端询问 `Learn from this match (LLM + PPO + replay)?`：输入 `y` 才更新 LLM 经验、PPO 和复盘经验；输入 `n` 跳过，直接回车或终端无交互则保留待定。原始记录均保留。可用 `--learn no` 预设本局不学，`--learn yes` 显式预先允许自动学习。暂时跳过后，可运行 `.\run_human_training.cmd --learn-run <run_id> --learn yes` 补学，不会打开游戏；成功消费的 PPO 不会重复训练。直接调用 learner 或复盘经验写入也检查批准和永久排除。

用户指定不算的退出局 `human_20261023_200418_872055` 已永久排除，备份共享经验后从其余三局重建 LLM 聚合经验，防止只删记录而残留 lessons。该局约50.09秒，原记录显示 Agent Victory，但不计有效战果；PPO有效样本0、未更新模型。后继有效局 `human_20261023_200655_490506` 的161条PPO样本、27段轨迹、6次优化保留，最新模型指针未改。后继 LLM 在当局可能已读取退出局经验，这部分历史影响无法追溯撤销。详见[人工学习开关与排除报告](docs/HUMAN_LEARNING_APPROVAL_REPORT.md)。下方旧“赛后自动学习”说明为历史流程，以本节为准。


永久排除记录为退出局目录内 `learning_excluded.json`，原始 learning_report、回放和事件保留作审计，备份位于 `learning_exclusion_backup/`。人工决定保存为 `learning_decision.json`。永久排除优先于批准，不能以 `--learn yes` 清除。该机制阻止赛后经验更新；比赛进行期间仍启用 LLM 指挥与 PPO 采样。

本轮没有新开游戏、API请求或重新训练。离线检查覆盖批准/跳过/待定、直接学习拦截、回放经验拦截、排除经验重建和模型指针保持。PPO若已经更新，排除工具拒绝自动回滚，必须先检查后继模型血缘，不能声称删一局记录就撤销梯度。
