# P5 训练预算 graceful close 有限 MVP（2026-10-20）

预算关闭协议已完成两次真实短场验收：reset 后立即 close、reset 后执行一次合法 action 再 close，均收到身份匹配的 ACK、已落盘 summary，worker exit0；无 EOFError、Traceback、额外 transition 或 SC2 残留。未训练 PPO 或更新模型，不代表 P5 全面验收、规模训练就绪或战斗收益。

## 修复范围

父端在当前 episode/decision/frame 发送 `close`，等待同身份 `closed` 和 worker exit0；失败抛出 `MicroEnvCloseError`，强制清理仅限自有 worker 树，不把强杀当正常关闭。worker 接受控制消息后停止动作采样、主动 leave，等待双方 SDK 返回，先关闭 rollout/写 summary，再 ACK。worker 专用 Telemetry 延后继承 on_end 的提前 finish，避免预算原因被单方结果覆盖、事件文件过早关闭。训练清理若与原异常同时失败，保留原异常并附注关闭错误。

预算 `summary.status=interrupted`、`stop_reason=training_budget_close`、`result=null/error=null`；`scenario_result` 同原因为 truncated/非 terminated。ACK/事件保留官方 Defeat/Victory，仅说明主动 leave 握手完成，不能计作自然战斗胜负。关闭本身不伪造终态奖励或 transition，原有合法样本保持原样。

## 唯一真实验收

源码冻结后新建 `artifacts/p5_graceful_close_20261020/plan.json`，SHA256 `9cb3779c2e5f9d850b0f7b217c84286453b6760265535d55dbb55752c2af78ed`。两局均 Ancient Cistern LE、Marine 对 Zergling、名义距8、满HP、12游戏秒上限、非实时8loops、seed20261020；runtime `C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe -s`，SC2 `C:/Program Files (x86)/StarCraft II`。本次实际唯一命令：

```powershell
& C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s artifacts/p5_graceful_close_20261020/validate_close.py
```

| case / episode | 关闭时 decision / frame | 合法 RL / micro 行数 | 关闭墙秒 / exit |
|---|---|---|---|
| reset_close / 686151eb64bb4328ba4905a75571bcf5 | 0 / 17 | 0 / 0 | 2.094 / 0 |
| reset_step_close / 6e796a83c28840689078903e20794c40 | 1 / 25 | 1 / 1 | 2.094 / 0 |

第二局按预冻结“最低 index 合法动作”选择 action2（退却），17→25 恰8loops，engine_confirmed于loop18；HP45/35、奖励0、未终止/截断后 close。两个 case 的 ACK episode/decision/frame 均与关闭前 state 相同，收到 ACK 的当刻 summary 已存在且预算分类正确；之后 worker 真正 exit0。两局 `sc2_base_build=98370`，无命令冲突，前后 SC2 进程均0。包装实例 `_receive` 仅观测原样返回的 ACK/summary 是否存在，不改变协议。

原始 `rl_rollout.jsonl`、`micro_transitions.jsonl` 各为0/1行，未增加关闭 transition。唯一 micro 行 expert=null、bc_eligible=false、reward=null；环境 RL 奖励0与场景旧 reward=null 各按原语义保留。两新 case 的 learning_exclusion 按 raw SHA 永久排除未来训练；本次没有学习。

## 证据与边界

68个 tracked Python 源文件、仓库/安装两份地图及4个指定历史课程/PPO报告证据 SHA 前后一致。plan、results、console、postcheck、每局 manifest/summary/scenario/事件/rollout/回放等33个新文件的终态 SHA 在 `artifacts/p5_graceful_close_20261020/hashes.json`，其 SHA256 `9af1310d8f89a7389d8f214bcfb7922479cb6f4526b98a61a50791116213848b`；共享完整清单见 [p5_graceful_close_mvp.json](validation/p5_graceful_close_mvp.json)。未读取 live latest_state、凭据或完整 API 配置，旧 artifact/模型/报告不修改，原始工件 Git 忽略，迁移另带。

实现代理只新增1项合并定向 mock：`python -s -m unittest tests.test_sc2_micro_env.MicroEnvContractTests.test_budget_close_handshake_cleanup_and_no_extra_transition -v`。初版1/1通过，scope发现继承on_end提前finish缺陷后修复并扩充同一项，必要重跑1次1/1通过；最终5文件py_compile、worker --help、diff检查通过，scope复核无阻碍。该项覆盖正常 ACK、超时/错误身份/非零退出及自有树清理；失败强制清理仅 mock，未真实制造超时/kill。真实范围严格限上述2 case，无失败重试、额外对局、安装、LLM、PPO训练或历史全 suite 重跑。旧课程 budgetclose 的 EOFError/缺 summary 等失败证据仍保留；本轮两次成功不能改写旧结论，也未复验自然终局或训练后的关闭行为。后续新授权训练/任务验收仍按预算和初态边界进行。

用户要求先推的基线 `f2618ccf589225ef776dece79f5c45b30acc6cf8` 已在 `origin/MacZhi-P6`；本轮修复及报告为本地待提交变更，不擅自 push。
