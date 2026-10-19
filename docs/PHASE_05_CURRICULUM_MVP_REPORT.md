# P5 三任务课程 PPO256 有限 MVP（2026-10-19）

唯一真实续训已完成：从 BC 来源近战128 checkpoint 保留 actor、critic 与 Adam，新采样128步→累计256。三项预冻结课程都被采样，导出 NumPy actor 与128个既有真实观测一致；只运行预冻结 heldout 配置的 PPO/规则各1短场。没有强度、胜率、泛化或本轮训练收益结论。默认 `run_ppo.cmd` 仍使用原64步actor。

## 冻结任务与来源

`configs/micro_curriculum_v1.json` 固定按 episode reset 轮转，全部是 Ancient Cistern LE、1 Marine 对1 Zergling、12秒、8loops、敌满HP、原奖励scale45。A→B只增加名义距离，B→C再降低己血量；未改奖励或规则。各新run从索引0开始，冷启动新局，不恢复父引擎轨迹或完整RNG。

| 索引 | 名义距离 | 己HP比例/真实初始HP | 新增步数 | 完整局结果 |
|---|---:|---:|---:|---|
| A/0 | 6 | 1/45 | 41 | 3 enemy_dead |
| B/1 | 8 | 1/45 | 44 | 3 enemy_dead |
| C/2 | 8 | .6/27 | 43 | 2 marine_dead，另14步预算关闭 |

原敌真实type105/ZERGLING、health_max35、ground_range0.10009765625。各步task与课程对应、episode_index模3与curriculum_index一致，9个实际局顺序0/1/2重复三次。每局 `initial_scene_observation.json` 保留真实初态HP、位置、距离、cooldown、obs和mask，名义距离不等于ready实际距离：A为1.658203125/4.4267578125/3.134765625且cooldown5.881103515625/7.51806640625/0；B/C约6.7080078125..6.892578125且cooldown0。未声称训练初态已标准化。

父目录 `artifacts/micro_ppo/p5_melee_bc128_20261019` 的zip与metadata SHA均前后不变。父zip SHA `177d1b91f420acfbdfa39e0ffc3d18b53975b23a75f394f9fe5122177b9158ea`。显式 `--allow-task-change` 记录父单任务→新三任务与双方task-set SHA；未静默换任务。metadata中的`task`仅兼容默认A，以`curriculum`治理reset，`task_semantics`明确，导出producer透传course/task-change/BC及父checkpoint来源。

实际唯一训练命令（未重跑）：

```powershell
& C:\code\sc2-ares-training\Scripts\python.exe -s tools/train_micro_ppo.py artifacts/micro_ppo/p5_curriculum256_20261019 --worker-python C:/Users/27932/anaconda3/envs/sc2-ares-runtime/python.exe --resume artifacts/micro_ppo/p5_melee_bc128_20261019 --curriculum configs/micro_curriculum_v1.json --allow-task-change --total-timesteps 128
```

## 更新与原始证据核验

继承父seed42/n_steps32/batch16/epochs2/lr.0003/CPU，154.375秒、exit0。初始完整policy及actor hash与加载父相同，12项Adam step16→32、updates8→16；actor最大参数变化.0031970739364624023，全参数最大.004540875554084778，参数finite，保存重载概率误差0。

128条真实相邻HP重新计算signed loss与奖励，Zergling自然回血保留，raw奖励误差0、trace float32误差在共享JSON记录；mask合法、实际均8loops，buffer system_failure/discard/conflict/专家标签均0。采样动作0..4=`[0,26,24,6,72]`；53 engine_confirmed、72 hold、3 order_preserved，后者不冒充新确认。8完整局均官方结果及关闭确认，完整回报均.593520793；混合任务回报不能与旧单任务直接比较。

第9局（C）14条合法样本后预算关闭，己HP2/敌.7431640625；worker.log仍有EOFError/Traceback，无summary/官方Result。异常未作为transition入buffer，trainer exit0且最终SC2/worker残留0；预算关闭缺口未修复，不可称全部日志无错误。

新checkpoint `artifacts/micro_ppo/p5_curriculum256_20261019/model.zip` SHA `9c94690a2cb8eaabfb5fd24c6c0984896825d6f27f87700335f9e41df3aaafd1`。actor `artifacts/models/marine_ppo_curriculum256_20261019` weights SHA `8a0e810b5e686fd71fa74f4a7f7b5be486401647b3119b4ec7bd87e1a94bbfc1`。128个本轮已有真实source_obs+source_mask的SB3→NumPy概率最大误差5.662441253662109e-7（1e-6内）、动作128/128同、masked概率0，无额外游戏。对同128观测，父/新actor动作分别`[0,26,26,4,72]`/`[0,26,23,7,72]`，3个argmax改变、概率最大变化.4349347651；只证明更新，不是独立收益评估。

## 仅2场预冻结 heldout 探索

训练结束后、两场启动前写 `artifacts/heldout_plan.json`，SHA `301db03560426486423a363f5ad50704af48c61b04e48dd94428963a68d6e956`。配置为Zergling、名义距7、己.8/36HP、敌1/35HP、12秒、seed20261019、非实时、PPO和规则kite各1局，不改seed/不重跑。它是未进入课程的名义配置，不表示所有连续观测状态都未见。runner仅在训练结束后修复distance CLI为有限(0,10]以支持7，保留原3/6/10及默认6；训练期间源冻结。

实跑参数共同部分：`--scenario marine-vs-zergling --distance 7 --health-fraction 0.8 --enemy-health-fraction 1 --enemy-count 1 --max-game-seconds 12 --seed 20261019`；PPO加`--policy ppo --ppo-model artifacts/models/marine_ppo_curriculum256_20261019 --run-id p5_curriculum_heldout_ppo_20261019`，规则加`--policy rule --expert kite --run-id p5_curriculum_heldout_rule_20261019`，runtime Python `-s tools/run_micro_scenario.py`。

| 策略 | 决策/动作0..4 | 结束 | 己/敌最终HP |
|---|---|---|---|
| 新PPO | 13 / [0,3,3,1,6] | 5.401785714秒low_health_safety_exit | 6 / .6064453125 |
| 规则kite | 13 / [0,3,3,1,6] | 同上 | 6 / .58935546875 |

两场均exit0、7 engine_confirmed+6hold、全部mask/8loops合法，无fallback/冲突/telemetry error，最终无残留。源码hash相同；已核对可观测初态完全一致：frame17、己36敌35、实际距5.892578125、cooldown0、obs/mask/位置相同。只有1pair且未固定完整引擎状态，仍非严格因果强度对照，敌剩HP细差不能归因于策略。两场是部署20%低HP保护截断，不是死亡/负场，训练可运行至死亡/击杀；不能判泛化失败，也不能假设继续必胜。summary旧game_time_limit标签/外层Defeat不替代局部scenario_result，场景reward null不是训练奖励。

PPO原始13行split=validation、全部bc_eligible=false；规则原始split=train且前12行bc_eligible=true、末行false，这是旧runner专家默认，**未导出数据集、未进入已结束的本轮学习**。不改原始标签。两run各保存`learning_exclusion.json`，写明excluded_from_future_training=true、plan SHA、run_id及原始文件SHA，共享JSON同样保存排除记录；今后收集器必须排除此heldout。后续探索应显式`--data-split test`，本轮没有借此重跑。

## 使用、范围和下一步

显式运行 `.\run_ppo.cmd --ppo-model artifacts/models/marine_ppo_curriculum256_20261019`；默认64actor、旧128/384/BC工件保留。续训该256目录将继承内嵌课程，不需再次initBC；未来任何任务集变化仍需显式allow-task-change。模型/原始工件Git忽略，迁移需另带。

只执行必要任务合并检查1项、CLI静态核验、唯一128步训练、导出/既有128真obs离线核验及2场探索；未装包、改.env、调外部模型、扫参、挑seed或重复历史suite。共享摘要：[ppo_curriculum_mvp.json](validation/ppo_curriculum_mvp.json)。下一步先修预算关闭协议并明确训练/部署安全边界，再在新授权小预算下做预冻结比较；不据本轮自动追加训练。P5全面验收、规模就绪、真实训练时间截断/系统崩溃与战斗收益尚未建立。
