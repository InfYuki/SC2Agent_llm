# P5 PPO 续训与局部部署最小 MVP

日期：2026-10-19。已有32步PPO checkpoint成功再训练32步，累计64步；导出NumPy actor后完成一次真实单Marine短场景接管。属于工程链路验证，无战斗收益或胜率结论，P5整阶段与规模训练就绪尚未验收。

## 本轮唯一真实训练与部署

| 项目 | 结果 |
|---|---|
| 续训来源 | `artifacts/micro_ppo/p5_ppo_mvp_20261018/model.zip`；父模型与metadata SHA256均保持不变 |
| 续训输出 | `artifacts/micro_ppo/p5_ppo_resume_mvp_20261019/`；新目录，不覆盖父模型 |
| 累计与优化器 | 32→64步，本轮32步；n_updates 2→4；12个Adam状态step均4→8；初始policy hash与加载父模型一致 |
| 超参 | 从父checkpoint继承n_steps32/batch16/epochs2/lr0.0003、CPU；冲突参数拒绝 |
| 实机采样 | 14+14步完整marine_dead，官方Defeat/Victory及close确认；另4步预算close部分episode；49.359秒 |
| 逐条核验 | 32/32 mask合法、真实8loops、HP奖励复算误差0；system_failure/discard/专家标签均0 |
| 命令结果 | 21 engine_confirmed、8 hold、3 order_preserved；preserved只表示已有order保留 |
| 更新与重载 | 全参数finite且actor改变；最大参数变化0.001214163；保存重载同obs+mask概率误差0、确定性动作一致 |
| 导出一致性 | 复用父训练32条真实source_obs/source_mask，SB3→NumPy概率最大误差5.9604645e-8、动作32/32一致、masked概率全0 |
| 部署范围 | 唯一`marine-vs-marine`、seed42、20秒上限；exit0，10次PPO推理/10 owned，10条全HOLD（action4） |
| 局部结果 | 4.375游戏秒low_health_safety_exit，己/敌HP均9；truncated=true、terminated=false；外层Defeat不作为全局战斗结论 |
| 安全与边界 | fallback/非法mask/命令冲突/telemetry error均0；PPO行expert=null、bc_eligible=false；结束无SC2_x64残留 |

actor目录为`artifacts/models/marine_ppo_mvp_20261019`，只有actor权重与来源metadata；运行时只用NumPy、不import Torch/SB3。新checkpoint SHA256：`eaf6f375b1f37b42c88555916f4e9afcf953c1b3f08a0ac410f6f686177b8fd9`；weights.npz SHA256：`dc4964b5d0d0f813d791c126675ef6ed7fe87af1268e4ce216159a6412efde03`。模型与原始证据被Git忽略，迁移另带。

完整机器摘要见[micro_ppo_deploy_mvp.json](validation/micro_ppo_deploy_mvp.json)。续训目录含training_report、training_transitions、verification_report、export_parity_report及episodes/*/game/rl_rollout.jsonl。部署原始目录`artifacts/runs/p5_ppo_deploy_mvp_20261019`，含manifest、events、micro_transitions、scenario_result、summary与回放。

## 使用与继续训练

双击或运行`.\run_ppo.cmd`即以规则宏观战略+本轮PPO Marine微操启动实时对局；`.\run_ppo.cmd --show-config`只显示配置，已核验mode=rule_ppo及默认模型路径。`--ppo-model <目录>`可覆盖。默认规则、BC入口保留；加载或推理错误明确记录后规则回退，PPO与fallback均为非专家标签。局部PPO不调用LLM、不读凭据。完整对局入口已做CLI验证，本轮真实部署验证范围仅上述短场景。

在项目目录继续现64步模型，例如新增320步（10个32步rollout，示例未运行；输出目录必须不存在）：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/p5_ppo_next --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_ppo_resume_mvp_20261019 --total-timesteps 320
```

`--total-timesteps`表示本次新增步数，正整数且为继承n_steps32的倍数；示例成功后累计384步。`--resume`可接模型目录或model.zip，恢复policy、optimizer及累计timesteps；新SC2 episode重新开始、随机状态不保证逐位复演。冲突超参拒绝。每次训练结果另存新目录，部署需另行导出actor并显式选新目录：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/export_micro_ppo.py artifacts/micro_ppo/p5_ppo_next/model.zip artifacts/models/marine_ppo_next
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_next
```

## 验证与下一步

本轮仅trainer一项合成续训/失败定向检查、runtime两项定向检查，配合上述真实32步、已有32观测parity和唯一短部署；未重跑历史suite、未额外跑fallback游戏。真实部署全部HOLD，说明接管链路可用，也显示当前64步模型不能称为已学会战斗。下一步使用续训入口增加有限训练预算并诊断奖励/动作分布，再做少量规则/BC对比；不继续扩大工程验证范围。真实系统崩溃、训练时间截断、训练敌死、完整局部署强度仍未验收。summary历史stop_reason统一写game_time_limit，局部退出以scenario_result和尾transition为准；场景micro_transitions.reward仍null，不能当成训练RL rollout奖励。
