# P5 Marine 对近战 Zergling：BC 初始化 PPO 128 步 MVP

日期：2026-10-19。已将近战任务贯穿父环境、Gym适配、worker和trainer，完成唯一一次BC初始化真实128步训练、NumPy导出及既有真实观测parity，随后串行执行固定预算的PPO/规则各1短场。默认`run_ppo.cmd`仍选原64步actor；本轮未使用外部模型、安装依赖或读取凭据。该结果证明训练与部署链路覆盖近战任务，不证明PPO训练带来战斗收益。

## 任务与来源

任务固定为`marine-vs-zergling-v6`，Ancient Cistern LE、1v1、双方满HP、名义出生间距6、12游戏秒上限、非实时、每8loops决策；奖励保持`effective-hp-delta-45-terminal-1-v1`：`(敌有效HP损失-己有效HP损失)/45 + 敌死1 - 己死1`。敌HP来自真实单位，不能按Marine45HP重建Zergling生命。真实transition观测确认ZERGLING/type105、health_max35、ground_range0.10009765625；55行自然回血导致敌HP损失为负，原样进入有符号奖励，不clip。

新PPO直接从`artifacts/models/marine_bc_mvp_20261018_seed42`迁移actor，critic新建、optimizer空，累计0→128；没有把镜像Marine checkpoint改任务resume。冻结82条初始化parity：raw logits最大差2.861022949e-6、masked概率3.87430191e-7、动作82/82一致，critic未变；82条是迁移诊断，非正式1000观测验收。原BC weights/metadata hash均未变。

任务记录进入initialization、checkpoint metadata、training report、worker manifest及transition.info；导出`producer.task`与训练task完全相同。Resume继承任务并拒绝冲突覆盖，旧无task元数据按原Marine/6/8解释，不能静默换任务。默认规则/BC/PPO入口用途保持不变。

## 唯一真实训练

| 项目 | 结果 |
|---|---|
| 输出 | `artifacts/micro_ppo/p5_melee_bc128_20261019` |
| 预算/超参 | 128真实steps；seed42、n_steps32/batch16/epochs2/lr0.0003、CPU |
| 耗时/更新 | 169.688秒；n_updates0→8；12个Adam状态空→step16 |
| 完整episode | 9次enemy_dead、每局13或14步，terminated=true/truncated=false；己最终HP10或15，完整回报均值1.024691357 |
| 真实128条 | mask合法、实际8loops；逐条从相邻真实HP复算损失/奖励，raw误差0、trace float32最大3.1789144e-8 |
| buffer边界 | system_failure/discard/专家标签/command_conflict均0；系统故障仍在buffer前raise并丢弃 |
| 采样动作0..4 | `[0,24,20,0,84]`；39 engine_confirmed、84 hold、5 order_preserved，保留旧order不冒充新确认 |
| 参数/重载 | 全参数finite、actor改变；全参数最大变化0.0049501755，actor最大0.0012750775；保存重载概率误差0、动作一致 |

checkpoint SHA256：`177d1b91f420acfbdfa39e0ffc3d18b53975b23a75f394f9fe5122177b9158ea`。

9完整局均有官方结果及worker close确认；场景主动leave使外层结果为Defeat/Victory，该结果不替代局部enemy_dead，更不能转写为完整比赛胜率。训练第10局仅3步时预算结束，末己/敌HP40/29.205078125；worker.log仍出现EOFError/Traceback，无summary或官方结局。最后3条是close之前的正常transition，没有将该关闭异常作为transition塞入buffer；trainer exit0且无SC2/worker残留，但历史budget-close缺口没有解决。

名义出生间距6并非ready实际初距：本轮ready距离为2.9501953125、3.134765625或4.4267578125，初始双方仍满HP，己cooldown0..7.44921875。引擎在ready前已有移动/自动攻击启动，初态尚未标准化，不可只凭同seed称严格匹配。

## 导出与两局探索

NumPy actor：`artifacts/models/marine_ppo_melee_bc128_20261019`；weights SHA256 `4f22c0f05e428600183983244b0be2e48a024326fa1a8b404341f95d3681f0d2`。producer保留checkpoint、BC及近战task来源；runtime无需Torch。128条本轮既有真实source_obs/source_mask的SB3→NumPy概率最大差1.0477379e-9、确定性动作128/128相同、非法mask概率0，无新增游戏。

同128条观测，原BC与更新actor的确定性动作均`[0,24,20,0,84]`、0条改变，单概率最大变化0.000189065933。训练中enemy_dead与正回报不证明128步更新改善了原BC。

仅同新seed20261019的两局探索，任务仍为近战1v1/满HP/名义距6/12秒上限；原始目录`artifacts/runs/p5_melee_ppo_20261019`与`p5_melee_rule_20261019`：

| 项目 | PPO | 规则kite |
|---|---|---|
| 决策/动作0..4 | 14 / `[0,2,2,0,10]` | 14 / `[0,3,2,0,9]` |
| 命令 | 4 engine_confirmed +10 hold | 4 engine_confirmed +9 hold +1 order_preserved |
| 局部结果 | enemy_dead、己10HP、6.116071429秒 | enemy_dead、己10HP、6.116071429秒 |
| 初始cooldown | 0.52783203125 | 0.417236328125 |

两局均exit0、局部terminated=true/truncated=false、mask合法/8loops、无fallback/冲突/telemetry.error；PPO全部expert=null/bc_eligible=false，无SC2或worker残留。源码hash、初frame25、HP、位置、mask相同，ready实际距3.134765625；cooldown不同，`initial_state_fully_matched=false`、`controlled_comparison=false`。未换seed挑结果、未跑旧策略或BC额外game，不推胜率、泛化或训练收益。summary仍沿用历史game_time_limit/truncated分类，局部结果以scenario_result/尾transition为准；场景reward=null不当训练奖励。

## 使用和接续

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/new_melee_run --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --scenario marine-vs-zergling --distance 6 --max-game-seconds 12 --init-bc artifacts/models/marine_bc_mvp_20261018_seed42 --total-timesteps 128 --seed 42
.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_melee_bc128_20261019
```

第一条为新运行示例，输出目录必须不存在、执行会启动真实SC2，本轮预算已完成无需重跑。继续此近战checkpoint使用`--resume artifacts/micro_ppo/p5_melee_bc128_20261019`，任务从metadata继承；不再加`--init-bc`，不允许静默改回Marine任务。第二条选择actor用于规则宏观+局部PPO，不能宣称完整比赛已验证。模型与原始工件被Git忽略，迁移另带，默认仍64步actor。

机器摘要：[ppo_melee_mvp.json](validation/ppo_melee_mvp.json)。原始训练目录保留initialization/training/verification/behavior报告、checkpoint与各局rollout，探索保留manifest/scenario/initial/transitions/summary/replay。实现仅1项合并任务契约测试通过及compile/CLI检查，未重复旧suite。P5整阶段、规模训练就绪、真实训练时间截断/系统崩溃与战斗收益未建立。下一步按规划10.3可扩不同距离/HP，但先冻结小任务集、修复budget-close协议并标准化含cooldown的初态，再按新预算做有限独立比较；不因本轮正回报盲目加步。
