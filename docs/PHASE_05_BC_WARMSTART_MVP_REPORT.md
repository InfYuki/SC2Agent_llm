# P5 BC actor warm-start → PPO 最小 MVP

日期：2026-10-19。冻结BC actor成功迁移到新PPO，并完成唯一一次真实32步训练及唯一一次训练后短部署；不是原随机初始化384步checkpoint续训。默认`run_ppo.cmd`仍指原64步actor，奖励、场景、依赖与BC原文件未改。仅工程MVP，无战斗收益结论。

## 迁移与真实训练

`tools/train_micro_ppo.py --init-bc <目录>`严格验证NumPy BC契约、权重与冻结数据hash，仅将三层actor权重转置复制到SB3 Linear；critic保留独立随机初始化、optimizer空状态。与`--resume`互斥；warm-start来源与后续resume来源分别记录，不能混淆累计步数。初始化前验证失败不启动SC2。

来源`artifacts/models/marine_bc_mvp_20261018_seed42`，冻结数据`artifacts/micro_datasets/p3_v7_formal_20261018_115352_dataset`共82条。训练前已保存`initialization_report.json`：BC与PPO原始logits最大差2.861022949e-6、masked概率最大差3.87430191e-7，82/82确定性动作一致、critic未变、optimizer空。该证据是在learn之前生成；82条仅作迁移诊断，不冒充正式1000观测验收。

| 项目 | 本轮事实 |
|---|---|
| 新PPO输出 | `artifacts/micro_ppo/p5_bc_warmstart_20261019`，累计0→32，n_updates 0→2 |
| 超参 | seed42、n_steps32/batch16/epochs2/lr0.0003、CPU；12个Adam状态由空变step4 |
| 时间与采样 | 52.828秒；2局完整marine_dead，各16步，官方Defeat/Victory及close均确认；敌最终HP15/9 |
| 真实32条 | mask合法、实际8loops；HP奖励复算误差0，trace float32误差5.5631e-8；buffer内failure/discard/专家/冲突均0 |
| 采样动作0..4 | `[0,7,7,5,13]`；18 engine_confirmed、13 hold、1 order_preserved（不冒充新命令确认） |
| 更新/重载 | 所有参数finite、actor改变；全参数最大变化0.0012024492；保存重载概率误差0、动作一致 |
| BC来源 | weights与metadata hash均未变；无随机PPO父checkpoint |

checkpoint SHA256：`d81fe552b3b2a126283d3fb38b31aa8e86e69d506bd842611213ef0f9af47c9e`。

**关闭缺口仍存在。** 第32步恰好终止后，SB3自动reset了第三局`f9c100aede024777b7321232b3a1c3b8`，该局0采样；预算close时worker.log出现EOFError/Traceback，没有官方结果或summary。这没有作为transition进入buffer，trainer退出0、结束无SC2残留，但不能称本轮零系统日志错误，也没有解决历史budget-close缺口。保留原始证据，不追加游戏或掩盖失败。

## 导出与最小行为观察

独立NumPy actor：`artifacts/models/marine_ppo_bc_warmstart_20261019`，weights SHA256 `bccce3aa15dfda49518f8dd0bbd5a2b9949a3ed38d814291a3ad38ba9b876ec1`。producer透传BC初始化来源、数据与checkpoint hash；runtime仍只用NumPy。同82冻结观测SB3→NumPy概率最大差5.96046448e-8、动作82/82相同。

同82观测的BC、迁移初始PPO、更新后PPO确定性动作计数均`[4,17,28,6,27]`，更新后0条argmax改变；最大单概率变化0.100795686，平均HOLD概率0.329399162→0.329504639。这仅说明保留BC动作选择并发生概率更新，不能当独立评估或收益。

唯一部署目录`artifacts/runs/p5_bc_warmstart_ppo_20261019`：Ancient Cistern LE、marine-vs-marine-v6、distance6、双方满HP、seed20261019、非实时、20秒上限，exit0。12次PPO推理/12 owned，动作`[0,3,4,3,2]`，10 engine_confirmed+2 hold；5.044642857游戏秒low_health_safety_exit，己/敌HP9/21，truncated=true、terminated=false。mask与8loops合法、无fallback/冲突/telemetry error，全部expert=null、bc_eligible=false；结束无SC2残留。初始frame17、obs[2]=0.379345703125，对应己武器cooldown5.690185546875；没有标准化引擎初始cooldown，也没有另跑BC游戏，因此不作策略强弱、胜率或泛化结论。外层Result.Defeat不替代局部结果。

## 使用与接续

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/my_bc_warmstart --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --init-bc artifacts/models/marine_bc_mvp_20261018_seed42 --total-timesteps 32
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_bc_warmstart_20261019
```

第一条为新运行示例，输出目录须不存在，执行会启动真实SC2；本轮预算已经完成，不需重跑。此32步checkpoint可用`--resume artifacts/micro_ppo/p5_bc_warmstart_20261019`继续，继承BC来源与真实累计步数；不使用`--init-bc`重复初始化。新模型不是默认或最佳。模型及原始工件被Git忽略，迁移另带。

机器摘要见[ppo_bc_warmstart_mvp.json](validation/ppo_bc_warmstart_mvp.json)。原始run保留initialization/training/verification/offline_policy_comparison报告与各局RL rollout；部署保留manifest/events/transitions/scenario_result/summary。必要定向检查由实现代理执行，未重跑历史suite。部署呈现多动作，与历史随机PPO全HOLD的行为记录不同；本轮无严格对照，不能归因于32步训练收益。下一步优先扩展可学习的近战/射程差训练任务并做小对照，避免盲目堆镜像Marine训练；预算close协议与初态cooldown标准化保留待办。P5全面验收、规模训练就绪、训练敌死/时间截断/系统崩溃和战斗收益仍未建立。
