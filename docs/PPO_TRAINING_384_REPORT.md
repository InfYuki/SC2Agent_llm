# PPO 有限续训至384步与单组局部对比

日期：2026-10-19。从64步模型唯一新增320步，累计384步；保存、重载及NumPy导出通过，随后仅串行运行新PPO与规则kite各1局。没有明确训练收益趋势，不能宣称胜率提升、模型最佳或P5全面验收。预算结束关闭worker时出现EOFError，保留为未解决边界。

## 训练与导出

| 项目 | 本轮事实 |
|---|---|
| 来源与输出 | 父`artifacts/micro_ppo/p5_ppo_resume_mvp_20261019`保持不变；新`artifacts/micro_ppo/p5_ppo_train384_20261019` |
| 步数与更新 | 64→384，新增320真实8loops步；10个32步rollout；n_updates4→24，12个Adam状态step8→48 |
| 超参 | 继承n_steps32/batch16/epochs2/lr0.0003/gamma0.99/GAE0.95/clip0.2、CPU；不改奖励、不用BC初始化 |
| 采样 | 21完整marine_dead（每局13..17步，均有双方官方Result及close确认），另1局预算close前5步；360.344墙钟秒 |
| 采样核验 | 320/320 mask合法、真实8loops、HP奖励复算误差0；trace float32奖励最大误差5.5631e-8；buffer内system_failure/discard/conflict/专家标签均0 |
| 请求动作0..4 | [23,34,71,89,103]；199 engine_confirmed、103 hold、10 queued、8 order_preserved；后两类不冒充新命令确认 |
| 参数与重载 | 全参数finite、actor改变，最大参数变化0.010989979；同obs+mask保存重载概率误差0、确定性动作一致 |
| NumPy导出 | `artifacts/models/marine_ppo_train384_20261019`；复用本轮320条真实source_obs/source_mask，SB3→NumPy概率最大误差8.9406967e-8，动作320/320一致、masked概率全0 |

新checkpoint SHA256：`543c059aec4cd790322d5e7b9d14c03744c34163e78d6c0d64dfebcc91c6a3c2`。actor weights SHA256：`9412ff95de1bdb865eb30f3dc42ba9489f5ca857a72d473854046f8ffa33f22b`。模型、回放与逐步原始证据被Git忽略，迁移需另带。

最后部分episode `6cb62b746d2b422e829dde3103dd894e`的5条采样均正常，尾步terminated/truncated均false，己/敌HP27/33；预算结束close后worker.log出现EOFError/Unknown exception，无该局summary或官方Result。关闭异常未作为新transition进入buffer，trainer exit0并保存模型，关闭后无SC2残留；不能据此写成所有日志零错误或该局正常完成，预算close的异常传播/清理语义仍需后续修复。本轮未为此追加游戏或改代码。

## 行为与奖励诊断

21完整训练局己方最终HP均0，敌方最终HP15..33、均值22.429，完整回报均值-1.498413。五个连续64步块奖励和依次-5.8667、-6.1333、-7.3333、-6.2667、-6.0000；每块完成局数不同，不作为严格同条件强度指标，未见清晰改善。

复用同一批320条真实观测离线比较父64步与新384步actor：两者确定性argmax均320次HOLD，平均HOLD概率0.309289→0.342991；这与训练时随机采样五动作的分布不同。HOLD保留既有order，Marine可自动攻击，不能只按HOLD占比判模型无效。没有额外运行旧策略游戏。

## 同场景配置的2探索短场（非严格因果对照）

固定新seed20261019、Ancient Cistern LE、marine-vs-marine-v6、双方各1 Marine、初始满HP、distance6、20游戏秒上限、非实时8loops、test标记。训练释放SC2后才串行运行；两局源哈希、初始frame18、位置、HP、mask一致。初始16维观测仅己方武器cooldown不同（归一化obs[2]：PPO0.35891927、规则0.19773763）；同seed只固定场景seed，不是完整引擎随机状态；pair_initial_state_fully_matched=false、controlled_comparison=false，限制因果解释，未挑seed或重跑。

| 指标 | PPO384 | 规则kite |
|---|---|---|
| 局部结果 | low_health_safety_exit | low_health_safety_exit |
| 结束游戏时间 | 4.375秒 | 5.089286秒 |
| 有效HP：己/敌 | 45/45→9/9 | 45/45→9/27 |
| 请求动作0..4 | [0,0,0,0,10] | [0,3,4,3,2] |
| 命令结果 | 10 hold，无新增命令确认 | 10 engine_confirmed、2 hold |

两局均exit0、truncated=true/terminated=false，mask合法、8loops、0命令冲突、summary.error=null，PPO10推理/10owned、无fallback，PPO行expert=null/bc_eligible=false；结束无SC2残留。有效HP由初始真实HP和尾next_obs的Marine血量比例×45复算，Marine无盾。两局双方官方Defeat/Victory只确认外层主动结束，不能当完整比赛胜负。场景reward=null，未冒充训练奖励。

本样本PPO敌方损失36HP、规则18HP，但规则多存活约0.714游戏秒；初始cooldown有差异、且只有一组局部截断样本，HP差18不能归因于策略更强，不能推出胜率或通用强度改善。训练环境以死亡终止，部署场景有20%低血退出，两者范围不同。

原始目录：`artifacts/runs/p5_ppo384_pair_ppo_20261019`与`artifacts/runs/p5_ppo384_pair_rule_20261019`。共享机器摘要：[ppo_training_384.json](validation/ppo_training_384.json)。训练目录另有training_report、verification_report、behavior_report、export_parity_report与episodes原始日志。

## 运行与下一步

`run_ppo.cmd`默认仍指向原64步actor `artifacts/models/marine_ppo_mvp_20261019`，本轮未改脚本；新384步只是最新有限训练模型，没有证据称为最佳。显式运行新模型：

```powershell
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_train384_20261019
```

本轮复用现有续训/导出路径，未改实现、依赖、奖励或凭据；未重跑旧suite、未额外做BC/旧策略游戏。下一步优先诊断预算close异常、训练任务/奖励与确定性部署行为，标准化含cooldown的初态后再做小对照，评估是否采用BC初始化；不要仅凭本轮结果无限加步。P5全面验收、规模训练就绪、完整局部署强度及泛化仍未建立。
