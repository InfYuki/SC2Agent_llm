# P5 Gymnasium 与 PPO 最小训练 MVP

日期：2026-10-19。已在真实 SC2 单 Marine 场景完成一次32步 MaskablePPO 采样、有限参数更新、保存与重载一致性检查。属于随机初始化独立 PPO 工程基线；没有沿用 BC 权重，没有战斗收益或胜率结论，P5整阶段与规模化训练就绪仍未验收。

## 环境与依赖

`envs.gym_sc2_micro_env.GymSC2MicroEnv` 继承 Gymnasium Env，观测为 `Box(-1,1,(16,),float32)`、动作 `Discrete(5)`，`action_masks()` 返回bool数组。真正死亡且原桥接obs为空时返回明确标记的零吸收终态；时间截断保留真实观测供bootstrap。系统失败或rollout_discard在进入采样buffer前抛 `RolloutDiscardError` 并关闭，不把它记为战术负样本；训练失败保留failed_report且不保留成功命名checkpoint。

独立训练环境 `C:\code\sc2-ares-training`：Gymnasium1.2.3、Torch2.10.0+cpu、stable-baselines3/sb3-contrib2.7.1、NumPy2.4.6。worker仍使用 `C:\Users\27932\anaconda3\envs\sc2-ares-runtime\python.exe -s` 的Ares锁定运行环境；未改poetry.lock、Ares子模块或运行环境依赖。重建使用 [requirements-ppo.txt](../requirements-ppo.txt) 中的固定版本，CPU Torch先从其CPU索引安装；训练环境安装依赖不等于重建运行worker。

## 唯一真实训练证据

运行目录 `artifacts/micro_ppo/p5_ppo_mvp_20261018/`，含 `model.zip`、`metadata.json`、`training_report.json`、`training_transitions.jsonl`、`verification_report.json`；逐局原始证据在 `episodes/<id>/game/rl_rollout.jsonl`。共享摘要 [micro_ppo_mvp.json](validation/micro_ppo_mvp.json)。模型被Git忽略，迁移需另带。

| 项目 | 结果 |
|---|---|
| 配置 | Ancient Cistern LE、初始seed42、后续episode seeds191664964/1662057958、8游戏秒上限、每步8loops |
| 采样 | 恰32步；14步与13步marine_dead完整episode各1，另5步为预算用尽主动close的部分episode；无空reset |
| 完整终止 | 2次terminated=true/truncated=false，均官方Defeat/Victory且close确认；部分episode尾步两标记均false，不伪造结局 |
| 请求mask | 32/32合法，动作0..4计数[1,5,8,10,8]，frame/decision与raw逐条对齐 |
| 奖励 | 32条按真实HP损失/45+终局重算一致；采样float32最大误差5.5631e-8；raw完整局回报-1.6/-1.466667，部分局0 |
| 参数更新 | n_steps32/batch16/epochs2、CPU、lr0.0003；SB3 n_updates=2，参数全finite且actor改变，全部参数最大变化0.001200091 |
| 保存重载 | 同一真实obs+mask的概率最大误差0，确定性动作均4，masked动作概率0 |
| 安全与清理 | system_failure/discard/conflict均0；32条非专家标签；训练后无SC2_x64残留 |
| 墙钟与吞吐 | 49.562秒、约0.646步/秒，包含3次冷启动与训练；单次MVP测量，无并行/长时吞吐结论 |

动作请求与新增命令并非完全相等：第一完整episode decision5请求1、执行记录4，原因 `order_preserved`。既有出口检测到相同命令已在执行而保留原order；不是mask非法或IPC错序。PPO记录所选请求动作，奖励来自其后真实状态。32条结果为21 engine_confirmed、8 hold、2 queued、1 order_preserved；不能把queued或preserved写成新命令已被引擎确认。

checkpoint SHA256：`80139d368fbb24a0eb1d6262c3e0dc53b3688ed1c94f1b469d107f118608a793`。本轮仅2项adapter定向测试、1项合并trainer定向测试及训练环境pip check，通过后执行上述唯一32步训练；未重跑历史suite或额外评估游戏。无SC2假环境测试覆盖故障抛出与成功checkpoint抑制；真实系统崩溃、时间截断、敌死尚未实测。

## 本机再次训练

以下会启动真实游戏，输出目录必须不存在：

```powershell
Set-Location C:\code\SC2Agent_llm
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/new_run --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --seed 42 --total-timesteps 32 --n-steps 32 --batch-size 16 --n-epochs 2
```

本轮模型仅供训练工程验证，尚无PPO整局部署入口。默认规则、显式BC入口及LLM战略用途保持原状；局部PPO不调用LLM或读取凭据。下一步可优先明确需要的局部部署接口与短时行为验证，再决定增加训练预算；不要将当前32步模型直接称为已学会战斗。
