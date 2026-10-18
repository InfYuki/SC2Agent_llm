# P5 真实步进环境 MVP

日期：2026-10-18。单 Marine 对单 Marine，真实 SC2 冷启动 `reset(seed=42)`、`step(action)`、`action_masks()`、`close()` 已接通。环境为自定义 Gym 风格接口，未继承 Gymnasium Env；尚未安装 Torch/PPO 或训练策略。P5整阶段与训练就绪均未验收。

## 接口与奖励

`envs.sc2_micro_env.SC2MicroEnv` 在独立 worker 启动固定步游戏，通过本机认证 IPC 交换 episode/decision/frame/unit_slot。父端拒绝越界及当帧 masked 动作，再由 worker复核身份与mask；合法动作经既有arbiter唯一出口执行。reset重新启动一局，支持seed；MVP固定1v1 Marine、距离6，不支持动态scenario/options。每步实际推进8 game loops。

奖励版本 `effective-hp-delta-45-terminal-1-v1`：`(敌方有效生命损失 - 己方有效生命损失) / 45 + 敌方死亡 - 己方死亡`。有效生命包含护盾，治疗对应负损失；明确死亡按0结算。敌方失去可见性或单位无解释缺失时不推定击杀，丢弃rollout。死亡/目标死亡为terminated；时间上限为truncated；IPC/worker异常为系统失败、truncated且rollout_discard，不能作战术胜负训练。

活状态返回16维观测和5维mask。己方死亡可返回`obs=None`、HOLD-only mask，这不是可直接送入标准Gymnasium/PPO采样器的终态数组契约。外部训练动作日志为`external-training-action-v1`，`expert_labels=false`、`bc_eligible=0`，与P3专家数据隔离。

## 唯一真实 episode 证据

运行目录 `artifacts/micro_env/c06761effef34708901c214e7d7c3bd7/`；完整driver及原始报告位于`artifacts/p5_verify_one.py`、该目录`verification_report.json`。共享摘要 [micro_env_mvp.json](validation/micro_env_mvp.json)。通过真实env API调用，没有旁路原场景runner。

| 项目 | 结果 |
|---|---|
| 配置 | Ancient Cistern LE、seed42、固定步、8游戏秒上限、确定性合法动作优先0/1/3/4 |
| reset / step | reset frame17；14步至frame129，每步8loops，decision_id连续 |
| 非法动作 | action5与当帧masked action0均ValueError，frame17/decision0不变 |
| HP与奖励 | 己方45→0，敌方45→9；14条逐步按前后HP复算一致；总奖励-1.2，其中终局-1 |
| 局部结束 | marine_dead，5.759游戏秒，terminated=true、truncated=false、obs=None、HOLD-only |
| 系统与出口 | error=null、rollout_discard=false、0命令冲突；14条训练动作日志、0 BC合格标签 |
| 关闭 | 双方原SDK官方Result为Defeat/Victory；父端收到closed；worker exit0；close后自己新增SC2 PID全部退出 |

14步中4次attack、10次approach；规则专家及BC未参与动作选择。本局不证明策略强度。6条engine_confirmed、7条engine_unconfirmed、1条order_preserved；未把所有排队命令写成引擎确认。

第一次reset在启动游戏前因父端与Telemetry同时创建输出目录失败（`9ebf9ed0bcc74ece829644dd0608526a/worker.log`）。最小修复为worker游戏证据写入`game/`子目录，父端保留episode根目录及worker.log；修复后仅启动上述一局真实游戏。失败证据保留，不计成功episode或训练数据。

## 使用与边界

```powershell
python -s tools/smoke_micro_env.py --seed 42 --max-game-seconds 8 --game-path 'C:\Program Files (x86)\StarCraft II'
```

该命令会新启动一局，只用于主动重验；本轮实际使用带HP/非法动作/PID断言的临时driver。普通smoke写episode根目录`smoke_report.json`；worker证据在`game/`，训练转移在`game/rl_rollout.jsonl`。不读取LLM凭据、不调用LLM。

新增2项父端定向契约测试通过，worker编译/CLI通过；未重复历史全suite/24局。实机仅覆盖marine_dead，时间截断、敌方死亡、主动中途close、超时/崩溃、重复reset尚未做真实游戏验证。冷启动reset约19.515秒；单局不足以验收训练吞吐。通用场景`summary.json`仍沿历史分类为game_time_limit/truncated；环境终止以`rl_rollout.jsonl`及env返回为准，`micro_summary.reward=not_implemented`是旧示范记录器字段，真实奖励位于RL rollout。

下一步以当前自定义桥接为基础补齐训练适配与必要边界/吞吐证据，再另建训练环境接PPO；默认规则、P3/P4基线保持原用途。
